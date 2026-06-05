from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import threading
from html import escape as html_escape
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4

from fastapi import FastAPI, File, Form, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .director_service import DirectorAgentService
from .errors import bad_request, conflict, unprocessable
from .export import build_markdown_export
from .repository import BreakdownRepository
from .schemas import (
    AssetReviewRequest,
    AssetSemanticReviewRequest,
    BreakdownCreate,
    BreakdownRecord,
    CreatorPersonaRecord,
    DirectorGenerationJobRecord,
    DirectorPlanAssetBindingRecord,
    DirectorPlanAssetBindingRequest,
    DirectorPlanRecord,
    DirectorPlanRequest,
    DirectorPublishRecord,
    DirectorPublishRequest,
    DirectorRenderArtifactRecord,
    DirectorRenderQaReviewRequest,
    DirectorRenderJobRecord,
    DirectorRenderJobStatus,
    DirectorRenderUsageRecord,
    ManualFactoryAssetRecord,
    MorasAssetLibraryRecord,
    PersonaEditRequest,
    PersonaGenerationJobRecord,
    PersonaGenerationJobStatus,
    PersonaGenerationRequest,
    ScriptEditRequest,
    ScriptGenerationJobRecord,
    ScriptGenerationJobStatus,
    ScriptGenerationRequest,
    ScriptRecord,
)
from .service import BreakdownService
from .script_service import ScriptAgentService, visible_script_records


ALLOWED_UPLOAD_SUFFIXES = {".mp4", ".mov"}
ALLOWED_FACTORY_ASSET_SUFFIXES = {".mp4", ".mov", ".webm"}
IMAGE_ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_MORAS_ASSET_SUFFIXES = ALLOWED_FACTORY_ASSET_SUFFIXES | IMAGE_ASSET_SUFFIXES
UPLOAD_CHUNK_SIZE = 1024 * 1024
MANUAL_GENERATION_DURATION_TOLERANCE_SEC = 0.75
MANUAL_GENERATION_ASPECT_RATIO = 9 / 16
MANUAL_GENERATION_ASPECT_TOLERANCE = 0.035
RENDER_WIDTH = 1080
RENDER_HEIGHT = 1920
RENDER_FPS = 30
DIRECTOR_RENDER_QUEUE_LOCK = threading.Lock()
PROBE_TIMEOUT_SECONDS = 15


def ffmpeg_command() -> str:
    return os.getenv("VIDEO_FACTORY_FFMPEG", "ffmpeg").strip() or "ffmpeg"


def ffprobe_command() -> str:
    return os.getenv("VIDEO_FACTORY_FFPROBE", "ffprobe").strip() or "ffprobe"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="社媒视频生产 Agent API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
    repo = BreakdownRepository()
    service = BreakdownService(repo)
    script_service = ScriptAgentService(repo)
    director_service = DirectorAgentService(repo)
    repo.recover_stale_director_generation_jobs(settings.director_generation_stale_after_seconds)
    repo.recover_stale_director_render_jobs(settings.director_render_stale_after_seconds)
    repo.recover_stale_script_generation_jobs(settings.script_generation_stale_after_seconds)
    repo.recover_stale_persona_generation_jobs(settings.persona_generation_stale_after_seconds)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "provider": settings.provider}

    @app.post("/api/breakdowns", response_model=BreakdownRecord)
    async def create_breakdown(payload: BreakdownCreate) -> BreakdownRecord:
        return await service.create_and_run(payload)

    @app.post("/api/breakdowns/upload", response_model=BreakdownRecord)
    async def upload_and_create_breakdown(file: UploadFile = File(...), provider: str | None = None) -> BreakdownRecord:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in ALLOWED_UPLOAD_SUFFIXES:
            raise bad_request("UNSUPPORTED_FILE_TYPE", "Only mp4 and mov files are supported")
        stored_name = f"{uuid4().hex}{suffix}"
        dest = settings.upload_dir / stored_name
        with dest.open("wb") as handle:
            shutil.copyfileobj(file.file, handle)
        return await service.create_and_run(BreakdownCreate(video_url=f"/uploads/{stored_name}", provider=provider))

    @app.get("/api/breakdowns", response_model=list[BreakdownRecord])
    def list_breakdowns() -> list[BreakdownRecord]:
        return repo.list()

    @app.get("/api/breakdowns/{breakdown_id}", response_model=BreakdownRecord)
    def get_breakdown(breakdown_id: str) -> BreakdownRecord:
        return repo.get(breakdown_id)

    @app.delete("/api/breakdowns/{breakdown_id}", status_code=204)
    def delete_breakdown(breakdown_id: str) -> Response:
        record = repo.get(breakdown_id)
        repo.delete(breakdown_id)
        imported_video_url = ""
        if record.source_video:
            imported_video_url = str(record.source_video.get("imported_video_url") or "")
        if imported_video_url.startswith("/uploads/"):
            upload_path = settings.upload_dir / Path(imported_video_url).name
            if upload_path.exists():
                upload_path.unlink()
        return Response(status_code=204)

    @app.get("/api/breakdowns/{breakdown_id}/export/markdown")
    def export_breakdown(breakdown_id: str) -> Response:
        record = repo.get(breakdown_id)
        markdown = build_markdown_export(record)
        title = ""
        if record.source_video:
            title = str(record.source_video.get("title") or "")
        encoded = quote(f"{title or record.id}.md")
        return Response(
            content=markdown,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
        )

    @app.get("/api/scripts", response_model=list[ScriptRecord])
    def list_scripts() -> list[ScriptRecord]:
        return visible_script_records(repo.list_scripts(), current_provider=settings.provider)

    @app.post("/api/script-generation-jobs", response_model=ScriptGenerationJobRecord)
    async def create_script_generation_job(
        payload: ScriptGenerationRequest,
    ) -> ScriptGenerationJobRecord:
        payload = script_service.resolve_script_generation_request(payload)
        job = repo.create_script_generation_job(payload)
        script_service.start_generation_job(job.id)
        return job

    @app.get("/api/creator-personas", response_model=list[CreatorPersonaRecord])
    def list_creator_personas() -> list[CreatorPersonaRecord]:
        return repo.list_creator_personas()

    @app.get("/api/creator-personas/{persona_id}", response_model=CreatorPersonaRecord)
    def get_creator_persona(persona_id: str) -> CreatorPersonaRecord:
        return repo.get_creator_persona(persona_id)

    @app.post("/api/creator-personas/generate", response_model=list[CreatorPersonaRecord])
    async def generate_creator_personas(payload: PersonaGenerationRequest) -> list[CreatorPersonaRecord]:
        return await script_service.generate_creator_personas(payload)

    @app.post("/api/persona-generation-jobs", response_model=PersonaGenerationJobRecord)
    def create_persona_generation_job(payload: PersonaGenerationRequest) -> PersonaGenerationJobRecord:
        return script_service.create_persona_generation_job(payload)

    @app.get("/api/persona-generation-jobs", response_model=list[PersonaGenerationJobRecord])
    def list_persona_generation_jobs(include_succeeded: bool = False) -> list[PersonaGenerationJobRecord]:
        repo.recover_stale_persona_generation_jobs(settings.persona_generation_stale_after_seconds)
        return repo.list_persona_generation_jobs(include_succeeded=include_succeeded)

    @app.get("/api/persona-generation-jobs/{job_id}", response_model=PersonaGenerationJobRecord)
    def get_persona_generation_job(job_id: str) -> PersonaGenerationJobRecord:
        repo.recover_stale_persona_generation_jobs(settings.persona_generation_stale_after_seconds)
        return repo.get_persona_generation_job(job_id)

    @app.post("/api/persona-generation-jobs/{job_id}/retry", response_model=PersonaGenerationJobRecord)
    def retry_persona_generation_job(job_id: str) -> PersonaGenerationJobRecord:
        repo.recover_stale_persona_generation_jobs(settings.persona_generation_stale_after_seconds)
        return script_service.retry_persona_generation_job(job_id)

    @app.delete("/api/persona-generation-jobs/{job_id}", status_code=204)
    def delete_persona_generation_job(job_id: str) -> Response:
        repo.recover_stale_persona_generation_jobs(settings.persona_generation_stale_after_seconds)
        job = repo.get_persona_generation_job(job_id)
        if job.status in {PersonaGenerationJobStatus.QUEUED, PersonaGenerationJobStatus.GENERATING}:
            raise conflict("PERSONA_GENERATION_JOB_ACTIVE", "Active persona generation jobs cannot be deleted")
        repo.delete_persona_generation_job(job_id)
        return Response(status_code=204)

    @app.post("/api/creator-personas/{persona_id}/edit", response_model=CreatorPersonaRecord)
    def edit_creator_persona(persona_id: str, payload: PersonaEditRequest) -> CreatorPersonaRecord:
        return script_service.edit_creator_persona(persona_id, payload)

    @app.delete("/api/creator-personas/{persona_id}", status_code=204)
    def delete_creator_persona(persona_id: str) -> Response:
        repo.delete_creator_persona(persona_id)
        return Response(status_code=204)

    @app.get("/api/script-generation-jobs", response_model=list[ScriptGenerationJobRecord])
    def list_script_generation_jobs(include_succeeded: bool = False) -> list[ScriptGenerationJobRecord]:
        repo.recover_stale_script_generation_jobs(settings.script_generation_stale_after_seconds)
        return repo.list_script_generation_jobs(include_succeeded=include_succeeded)

    @app.get("/api/script-generation-jobs/{job_id}", response_model=ScriptGenerationJobRecord)
    def get_script_generation_job(job_id: str) -> ScriptGenerationJobRecord:
        repo.recover_stale_script_generation_jobs(settings.script_generation_stale_after_seconds)
        return repo.get_script_generation_job(job_id)

    @app.post("/api/script-generation-jobs/{job_id}/retry", response_model=ScriptGenerationJobRecord)
    def retry_script_generation_job(job_id: str) -> ScriptGenerationJobRecord:
        repo.recover_stale_script_generation_jobs(settings.script_generation_stale_after_seconds)
        return script_service.retry_generation_job(job_id)

    @app.delete("/api/script-generation-jobs/{job_id}", status_code=204)
    def delete_script_generation_job(job_id: str) -> Response:
        repo.recover_stale_script_generation_jobs(settings.script_generation_stale_after_seconds)
        job = repo.get_script_generation_job(job_id)
        if job.status in {ScriptGenerationJobStatus.QUEUED, ScriptGenerationJobStatus.GENERATING}:
            raise conflict("SCRIPT_GENERATION_JOB_ACTIVE", "Active script generation jobs cannot be deleted")
        repo.delete_script_generation_job(job_id)
        return Response(status_code=204)

    @app.get("/api/scripts/{script_id}", response_model=ScriptRecord)
    def get_script(script_id: str) -> ScriptRecord:
        return repo.get_script(script_id)

    @app.post("/api/scripts/generate", response_model=list[ScriptRecord])
    async def generate_scripts(payload: ScriptGenerationRequest) -> list[ScriptRecord]:
        return await script_service.generate_scripts(payload)

    @app.post("/api/scripts/{script_id}/edit", response_model=ScriptRecord)
    async def edit_script(script_id: str, payload: ScriptEditRequest) -> ScriptRecord:
        return await script_service.edit_script(script_id, payload)

    @app.delete("/api/scripts/{script_id}", status_code=204)
    def delete_script(script_id: str) -> Response:
        repo.delete_script(script_id)
        return Response(status_code=204)

    @app.post("/api/video-factory/director-plans", response_model=DirectorPlanRecord)
    async def generate_director_plan(payload: DirectorPlanRequest) -> DirectorPlanRecord:
        return await director_service.generate_plan(payload)

    @app.post("/api/video-factory/director-generation-jobs", response_model=DirectorGenerationJobRecord)
    def create_director_generation_job(payload: DirectorPlanRequest) -> DirectorGenerationJobRecord:
        job = repo.create_director_generation_job(payload)
        director_service.start_generation_job(job.id)
        return job

    @app.get("/api/video-factory/director-generation-jobs", response_model=list[DirectorGenerationJobRecord])
    def list_director_generation_jobs(
        script_id: str | None = None,
        include_succeeded: bool = False,
    ) -> list[DirectorGenerationJobRecord]:
        return repo.list_director_generation_jobs(script_id=script_id, include_succeeded=include_succeeded)

    @app.get("/api/video-factory/director-generation-jobs/{job_id}", response_model=DirectorGenerationJobRecord)
    def get_director_generation_job(job_id: str) -> DirectorGenerationJobRecord:
        return repo.get_director_generation_job(job_id)

    @app.post("/api/video-factory/director-generation-jobs/{job_id}/cancel", response_model=DirectorGenerationJobRecord)
    def cancel_director_generation_job(job_id: str) -> DirectorGenerationJobRecord:
        return director_service.cancel_generation_job(job_id)

    @app.post("/api/video-factory/director-generation-jobs/{job_id}/retry", response_model=DirectorGenerationJobRecord)
    def retry_director_generation_job(job_id: str) -> DirectorGenerationJobRecord:
        return director_service.retry_generation_job(job_id)

    @app.get("/api/video-factory/director-plans", response_model=list[DirectorPlanRecord])
    def list_director_plans(script_id: str | None = None) -> list[DirectorPlanRecord]:
        return repo.list_director_plans(script_id)

    @app.get("/api/video-factory/director-plans/{plan_id}", response_model=DirectorPlanRecord)
    def get_director_plan(plan_id: str) -> DirectorPlanRecord:
        return repo.get_director_plan(plan_id)

    @app.get("/api/video-factory/moras-assets", response_model=list[MorasAssetLibraryRecord])
    def list_moras_assets(
        asset_type: str | None = None,
        moras_asset_category: str | None = None,
    ) -> list[MorasAssetLibraryRecord]:
        return repo.list_moras_assets(asset_type=asset_type, moras_asset_category=moras_asset_category)

    @app.post("/api/video-factory/moras-assets", response_model=MorasAssetLibraryRecord)
    async def upload_moras_asset(
        asset_type: str = Form(...),
        moras_asset_category: str = Form(...),
        title: str | None = Form(None),
        file: UploadFile = File(...),
    ) -> MorasAssetLibraryRecord:
        cleaned_asset_type = asset_type.strip()
        cleaned_category = moras_asset_category.strip() or "none"
        if not cleaned_asset_type:
            raise bad_request("MORAS_ASSET_TYPE_REQUIRED", "Moras asset type is required")

        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in ALLOWED_MORAS_ASSET_SUFFIXES:
            raise bad_request(
                "UNSUPPORTED_FILE_TYPE",
                "Only mp4, mov, webm, png, jpg, jpeg, and webp files are supported for Moras assets",
            )

        moras_upload_dir = settings.upload_dir / "moras-assets"
        moras_upload_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid4().hex}{suffix}"
        dest = moras_upload_dir / stored_name
        file_size = store_upload_file(file, dest, max_bytes=settings.max_upload_mb * 1024 * 1024)
        try:
            media = probe_moras_asset_metadata(dest, require_duration=suffix not in IMAGE_ASSET_SUFFIXES)
        except Exception:
            if dest.exists():
                dest.unlink()
            raise

        original_filename = file.filename or stored_name
        cleaned_title = (title or "").strip() or Path(original_filename).stem or cleaned_asset_type
        return repo.create_moras_asset(
            asset_type=cleaned_asset_type,
            moras_asset_category=cleaned_category,
            title=cleaned_title,
            original_filename=original_filename,
            stored_asset_url=f"/uploads/moras-assets/{stored_name}",
            mime_type=file.content_type or "",
            file_size_bytes=file_size,
            duration_sec=media["duration_sec"],
            width=media["width"],
            height=media["height"],
        )

    @app.post("/api/video-factory/moras-assets/{asset_id}/review", response_model=MorasAssetLibraryRecord)
    def review_moras_asset(asset_id: str, payload: AssetReviewRequest) -> MorasAssetLibraryRecord:
        return repo.update_moras_asset_review(
            asset_id,
            review_status=payload.review_status,
            review_notes=payload.review_notes,
        )

    @app.post("/api/video-factory/moras-assets/{asset_id}/semantic-review", response_model=MorasAssetLibraryRecord)
    def review_moras_asset_semantics(asset_id: str, payload: AssetSemanticReviewRequest) -> MorasAssetLibraryRecord:
        return repo.update_moras_asset_semantic_review(
            asset_id,
            status=payload.status,
            notes=payload.notes,
            method=payload.method,
            reviewer=payload.reviewer,
        )

    @app.get(
        "/api/video-factory/director-plans/{plan_id}/asset-bindings",
        response_model=list[DirectorPlanAssetBindingRecord],
    )
    def list_director_plan_asset_bindings(plan_id: str) -> list[DirectorPlanAssetBindingRecord]:
        return repo.list_director_plan_asset_bindings(plan_id)

    @app.post(
        "/api/video-factory/director-plans/{plan_id}/asset-bindings",
        response_model=DirectorPlanAssetBindingRecord,
    )
    def bind_director_plan_asset(plan_id: str, payload: DirectorPlanAssetBindingRequest) -> DirectorPlanAssetBindingRecord:
        return repo.create_director_plan_asset_binding(
            director_plan_id=plan_id,
            asset_ref=payload.asset_ref,
            library_asset_id=payload.library_asset_id,
        )

    @app.get(
        "/api/video-factory/director-plans/{plan_id}/manual-assets",
        response_model=list[ManualFactoryAssetRecord],
    )
    def list_manual_factory_assets(plan_id: str) -> list[ManualFactoryAssetRecord]:
        return repo.list_manual_factory_assets(plan_id)

    @app.post(
        "/api/video-factory/director-plans/{plan_id}/manual-assets",
        response_model=ManualFactoryAssetRecord,
    )
    async def upload_manual_factory_asset(
        plan_id: str,
        clip_id: str = Form(...),
        file: UploadFile = File(...),
    ) -> ManualFactoryAssetRecord:
        plan = repo.get_director_plan(plan_id)
        clip = find_manual_generation_clip(plan, clip_id)
        if clip is None:
            raise bad_request("MANUAL_GENERATION_CLIP_NOT_FOUND", "Manual Veo generation clip was not found in this director plan")

        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in ALLOWED_FACTORY_ASSET_SUFFIXES:
            raise bad_request("UNSUPPORTED_FILE_TYPE", "Only mp4, mov, and webm files are supported for manual factory assets")

        factory_upload_dir = settings.upload_dir / "factory"
        factory_upload_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid4().hex}{suffix}"
        dest = factory_upload_dir / stored_name
        file_size = store_upload_file(file, dest, max_bytes=settings.max_upload_mb * 1024 * 1024)
        media = validate_manual_generation_media(dest, clip)
        return repo.create_manual_factory_asset(
            director_plan_id=plan_id,
            clip_id=clip_id,
            source_reference_id=str(clip.get("source_reference_id") or clip.get("sourceReferenceId") or ""),
            asset_role=str(clip.get("layer_role") or clip.get("layerRole") or "manual_veo_clip"),
            original_filename=file.filename or stored_name,
            stored_asset_url=f"/uploads/factory/{stored_name}",
            mime_type=file.content_type or "",
            file_size_bytes=file_size,
            duration_sec=media["duration_sec"],
            width=media["width"],
            height=media["height"],
        )

    @app.post("/api/video-factory/manual-assets/{asset_id}/review", response_model=ManualFactoryAssetRecord)
    def review_manual_factory_asset(asset_id: str, payload: AssetReviewRequest) -> ManualFactoryAssetRecord:
        return repo.update_manual_factory_asset_review(
            asset_id,
            review_status=payload.review_status,
            review_notes=payload.review_notes,
        )

    @app.post("/api/video-factory/manual-assets/{asset_id}/semantic-review", response_model=ManualFactoryAssetRecord)
    def review_manual_factory_asset_semantics(asset_id: str, payload: AssetSemanticReviewRequest) -> ManualFactoryAssetRecord:
        return repo.update_manual_factory_asset_semantic_review(
            asset_id,
            status=payload.status,
            notes=payload.notes,
            method=payload.method,
            reviewer=payload.reviewer,
        )

    @app.get(
        "/api/video-factory/director-plans/{plan_id}/render-jobs",
        response_model=list[DirectorRenderJobRecord],
    )
    def list_director_render_jobs(plan_id: str) -> list[DirectorRenderJobRecord]:
        return repo.list_director_render_jobs(plan_id)

    @app.get(
        "/api/video-factory/render-jobs/{render_job_id}",
        response_model=DirectorRenderJobRecord,
    )
    def get_director_render_job(render_job_id: str) -> DirectorRenderJobRecord:
        return repo.get_director_render_job(render_job_id)

    @app.get(
        "/api/video-factory/render-jobs/{render_job_id}/artifacts",
        response_model=list[DirectorRenderArtifactRecord],
    )
    def list_director_render_artifacts(render_job_id: str) -> list[DirectorRenderArtifactRecord]:
        return repo.list_director_render_artifacts(render_job_id)

    @app.post(
        "/api/video-factory/render-jobs/{render_job_id}/artifacts/cleanup-expired",
        response_model=list[DirectorRenderArtifactRecord],
    )
    def cleanup_expired_director_render_artifacts(render_job_id: str) -> list[DirectorRenderArtifactRecord]:
        artifacts = repo.list_director_render_artifacts(render_job_id)
        now = datetime.now(UTC)
        for artifact in artifacts:
            if artifact.storage_status == "deleted" or not is_artifact_retention_expired(artifact, now):
                continue
            delete_local_render_artifact_file(settings, artifact)
            repo.update_director_render_artifact_lifecycle(
                artifact.id,
                storage_status="deleted",
                deleted_at=datetime.now(UTC).isoformat(),
            )
        return repo.list_director_render_artifacts(render_job_id)

    @app.delete(
        "/api/video-factory/render-artifacts/{artifact_id}",
        response_model=DirectorRenderArtifactRecord,
    )
    def delete_director_render_artifact(artifact_id: str) -> DirectorRenderArtifactRecord:
        artifact = repo.get_director_render_artifact(artifact_id)
        if artifact.storage_status == "deleted":
            return artifact
        delete_local_render_artifact_file(settings, artifact)
        return repo.update_director_render_artifact_lifecycle(
            artifact.id,
            storage_status="deleted",
            deleted_at=datetime.now(UTC).isoformat(),
        )

    @app.get(
        "/api/video-factory/render-jobs/{render_job_id}/usage",
        response_model=DirectorRenderUsageRecord | None,
    )
    def get_director_render_usage(render_job_id: str) -> DirectorRenderUsageRecord | None:
        return repo.get_director_render_usage_record(render_job_id)

    @app.post(
        "/api/video-factory/render-jobs/{render_job_id}/retry",
        response_model=DirectorRenderJobRecord,
    )
    def retry_director_render_job(render_job_id: str) -> DirectorRenderJobRecord:
        render_job = repo.get_director_render_job(render_job_id)
        if render_job.status not in {DirectorRenderJobStatus.BLOCKED, DirectorRenderJobStatus.FAILED}:
            raise unprocessable(
                "DIRECTOR_RENDER_JOB_NOT_RETRYABLE",
                f"Director render job is {render_job.status}; only blocked or failed jobs can be retried.",
            )
        retry_job = repo.create_director_render_job(
            director_plan_id=render_job.director_plan_id,
            status=DirectorRenderJobStatus.QUEUED,
            readiness_summary={},
        )
        start_director_render_job(repo, settings, retry_job.id)
        return retry_job

    @app.post(
        "/api/video-factory/render-jobs/{render_job_id}/qa-review",
        response_model=DirectorRenderJobRecord,
    )
    def review_director_render_job(render_job_id: str, payload: DirectorRenderQaReviewRequest) -> DirectorRenderJobRecord:
        render_job = repo.get_director_render_job(render_job_id)
        if render_job.status != DirectorRenderJobStatus.SUCCEEDED:
            raise conflict("DIRECTOR_RENDER_JOB_NOT_SUCCEEDED", "Only succeeded render jobs can be QA reviewed.")
        return repo.update_director_render_job_qa_review(
            render_job_id,
            qa_review_status=payload.qa_review_status,
            qa_review_notes=payload.qa_review_notes,
        )

    @app.post(
        "/api/video-factory/director-plans/{plan_id}/render-jobs",
        response_model=DirectorRenderJobRecord,
    )
    def create_director_render_job(plan_id: str) -> DirectorRenderJobRecord:
        repo.get_director_plan(plan_id)
        job = repo.create_director_render_job(
            director_plan_id=plan_id,
            status=DirectorRenderJobStatus.QUEUED,
            readiness_summary={},
        )
        start_director_render_job(repo, settings, job.id)
        return job

    @app.get(
        "/api/video-factory/director-plans/{plan_id}/publish-records",
        response_model=list[DirectorPublishRecord],
    )
    def list_director_publish_records(plan_id: str) -> list[DirectorPublishRecord]:
        return repo.list_director_publish_records(plan_id)

    @app.post(
        "/api/video-factory/director-plans/{plan_id}/publish-records",
        response_model=DirectorPublishRecord,
    )
    def create_director_publish_record(plan_id: str, payload: DirectorPublishRequest) -> DirectorPublishRecord:
        repo.get_director_plan(plan_id)
        render_job = repo.get_director_render_job(payload.render_job_id)
        if render_job.director_plan_id != plan_id:
            raise conflict("DIRECTOR_RENDER_JOB_PLAN_MISMATCH", "Render job does not belong to this director plan.")
        if render_job.status != DirectorRenderJobStatus.SUCCEEDED or not render_job.output_asset_url:
            raise conflict("DIRECTOR_RENDER_JOB_NOT_READY", "Only succeeded render jobs with an output video can be published.")
        if render_job.qa_review_status != "approved":
            raise conflict("DIRECTOR_RENDER_JOB_QA_NOT_APPROVED", "Render job must pass human QA review before publishing.")
        if not is_render_output_video_artifact_active(repo, render_job):
            raise conflict(
                "DIRECTOR_RENDER_OUTPUT_ARTIFACT_DELETED",
                "The render output video artifact is no longer active. Re-render before creating a publish record.",
            )
        return repo.create_director_publish_record(
            director_plan_id=plan_id,
            render_job_id=payload.render_job_id,
            channel=payload.channel,
            publish_status=payload.publish_status,
            caption=payload.caption,
            scheduled_at=payload.scheduled_at,
            published_url=payload.published_url,
            notes=payload.notes,
        )

    return app


app = create_app()


def start_director_render_job(repo: BreakdownRepository, settings: Any, job_id: str) -> None:
    worker = threading.Thread(
        target=run_director_render_job,
        args=(repo, settings, job_id),
        daemon=True,
        name=f"director-render-{job_id[:8]}",
    )
    worker.start()


def run_director_render_job(repo: BreakdownRepository, settings: Any, job_id: str) -> None:
    readiness: dict[str, Any] = {}
    with DIRECTOR_RENDER_QUEUE_LOCK:
        job = repo.get_director_render_job(job_id)
        if job.status not in {DirectorRenderJobStatus.QUEUED, DirectorRenderJobStatus.RENDERING}:
            return
        repo.mark_director_render_job(job_id, DirectorRenderJobStatus.RENDERING)
        try:
            plan = repo.get_director_plan(job.director_plan_id)
            readiness = build_render_readiness(repo, plan)
            blockers = readiness.get("blockers") if isinstance(readiness.get("blockers"), list) else []
            if blockers:
                repo.finish_director_render_job(
                    job_id,
                    status=DirectorRenderJobStatus.BLOCKED,
                    readiness_summary=readiness,
                    error_message="渲染前还有素材未上传、未绑定或未审核通过。",
                )
                return

            output = render_director_plan_draft(settings, plan, readiness)
            repo.finish_director_render_job(
                job_id,
                status=DirectorRenderJobStatus.SUCCEEDED,
                output_asset_url=output["output_asset_url"],
                output_filename=output["output_filename"],
                output_audio_url=output["output_audio_url"],
                output_subtitle_url=output["output_subtitle_url"],
                file_size_bytes=output["file_size_bytes"],
                duration_sec=output["duration_sec"],
                width=output["width"],
                height=output["height"],
                readiness_summary=readiness,
                qa_summary=output["qa_summary"],
            )
            repo.replace_director_render_artifacts(
                job_id,
                output.get("artifacts") or [],
                retention_expires_at=render_artifact_retention_expires_at(settings),
            )
            repo.replace_director_render_usage_record(job_id, output.get("usage_summary") or {})
        except Exception as exc:
            repo.finish_director_render_job(
                job_id,
                status=DirectorRenderJobStatus.FAILED,
                readiness_summary=readiness,
                error_message=str(exc) or "视频草稿渲染失败。",
            )


def render_artifact_retention_expires_at(settings: Any) -> str | None:
    retention_days = int(getattr(settings, "director_render_artifact_retention_days", 14) or 0)
    if retention_days <= 0:
        return None
    return (datetime.now(UTC) + timedelta(days=retention_days)).isoformat()


def find_manual_generation_clip(plan: DirectorPlanRecord, clip_id: str) -> dict | None:
    tracks = plan.timeline.get("tracks") if isinstance(plan.timeline, dict) else {}
    if not isinstance(tracks, dict):
        return None
    video_tracks = tracks.get("video_tracks") or tracks.get("videoTracks") or []
    if not isinstance(video_tracks, list):
        return None
    for track in video_tracks:
        if not isinstance(track, dict):
            continue
        clips = track.get("clips") or []
        if not isinstance(clips, list):
            continue
        for clip in clips:
            if not isinstance(clip, dict):
                continue
            current_clip_id = str(clip.get("clip_id") or clip.get("clipId") or "")
            source_type = str(clip.get("source_type") or clip.get("sourceType") or "")
            if current_clip_id == clip_id and source_type in {"veo_generation", "seedance_generation"}:
                return clip
    return None


def build_render_readiness(repo: BreakdownRepository, plan: DirectorPlanRecord) -> dict[str, Any]:
    manual_assets = repo.list_manual_factory_assets(plan.id)
    asset_bindings = repo.list_director_plan_asset_bindings(plan.id)
    manual_asset_by_clip = {asset.clip_id: asset for asset in manual_assets}
    asset_binding_by_ref = {binding.asset_ref: binding for binding in asset_bindings}
    library_asset_by_id: dict[str, MorasAssetLibraryRecord] = {}
    blockers: list[dict[str, Any]] = []

    manual_clips = find_manual_generation_clips(plan)
    for clip in manual_clips:
        clip_id = text_field(clip, "clip_id", "clipId")
        if not clip_id:
            continue
        asset = manual_asset_by_clip.get(clip_id)
        if asset is None:
            blockers.append(
                {
                    "type": "manual_veo_clip",
                    "ref": clip_id,
                    "message": f"Veo 3.1 clip {clip_id} has not been uploaded.",
                }
            )
            continue
        if asset.review_status != "approved":
            status_label = "rejected" if asset.review_status == "rejected" else "pending review"
            note = f" Notes: {asset.review_notes}" if asset.review_notes else ""
            blockers.append(
                {
                    "type": "manual_veo_review",
                    "ref": clip_id,
                    "message": f"Veo 3.1 clip {clip_id} is {status_label} and cannot be rendered yet.{note}",
                }
            )
            continue
        if asset.semantic_review_status != "passed":
            status_label = "failed" if asset.semantic_review_status == "failed" else "pending semantic review"
            note = f" Notes: {asset.semantic_review_notes}" if asset.semantic_review_notes else ""
            blockers.append(
                {
                    "type": "manual_veo_semantic_review",
                    "ref": clip_id,
                    "message": f"Veo 3.1 clip {clip_id} is {status_label} and must pass prompt-match review before rendering.{note}",
                }
            )

    real_requirements = find_real_moras_requirements(plan)
    for requirement in real_requirements:
        ref = asset_ref(requirement)
        if ref not in asset_binding_by_ref:
            blockers.append(
                {
                    "type": "real_moras_asset",
                    "ref": ref,
                    "message": f"Real Moras asset {ref} has not been bound from the library.",
                }
            )
            continue
        binding = asset_binding_by_ref[ref]
        try:
            library_asset = repo.get_moras_asset(binding.library_asset_id)
            library_asset_by_id[binding.library_asset_id] = library_asset
            if library_asset.review_status != "approved":
                status_label = "rejected" if library_asset.review_status == "rejected" else "pending review"
                note = f" Notes: {library_asset.review_notes}" if library_asset.review_notes else ""
                blockers.append(
                    {
                        "type": "real_moras_asset_review",
                        "ref": ref,
                        "message": f"Bound Moras asset {binding.library_asset_id} is {status_label} and cannot be rendered yet.{note}",
                    }
                )
                continue
            if library_asset.semantic_review_status != "passed":
                status_label = "failed" if library_asset.semantic_review_status == "failed" else "pending semantic review"
                note = f" Notes: {library_asset.semantic_review_notes}" if library_asset.semantic_review_notes else ""
                blockers.append(
                    {
                        "type": "real_moras_asset_semantic_review",
                        "ref": ref,
                        "message": f"Bound Moras asset {binding.library_asset_id} is {status_label} and must pass prompt-match review before rendering.{note}",
                    }
                )
        except Exception as exc:
            blockers.append(
                {
                    "type": "real_moras_asset",
                    "ref": ref,
                    "message": f"Bound Moras asset {binding.library_asset_id} is not readable: {exc}",
                }
            )

    render_inputs: list[dict[str, Any]] = []
    for clip in find_base_track_clips(plan):
        clip_id = text_field(clip, "clip_id", "clipId")
        source_type = text_field(clip, "source_type", "sourceType")
        duration_sec = coerce_float(clip.get("duration_sec") or clip.get("durationSec"))
        source_url = ""
        source_label = ""
        if source_type in {"veo_generation", "seedance_generation"}:
            asset = manual_asset_by_clip.get(clip_id)
            if not asset:
                continue
            source_url = asset.stored_asset_url
            source_label = asset.original_filename
        elif source_type == "library_asset":
            candidate_refs = library_clip_candidate_refs(clip)
            binding = next((asset_binding_by_ref[ref] for ref in candidate_refs if ref in asset_binding_by_ref), None)
            library_asset = library_asset_by_id.get(binding.library_asset_id) if binding else None
            if library_asset:
                source_url = library_asset.stored_asset_url
                source_label = library_asset.original_filename
            else:
                source_label = text_field(clip, "source_reference_id", "sourceReferenceId") or clip_id or "visual_placeholder"
        else:
            continue
        render_inputs.append(
            {
                "clip_id": clip_id,
                "source_type": source_type,
                "source_url": source_url,
                "source_label": source_label,
                "placeholder": not source_url,
                "timeline_start_sec": coerce_float(clip.get("timeline_start_sec") or clip.get("timelineStartSec")),
                "duration_sec": duration_sec,
            }
        )

    return {
        "status": "ready" if not blockers else "blocked",
        "blockers": blockers,
        "manual_required_count": len(manual_clips),
        "manual_uploaded_count": sum(1 for clip in manual_clips if text_field(clip, "clip_id", "clipId") in manual_asset_by_clip),
        "manual_ready_count": sum(
            1
            for clip in manual_clips
            if (asset := manual_asset_by_clip.get(text_field(clip, "clip_id", "clipId"))) is not None
            and asset.review_status == "approved"
            and asset.semantic_review_status == "passed"
        ),
        "real_moras_required_count": len(real_requirements),
        "real_moras_bound_count": sum(1 for requirement in real_requirements if asset_ref(requirement) in asset_binding_by_ref),
        "real_moras_ready_count": sum(
            1
            for requirement in real_requirements
            if (
                binding := asset_binding_by_ref.get(asset_ref(requirement))
            ) is not None
            and (
                library_asset := library_asset_by_id.get(binding.library_asset_id)
            ) is not None
            and library_asset.review_status == "approved"
            and library_asset.semantic_review_status == "passed"
        ),
        "render_input_count": len(render_inputs),
        "render_inputs": render_inputs,
        "target_width": RENDER_WIDTH,
        "target_height": RENDER_HEIGHT,
        "target_fps": RENDER_FPS,
        "total_duration_sec": coerce_float(plan.metadata.get("total_duration_sec") if isinstance(plan.metadata, dict) else 0),
    }


def render_director_plan_draft(settings: Any, plan: DirectorPlanRecord, readiness: dict[str, Any]) -> dict[str, Any]:
    render_inputs = readiness.get("render_inputs") if isinstance(readiness.get("render_inputs"), list) else []
    if not render_inputs:
        raise RuntimeError("No renderable base-track inputs were resolved.")
    if shutil.which(ffmpeg_command()) is None:
        raise RuntimeError("ffmpeg is required to render Video Factory drafts.")

    render_dir = settings.upload_dir / "factory-renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    render_id = uuid4().hex
    temp_dir = render_dir / f"{render_id}-segments"
    temp_dir.mkdir(parents=True, exist_ok=True)
    visual_path = temp_dir / "visual.mp4"
    audio_path = render_dir / f"{render_id}.m4a"
    subtitle_path = render_dir / f"{render_id}.vtt"
    hyperframes_project_dir = render_dir / f"{render_id}-hyperframes"
    output_path = render_dir / f"{render_id}.mp4"

    try:
        segment_paths: list[Path] = []
        for index, item in enumerate(render_inputs, start=1):
            source_url = str(item.get("source_url") or "")
            duration_sec = coerce_float(item.get("duration_sec"))
            if duration_sec <= 0:
                raise RuntimeError(f"Clip {item.get('clip_id') or index} has no positive duration.")
            segment_path = temp_dir / f"segment-{index:02d}.mp4"
            if item.get("placeholder"):
                render_placeholder_segment(segment_path, duration_sec)
            else:
                source_path = upload_url_to_path(settings.upload_dir, source_url)
                transcode_render_segment(source_path, segment_path, duration_sec)
            segment_paths.append(segment_path)

        concat_list = temp_dir / "concat.txt"
        concat_list.write_text(
            "".join(f"file '{escape_ffconcat_path(path)}'\n" for path in segment_paths),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                ffmpeg_command(),
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
                "-an",
                "-c:v",
                "mpeg4",
                "-q:v",
                "5",
                "-pix_fmt",
                "yuv420p",
                str(visual_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "ffmpeg concat failed.")

        total_duration = coerce_float(readiness.get("total_duration_sec")) or probe_video_metadata(visual_path)["duration_sec"]
        subtitle_cues = build_subtitle_cues(plan, total_duration)
        write_webvtt_subtitles(subtitle_path, subtitle_cues)
        caption_summary = prepare_hyperframes_caption_overlay(
            settings=settings,
            cues=subtitle_cues,
            project_dir=hyperframes_project_dir,
            output_dir=render_dir,
            render_id=render_id,
            total_duration_sec=total_duration,
        )
        audio_summary = synthesize_tts_audio(plan, audio_path, temp_dir, total_duration)
        mux_audio_into_video(visual_path, audio_path, output_path)
        caption_engine = "webvtt_track_v1"
        if caption_summary.get("overlay_path"):
            composited_path = temp_dir / "hyperframes-composited.mp4"
            overlay_hyperframes_layer(output_path, Path(str(caption_summary["overlay_path"])), composited_path)
            shutil.move(str(composited_path), str(output_path))
            caption_engine = "hyperframes_cli_v1"
            caption_summary["engine"] = caption_engine
            caption_summary["hyperframes_status"] = "composited"
            caption_summary["note"] = "HyperFrames rendered RGBA caption frames, FFmpeg encoded a transparent WebM overlay, and FFmpeg composited it into the draft."
        metadata = probe_video_metadata(output_path)
        qa_summary = run_render_quality_check(
            output_path=output_path,
            expected_duration_sec=total_duration,
            subtitle_cues=subtitle_cues,
            audio_summary=audio_summary,
            caption_summary=public_caption_summary(caption_summary),
        )
        output_size = output_path.stat().st_size
        audio_size = audio_path.stat().st_size if audio_path.exists() else 0
        subtitle_size = subtitle_path.stat().st_size if subtitle_path.exists() else 0
        caption_composition_path = Path(str(caption_summary.get("composition_path") or hyperframes_project_dir / "index.html"))
        caption_composition_size = caption_composition_path.stat().st_size if caption_composition_path.exists() else 0
        caption_artifacts = [
            {
                "artifact_type": "caption_composition",
                "asset_url": str(caption_summary.get("composition_url") or f"/uploads/factory-renders/{hyperframes_project_dir.name}/index.html"),
                "filename": f"{hyperframes_project_dir.name}/index.html",
                "mime_type": "text/html",
                "file_size_bytes": caption_composition_size,
                "duration_sec": total_duration,
                "width": RENDER_WIDTH,
                "height": RENDER_HEIGHT,
            }
        ]
        if caption_summary.get("overlay_url") and caption_summary.get("overlay_path"):
            overlay_path = Path(str(caption_summary["overlay_path"]))
            caption_artifacts.append(
                {
                    "artifact_type": "caption_overlay",
                    "asset_url": str(caption_summary["overlay_url"]),
                    "filename": f"{hyperframes_project_dir.name}/{overlay_path.name}",
                    "mime_type": "video/webm",
                    "file_size_bytes": overlay_path.stat().st_size if overlay_path.exists() else 0,
                    "duration_sec": total_duration,
                    "width": RENDER_WIDTH,
                    "height": RENDER_HEIGHT,
                }
            )
        return {
            "output_asset_url": f"/uploads/factory-renders/{output_path.name}",
            "output_filename": output_path.name,
            "output_audio_url": f"/uploads/factory-renders/{audio_path.name}",
            "output_subtitle_url": f"/uploads/factory-renders/{subtitle_path.name}",
            "file_size_bytes": output_size,
            "duration_sec": metadata["duration_sec"],
            "width": metadata["width"],
            "height": metadata["height"],
            "qa_summary": qa_summary,
            "artifacts": [
                {
                    "artifact_type": "video",
                    "asset_url": f"/uploads/factory-renders/{output_path.name}",
                    "filename": output_path.name,
                    "mime_type": "video/mp4",
                    "file_size_bytes": output_size,
                    "duration_sec": metadata["duration_sec"],
                    "width": metadata["width"],
                    "height": metadata["height"],
                },
                {
                    "artifact_type": "audio",
                    "asset_url": f"/uploads/factory-renders/{audio_path.name}",
                    "filename": audio_path.name,
                    "mime_type": "audio/mp4",
                    "file_size_bytes": audio_size,
                    "duration_sec": coerce_float(audio_summary.get("duration_sec")),
                    "width": 0,
                    "height": 0,
                },
                {
                    "artifact_type": "subtitle",
                    "asset_url": f"/uploads/factory-renders/{subtitle_path.name}",
                    "filename": subtitle_path.name,
                    "mime_type": "text/vtt",
                    "file_size_bytes": subtitle_size,
                    "duration_sec": total_duration,
                    "width": 0,
                    "height": 0,
                },
                *caption_artifacts,
            ],
            "usage_summary": {
                "input_clip_count": len(render_inputs),
                "output_duration_sec": metadata["duration_sec"],
                "output_bytes": output_size,
                "subtitle_cue_count": len(subtitle_cues),
                "tts_character_count": int(audio_summary.get("voiceover_characters") or 0),
                "render_engine": "local_ffmpeg_draft_v1",
                "audio_engine": str(audio_summary.get("engine") or "unknown"),
                "caption_engine": caption_engine,
            },
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def build_subtitle_cues(plan: DirectorPlanRecord, total_duration_sec: float) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    for audio_clip in find_audio_clips(plan):
        if text_field(audio_clip, "source_type", "sourceType") != "tts_voiceover":
            continue
        text = text_field(audio_clip, "text_content", "textContent", "notes")
        start = coerce_float(audio_clip.get("timeline_start_sec") or audio_clip.get("timelineStartSec"))
        end = coerce_float(audio_clip.get("timeline_end_sec") or audio_clip.get("timelineEndSec")) or total_duration_sec
        cues.extend(split_text_into_cues(text, start, end))
    if not cues:
        cues = split_text_into_cues("Moras workflow draft preview.", 0, total_duration_sec)
    return cues


def find_audio_clips(plan: DirectorPlanRecord) -> list[dict[str, Any]]:
    tracks = plan.timeline.get("tracks") if isinstance(plan.timeline, dict) else {}
    audio_tracks = tracks.get("audio_tracks") or tracks.get("audioTracks") if isinstance(tracks, dict) else []
    clips: list[dict[str, Any]] = []
    if not isinstance(audio_tracks, list):
        return clips
    for track in audio_tracks:
        if not isinstance(track, dict):
            continue
        clips.extend(list_field(track, "clips"))
    return clips


def split_text_into_cues(text: str, start_sec: float, end_sec: float) -> list[dict[str, Any]]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    parts = [part.strip(" ,") for part in re.split(r"(?<=[.!?。！？])\s+", cleaned) if part.strip(" ,")]
    chunks: list[str] = []
    for part in parts or [cleaned]:
        if len(part) <= 72:
            chunks.append(part)
            continue
        words = part.split()
        current: list[str] = []
        current_len = 0
        for word in words:
            if current and current_len + len(word) + 1 > 72:
                chunks.append(" ".join(current))
                current = [word]
                current_len = len(word)
            else:
                current.append(word)
                current_len += len(word) + (1 if current_len else 0)
        if current:
            chunks.append(" ".join(current))
    duration = max(0.5, end_sec - start_sec)
    cue_duration = duration / max(1, len(chunks))
    cues = []
    for index, chunk in enumerate(chunks):
        cue_start = start_sec + cue_duration * index
        cue_end = end_sec if index == len(chunks) - 1 else min(end_sec, cue_start + cue_duration)
        cues.append({"start_sec": round(cue_start, 3), "end_sec": round(cue_end, 3), "text": chunk})
    return cues


def write_webvtt_subtitles(path: Path, cues: list[dict[str, Any]]) -> None:
    lines = ["WEBVTT", ""]
    for index, cue in enumerate(cues, start=1):
        start = format_vtt_timestamp(coerce_float(cue.get("start_sec")))
        end = format_vtt_timestamp(coerce_float(cue.get("end_sec")))
        text = str(cue.get("text") or "").replace("\n", " ").strip()
        lines.extend([str(index), f"{start} --> {end}", text, ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def format_vtt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def synthesize_tts_audio(plan: DirectorPlanRecord, output_path: Path, temp_dir: Path, duration_sec: float) -> dict[str, Any]:
    voiceover_text = build_voiceover_text(plan)
    say_path = shutil.which("say")
    if voiceover_text and say_path:
        raw_path = temp_dir / "voiceover.aiff"
        say_completed = subprocess.run(
            [say_path, "-o", str(raw_path), voiceover_text],
            check=False,
            capture_output=True,
            text=True,
        )
        if say_completed.returncode == 0 and raw_path.exists():
            normalize_completed = subprocess.run(
                [
                    ffmpeg_command(),
                    "-y",
                    "-i",
                    str(raw_path),
                    "-af",
                    f"apad,atrim=0:{duration_sec:.3f},volume=0.95",
                    "-ar",
                    "44100",
                    "-ac",
                    "2",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    str(output_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if normalize_completed.returncode == 0:
                return {
                    "status": "succeeded",
                    "engine": "macos_say",
                    "voiceover_characters": len(voiceover_text),
                    "duration_sec": duration_sec,
                }
    render_silent_audio(output_path, duration_sec)
    return {
        "status": "fallback_silent",
        "engine": "ffmpeg_anullsrc",
        "voiceover_characters": len(voiceover_text),
        "duration_sec": duration_sec,
    }


def build_voiceover_text(plan: DirectorPlanRecord) -> str:
    lines = [
        text_field(clip, "text_content", "textContent")
        for clip in find_audio_clips(plan)
        if text_field(clip, "source_type", "sourceType") == "tts_voiceover"
    ]
    return " ".join(line for line in lines if line).strip()


def render_silent_audio(output_path: Path, duration_sec: float) -> None:
    completed = subprocess.run(
        [
            ffmpeg_command(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t",
            f"{duration_sec:.3f}",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffmpeg failed to synthesize fallback audio.")


def mux_audio_into_video(visual_path: Path, audio_path: Path, output_path: Path) -> None:
    completed = subprocess.run(
        [
            ffmpeg_command(),
            "-y",
            "-i",
            str(visual_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffmpeg failed to mux audio into the rendered draft.")


def run_render_quality_check(
    *,
    output_path: Path,
    expected_duration_sec: float,
    subtitle_cues: list[dict[str, Any]],
    audio_summary: dict[str, Any],
    caption_summary: dict[str, Any],
) -> dict[str, Any]:
    metadata = probe_video_metadata(output_path)
    audio_stream = probe_audio_stream(output_path)
    duration_delta = abs(metadata["duration_sec"] - expected_duration_sec)
    checks = {
        "timeline_duration_match": duration_delta <= 1.0,
        "vertical_1080x1920": metadata["width"] == RENDER_WIDTH and metadata["height"] == RENDER_HEIGHT,
        "audio_stream_present": audio_stream.get("has_audio") is True,
        "subtitle_cues_present": len(subtitle_cues) > 0,
    }
    return {
        "status": "passed" if all(checks.values()) else "needs_review",
        "checks": checks,
        "expected_duration_sec": round(expected_duration_sec, 2),
        "actual_duration_sec": metadata["duration_sec"],
        "duration_delta_sec": round(duration_delta, 2),
        "subtitle_cue_count": len(subtitle_cues),
        "audio": audio_summary,
        "caption": caption_summary,
    }


def prepare_hyperframes_caption_overlay(
    *,
    settings: Any,
    cues: list[dict[str, Any]],
    project_dir: Path,
    output_dir: Path,
    render_id: str,
    total_duration_sec: float,
) -> dict[str, Any]:
    project_dir.mkdir(parents=True, exist_ok=True)
    composition_path = project_dir / "index.html"
    transcript_path = project_dir / "transcript.json"
    frames_dir = project_dir / "overlay-frames"
    overlay_path = project_dir / "overlay.webm"
    transcript = [
        {
            "text": str(cue.get("text") or ""),
            "start": coerce_float(cue.get("start")),
            "end": coerce_float(cue.get("end")),
        }
        for cue in cues
    ]
    transcript_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")
    composition_path.write_text(
        build_hyperframes_caption_html(cues=transcript, total_duration_sec=total_duration_sec),
        encoding="utf-8",
    )
    summary = {
        "engine": "webvtt_track_v1",
        "hyperframes_status": "cli_disabled",
        "composition_url": f"/uploads/factory-renders/{project_dir.name}/index.html",
        "composition_path": str(composition_path),
        "overlay_url": None,
        "overlay_path": None,
        "note": "HyperFrames composition sidecar was generated; WebVTT remains the final caption track until CLI rendering is enabled.",
    }
    if not getattr(settings, "video_factory_enable_hyperframes_cli", False):
        return summary
    cli_command = str(getattr(settings, "hyperframes_cli_command", "hyperframes") or "hyperframes")
    cli_args = resolve_hyperframes_cli_args(cli_command)
    if cli_args is None:
        summary["hyperframes_status"] = "package_missing"
        summary["note"] = f"HyperFrames CLI command '{cli_command}' was not found; WebVTT caption track was used."
        return summary
    timeout_seconds = int(getattr(settings, "hyperframes_cli_timeout_seconds", 120) or 120)
    extra_render_args = hyperframes_cli_render_args(settings)
    cli_env = hyperframes_cli_env(settings, output_dir)
    try:
        completed = subprocess.run(
            [
                *cli_args,
                "render",
                "--format",
                "png-sequence",
                "--output",
                str(frames_dir),
                "--fps",
                str(RENDER_FPS),
                "--quality",
                "draft",
                *extra_render_args,
                "--quiet",
            ],
            cwd=project_dir,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=cli_env,
        )
    except subprocess.TimeoutExpired:
        summary["hyperframes_status"] = "render_timeout"
        summary["note"] = f"HyperFrames render timed out after {timeout_seconds}s; WebVTT caption track was used."
        return summary
    frame_pattern = frames_dir / "frame_%06d.png"
    rendered_frames = sorted(frames_dir.glob("frame_*.png")) if frames_dir.exists() else []
    if completed.returncode != 0 or not rendered_frames:
        summary["hyperframes_status"] = "render_failed"
        summary["note"] = (completed.stderr or completed.stdout or "HyperFrames render did not create PNG overlay frames.").strip()
        return summary
    encode_completed = subprocess.run(
        [
            ffmpeg_command(),
            "-y",
            "-framerate",
            str(RENDER_FPS),
            "-i",
            str(frame_pattern),
            "-r",
            str(RENDER_FPS),
            "-c:v",
            "libvpx-vp9",
            "-b:v",
            "0",
            "-crf",
            "28",
            "-deadline",
            "good",
            "-row-mt",
            "1",
            "-auto-alt-ref",
            "0",
            "-metadata:s:v:0",
            "alpha_mode=1",
            "-pix_fmt",
            "yuva420p",
            str(overlay_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if encode_completed.returncode != 0 or not overlay_path.exists():
        summary["hyperframes_status"] = "overlay_encode_failed"
        summary["note"] = (
            encode_completed.stderr
            or encode_completed.stdout
            or "FFmpeg failed to encode HyperFrames PNG frames into an overlay WebM."
        ).strip()
        return summary
    summary.update(
        {
            "hyperframes_status": "overlay_rendered",
            "overlay_url": f"/uploads/factory-renders/{project_dir.name}/{overlay_path.name}",
            "overlay_path": str(overlay_path),
            "overlay_frame_count": len(rendered_frames),
            "frames_path": str(frames_dir),
            "note": "HyperFrames rendered RGBA PNG caption frames and FFmpeg encoded them into a transparent WebM overlay; final caption engine is promoted only after FFmpeg composite succeeds.",
        }
    )
    return summary


def resolve_hyperframes_cli_args(cli_command: str) -> list[str] | None:
    try:
        parts = shlex.split(cli_command)
    except ValueError:
        return None
    if not parts:
        parts = ["hyperframes"]
    executable = shutil.which(parts[0])
    if executable is None:
        return None
    return [executable, *parts[1:]]


def hyperframes_cli_render_args(settings: Any) -> list[str]:
    args: list[str] = []
    if getattr(settings, "hyperframes_cli_use_docker", False):
        args.append("--docker")
    workers = str(getattr(settings, "hyperframes_cli_workers", "1") or "").strip()
    if workers and workers != "0":
        args.extend(["--workers", workers])
    if getattr(settings, "hyperframes_cli_no_browser_gpu", True):
        args.append("--no-browser-gpu")
    return args


def hyperframes_cli_env(settings: Any, output_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("HYPERFRAMES_NO_UPDATE_CHECK", "1")
    home_dir = str(getattr(settings, "hyperframes_cli_home_dir", "") or "").strip()
    cache_root = Path(home_dir).expanduser() if home_dir else output_dir / ".hyperframes-home"
    cache_root.mkdir(parents=True, exist_ok=True)
    env["HOME"] = str(cache_root)
    cache_dir = cache_root / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    env["XDG_CACHE_HOME"] = str(cache_dir)
    browser_path = str(getattr(settings, "hyperframes_cli_browser_path", "") or "").strip()
    if browser_path:
        env["HYPERFRAMES_BROWSER_PATH"] = browser_path
        env["PRODUCER_HEADLESS_SHELL_PATH"] = browser_path
    return env


def public_caption_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in summary.items()
        if key not in {"composition_path", "overlay_path", "frames_path"}
    }


def build_hyperframes_caption_html(*, cues: list[dict[str, Any]], total_duration_sec: float) -> str:
    duration = max(0.5, total_duration_sec)
    caption_items: list[str] = []
    for index, cue in enumerate(cues):
        text = str(cue.get("text") or "").strip()
        if not text:
            continue
        start = max(0.0, coerce_float(cue.get("start")))
        end = coerce_float(cue.get("end"))
        if end <= start:
            end = min(duration, start + 1.0)
        caption_items.append(
            f"""    <div
      id="caption-{index}"
      class="caption"
      data-caption-start="{start:.3f}"
      data-caption-end="{min(end, duration):.3f}"
    >{html_escape(text)}</div>"""
        )
    if not caption_items:
        caption_items.append(
            """    <div id="caption-0" class="caption" data-caption-start="0.000" data-caption-end="0.500">Moras workflow draft preview.</div>"""
        )
    overlay_lines = [str(cue.get("text") or "").strip() for cue in cues if str(cue.get("text") or "").strip()][:2]
    overlay_items = "\n".join(
        f"""    <div class="overlay" data-caption-start="0.000" data-caption-end="{min(3.0, duration):.3f}">{html_escape(line)}</div>"""
        for line in overlay_lines
    )
    data = {
        "duration": duration,
        "cues": cues,
        "overlays": overlay_lines,
    }
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=1080, height=1920, initial-scale=1" />
  <title>Moras HyperFrames Caption Composition</title>
  <script id="moras-caption-data" type="application/json">{json.dumps(data, ensure_ascii=False)}</script>
  <style>
    html, body {{
      margin: 0;
      width: 1080px;
      height: 1920px;
      overflow: hidden;
      background: transparent;
      font-family: Inter, Arial, sans-serif;
      color: #fff;
    }}
    #moras-caption-root {{
      position: relative;
      width: 1080px;
      height: 1920px;
      overflow: hidden;
    }}
    .caption {{
      position: absolute;
      left: 72px;
      right: 72px;
      bottom: 190px;
      padding: 26px 34px;
      border-radius: 28px;
      background: rgba(8, 18, 32, 0.78);
      box-shadow: 0 18px 60px rgba(0, 0, 0, 0.35);
      font-size: 54px;
      line-height: 1.12;
      font-weight: 800;
      text-align: center;
      opacity: 0;
      visibility: hidden;
      transform: translateY(12px) scale(0.98);
      transition: none;
    }}
    .overlay {{
      position: absolute;
      top: 104px;
      left: 72px;
      max-width: 780px;
      padding: 18px 24px;
      border-radius: 22px;
      background: #2f6df6;
      font-size: 38px;
      line-height: 1.1;
      font-weight: 800;
      opacity: 0;
      visibility: hidden;
    }}
  </style>
</head>
<body>
  <div
    id="moras-caption-root"
    data-composition-id="moras-caption-overlay"
    data-start="0"
    data-duration="{duration:.3f}"
    data-width="1080"
    data-height="1920"
  >
{overlay_items}
{chr(10).join(caption_items)}
  </div>
  <script>
    const DURATION = {duration:.3f};
    const timedElements = Array.from(document.querySelectorAll("[data-caption-start][data-caption-end]"));
    function applyCaptionTime(time) {{
      for (const element of timedElements) {{
        const start = Number.parseFloat(element.dataset.captionStart || "0");
        const end = Number.parseFloat(element.dataset.captionEnd || "0");
        const active = time >= start && time < end;
        element.style.opacity = active ? "1" : "0";
        element.style.visibility = active ? "visible" : "hidden";
        if (element.classList.contains("caption")) {{
          element.style.transform = active ? "translateY(0) scale(1)" : "translateY(12px) scale(0.98)";
        }}
      }}
    }}
    const timeline = {{
      duration: () => DURATION,
      pause: () => timeline,
      seek: (time) => {{
        applyCaptionTime(Number(time) || 0);
        return timeline;
      }},
    }};
    window.__timelines = window.__timelines || {{}};
    window.__timelines["moras-caption-overlay"] = timeline;
    window.__hf = {{
      duration: DURATION,
      seek: (time) => applyCaptionTime(Number(time) || 0),
    }};
    applyCaptionTime(0);
  </script>
</body>
</html>
"""


def overlay_hyperframes_layer(base_video_path: Path, overlay_path: Path, output_path: Path) -> None:
    completed = subprocess.run(
        [
            ffmpeg_command(),
            "-y",
            "-i",
            str(base_video_path),
            "-c:v",
            "libvpx-vp9",
            "-i",
            str(overlay_path),
            "-filter_complex",
            "[0:v][1:v]overlay=0:0:format=auto[v]",
            "-map",
            "[v]",
            "-map",
            "0:a?",
            "-c:v",
            "mpeg4",
            "-q:v",
            "5",
            "-c:a",
            "copy",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffmpeg failed to overlay HyperFrames caption layer.")


def probe_audio_stream(path: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [
                ffprobe_command(),
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_name,duration",
                "-of",
                "json",
                str(path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return probe_audio_stream_with_ffmpeg(path)
    if completed.returncode != 0:
        return probe_audio_stream_with_ffmpeg(path)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"has_audio": False}
    streams = payload.get("streams") if isinstance(payload, dict) else None
    stream = streams[0] if isinstance(streams, list) and streams else None
    if not isinstance(stream, dict):
        return {"has_audio": False}
    return {
        "has_audio": True,
        "codec_name": stream.get("codec_name") or "",
        "duration_sec": round(coerce_float(stream.get("duration")), 2),
    }


def probe_audio_stream_with_ffmpeg(path: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [ffmpeg_command(), "-hide_banner", "-i", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"has_audio": False}
    output = f"{completed.stdout}\n{completed.stderr}"
    match = re.search(r"Audio:\s*([A-Za-z0-9_]+)", output)
    if not match:
        return {"has_audio": False}
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
    duration_sec = 0.0
    if duration_match:
        hours, minutes, seconds = duration_match.groups()
        duration_sec = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    return {"has_audio": True, "codec_name": match.group(1), "duration_sec": round(duration_sec, 2)}


def transcode_render_segment(source_path: Path, output_path: Path, duration_sec: float) -> None:
    suffix = source_path.suffix.lower()
    if suffix in IMAGE_ASSET_SUFFIXES:
        input_args = ["-loop", "1", "-t", f"{duration_sec:.3f}", "-i", str(source_path)]
    else:
        input_args = ["-stream_loop", "-1", "-i", str(source_path), "-t", f"{duration_sec:.3f}"]
    completed = subprocess.run(
        [
            ffmpeg_command(),
            "-y",
            *input_args,
            "-vf",
            (
                f"scale={RENDER_WIDTH}:{RENDER_HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={RENDER_WIDTH}:{RENDER_HEIGHT},setsar=1,fps={RENDER_FPS},format=yuv420p"
            ),
            "-an",
            "-c:v",
            "mpeg4",
            "-q:v",
            "5",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"ffmpeg failed to render {source_path.name}.")


def render_placeholder_segment(output_path: Path, duration_sec: float) -> None:
    completed = subprocess.run(
        [
            ffmpeg_command(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x111827:s={RENDER_WIDTH}x{RENDER_HEIGHT}:d={duration_sec:.3f}:r={RENDER_FPS}",
            "-an",
            "-c:v",
            "mpeg4",
            "-q:v",
            "5",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffmpeg failed to render a visual placeholder.")


def upload_url_to_path(upload_dir: Path, upload_url: str) -> Path:
    if not upload_url.startswith("/uploads/"):
        raise RuntimeError(f"Unsupported local asset URL: {upload_url}")
    relative = upload_url.removeprefix("/uploads/")
    path = (upload_dir / relative).resolve()
    upload_root = upload_dir.resolve()
    if not path.is_relative_to(upload_root):
        raise RuntimeError("Resolved asset path escaped upload directory.")
    if not path.exists():
        raise RuntimeError(f"Resolved asset file does not exist: {upload_url}")
    return path


def resolve_render_artifact_path(upload_dir: Path, asset_url: str) -> Path:
    if not asset_url.startswith("/uploads/factory-renders/"):
        raise unprocessable(
            "DIRECTOR_RENDER_ARTIFACT_SCOPE_UNSUPPORTED",
            "Only local Video Factory render artifacts can be deleted from this control.",
        )
    relative = asset_url.removeprefix("/uploads/")
    path = (upload_dir / relative).resolve()
    render_root = (upload_dir / "factory-renders").resolve()
    if not path.is_relative_to(render_root):
        raise unprocessable(
            "DIRECTOR_RENDER_ARTIFACT_PATH_INVALID",
            "Resolved render artifact path escaped the factory render directory.",
        )
    return path


def delete_local_render_artifact_file(settings: Any, artifact: DirectorRenderArtifactRecord) -> None:
    path = resolve_render_artifact_path(settings.upload_dir, artifact.asset_url)
    if not path.exists():
        return
    if not path.is_file():
        raise unprocessable(
            "DIRECTOR_RENDER_ARTIFACT_NOT_FILE",
            "Render artifact cleanup only deletes individual output files.",
        )
    path.unlink()


def is_artifact_retention_expired(artifact: DirectorRenderArtifactRecord, now: datetime) -> bool:
    if artifact.storage_status == "retention_expired":
        return True
    if not artifact.retention_expires_at:
        return False
    try:
        expires_at = datetime.fromisoformat(artifact.retention_expires_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= now


def is_render_output_video_artifact_active(repo: BreakdownRepository, render_job: DirectorRenderJobRecord) -> bool:
    artifacts = repo.list_director_render_artifacts(render_job.id)
    if not artifacts:
        return True
    video_artifacts = [
        artifact
        for artifact in artifacts
        if artifact.artifact_type == "video" and artifact.asset_url == render_job.output_asset_url
    ]
    return any(artifact.storage_status == "active" for artifact in video_artifacts)


def escape_ffconcat_path(path: Path) -> str:
    return str(path).replace("'", "'\\''")


def find_manual_generation_clips(plan: DirectorPlanRecord) -> list[dict[str, Any]]:
    return [
        clip
        for track in find_video_tracks(plan)
        for clip in list_field(track, "clips")
        if text_field(clip, "source_type", "sourceType") in {"veo_generation", "seedance_generation"}
    ]


def find_base_track_clips(plan: DirectorPlanRecord) -> list[dict[str, Any]]:
    for track in find_video_tracks(plan):
        if text_field(track, "layer") == "base_track":
            return sorted(list_field(track, "clips"), key=lambda clip: coerce_float(clip.get("timeline_start_sec") or clip.get("timelineStartSec")))
    return []


def find_video_tracks(plan: DirectorPlanRecord) -> list[dict[str, Any]]:
    tracks = plan.timeline.get("tracks") if isinstance(plan.timeline, dict) else {}
    video_tracks = tracks.get("video_tracks") or tracks.get("videoTracks") if isinstance(tracks, dict) else []
    return [track for track in video_tracks if isinstance(track, dict)] if isinstance(video_tracks, list) else []


def find_real_moras_requirements(plan: DirectorPlanRecord) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    for asset in plan.asset_resolution:
        if not isinstance(asset, dict):
            continue
        required_type = text_field(asset, "required_asset_type", "requiredAssetType")
        category = text_field(asset, "moras_asset_category", "morasAssetCategory")
        if required_type in {"manual_veo_clip", "manual_seedance_clip"}:
            continue
        if "veo" in required_type or "seedance" in required_type:
            continue
        if "moras" in required_type or category not in {"", "none"}:
            requirements.append(asset)
    return requirements


def library_clip_candidate_refs(clip: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for value in [
        text_field(clip, "source_reference_id", "sourceReferenceId"),
        text_field(clip, "clip_id", "clipId"),
    ]:
        if value and value not in refs:
            refs.append(value)
        if value.startswith("asset_clip_"):
            stripped = value.removeprefix("asset_clip_")
            if stripped and stripped not in refs:
                refs.append(stripped)
    return refs


def asset_ref(asset: dict[str, Any]) -> str:
    return text_field(asset, "asset_ref", "assetRef", "source_plan_id", "sourcePlanId") or "asset"


def text_field(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return str(value).strip()
    return ""


def list_field(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def store_upload_file(file: UploadFile, dest: Path, max_bytes: int) -> int:
    total = 0
    try:
        with dest.open("wb") as handle:
            while chunk := file.file.read(UPLOAD_CHUNK_SIZE):
                total += len(chunk)
                if total > max_bytes:
                    raise bad_request("UPLOAD_TOO_LARGE", "Uploaded file is larger than the configured limit")
                handle.write(chunk)
    except Exception:
        if dest.exists():
            dest.unlink()
        raise
    return total


def validate_manual_generation_media(path: Path, clip: dict[str, Any]) -> dict[str, Any]:
    try:
        metadata = probe_video_metadata(path)
        expected_duration = coerce_float(clip.get("duration_sec") or clip.get("durationSec"))
        if expected_duration > 0 and abs(metadata["duration_sec"] - expected_duration) > MANUAL_GENERATION_DURATION_TOLERANCE_SEC:
            raise bad_request(
                "MANUAL_ASSET_DURATION_MISMATCH",
                (
                    f"Uploaded clip duration {metadata['duration_sec']:.2f}s does not match "
                    f"the planned slot {expected_duration:.2f}s (±{MANUAL_GENERATION_DURATION_TOLERANCE_SEC}s)"
                ),
            )
        width = metadata["width"]
        height = metadata["height"]
        if height <= width:
            raise bad_request("MANUAL_ASSET_ASPECT_MISMATCH", f"Uploaded clip must be vertical 9:16; got {width}x{height}")
        aspect_ratio = width / height
        if abs(aspect_ratio - MANUAL_GENERATION_ASPECT_RATIO) > MANUAL_GENERATION_ASPECT_TOLERANCE:
            raise bad_request("MANUAL_ASSET_ASPECT_MISMATCH", f"Uploaded clip must be vertical 9:16; got {width}x{height}")
        return metadata
    except Exception:
        if path.exists():
            path.unlink()
        raise


def probe_video_metadata(path: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [
                ffprobe_command(),
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,duration:format=duration",
                "-of",
                "json",
                str(path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        return probe_video_metadata_with_ffmpeg(path, error_code="MANUAL_ASSET_PROBE_FAILED")
    except subprocess.TimeoutExpired as exc:
        return probe_video_metadata_with_ffmpeg(path, error_code="MANUAL_ASSET_PROBE_FAILED")

    if completed.returncode != 0:
        return probe_video_metadata_with_ffmpeg(path, error_code="MANUAL_ASSET_PROBE_FAILED")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise bad_request("MANUAL_ASSET_PROBE_FAILED", "ffprobe returned invalid metadata") from exc

    streams = payload.get("streams") if isinstance(payload, dict) else None
    stream = streams[0] if isinstance(streams, list) and streams else {}
    format_info = payload.get("format") if isinstance(payload, dict) and isinstance(payload.get("format"), dict) else {}
    width = int(coerce_float(stream.get("width")))
    height = int(coerce_float(stream.get("height")))
    duration = coerce_float(stream.get("duration")) or coerce_float(format_info.get("duration"))
    if width <= 0 or height <= 0 or duration <= 0:
        raise bad_request("MANUAL_ASSET_PROBE_FAILED", "Uploaded clip is missing readable video dimensions or duration")
    return {"duration_sec": round(duration, 2), "width": width, "height": height}


def probe_video_metadata_with_ffmpeg(path: Path, *, error_code: str, require_duration: bool = True) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [ffmpeg_command(), "-hide_banner", "-i", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise bad_request("FFMPEG_NOT_AVAILABLE", "ffmpeg is required to validate uploaded video clips") from exc
    except subprocess.TimeoutExpired as exc:
        raise bad_request(error_code, "ffmpeg timed out while probing uploaded video metadata") from exc
    output = f"{completed.stdout}\n{completed.stderr}"
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
    dimensions_match = re.search(r"Video:.*?,\s*(\d+)x(\d+)\b", output)
    if not dimensions_match or (require_duration and not duration_match):
        raise bad_request(error_code, "Uploaded clip is missing readable video dimensions or duration")
    duration = 0.0
    if duration_match:
        hours, minutes, seconds = duration_match.groups()
        duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    width = int(dimensions_match.group(1))
    height = int(dimensions_match.group(2))
    if width <= 0 or height <= 0 or (require_duration and duration <= 0):
        raise bad_request(error_code, "Uploaded clip is missing readable video dimensions or duration")
    return {"duration_sec": round(duration, 2), "width": width, "height": height}


def probe_moras_asset_metadata(path: Path, *, require_duration: bool) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [
                ffprobe_command(),
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,duration:format=duration",
                "-of",
                "json",
                str(path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        return probe_moras_asset_metadata_with_ffmpeg(path, require_duration=require_duration)
    except subprocess.TimeoutExpired as exc:
        return probe_moras_asset_metadata_with_ffmpeg(path, require_duration=require_duration)

    if completed.returncode != 0:
        return probe_moras_asset_metadata_with_ffmpeg(path, require_duration=require_duration)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise bad_request("MORAS_ASSET_PROBE_FAILED", "ffprobe returned invalid Moras asset metadata") from exc

    streams = payload.get("streams") if isinstance(payload, dict) else None
    stream = streams[0] if isinstance(streams, list) and streams else {}
    format_info = payload.get("format") if isinstance(payload, dict) and isinstance(payload.get("format"), dict) else {}
    width = int(coerce_float(stream.get("width")))
    height = int(coerce_float(stream.get("height")))
    duration = coerce_float(stream.get("duration")) or coerce_float(format_info.get("duration"))
    if width <= 0 or height <= 0:
        raise bad_request("MORAS_ASSET_PROBE_FAILED", "Uploaded Moras asset is missing readable dimensions")
    if require_duration and duration <= 0:
        raise bad_request("MORAS_ASSET_PROBE_FAILED", "Uploaded Moras video asset is missing readable duration")
    return {"duration_sec": round(max(duration, 0.0), 2), "width": width, "height": height}


def probe_moras_asset_metadata_with_ffmpeg(path: Path, *, require_duration: bool) -> dict[str, Any]:
    metadata = probe_video_metadata_with_ffmpeg(
        path,
        error_code="MORAS_ASSET_PROBE_FAILED",
        require_duration=require_duration,
    )
    if require_duration and metadata["duration_sec"] <= 0:
        raise bad_request("MORAS_ASSET_PROBE_FAILED", "Uploaded Moras video asset is missing readable duration")
    return metadata


def coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

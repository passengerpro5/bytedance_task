from __future__ import annotations

import asyncio
from copy import deepcopy
import json
import re
import threading
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .config import get_settings
from .errors import unprocessable
from .persona_defaults import ensure_digital_human_prompt_assets
from .provider import generate_gemini_text
from .repository import BreakdownRepository
from .schemas import (
    DirectorAgentOutput,
    DirectorGenerationJobRecord,
    DirectorGenerationJobStatus,
    DirectorPlanRecord,
    DirectorPlanRequest,
    ScriptRecord,
)
from .service import error_message, strip_json_fence


PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "director_agent_v1.md"
PROMPT_VERSION = "moras_director_agent_v1"
DIRECTOR_OUTPUT_VERSION = "director-agent-v1.0.0"
DIRECTOR_GENERATION_MAX_ATTEMPTS = 2
DIRECTOR_GENERATION_QUEUE_LOCK = threading.Lock()
REAL_MORAS_ASSET_TYPES = {"real_moras_screen_recording", "real_moras_screenshot", "moras_product_workflow"}
DIRECTOR_VIDEO_CLIP_KEYS = {
    "clip_id",
    "source_type",
    "source_reference_id",
    "timeline_start_sec",
    "timeline_end_sec",
    "duration_sec",
    "layer_role",
    "crop_and_scale",
    "manual_binding_status",
    "manual_prompt_text",
    "bound_asset_url",
    "notes",
}
DIRECTOR_AUDIO_CLIP_KEYS = {
    "clip_id",
    "source_type",
    "timeline_start_sec",
    "timeline_end_sec",
    "duration_sec",
    "volume_db",
    "text_content",
    "voice_prompt",
    "voice_asset_ref",
    "notes",
}
VIDEO_SOURCE_TYPE_ALIASES = {
    "veo": "veo_generation",
    "veo_clip": "veo_generation",
    "veo3_generation": "veo_generation",
    "veo_3_1_generation": "veo_generation",
    "ai_broll": "veo_generation",
    "ai_b_roll": "veo_generation",
    "ai_b-roll": "veo_generation",
    "ai_generated_broll": "veo_generation",
    "ai_generated_b_roll": "veo_generation",
    "ai_generated_b-roll": "veo_generation",
    "ai_product_broll": "veo_generation",
    "generated_broll": "veo_generation",
    "real_moras_screen_recording": "library_asset",
    "real_moras_screenshot": "library_asset",
    "moras_product_workflow": "library_asset",
    "moras_screen_recording": "library_asset",
    "moras_screenshot": "library_asset",
    "screen_recording": "library_asset",
    "uploaded_moras_asset": "library_asset",
    "subtitle_overlay": "hyperframes_overlay",
    "caption_overlay": "hyperframes_overlay",
}
AUDIO_SOURCE_TYPE_ALIASES = {
    "voiceover": "tts_voiceover",
    "primary_voiceover": "tts_voiceover",
    "script_voiceover": "tts_voiceover",
    "background_music": "bg_music",
    "music": "bg_music",
    "sound_effect": "sound_design",
    "sfx": "sound_design",
}
MANUAL_BINDING_STATUS_ALIASES = {
    "pending_asset": "pending_binding",
    "pending_asset_binding": "pending_binding",
    "needs_binding": "pending_binding",
    "pending_manual_upload": "pending_upload",
    "not_applicable": "not_required",
    "not applicable": "not_required",
    "not needed": "not_required",
    "not_needed": "not_required",
    "no_binding_required": "not_required",
    "n/a": "not_required",
    "none": "not_required",
}


class DirectorAgentService:
    def __init__(self, repo: BreakdownRepository | None = None) -> None:
        self.repo = repo or BreakdownRepository()

    def start_generation_job(self, job_id: str) -> None:
        worker = threading.Thread(
            target=self._run_generation_job_thread,
            args=(job_id,),
            daemon=True,
            name=f"director-generation-{job_id[:8]}",
        )
        worker.start()

    def _run_generation_job_thread(self, job_id: str) -> None:
        asyncio.run(self.run_generation_job(job_id))

    async def run_generation_job(self, job_id: str) -> None:
        with DIRECTOR_GENERATION_QUEUE_LOCK:
            job = self.repo.get_director_generation_job(job_id)
            if job.status not in {DirectorGenerationJobStatus.QUEUED, DirectorGenerationJobStatus.GENERATING}:
                return
            self.repo.mark_director_generation_job(job_id, DirectorGenerationJobStatus.GENERATING)
            try:
                plan = await self.generate_plan(DirectorPlanRequest(script_id=job.script_id))
                current_job = self.repo.get_director_generation_job(job_id)
                if current_job.status == DirectorGenerationJobStatus.CANCELED:
                    self.repo.delete_director_plan(plan.id)
                    return
                self.repo.finish_director_generation_job(
                    job_id,
                    status=DirectorGenerationJobStatus.SUCCEEDED,
                    director_plan_id=plan.id,
                )
            except Exception as exc:
                self.repo.finish_director_generation_job(
                    job_id,
                    status=DirectorGenerationJobStatus.FAILED,
                    error_message=error_message(exc),
                )

    def cancel_generation_job(self, job_id: str) -> DirectorGenerationJobRecord:
        job = self.repo.get_director_generation_job(job_id)
        if job.status == DirectorGenerationJobStatus.CANCELED:
            return job
        if job.status not in {DirectorGenerationJobStatus.QUEUED, DirectorGenerationJobStatus.GENERATING}:
            raise unprocessable(
                "DIRECTOR_GENERATION_JOB_NOT_CANCELABLE",
                f"Director generation job is already {job.status}.",
            )
        return self.repo.cancel_director_generation_job(job_id, "用户取消了导演计划生成任务。")

    def retry_generation_job(self, job_id: str) -> DirectorGenerationJobRecord:
        job = self.repo.get_director_generation_job(job_id)
        if job.status not in {DirectorGenerationJobStatus.FAILED, DirectorGenerationJobStatus.CANCELED}:
            raise unprocessable(
                "DIRECTOR_GENERATION_JOB_NOT_RETRYABLE",
                f"Director generation job is {job.status}; only failed or canceled jobs can be retried.",
            )
        retry_job = self.repo.create_director_generation_job(DirectorPlanRequest(script_id=job.script_id))
        self.start_generation_job(retry_job.id)
        return retry_job

    async def generate_plan(self, request: DirectorPlanRequest) -> DirectorPlanRecord:
        script = self.repo.get_script(request.script_id)
        settings = get_settings()
        raw_text: str | None = None
        try:
            if settings.provider == "mock":
                output = build_mock_director_output(script)
                raw_text = output.model_dump_json()
                provider = "mock"
                model_name = "mock-director-agent-v1"
            else:
                prompt = build_director_prompt(script)
                output = None
                result = None
                parse_error: Exception | None = None
                for attempt in range(DIRECTOR_GENERATION_MAX_ATTEMPTS):
                    retry_prompt = prompt if attempt == 0 else build_director_retry_prompt(prompt, parse_error)
                    result = await generate_gemini_text(retry_prompt, settings.gemini_director_model)
                    raw_text = result.text
                    try:
                        output = parse_director_output(raw_text)
                        break
                    except Exception as exc:
                        parse_error = exc
                        if attempt == DIRECTOR_GENERATION_MAX_ATTEMPTS - 1:
                            raise
                if output is None or result is None:
                    raise unprocessable("DIRECTOR_AGENT_FAILED", "Director Agent did not return a usable plan")
                provider = "gemini"
                model_name = result.model_name
            return self.repo.create_director_plan(
                script_id=script.id,
                output=output,
                provider=provider,
                model_name=model_name,
                prompt_version=PROMPT_VERSION,
            )
        except Exception as exc:
            message = error_message(exc)
            raise unprocessable("DIRECTOR_AGENT_FAILED", message) from exc


def build_director_prompt(script: ScriptRecord) -> str:
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    context = compact_script_for_director(script)
    return (
        f"{system_prompt}\n\n"
        "Create a Director Agent plan from this ScriptRecord. Return JSON only.\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )


def build_director_retry_prompt(prompt: str, parse_error: Exception | None) -> str:
    return (
        f"{prompt}\n\n"
        "The previous Director Agent response could not be parsed or validated by the strict internal schema.\n"
        f"Validation error summary: {error_message(parse_error) if parse_error else 'unknown'}\n"
        "Retry once. Return exactly one complete valid JSON object. Do not use markdown fences, comments, trailing prose, or partial JSON."
    )


def parse_director_output(raw_text: str) -> DirectorAgentOutput:
    try:
        data = json.loads(strip_json_fence(raw_text))
    except json.JSONDecodeError as exc:
        raise unprocessable("DIRECTOR_OUTPUT_NOT_JSON", f"Director Agent output was not valid JSON: {exc}") from exc
    try:
        return DirectorAgentOutput.model_validate(sanitize_director_output(data))
    except ValidationError as exc:
        raise unprocessable("DIRECTOR_OUTPUT_SCHEMA_INVALID", str(exc)) from exc


def sanitize_director_output(data: Any) -> Any:
    if not isinstance(data, dict):
        return data
    payload = deepcopy(data)
    tracks = (
        payload.get("timeline", {})
        if isinstance(payload.get("timeline"), dict)
        else {}
    ).get("tracks", {})
    if not isinstance(tracks, dict):
        return payload

    video_tracks = tracks.get("video_tracks")
    target_duration = director_total_duration(payload)
    if isinstance(video_tracks, list):
        for track in video_tracks:
            if not isinstance(track, dict):
                continue
            clips = track.get("clips")
            if isinstance(clips, list):
                track["clips"] = [sanitize_director_video_clip(clip) for clip in clips if isinstance(clip, dict)]
                if track.get("layer") == "base_track" and target_duration is not None:
                    track["clips"] = repair_director_base_track_gaps(track["clips"], target_duration)

    audio_tracks = tracks.get("audio_tracks")
    if isinstance(audio_tracks, list):
        for track in audio_tracks:
            if not isinstance(track, dict):
                continue
            clips = track.get("clips")
            if isinstance(clips, list):
                track["clips"] = [sanitize_director_audio_clip(clip) for clip in clips if isinstance(clip, dict)]
    return payload


def director_total_duration(payload: dict[str, Any]) -> float | None:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return None
    try:
        duration = float(metadata.get("total_duration_sec"))
    except (TypeError, ValueError):
        return None
    return duration if duration > 0 else None


def repair_director_base_track_gaps(clips: list[dict[str, Any]], target_duration: float) -> list[dict[str, Any]]:
    ordered: list[dict[str, Any]] = []
    for clip in clips:
        try:
            start = float(clip.get("timeline_start_sec"))
            end = float(clip.get("timeline_end_sec"))
        except (TypeError, ValueError):
            continue
        if end <= start or start >= target_duration:
            continue
        normalized = dict(clip)
        if end > target_duration:
            end = target_duration
            normalized["timeline_end_sec"] = round(end, 2)
            normalized["duration_sec"] = round(end - start, 2)
        ordered.append(normalized)

    ordered.sort(key=lambda item: (float(item["timeline_start_sec"]), float(item["timeline_end_sec"])))
    repaired: list[dict[str, Any]] = []
    cursor = 0.0
    for clip in ordered:
        start = float(clip["timeline_start_sec"])
        end = float(clip["timeline_end_sec"])
        if end <= cursor + 0.05:
            continue
        if start > cursor + 0.05:
            repaired.append(placeholder_clip(cursor, start, len(repaired) + 1))
        next_clip = dict(clip)
        if start < cursor:
            next_clip["timeline_start_sec"] = round(cursor, 2)
            next_clip["duration_sec"] = round(end - cursor, 2)
        repaired.append(next_clip)
        cursor = end

    if cursor < target_duration - 0.05:
        repaired.append(placeholder_clip(cursor, target_duration, len(repaired) + 1))
    return repaired


def sanitize_director_video_clip(clip: dict[str, Any]) -> dict[str, Any]:
    sanitized = {key: clip[key] for key in DIRECTOR_VIDEO_CLIP_KEYS if key in clip}
    source_type = str(
        sanitized.get("source_type")
        or clip.get("sourceType")
        or clip.get("asset_type")
        or clip.get("assetType")
        or ""
    ).strip().lower()
    sanitized["source_type"] = VIDEO_SOURCE_TYPE_ALIASES.get(source_type, source_type)
    if sanitized.get("crop_and_scale") is None:
        sanitized.pop("crop_and_scale", None)
    if not isinstance(sanitized.get("crop_and_scale", {}), dict):
        sanitized.pop("crop_and_scale", None)
    if "manual_binding_status" in sanitized:
        status = str(sanitized["manual_binding_status"]).strip().lower()
        status = MANUAL_BINDING_STATUS_ALIASES.get(status, status)
        if status in {"resolved", "ready", "complete", "completed"}:
            if sanitized["source_type"] == "library_asset" and not sanitized.get("bound_asset_url"):
                status = "pending_binding"
            elif sanitized["source_type"] in {"veo_generation", "seedance_generation"}:
                status = "pending_upload"
            else:
                status = "not_required"
        if sanitized["source_type"] == "library_asset" and status in {"pending_upload", "pending_generation"}:
            status = "pending_binding"
        if sanitized["source_type"] == "hyperframes_overlay" and status in {"pending_upload", "pending_binding", "pending_generation"}:
            status = "not_required"
        if sanitized["source_type"] in {"veo_generation", "seedance_generation"} and status == "pending_binding":
            status = "pending_upload"
        sanitized["manual_binding_status"] = status
    if not sanitized.get("source_reference_id"):
        sanitized["source_reference_id"] = str(
            clip.get("source_reference_id")
            or clip.get("sourceReferenceId")
            or clip.get("asset_ref")
            or clip.get("assetRef")
            or clip.get("clip_id")
            or "unknown_source"
        )
    return sanitized


def sanitize_director_audio_clip(clip: dict[str, Any]) -> dict[str, Any]:
    sanitized = {key: clip[key] for key in DIRECTOR_AUDIO_CLIP_KEYS if key in clip}
    source_type = str(sanitized.get("source_type") or clip.get("sourceType") or "").strip().lower()
    sanitized["source_type"] = AUDIO_SOURCE_TYPE_ALIASES.get(source_type, source_type)
    if not sanitized.get("voice_prompt") and clip.get("voicePrompt"):
        sanitized["voice_prompt"] = str(clip.get("voicePrompt") or "")
    if not sanitized.get("voice_asset_ref") and clip.get("voiceAssetRef"):
        sanitized["voice_asset_ref"] = str(clip.get("voiceAssetRef") or "")
    return sanitized


def digital_human_prompt_assets_from_script(script: ScriptRecord) -> dict[str, Any]:
    persona = deepcopy(script.creator_persona) if isinstance(script.creator_persona, dict) else {}
    if not persona:
        return {}
    ensure_digital_human_prompt_assets(persona)
    assets = persona.get("digital_human_prompt_assets")
    return dict(assets) if isinstance(assets, dict) else {}


def compact_script_for_director(script: ScriptRecord) -> dict[str, Any]:
    return {
        "script_id": script.id,
        "script": script.script,
        "storyboard": script.storyboard,
        "creator_persona": script.creator_persona,
        "video_prompt": script.video_prompt,
        "production_asset_plan": script.production_asset_plan,
        "risk_check": script.risk_check,
        "source_component_summary": script.source_component_summary,
    }


def build_mock_director_output(script: ScriptRecord) -> DirectorAgentOutput:
    target_duration = coerce_seconds(script.video_prompt.get("target_duration_sec") or script.video_prompt.get("targetDurationSec") or 38)
    veo_segments = normalize_veo_segments(script.video_prompt.get("segments") or [])
    real_asset_clips = build_real_asset_base_clips(script.production_asset_plan)
    base_clips = build_contiguous_base_clips(target_duration, veo_segments, real_asset_clips)
    voiceover_text = " ".join(str(line) for line in script.script.get("voiceover", []) if str(line).strip())
    prompt_assets = digital_human_prompt_assets_from_script(script)
    voice_prompt = str(prompt_assets.get("voice_style_prompt") or "").strip()
    overlay_lines = [str(line) for line in script.script.get("overlay", []) if str(line).strip()]
    video_tracks = [
        {"layer": "base_track", "clips": base_clips},
        {
            "layer": "overlay",
            "clips": [
                {
                    "clip_id": "hyperframes_subtitle_overlay",
                    "source_type": "hyperframes_overlay",
                    "source_reference_id": "script.voiceover+script.overlay",
                    "timeline_start_sec": 0,
                    "timeline_end_sec": target_duration,
                    "duration_sec": target_duration,
                    "layer_role": "subtitles_and_keyword_overlays",
                    "notes": "HyperFrames renders word-level subtitles, keyword highlights, and short overlay lines.",
                }
            ],
        },
    ]
    audio_tracks = [
        {
            "layer": "audio",
            "clips": [
                {
                    "clip_id": "tts_voiceover_main",
                    "source_type": "tts_voiceover",
                    "timeline_start_sec": 0,
                    "timeline_end_sec": target_duration,
                    "duration_sec": target_duration,
                    "volume_db": 0,
                    "text_content": voiceover_text,
                    "voice_prompt": voice_prompt,
                    "voice_asset_ref": "creator_persona.digital_human_prompt_assets.voice_style_prompt" if voice_prompt else "",
                    "notes": "V1 plans synthetic TTS alignment only; real synthesis and duration fitting are render-worker work.",
                },
                {
                    "clip_id": "bg_music_bed",
                    "source_type": "bg_music",
                    "timeline_start_sec": 0,
                    "timeline_end_sec": target_duration,
                    "duration_sec": target_duration,
                    "volume_db": -18,
                    "notes": str(script.script.get("sound_effect") or "Low-volume music bed with ducking under voiceover."),
                },
            ],
        }
    ]
    dispatches = build_tool_dispatches(script, veo_segments, overlay_lines, target_duration)
    output = {
        "version": DIRECTOR_OUTPUT_VERSION,
        "metadata": {
            "target_aspect_ratio": "9:16",
            "total_duration_sec": target_duration,
            "render_intent": "plan_only",
            "director_model": "gemini-3.5-flash",
            "provider_route": "vertex-primary-aihubmix-fallback",
        },
        "timeline": {"tracks": {"video_tracks": video_tracks, "audio_tracks": audio_tracks}},
        "asset_resolution": build_asset_resolution(script.production_asset_plan, veo_segments),
        "tool_dispatches": dispatches,
        "validation_summary": {
            "timeline_continuity": "base_track covers 0s through target duration with Veo 3.1 gaps plus library/Moras clips",
            "layer_collision_check": "validated per layer by backend schema",
            "veo_limit_check": "every Veo 3.1 dispatch stays within 8 seconds",
            "asset_readiness": "Veo 3.1 clips require manual external generation and upload; real Moras assets are placeholders until asset library IDs are bound",
            "render_scope": "V1 stores Director Plan and manual upload bindings only; FFmpeg, HyperFrames, and TTS execution are planned but not run",
        },
    }
    return DirectorAgentOutput.model_validate(output)


def normalize_veo_segments(value: Any) -> list[dict[str, Any]]:
    segments = value if isinstance(value, list) else []
    normalized: list[dict[str, Any]] = []
    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            continue
        start = coerce_seconds(first_present(segment.get("timelineStartSec"), segment.get("timeline_start_sec")))
        end = coerce_seconds(first_present(segment.get("timelineEndSec"), segment.get("timeline_end_sec")))
        duration = coerce_seconds(segment.get("durationSec") or segment.get("duration_sec") or (end - start))
        if end <= start or duration <= 0:
            continue
        normalized.append(
            {
                "segment_index": int(segment.get("segmentIndex") or segment.get("segment_index") or index),
                "timeline_start_sec": start,
                "timeline_end_sec": end,
                "duration_sec": duration,
                "veo_prompt": str(
                    segment.get("veoPrompt")
                    or segment.get("veo_prompt")
                    or segment.get("visualPrompt")
                    or segment.get("visual_prompt")
                    or ""
                ),
            }
        )
    return normalized


def build_real_asset_base_clips(production_asset_plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clips: list[dict[str, Any]] = []
    for entry in production_asset_plan:
        if not isinstance(entry, dict):
            continue
        asset_type = str(entry.get("assetType") or entry.get("asset_type") or "")
        layer = str(entry.get("layer") or "")
        if asset_type not in REAL_MORAS_ASSET_TYPES or layer not in {"cutaway", "base_track"}:
            continue
        start, end = parse_time_range(str(entry.get("timeRange") or entry.get("time_range") or ""))
        if end <= start:
            continue
        plan_id = str(entry.get("planId") or entry.get("plan_id") or f"asset_{len(clips) + 1}")
        clips.append(
            {
                "clip_id": f"asset_clip_{plan_id}",
                "source_type": "library_asset",
                "source_reference_id": plan_id,
                "timeline_start_sec": start,
                "timeline_end_sec": end,
                "duration_sec": round(end - start, 2),
                "layer_role": f"{asset_type}:{layer}",
                "notes": str(entry.get("editorNote") or entry.get("editor_note") or entry.get("usageReason") or ""),
            }
        )
    return clips


def build_contiguous_base_clips(
    target_duration: float,
    veo_segments: list[dict[str, Any]],
    real_asset_clips: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    clips: list[dict[str, Any]] = []
    for segment in veo_segments:
        clips.append(
            {
                "clip_id": f"veo_clip_{segment['segment_index']}",
                "source_type": "veo_generation",
                "source_reference_id": f"video_prompt.segments[{segment['segment_index']}]",
                "timeline_start_sec": segment["timeline_start_sec"],
                "timeline_end_sec": segment["timeline_end_sec"],
                "duration_sec": segment["duration_sec"],
                "layer_role": "ai_generated_base_visual",
                "manual_binding_status": "pending_upload",
                "manual_prompt_text": segment["veo_prompt"],
                "notes": segment["veo_prompt"],
            }
        )
    clips.extend(real_asset_clips)
    clips = sorted(clips, key=lambda item: (item["timeline_start_sec"], item["timeline_end_sec"]))
    contiguous: list[dict[str, Any]] = []
    cursor = 0.0
    for clip in clips:
        start = float(clip["timeline_start_sec"])
        end = float(clip["timeline_end_sec"])
        if end <= cursor + 0.05:
            continue
        if start > cursor + 0.05:
            contiguous.append(placeholder_clip(cursor, start, len(contiguous) + 1))
        next_clip = dict(clip)
        if start < cursor:
            next_clip["timeline_start_sec"] = cursor
            next_clip["duration_sec"] = round(end - cursor, 2)
        contiguous.append(next_clip)
        cursor = end
    if cursor < target_duration - 0.05:
        contiguous.append(placeholder_clip(cursor, target_duration, len(contiguous) + 1))
    return contiguous


def placeholder_clip(start: float, end: float, index: int) -> dict[str, Any]:
    return {
        "clip_id": f"placeholder_visual_{index}",
        "source_type": "library_asset",
        "source_reference_id": "missing_visual_placeholder",
        "timeline_start_sec": round(start, 2),
        "timeline_end_sec": round(end, 2),
        "duration_sec": round(end - start, 2),
        "layer_role": "gap_placeholder",
        "notes": "Generated because the current script package leaves an unbound base-track gap.",
    }


def build_asset_resolution(
    production_asset_plan: list[dict[str, Any]],
    veo_segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    resolutions: list[dict[str, Any]] = []
    for segment in veo_segments:
        clip_id = f"veo_clip_{segment['segment_index']}"
        resolutions.append(
            {
                "asset_ref": clip_id,
                "source_plan_id": f"video_prompt.segments[{segment['segment_index']}]",
                "required_asset_type": "manual_veo_clip",
                "moras_asset_category": "none",
                "resolution_status": "missing_placeholder",
                "resolver_note": "User must copy the Veo 3.1 prompt, generate this clip externally, then upload it back to Video Factory.",
            }
        )
    for entry in production_asset_plan:
        if not isinstance(entry, dict):
            continue
        plan_id = str(entry.get("planId") or entry.get("plan_id") or f"asset_{len(resolutions) + 1}")
        asset_type = str(entry.get("assetType") or entry.get("asset_type") or "")
        moras_category = str(entry.get("morasAssetCategory") or entry.get("moras_asset_category") or "none")
        if asset_type in REAL_MORAS_ASSET_TYPES:
            status = "missing_placeholder"
            note = "Needs an approved file id from the Moras asset library before render execution."
        elif asset_type == "digital_human_avatar":
            status = "ready"
            note = "Persona prompt asset is ready; no real media sample is required, but the matching visual clip still comes from Veo generation/upload tasks."
        elif asset_type == "live_creator_footage":
            status = "ready"
            note = "Ready as a plan requirement only; real live-creator footage must be manually uploaded or bound before final render."
        elif asset_type == "ai_generated_broll":
            status = "ready"
            note = "Can be produced by generation workers in a later render phase."
        else:
            status = "ready"
            note = "Can be handled by post-production templates or audio workers."
        resolutions.append(
            {
                "asset_ref": plan_id,
                "source_plan_id": plan_id,
                "required_asset_type": asset_type or "unknown",
                "moras_asset_category": moras_category,
                "resolution_status": status,
                "resolver_note": note,
            }
        )
    return resolutions


def build_tool_dispatches(
    script: ScriptRecord,
    veo_segments: list[dict[str, Any]],
    overlay_lines: list[str],
    target_duration: float,
) -> list[dict[str, Any]]:
    dispatches: list[dict[str, Any]] = []
    prompt_assets = digital_human_prompt_assets_from_script(script)
    voice_prompt = str(prompt_assets.get("voice_style_prompt") or "").strip()

    def add(tool_name: str, parameters: dict[str, Any], expected_output: str, status: str = "planned") -> None:
        dispatches.append(
            {
                "sequence_order": len(dispatches) + 1,
                "tool_name": tool_name,
                "status": status,
                "parameters": parameters,
                "expected_output": expected_output,
            }
        )

    add(
        "asset_resolver",
        {"script_id": script.id, "production_asset_plan": script.production_asset_plan},
        "asset binding table for real Moras and generated assets",
        status="blocked" if any(item.get("asset_type") in REAL_MORAS_ASSET_TYPES for item in script.production_asset_plan) else "planned",
    )
    for segment in veo_segments:
        clip_id = f"veo_clip_{segment['segment_index']}"
        add(
            "manual_veo_generation",
            {
                "clip_id": clip_id,
                "segment_index": segment["segment_index"],
                "timeline_start_sec": segment["timeline_start_sec"],
                "timeline_end_sec": segment["timeline_end_sec"],
                "veo_prompt": segment["veo_prompt"],
            },
            "manual external Veo 3.1 clip generated by the user",
            status="blocked",
        )
        add(
            "manual_veo_upload",
            {
                "clip_id": clip_id,
                "accepted_formats": ["mp4", "mov", "webm"],
                "target_duration_sec": segment["duration_sec"],
            },
            "uploaded Veo 3.1 clip bound to the matching Director Plan clip_id",
            status="blocked",
        )
    for entry in script.production_asset_plan:
        asset_type = str(entry.get("assetType") or entry.get("asset_type") or "")
        if asset_type in REAL_MORAS_ASSET_TYPES:
            add(
                "fetch_library_asset",
                {"plan_id": entry.get("planId") or entry.get("plan_id"), "asset_type": asset_type},
                "resolved local file path or asset id",
                status="blocked",
            )
    add(
        "render_hyperframes_subtitle",
        {"duration_sec": target_duration, "voiceover": script.script.get("voiceover", []), "overlay": overlay_lines},
        "transparent subtitle/overlay video layer",
    )
    add(
        "synthesize_tts",
        {
            "duration_sec": target_duration,
            "voiceover": script.script.get("voiceover", []),
            "voice_prompt": voice_prompt,
            "voice_asset_ref": "creator_persona.digital_human_prompt_assets.voice_style_prompt" if voice_prompt else "",
        },
        "voiceover audio track with timestamps",
    )
    add(
        "run_ffmpeg_mix",
        {"duration_sec": target_duration, "aspect_ratio": "9:16", "timeline_json": "director_plan.timeline"},
        "draft MP4 rendered from resolved assets",
        status="blocked",
    )
    add(
        "run_quality_check",
        {"checks": ["timeline_bounds", "black_frame", "subtitle_overlap", "audio_loudness"]},
        "render QA report",
        status="blocked",
    )
    return dispatches


def parse_time_range(value: str) -> tuple[float, float]:
    numbers = [coerce_seconds(match) for match in re.findall(r"\\d+(?:\\.\\d+)?", value)]
    if len(numbers) >= 2:
        return numbers[0], numbers[1]
    return 0.0, 0.0


def coerce_seconds(value: Any) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None

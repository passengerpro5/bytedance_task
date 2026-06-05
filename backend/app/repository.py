from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from .config import get_settings
from .errors import not_found
from .persona_defaults import (
    creator_persona_needs_refresh,
    normalize_creator_persona_payload,
)
from .schemas import (
    BreakdownRecord,
    BreakdownResult,
    BreakdownStatus,
    CreatorPersonaRecord,
    DirectorAgentOutput,
    DirectorGenerationJobRecord,
    DirectorGenerationJobStatus,
    DirectorPlanAssetBindingRecord,
    DirectorPlanRecord,
    DirectorPlanRequest,
    DirectorPlanStatus,
    DirectorPublishRecord,
    DirectorRenderArtifactRecord,
    DirectorRenderJobStatus,
    DirectorRenderJobRecord,
    DirectorRenderUsageRecord,
    ManualFactoryAssetRecord,
    MorasAssetLibraryRecord,
    PersonaGenerationJobRecord,
    PersonaGenerationJobStatus,
    PersonaGenerationRequest,
    ScriptAgentItem,
    ScriptGenerationJobRecord,
    ScriptGenerationJobStatus,
    ScriptGenerationRequest,
    ScriptRecord,
    ScriptStatus,
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class BreakdownRepository:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or get_settings().db_path
        self.lock = RLock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def create(self, provider: str, input_video_url: str | None = None, input_video_key: str | None = None) -> BreakdownRecord:
        now = utc_now()
        record_id = uuid4().hex
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO breakdowns (id, status, provider, input_video_url, input_video_key, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (record_id, BreakdownStatus.PENDING.value, provider, input_video_url, input_video_key, now, now),
            )
        return self.get(record_id)

    def find_reusable_by_video_key(self, provider: str, input_video_key: str) -> BreakdownRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM breakdowns
                WHERE provider = ?
                  AND input_video_key = ?
                  AND status != ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (provider, input_video_key, BreakdownStatus.FAILED.value),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def mark_status(self, record_id: str, status: BreakdownStatus, error_message: str | None = None) -> BreakdownRecord:
        return self._update(
            record_id,
            {
                "status": status.value,
                "error_message": error_message,
            },
        )

    def save_success(self, record_id: str, result: BreakdownResult, raw_response_text: str | None = None) -> BreakdownRecord:
        payload = result.model_dump(mode="json")
        payload.update(
            {
                "status": BreakdownStatus.SUCCEEDED.value,
                "error_message": None,
                "raw_response_text": raw_response_text,
            }
        )
        return self._update(record_id, payload)

    def list(self) -> list[BreakdownRecord]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM breakdowns ORDER BY created_at DESC").fetchall()
        return [self._row_to_record(row) for row in rows]

    def get(self, record_id: str) -> BreakdownRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM breakdowns WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            raise not_found("BREAKDOWN_NOT_FOUND", "Breakdown record not found")
        return self._row_to_record(row)

    def delete(self, record_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM breakdown_model_runs WHERE breakdown_id = ?", (record_id,))
            cursor = connection.execute("DELETE FROM breakdowns WHERE id = ?", (record_id,))
            if cursor.rowcount == 0:
                raise not_found("BREAKDOWN_NOT_FOUND", "Breakdown record not found")

    def create_model_run(
        self,
        *,
        breakdown_id: str,
        status: str,
        model_name: str,
        prompt_version: str,
        request: dict[str, Any],
    ) -> str:
        now = utc_now()
        model_run_id = uuid4().hex
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO breakdown_model_runs (
                    id, breakdown_id, status, model_name, prompt_version,
                    request_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (model_run_id, breakdown_id, status, model_name, prompt_version, _dump(request), now, now),
            )
        return model_run_id

    def finish_model_run(
        self,
        model_run_id: str,
        status: str,
        raw_response_text: str | None = None,
        parsed_output: BreakdownResult | dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        parsed_json = None
        if isinstance(parsed_output, BreakdownResult):
            parsed_json = _dump(parsed_output.model_dump(mode="json"))
        elif parsed_output is not None:
            parsed_json = _dump(parsed_output)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE breakdown_model_runs
                SET status = ?,
                    raw_response_text = ?,
                    parsed_output_json = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (status, raw_response_text, parsed_json, error_message, utc_now(), model_run_id),
            )

    def model_runs_for(self, breakdown_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM breakdown_model_runs WHERE breakdown_id = ? ORDER BY created_at",
                (breakdown_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_script_records(
        self,
        *,
        items: list[ScriptAgentItem],
        provider: str,
        model_name: str,
        script_type: str,
        allow_duplicate_persona: bool = False,
        preserve_creator_persona: bool = False,
    ) -> list[ScriptRecord]:
        now = utc_now()
        created_ids: list[str] = []
        with self._connect() as connection:
            used_persona_names: set[str] = set()
            for index, item in enumerate(items):
                record_id = uuid4().hex
                payload = item.model_dump(mode="json")
                if preserve_creator_persona and isinstance(payload.get("creator_persona"), dict):
                    payload["creator_persona"] = dict(payload["creator_persona"])
                else:
                    payload["creator_persona"] = _normalize_creator_persona_for_storage(
                        payload.get("creator_persona"),
                        payload.get("topic_plan") or {},
                        payload.get("script") or {},
                        seed=f"{record_id}|{index}",
                        variant_index=index,
                        excluded_names=None if allow_duplicate_persona else used_persona_names,
                    )
                _sync_script_payload_to_creator_persona(payload, force=preserve_creator_persona)
                persona_name = _persona_display_name(payload.get("creator_persona"))
                if persona_name and not allow_duplicate_persona:
                    used_persona_names.add(persona_name)
                payload["video_prompt"] = _normalize_video_prompt_for_storage(
                    payload.get("video_prompt"),
                    payload.get("script") or {},
                    payload.get("storyboard") or [],
                    payload.get("production_asset_plan") or [],
                    payload.get("creator_persona"),
                )
                connection.execute(
                    """
                    INSERT INTO scripts (
                        id, status, provider, model_name, script_type,
                        source_breakdown_ids, topic_plan, script, storyboard,
                        creator_persona, video_prompt, production_asset_plan, risk_check, source_component_summary,
                        revision_history, error_message, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record_id,
                        ScriptStatus.READY.value,
                        provider,
                        model_name,
                        script_type,
                        _dump(payload.get("source_breakdown_ids", [])),
                        _dump(payload["topic_plan"]),
                        _dump(payload["script"]),
                        _dump(payload["storyboard"]),
                        _dump(payload["creator_persona"]),
                        _dump(payload["video_prompt"]),
                        _dump(payload.get("production_asset_plan", [])),
                        _dump(payload["risk_check"]),
                        _dump(payload.get("source_component_summary", [])),
                        _dump([]),
                        None,
                        now,
                        now,
                    ),
                )
                created_ids.append(record_id)
        return [self.get_script(record_id) for record_id in created_ids]

    def create_script_generation_job(self, request: ScriptGenerationRequest) -> ScriptGenerationJobRecord:
        now = utc_now()
        record_id = uuid4().hex
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO script_generation_jobs (
                    id, status, script_count, script_type, source_breakdown_ids,
                    persona_id, persona_hint, completed_count, script_ids, error_message, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    ScriptGenerationJobStatus.QUEUED.value,
                    request.script_count,
                    request.script_type,
                    _dump(request.source_breakdown_ids),
                    request.persona_id,
                    _dump(request.persona_hint),
                    0,
                    _dump([]),
                    None,
                    now,
                    now,
                ),
            )
        return self.get_script_generation_job(record_id)

    def update_script_generation_job_progress(self, record_id: str, script_ids: list[str]) -> ScriptGenerationJobRecord:
        ordered_script_ids = list(dict.fromkeys(script_ids))
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE script_generation_jobs
                SET status = ?,
                    completed_count = ?,
                    script_ids = ?,
                    error_message = NULL,
                    updated_at = ?
                WHERE id = ?
                  AND status IN (?, ?)
                """,
                (
                    ScriptGenerationJobStatus.GENERATING.value,
                    len(ordered_script_ids),
                    _dump(ordered_script_ids),
                    utc_now(),
                    record_id,
                    ScriptGenerationJobStatus.QUEUED.value,
                    ScriptGenerationJobStatus.GENERATING.value,
                ),
            )
            if cursor.rowcount == 0:
                return self.get_script_generation_job(record_id)
        return self.get_script_generation_job(record_id)

    def attach_creator_persona_scripts(self, record_id: str, script_ids: list[str]) -> CreatorPersonaRecord:
        record = self.get_creator_persona(record_id)
        existing_ids = [str(item) for item in record.source_script_ids]
        next_ids = existing_ids[:]
        for script_id in script_ids:
            if script_id not in next_ids:
                next_ids.append(script_id)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE creator_personas
                SET source_script_ids = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (_dump(next_ids), utc_now(), record_id),
            )
            if cursor.rowcount == 0:
                raise not_found("CREATOR_PERSONA_NOT_FOUND", "Creator persona not found")
        return self.get_creator_persona(record_id)

    def list_script_generation_jobs(self, include_succeeded: bool = False) -> list[ScriptGenerationJobRecord]:
        with self._connect() as connection:
            if include_succeeded:
                rows = connection.execute(
                    "SELECT * FROM script_generation_jobs ORDER BY created_at DESC",
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM script_generation_jobs
                    WHERE status != ?
                    ORDER BY created_at DESC
                    """,
                    (ScriptGenerationJobStatus.SUCCEEDED.value,),
                ).fetchall()
        return [self._row_to_script_generation_job_record(row) for row in rows]

    def get_script_generation_job(self, record_id: str) -> ScriptGenerationJobRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM script_generation_jobs WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            raise not_found("SCRIPT_GENERATION_JOB_NOT_FOUND", "Script generation job not found")
        return self._row_to_script_generation_job_record(row)

    def delete_script_generation_job(self, record_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM script_generation_jobs WHERE id = ?", (record_id,))
            if cursor.rowcount == 0:
                raise not_found("SCRIPT_GENERATION_JOB_NOT_FOUND", "Script generation job not found")

    def recover_stale_script_generation_jobs(self, max_age_seconds: int) -> list[ScriptGenerationJobRecord]:
        if max_age_seconds <= 0:
            threshold = datetime.now(UTC)
        else:
            threshold = datetime.now(UTC) - timedelta(seconds=max_age_seconds)
        recovered_ids: list[str] = []
        message = "Script generation job recovered after backend restart or stale worker timeout."
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM script_generation_jobs
                WHERE status IN (?, ?)
                """,
                (ScriptGenerationJobStatus.QUEUED.value, ScriptGenerationJobStatus.GENERATING.value),
            ).fetchall()
            for row in rows:
                updated_at = _parse_utc_datetime(str(row["updated_at"]))
                if updated_at > threshold:
                    continue
                connection.execute(
                    """
                    UPDATE script_generation_jobs
                    SET status = ?,
                        error_message = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        ScriptGenerationJobStatus.FAILED.value,
                        message,
                        utc_now(),
                        row["id"],
                    ),
                )
                recovered_ids.append(row["id"])
        return [self.get_script_generation_job(record_id) for record_id in recovered_ids]

    def create_persona_generation_job(self, request: PersonaGenerationRequest) -> PersonaGenerationJobRecord:
        now = utc_now()
        record_id = uuid4().hex
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO persona_generation_jobs (
                    id, status, persona_count, topic_or_brand_context, target_audience,
                    required_demographic, completed_count, persona_ids, error_message,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    PersonaGenerationJobStatus.QUEUED.value,
                    request.persona_count,
                    request.topic_or_brand_context,
                    request.target_audience,
                    request.required_demographic,
                    0,
                    _dump([]),
                    None,
                    now,
                    now,
                ),
            )
        return self.get_persona_generation_job(record_id)

    def list_persona_generation_jobs(self, include_succeeded: bool = False) -> list[PersonaGenerationJobRecord]:
        with self._connect() as connection:
            if include_succeeded:
                rows = connection.execute(
                    "SELECT * FROM persona_generation_jobs ORDER BY created_at DESC",
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM persona_generation_jobs
                    WHERE status != ?
                    ORDER BY created_at DESC
                    """,
                    (PersonaGenerationJobStatus.SUCCEEDED.value,),
                ).fetchall()
        return [self._row_to_persona_generation_job_record(row) for row in rows]

    def get_persona_generation_job(self, record_id: str) -> PersonaGenerationJobRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM persona_generation_jobs WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            raise not_found("PERSONA_GENERATION_JOB_NOT_FOUND", "Persona generation job not found")
        return self._row_to_persona_generation_job_record(row)

    def delete_persona_generation_job(self, record_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM persona_generation_jobs WHERE id = ?", (record_id,))
            if cursor.rowcount == 0:
                raise not_found("PERSONA_GENERATION_JOB_NOT_FOUND", "Persona generation job not found")

    def recover_stale_persona_generation_jobs(self, max_age_seconds: int) -> list[PersonaGenerationJobRecord]:
        if max_age_seconds <= 0:
            threshold = datetime.now(UTC)
        else:
            threshold = datetime.now(UTC) - timedelta(seconds=max_age_seconds)
        recovered_ids: list[str] = []
        message = "Persona generation job recovered after backend restart or stale worker timeout."
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM persona_generation_jobs
                WHERE status IN (?, ?)
                """,
                (PersonaGenerationJobStatus.QUEUED.value, PersonaGenerationJobStatus.GENERATING.value),
            ).fetchall()
            for row in rows:
                updated_at = _parse_utc_datetime(str(row["updated_at"]))
                if updated_at > threshold:
                    continue
                connection.execute(
                    """
                    UPDATE persona_generation_jobs
                    SET status = ?,
                        error_message = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        PersonaGenerationJobStatus.FAILED.value,
                        message,
                        utc_now(),
                        row["id"],
                    ),
                )
                recovered_ids.append(row["id"])
        return [self.get_persona_generation_job(record_id) for record_id in recovered_ids]

    def mark_persona_generation_job(
        self,
        record_id: str,
        status: PersonaGenerationJobStatus,
        error_message: str | None = None,
    ) -> PersonaGenerationJobRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE persona_generation_jobs
                SET status = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (status.value, error_message, utc_now(), record_id),
            )
            if cursor.rowcount == 0:
                raise not_found("PERSONA_GENERATION_JOB_NOT_FOUND", "Persona generation job not found")
        return self.get_persona_generation_job(record_id)

    def update_persona_generation_job_progress(
        self,
        record_id: str,
        *,
        persona_ids: list[str],
    ) -> PersonaGenerationJobRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE persona_generation_jobs
                SET completed_count = ?,
                    persona_ids = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (len(persona_ids), _dump(persona_ids), utc_now(), record_id),
            )
            if cursor.rowcount == 0:
                raise not_found("PERSONA_GENERATION_JOB_NOT_FOUND", "Persona generation job not found")
        return self.get_persona_generation_job(record_id)

    def finish_persona_generation_job(
        self,
        record_id: str,
        *,
        status: PersonaGenerationJobStatus,
        persona_ids: list[str] | None = None,
        error_message: str | None = None,
    ) -> PersonaGenerationJobRecord:
        with self._connect() as connection:
            current_ids = persona_ids
            if current_ids is None:
                row = connection.execute(
                    "SELECT * FROM persona_generation_jobs WHERE id = ?",
                    (record_id,),
                ).fetchone()
                if row is None:
                    raise not_found("PERSONA_GENERATION_JOB_NOT_FOUND", "Persona generation job not found")
                if row["status"] not in {PersonaGenerationJobStatus.QUEUED.value, PersonaGenerationJobStatus.GENERATING.value}:
                    return self._row_to_persona_generation_job_record(row)
                current_ids = [str(item) for item in (_loads(row["persona_ids"]) or [])]
            else:
                row = connection.execute(
                    "SELECT * FROM persona_generation_jobs WHERE id = ?",
                    (record_id,),
                ).fetchone()
                if row is None:
                    raise not_found("PERSONA_GENERATION_JOB_NOT_FOUND", "Persona generation job not found")
                if row["status"] not in {PersonaGenerationJobStatus.QUEUED.value, PersonaGenerationJobStatus.GENERATING.value}:
                    return self._row_to_persona_generation_job_record(row)
            cursor = connection.execute(
                """
                UPDATE persona_generation_jobs
                SET status = ?,
                    completed_count = ?,
                    persona_ids = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (status.value, len(current_ids), _dump(current_ids), error_message, utc_now(), record_id),
            )
            if cursor.rowcount == 0:
                raise not_found("PERSONA_GENERATION_JOB_NOT_FOUND", "Persona generation job not found")
        return self.get_persona_generation_job(record_id)

    def list_creator_personas(self) -> list[CreatorPersonaRecord]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM creator_personas ORDER BY created_at DESC").fetchall()
        return [self._row_to_creator_persona_record(row) for row in rows]

    def get_creator_persona(self, record_id: str) -> CreatorPersonaRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM creator_personas WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            raise not_found("CREATOR_PERSONA_NOT_FOUND", "Creator persona not found")
        return self._row_to_creator_persona_record(row)

    def create_creator_persona_records(
        self,
        *,
        personas: list[dict[str, Any]],
        provider: str,
        model_name: str,
    ) -> list[CreatorPersonaRecord]:
        now = utc_now()
        created_ids: list[str] = []
        with self._connect() as connection:
            for persona in personas:
                record_id = uuid4().hex
                connection.execute(
                    """
                    INSERT INTO creator_personas (
                        id, status, provider, model_name, creator_persona,
                        source_script_ids, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record_id,
                        "ready",
                        provider,
                        model_name,
                        _dump(persona),
                        _dump([]),
                        now,
                        now,
                    ),
                )
                created_ids.append(record_id)
        return [self.get_creator_persona(record_id) for record_id in created_ids]

    def update_creator_persona(
        self,
        record_id: str,
        *,
        creator_persona: dict[str, Any],
        provider: str | None = None,
        model_name: str | None = None,
    ) -> CreatorPersonaRecord:
        assignments = [
            "creator_persona = ?",
            "updated_at = ?",
        ]
        values: list[Any] = [_dump(creator_persona), utc_now()]
        if provider is not None:
            assignments.append("provider = ?")
            values.append(provider)
        if model_name is not None:
            assignments.append("model_name = ?")
            values.append(model_name)
        values.append(record_id)
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE creator_personas SET {', '.join(assignments)} WHERE id = ?",
                tuple(values),
            )
            if cursor.rowcount == 0:
                raise not_found("CREATOR_PERSONA_NOT_FOUND", "Creator persona not found")
        return self.get_creator_persona(record_id)

    def delete_creator_persona(self, record_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM creator_personas WHERE id = ?", (record_id,))
            if cursor.rowcount == 0:
                raise not_found("CREATOR_PERSONA_NOT_FOUND", "Creator persona not found")

    def mark_script_generation_job(
        self,
        record_id: str,
        status: ScriptGenerationJobStatus,
        error_message: str | None = None,
    ) -> ScriptGenerationJobRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE script_generation_jobs
                SET status = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (status.value, error_message, utc_now(), record_id),
            )
            if cursor.rowcount == 0:
                raise not_found("SCRIPT_GENERATION_JOB_NOT_FOUND", "Script generation job not found")
        return self.get_script_generation_job(record_id)

    def finish_script_generation_job(
        self,
        record_id: str,
        *,
        status: ScriptGenerationJobStatus,
        script_ids: list[str] | None = None,
        error_message: str | None = None,
    ) -> ScriptGenerationJobRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT script_ids FROM script_generation_jobs WHERE id = ?",
                (record_id,),
            ).fetchone()
            if row is None:
                raise not_found("SCRIPT_GENERATION_JOB_NOT_FOUND", "Script generation job not found")
            final_script_ids = list(dict.fromkeys(
                script_ids if script_ids is not None else (_loads(row["script_ids"]) or [])
            ))
            cursor = connection.execute(
                """
                UPDATE script_generation_jobs
                SET status = ?,
                    completed_count = ?,
                    script_ids = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE id = ?
                  AND status IN (?, ?)
                """,
                (
                    status.value,
                    len(final_script_ids),
                    _dump(final_script_ids),
                    error_message,
                    utc_now(),
                    record_id,
                    ScriptGenerationJobStatus.QUEUED.value,
                    ScriptGenerationJobStatus.GENERATING.value,
                ),
            )
            if cursor.rowcount == 0:
                return self.get_script_generation_job(record_id)
        return self.get_script_generation_job(record_id)

    def list_scripts(self) -> list[ScriptRecord]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM scripts ORDER BY created_at DESC").fetchall()
        return [self._row_to_script_record(row) for row in rows]

    def get_script(self, record_id: str) -> ScriptRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM scripts WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            raise not_found("SCRIPT_NOT_FOUND", "Script record not found")
        return self._row_to_script_record(row)

    def delete_script(self, record_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM script_model_runs WHERE script_id = ?", (record_id,))
            cursor = connection.execute("DELETE FROM scripts WHERE id = ?", (record_id,))
            if cursor.rowcount == 0:
                raise not_found("SCRIPT_NOT_FOUND", "Script record not found")

    def replace_script_content(
        self,
        *,
        record_id: str,
        item: ScriptAgentItem,
        revision: dict[str, Any],
    ) -> ScriptRecord:
        existing = self.get_script(record_id)
        history = [*existing.revision_history, revision]
        payload = item.model_dump(mode="json")
        payload["creator_persona"] = _normalize_creator_persona_for_storage(
            payload.get("creator_persona"),
            payload.get("topic_plan") or {},
            payload.get("script") or {},
            seed=record_id,
        )
        _sync_script_payload_to_creator_persona(payload)
        payload["video_prompt"] = _normalize_video_prompt_for_storage(
            payload.get("video_prompt"),
            payload.get("script") or {},
            payload.get("storyboard") or [],
            payload.get("production_asset_plan") or [],
            payload.get("creator_persona"),
        )
        return self._update_script(
            record_id,
            {
                "status": ScriptStatus.READY.value,
                "source_breakdown_ids": payload.get("source_breakdown_ids", existing.source_breakdown_ids),
                "topic_plan": payload["topic_plan"],
                "script": payload["script"],
                "storyboard": payload["storyboard"],
                "creator_persona": payload["creator_persona"],
                "video_prompt": payload["video_prompt"],
                "production_asset_plan": payload.get("production_asset_plan", existing.production_asset_plan),
                "risk_check": payload["risk_check"],
                "source_component_summary": payload.get("source_component_summary", existing.source_component_summary),
                "revision_history": history,
                "error_message": None,
            },
        )

    def mark_script_status(
        self,
        record_id: str,
        status: ScriptStatus,
        error_message: str | None = None,
    ) -> ScriptRecord:
        return self._update_script(record_id, {"status": status.value, "error_message": error_message})

    def create_director_plan(
        self,
        *,
        script_id: str,
        output: DirectorAgentOutput,
        provider: str,
        model_name: str,
        prompt_version: str,
    ) -> DirectorPlanRecord:
        self.get_script(script_id)
        now = utc_now()
        record_id = uuid4().hex
        payload = output.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO director_plans (
                    id, script_id, status, provider, model_name, prompt_version,
                    metadata, timeline, asset_resolution, tool_dispatches,
                    validation_summary, error_message, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    script_id,
                    DirectorPlanStatus.READY.value,
                    provider,
                    model_name,
                    prompt_version,
                    _dump(payload["metadata"]),
                    _dump(payload["timeline"]),
                    _dump(payload.get("asset_resolution", [])),
                    _dump(payload["tool_dispatches"]),
                    _dump(payload["validation_summary"]),
                    None,
                    now,
                    now,
                ),
            )
        return self.get_director_plan(record_id)

    def create_director_generation_job(self, request: DirectorPlanRequest) -> DirectorGenerationJobRecord:
        self.get_script(request.script_id)
        now = utc_now()
        record_id = uuid4().hex
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO director_generation_jobs (
                    id, status, script_id, director_plan_id, error_message, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    DirectorGenerationJobStatus.QUEUED.value,
                    request.script_id,
                    None,
                    None,
                    now,
                    now,
                ),
            )
        return self.get_director_generation_job(record_id)

    def list_director_generation_jobs(
        self,
        *,
        script_id: str | None = None,
        include_succeeded: bool = False,
    ) -> list[DirectorGenerationJobRecord]:
        clauses: list[str] = []
        values: list[Any] = []
        if script_id:
            clauses.append("script_id = ?")
            values.append(script_id)
        if not include_succeeded:
            clauses.append("status NOT IN (?, ?)")
            values.extend([DirectorGenerationJobStatus.SUCCEEDED.value, DirectorGenerationJobStatus.CANCELED.value])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM director_generation_jobs {where} ORDER BY created_at DESC",
                tuple(values),
            ).fetchall()
        return [self._row_to_director_generation_job_record(row) for row in rows]

    def get_director_generation_job(self, record_id: str) -> DirectorGenerationJobRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM director_generation_jobs WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            raise not_found("DIRECTOR_GENERATION_JOB_NOT_FOUND", "Director generation job not found")
        return self._row_to_director_generation_job_record(row)

    def cancel_director_generation_job(self, record_id: str, error_message: str | None = None) -> DirectorGenerationJobRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE director_generation_jobs
                SET status = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE id = ?
                  AND status IN (?, ?)
                """,
                (
                    DirectorGenerationJobStatus.CANCELED.value,
                    error_message,
                    utc_now(),
                    record_id,
                    DirectorGenerationJobStatus.QUEUED.value,
                    DirectorGenerationJobStatus.GENERATING.value,
                ),
            )
            if cursor.rowcount == 0:
                row = connection.execute("SELECT * FROM director_generation_jobs WHERE id = ?", (record_id,)).fetchone()
                if row is None:
                    raise not_found("DIRECTOR_GENERATION_JOB_NOT_FOUND", "Director generation job not found")
        return self.get_director_generation_job(record_id)

    def recover_stale_director_generation_jobs(self, max_age_seconds: int) -> list[DirectorGenerationJobRecord]:
        if max_age_seconds <= 0:
            threshold = datetime.now(UTC)
        else:
            threshold = datetime.now(UTC) - timedelta(seconds=max_age_seconds)
        recovered_ids: list[str] = []
        message = "Director generation job recovered after backend restart or stale worker timeout."
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM director_generation_jobs
                WHERE status = ?
                """,
                (DirectorGenerationJobStatus.GENERATING.value,),
            ).fetchall()
            for row in rows:
                updated_at = _parse_utc_datetime(str(row["updated_at"]))
                if updated_at > threshold:
                    continue
                connection.execute(
                    """
                    UPDATE director_generation_jobs
                    SET status = ?,
                        error_message = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        DirectorGenerationJobStatus.FAILED.value,
                        message,
                        utc_now(),
                        row["id"],
                    ),
                )
                recovered_ids.append(row["id"])
        return [self.get_director_generation_job(record_id) for record_id in recovered_ids]

    def mark_director_generation_job(
        self,
        record_id: str,
        status: DirectorGenerationJobStatus,
        error_message: str | None = None,
    ) -> DirectorGenerationJobRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE director_generation_jobs
                SET status = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (status.value, error_message, utc_now(), record_id),
            )
            if cursor.rowcount == 0:
                raise not_found("DIRECTOR_GENERATION_JOB_NOT_FOUND", "Director generation job not found")
        return self.get_director_generation_job(record_id)

    def finish_director_generation_job(
        self,
        record_id: str,
        *,
        status: DirectorGenerationJobStatus,
        director_plan_id: str | None = None,
        error_message: str | None = None,
    ) -> DirectorGenerationJobRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE director_generation_jobs
                SET status = ?,
                    director_plan_id = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE id = ?
                  AND status != ?
                """,
                (status.value, director_plan_id, error_message, utc_now(), record_id, DirectorGenerationJobStatus.CANCELED.value),
            )
            if cursor.rowcount == 0:
                return self.get_director_generation_job(record_id)
        return self.get_director_generation_job(record_id)

    def list_director_plans(self, script_id: str | None = None) -> list[DirectorPlanRecord]:
        with self._connect() as connection:
            if script_id:
                rows = connection.execute(
                    "SELECT * FROM director_plans WHERE script_id = ? ORDER BY created_at DESC",
                    (script_id,),
                ).fetchall()
            else:
                rows = connection.execute("SELECT * FROM director_plans ORDER BY created_at DESC").fetchall()
        return [self._row_to_director_plan_record(row) for row in rows]

    def get_director_plan(self, record_id: str) -> DirectorPlanRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM director_plans WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            raise not_found("DIRECTOR_PLAN_NOT_FOUND", "Director plan record not found")
        return self._row_to_director_plan_record(row)

    def delete_director_plan(self, record_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM director_render_artifacts WHERE director_plan_id = ?", (record_id,))
            connection.execute("DELETE FROM director_render_usage_records WHERE director_plan_id = ?", (record_id,))
            connection.execute("DELETE FROM director_publish_records WHERE director_plan_id = ?", (record_id,))
            connection.execute("DELETE FROM director_render_jobs WHERE director_plan_id = ?", (record_id,))
            connection.execute("DELETE FROM manual_factory_assets WHERE director_plan_id = ?", (record_id,))
            connection.execute("DELETE FROM director_plan_asset_bindings WHERE director_plan_id = ?", (record_id,))
            cursor = connection.execute("DELETE FROM director_plans WHERE id = ?", (record_id,))
            if cursor.rowcount == 0:
                raise not_found("DIRECTOR_PLAN_NOT_FOUND", "Director plan record not found")

    def create_manual_factory_asset(
        self,
        *,
        director_plan_id: str,
        clip_id: str,
        source_reference_id: str,
        asset_role: str,
        original_filename: str,
        stored_asset_url: str,
        mime_type: str,
        file_size_bytes: int,
        duration_sec: float,
        width: int,
        height: int,
        validation_status: str = "validated",
        review_status: str = "pending_review",
        review_notes: str = "",
        semantic_review_status: str = "pending_review",
        semantic_review_notes: str = "",
        semantic_review_method: str = "human_prompt_match_v1",
        semantic_review_reviewer: str = "",
    ) -> ManualFactoryAssetRecord:
        plan = self.get_director_plan(director_plan_id)
        now = utc_now()
        record_id = uuid4().hex
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO manual_factory_assets (
                    id, director_plan_id, script_id, clip_id, source_reference_id,
                    asset_role, original_filename, stored_asset_url, mime_type,
                    file_size_bytes, duration_sec, width, height, validation_status,
                    review_status, review_notes, reviewed_at, semantic_review_status,
                    semantic_review_notes, semantic_review_method, semantic_review_reviewer,
                    semantic_reviewed_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(director_plan_id, clip_id) DO UPDATE SET
                    id = excluded.id,
                    script_id = excluded.script_id,
                    source_reference_id = excluded.source_reference_id,
                    asset_role = excluded.asset_role,
                    original_filename = excluded.original_filename,
                    stored_asset_url = excluded.stored_asset_url,
                    mime_type = excluded.mime_type,
                    file_size_bytes = excluded.file_size_bytes,
                    duration_sec = excluded.duration_sec,
                    width = excluded.width,
                    height = excluded.height,
                    validation_status = excluded.validation_status,
                    review_status = excluded.review_status,
                    review_notes = excluded.review_notes,
                    reviewed_at = excluded.reviewed_at,
                    semantic_review_status = excluded.semantic_review_status,
                    semantic_review_notes = excluded.semantic_review_notes,
                    semantic_review_method = excluded.semantic_review_method,
                    semantic_review_reviewer = excluded.semantic_review_reviewer,
                    semantic_reviewed_at = excluded.semantic_reviewed_at,
                    updated_at = excluded.updated_at
                """,
                (
                    record_id,
                    director_plan_id,
                    plan.script_id,
                    clip_id,
                    source_reference_id,
                    asset_role,
                    original_filename,
                    stored_asset_url,
                    mime_type,
                    file_size_bytes,
                    duration_sec,
                    width,
                    height,
                    validation_status,
                    review_status,
                    review_notes,
                    None,
                    semantic_review_status,
                    semantic_review_notes,
                    semantic_review_method,
                    semantic_review_reviewer,
                    None,
                    now,
                    now,
                ),
            )
        return self.get_manual_factory_asset(record_id)

    def get_manual_factory_asset(self, record_id: str) -> ManualFactoryAssetRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM manual_factory_assets WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            raise not_found("MANUAL_FACTORY_ASSET_NOT_FOUND", "Manual factory asset record not found")
        return self._row_to_manual_factory_asset_record(row)

    def list_manual_factory_assets(self, director_plan_id: str) -> list[ManualFactoryAssetRecord]:
        self.get_director_plan(director_plan_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM manual_factory_assets
                WHERE director_plan_id = ?
                ORDER BY updated_at DESC
                """,
                (director_plan_id,),
            ).fetchall()
        return [self._row_to_manual_factory_asset_record(row) for row in rows]

    def update_manual_factory_asset_review(
        self,
        record_id: str,
        *,
        review_status: str,
        review_notes: str = "",
    ) -> ManualFactoryAssetRecord:
        reviewed_at = None if review_status == "pending_review" else utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE manual_factory_assets
                SET review_status = ?,
                    review_notes = ?,
                    reviewed_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (review_status, review_notes, reviewed_at, utc_now(), record_id),
            )
            if cursor.rowcount == 0:
                raise not_found("MANUAL_FACTORY_ASSET_NOT_FOUND", "Manual factory asset record not found")
        return self.get_manual_factory_asset(record_id)

    def update_manual_factory_asset_semantic_review(
        self,
        record_id: str,
        *,
        status: str,
        notes: str = "",
        method: str = "human_prompt_match_v1",
        reviewer: str = "",
    ) -> ManualFactoryAssetRecord:
        reviewed_at = None if status == "pending_review" else utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE manual_factory_assets
                SET semantic_review_status = ?,
                    semantic_review_notes = ?,
                    semantic_review_method = ?,
                    semantic_review_reviewer = ?,
                    semantic_reviewed_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (status, notes, method, reviewer, reviewed_at, utc_now(), record_id),
            )
            if cursor.rowcount == 0:
                raise not_found("MANUAL_FACTORY_ASSET_NOT_FOUND", "Manual factory asset record not found")
        return self.get_manual_factory_asset(record_id)

    def create_moras_asset(
        self,
        *,
        asset_type: str,
        moras_asset_category: str,
        title: str,
        original_filename: str,
        stored_asset_url: str,
        mime_type: str,
        file_size_bytes: int,
        duration_sec: float,
        width: int,
        height: int,
        validation_status: str = "uploaded",
        review_status: str = "pending_review",
        review_notes: str = "",
        semantic_review_status: str = "pending_review",
        semantic_review_notes: str = "",
        semantic_review_method: str = "human_prompt_match_v1",
        semantic_review_reviewer: str = "",
    ) -> MorasAssetLibraryRecord:
        now = utc_now()
        record_id = uuid4().hex
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO moras_asset_library (
                    id, asset_type, moras_asset_category, title, original_filename,
                    stored_asset_url, mime_type, file_size_bytes, duration_sec,
                    width, height, validation_status, review_status, review_notes,
                    reviewed_at, semantic_review_status, semantic_review_notes,
                    semantic_review_method, semantic_review_reviewer, semantic_reviewed_at,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    asset_type,
                    moras_asset_category,
                    title,
                    original_filename,
                    stored_asset_url,
                    mime_type,
                    file_size_bytes,
                    duration_sec,
                    width,
                    height,
                    validation_status,
                    review_status,
                    review_notes,
                    None,
                    semantic_review_status,
                    semantic_review_notes,
                    semantic_review_method,
                    semantic_review_reviewer,
                    None,
                    now,
                    now,
                ),
            )
        return self.get_moras_asset(record_id)

    def update_moras_asset_semantic_review(
        self,
        record_id: str,
        *,
        status: str,
        notes: str = "",
        method: str = "human_prompt_match_v1",
        reviewer: str = "",
    ) -> MorasAssetLibraryRecord:
        reviewed_at = None if status == "pending_review" else utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE moras_asset_library
                SET semantic_review_status = ?,
                    semantic_review_notes = ?,
                    semantic_review_method = ?,
                    semantic_review_reviewer = ?,
                    semantic_reviewed_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (status, notes, method, reviewer, reviewed_at, utc_now(), record_id),
            )
            if cursor.rowcount == 0:
                raise not_found("MORAS_ASSET_NOT_FOUND", "Moras asset record not found")
        return self.get_moras_asset(record_id)

    def get_moras_asset(self, record_id: str) -> MorasAssetLibraryRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM moras_asset_library WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            raise not_found("MORAS_ASSET_NOT_FOUND", "Moras asset record not found")
        return self._row_to_moras_asset_record(row)

    def list_moras_assets(
        self,
        *,
        asset_type: str | None = None,
        moras_asset_category: str | None = None,
    ) -> list[MorasAssetLibraryRecord]:
        clauses: list[str] = []
        values: list[str] = []
        if asset_type:
            clauses.append("asset_type = ?")
            values.append(asset_type)
        if moras_asset_category:
            clauses.append("moras_asset_category = ?")
            values.append(moras_asset_category)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM moras_asset_library
                {where}
                ORDER BY updated_at DESC
                """,
                values,
            ).fetchall()
        return [self._row_to_moras_asset_record(row) for row in rows]

    def update_moras_asset_review(
        self,
        record_id: str,
        *,
        review_status: str,
        review_notes: str = "",
    ) -> MorasAssetLibraryRecord:
        reviewed_at = None if review_status == "pending_review" else utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE moras_asset_library
                SET review_status = ?,
                    review_notes = ?,
                    reviewed_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (review_status, review_notes, reviewed_at, utc_now(), record_id),
            )
            if cursor.rowcount == 0:
                raise not_found("MORAS_ASSET_NOT_FOUND", "Moras asset record not found")
        return self.get_moras_asset(record_id)

    def create_director_plan_asset_binding(
        self,
        *,
        director_plan_id: str,
        asset_ref: str,
        library_asset_id: str,
    ) -> DirectorPlanAssetBindingRecord:
        plan = self.get_director_plan(director_plan_id)
        library_asset = self.get_moras_asset(library_asset_id)
        asset_resolution = _find_asset_resolution(plan.asset_resolution, asset_ref)
        if asset_resolution is None:
            raise not_found("DIRECTOR_ASSET_REF_NOT_FOUND", "Director plan asset reference not found")
        source_plan_id = str(asset_resolution.get("source_plan_id") or asset_resolution.get("sourcePlanId") or asset_ref)
        now = utc_now()
        record_id = uuid4().hex
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO director_plan_asset_bindings (
                    id, director_plan_id, script_id, asset_ref, source_plan_id,
                    library_asset_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(director_plan_id, asset_ref) DO UPDATE SET
                    id = excluded.id,
                    script_id = excluded.script_id,
                    source_plan_id = excluded.source_plan_id,
                    library_asset_id = excluded.library_asset_id,
                    updated_at = excluded.updated_at
                """,
                (
                    record_id,
                    director_plan_id,
                    plan.script_id,
                    asset_ref,
                    source_plan_id,
                    library_asset.id,
                    now,
                    now,
                ),
            )
        return self.get_director_plan_asset_binding(record_id)

    def get_director_plan_asset_binding(self, record_id: str) -> DirectorPlanAssetBindingRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM director_plan_asset_bindings WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            raise not_found("DIRECTOR_ASSET_BINDING_NOT_FOUND", "Director plan asset binding not found")
        return self._row_to_director_plan_asset_binding_record(row)

    def list_director_plan_asset_bindings(self, director_plan_id: str) -> list[DirectorPlanAssetBindingRecord]:
        self.get_director_plan(director_plan_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM director_plan_asset_bindings
                WHERE director_plan_id = ?
                ORDER BY updated_at DESC
                """,
                (director_plan_id,),
            ).fetchall()
        return [self._row_to_director_plan_asset_binding_record(row) for row in rows]

    def create_director_render_job(
        self,
        *,
        director_plan_id: str,
        status: str | DirectorRenderJobStatus,
        readiness_summary: dict[str, Any] | None = None,
        output_asset_url: str | None = None,
        output_filename: str | None = None,
        output_audio_url: str | None = None,
        output_subtitle_url: str | None = None,
        file_size_bytes: int = 0,
        duration_sec: float = 0,
        width: int = 0,
        height: int = 0,
        error_message: str | None = None,
        qa_summary: dict[str, Any] | None = None,
    ) -> DirectorRenderJobRecord:
        plan = self.get_director_plan(director_plan_id)
        now = utc_now()
        record_id = uuid4().hex
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO director_render_jobs (
                    id, director_plan_id, script_id, status, output_asset_url,
                    output_filename, output_audio_url, output_subtitle_url,
                    file_size_bytes, duration_sec, width, height,
                    readiness_summary, qa_summary, qa_review_status, qa_review_notes,
                    qa_reviewed_at, error_message, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    director_plan_id,
                    plan.script_id,
                    _status_value(status),
                    output_asset_url,
                    output_filename,
                    output_audio_url,
                    output_subtitle_url,
                    file_size_bytes,
                    duration_sec,
                    width,
                    height,
                    _dump(readiness_summary or {}),
                    _dump(qa_summary or {}),
                    "pending_review",
                    "",
                    None,
                    error_message,
                    now,
                    now,
                ),
            )
        return self.get_director_render_job(record_id)

    def mark_director_render_job(
        self,
        record_id: str,
        status: str | DirectorRenderJobStatus,
        error_message: str | None = None,
    ) -> DirectorRenderJobRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE director_render_jobs
                SET status = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (_status_value(status), error_message, utc_now(), record_id),
            )
            if cursor.rowcount == 0:
                raise not_found("DIRECTOR_RENDER_JOB_NOT_FOUND", "Director render job not found")
        return self.get_director_render_job(record_id)

    def finish_director_render_job(
        self,
        record_id: str,
        *,
        status: str | DirectorRenderJobStatus,
        readiness_summary: dict[str, Any] | None = None,
        output_asset_url: str | None = None,
        output_filename: str | None = None,
        output_audio_url: str | None = None,
        output_subtitle_url: str | None = None,
        file_size_bytes: int = 0,
        duration_sec: float = 0,
        width: int = 0,
        height: int = 0,
        qa_summary: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> DirectorRenderJobRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE director_render_jobs
                SET status = ?,
                    output_asset_url = ?,
                    output_filename = ?,
                    output_audio_url = ?,
                    output_subtitle_url = ?,
                    file_size_bytes = ?,
                    duration_sec = ?,
                    width = ?,
                    height = ?,
                    readiness_summary = ?,
                    qa_summary = ?,
                    qa_review_status = ?,
                    qa_review_notes = ?,
                    qa_reviewed_at = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    _status_value(status),
                    output_asset_url,
                    output_filename,
                    output_audio_url,
                    output_subtitle_url,
                    file_size_bytes,
                    duration_sec,
                    width,
                    height,
                    _dump(readiness_summary or {}),
                    _dump(qa_summary or {}),
                    "pending_review",
                    "",
                    None,
                    error_message,
                    utc_now(),
                    record_id,
                ),
            )
            if cursor.rowcount == 0:
                raise not_found("DIRECTOR_RENDER_JOB_NOT_FOUND", "Director render job not found")
        return self.get_director_render_job(record_id)

    def recover_stale_director_render_jobs(self, max_age_seconds: int) -> list[DirectorRenderJobRecord]:
        if max_age_seconds <= 0:
            threshold = datetime.now(UTC)
        else:
            threshold = datetime.now(UTC) - timedelta(seconds=max_age_seconds)
        recovered_ids: list[str] = []
        queued_message = "Director render job recovered after backend restart before worker execution."
        rendering_message = "Director render job recovered after backend restart or stale worker timeout."
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM director_render_jobs
                WHERE status IN (?, ?)
                """,
                (DirectorRenderJobStatus.QUEUED.value, DirectorRenderJobStatus.RENDERING.value),
            ).fetchall()
            for row in rows:
                status = str(row["status"])
                if status == DirectorRenderJobStatus.RENDERING.value:
                    updated_at = _parse_utc_datetime(str(row["updated_at"]))
                    if updated_at > threshold:
                        continue
                connection.execute(
                    """
                    UPDATE director_render_jobs
                    SET status = ?,
                        output_asset_url = NULL,
                        output_filename = NULL,
                        output_audio_url = NULL,
                        output_subtitle_url = NULL,
                        file_size_bytes = 0,
                        duration_sec = 0,
                        width = 0,
                        height = 0,
                        qa_summary = ?,
                        qa_review_status = ?,
                        qa_review_notes = ?,
                        qa_reviewed_at = NULL,
                        error_message = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        DirectorRenderJobStatus.FAILED.value,
                        _dump({}),
                        "pending_review",
                        "",
                        queued_message if status == DirectorRenderJobStatus.QUEUED.value else rendering_message,
                        utc_now(),
                        row["id"],
                    ),
                )
                recovered_ids.append(row["id"])
        return [self.get_director_render_job(record_id) for record_id in recovered_ids]

    def get_director_render_job(self, record_id: str) -> DirectorRenderJobRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM director_render_jobs WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            raise not_found("DIRECTOR_RENDER_JOB_NOT_FOUND", "Director render job not found")
        return self._row_to_director_render_job_record(row)

    def list_director_render_jobs(self, director_plan_id: str) -> list[DirectorRenderJobRecord]:
        self.get_director_plan(director_plan_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM director_render_jobs
                WHERE director_plan_id = ?
                ORDER BY created_at DESC
                """,
                (director_plan_id,),
            ).fetchall()
        return [self._row_to_director_render_job_record(row) for row in rows]

    def replace_director_render_artifacts(
        self,
        render_job_id: str,
        artifacts: list[dict[str, Any]],
        *,
        retention_expires_at: str | None,
    ) -> list[DirectorRenderArtifactRecord]:
        render_job = self.get_director_render_job(render_job_id)
        now = utc_now()
        with self._connect() as connection:
            connection.execute("DELETE FROM director_render_artifacts WHERE render_job_id = ?", (render_job_id,))
            for artifact in artifacts:
                connection.execute(
                    """
                    INSERT INTO director_render_artifacts (
                        id, render_job_id, director_plan_id, script_id, artifact_type,
                        asset_url, filename, mime_type, file_size_bytes, duration_sec,
                        width, height, storage_status, retention_expires_at,
                        deleted_at, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid4().hex,
                        render_job.id,
                        render_job.director_plan_id,
                        render_job.script_id,
                        str(artifact.get("artifact_type") or ""),
                        str(artifact.get("asset_url") or ""),
                        str(artifact.get("filename") or ""),
                        str(artifact.get("mime_type") or ""),
                        int(artifact.get("file_size_bytes") or 0),
                        float(artifact.get("duration_sec") or 0),
                        int(artifact.get("width") or 0),
                        int(artifact.get("height") or 0),
                        str(artifact.get("storage_status") or "active"),
                        retention_expires_at,
                        artifact.get("deleted_at"),
                        now,
                        now,
                    ),
                )
        return self.list_director_render_artifacts(render_job_id)

    def get_director_render_artifact(self, artifact_id: str) -> DirectorRenderArtifactRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM director_render_artifacts WHERE id = ?", (artifact_id,)).fetchone()
        if row is None:
            raise not_found("DIRECTOR_RENDER_ARTIFACT_NOT_FOUND", "Director render artifact not found")
        return self._row_to_director_render_artifact_record(row)

    def list_director_render_artifacts(self, render_job_id: str) -> list[DirectorRenderArtifactRecord]:
        self.get_director_render_job(render_job_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM director_render_artifacts
                WHERE render_job_id = ?
                ORDER BY created_at ASC
                """,
                (render_job_id,),
            ).fetchall()
        return [self._row_to_director_render_artifact_record(row) for row in rows]

    def update_director_render_artifact_lifecycle(
        self,
        artifact_id: str,
        *,
        storage_status: str,
        deleted_at: str | None = None,
    ) -> DirectorRenderArtifactRecord:
        self.get_director_render_artifact(artifact_id)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE director_render_artifacts
                SET storage_status = ?, deleted_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (storage_status, deleted_at, utc_now(), artifact_id),
            )
        return self.get_director_render_artifact(artifact_id)

    def replace_director_render_usage_record(
        self,
        render_job_id: str,
        usage: dict[str, Any],
    ) -> DirectorRenderUsageRecord:
        render_job = self.get_director_render_job(render_job_id)
        now = utc_now()
        with self._connect() as connection:
            connection.execute("DELETE FROM director_render_usage_records WHERE render_job_id = ?", (render_job_id,))
            connection.execute(
                """
                INSERT INTO director_render_usage_records (
                    id, render_job_id, director_plan_id, script_id,
                    input_clip_count, output_duration_sec, output_bytes,
                    subtitle_cue_count, tts_character_count,
                    render_engine, audio_engine, caption_engine,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid4().hex,
                    render_job.id,
                    render_job.director_plan_id,
                    render_job.script_id,
                    int(usage.get("input_clip_count") or 0),
                    float(usage.get("output_duration_sec") or 0),
                    int(usage.get("output_bytes") or 0),
                    int(usage.get("subtitle_cue_count") or 0),
                    int(usage.get("tts_character_count") or 0),
                    str(usage.get("render_engine") or "unknown"),
                    str(usage.get("audio_engine") or "unknown"),
                    str(usage.get("caption_engine") or "unknown"),
                    now,
                    now,
                ),
            )
        record = self.get_director_render_usage_record(render_job_id)
        if record is None:
            raise not_found("DIRECTOR_RENDER_USAGE_NOT_FOUND", "Director render usage record not found")
        return record

    def get_director_render_usage_record(self, render_job_id: str) -> DirectorRenderUsageRecord | None:
        self.get_director_render_job(render_job_id)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM director_render_usage_records
                WHERE render_job_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (render_job_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_director_render_usage_record(row)

    def update_director_render_job_qa_review(
        self,
        record_id: str,
        *,
        qa_review_status: str,
        qa_review_notes: str = "",
    ) -> DirectorRenderJobRecord:
        record = self.get_director_render_job(record_id)
        reviewed_at = None if qa_review_status == "pending_review" else utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE director_render_jobs
                SET qa_review_status = ?,
                    qa_review_notes = ?,
                    qa_reviewed_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (qa_review_status, qa_review_notes, reviewed_at, utc_now(), record.id),
            )
        return self.get_director_render_job(record_id)

    def create_director_publish_record(
        self,
        *,
        director_plan_id: str,
        render_job_id: str,
        channel: str,
        publish_status: str,
        caption: str = "",
        scheduled_at: str | None = None,
        published_url: str | None = None,
        notes: str = "",
    ) -> DirectorPublishRecord:
        plan = self.get_director_plan(director_plan_id)
        now = utc_now()
        record_id = uuid4().hex
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO director_publish_records (
                    id, director_plan_id, script_id, render_job_id, channel,
                    publish_status, caption, scheduled_at, published_url, notes,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    director_plan_id,
                    plan.script_id,
                    render_job_id,
                    channel,
                    publish_status,
                    caption,
                    scheduled_at,
                    published_url,
                    notes,
                    now,
                    now,
                ),
            )
        return self.get_director_publish_record(record_id)

    def get_director_publish_record(self, record_id: str) -> DirectorPublishRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM director_publish_records WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            raise not_found("DIRECTOR_PUBLISH_RECORD_NOT_FOUND", "Director publish record not found")
        return self._row_to_director_publish_record(row)

    def list_director_publish_records(self, director_plan_id: str) -> list[DirectorPublishRecord]:
        self.get_director_plan(director_plan_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM director_publish_records
                WHERE director_plan_id = ?
                ORDER BY created_at DESC
                """,
                (director_plan_id,),
            ).fetchall()
        return [self._row_to_director_publish_record(row) for row in rows]

    def create_script_model_run(
        self,
        *,
        script_id: str | None,
        status: str,
        model_name: str,
        prompt_version: str,
        request: dict[str, Any],
    ) -> str:
        now = utc_now()
        model_run_id = uuid4().hex
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO script_model_runs (
                    id, script_id, status, model_name, prompt_version,
                    request_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (model_run_id, script_id, status, model_name, prompt_version, _dump(request), now, now),
            )
        return model_run_id

    def finish_script_model_run(
        self,
        model_run_id: str,
        status: str,
        raw_response_text: str | None = None,
        parsed_output: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE script_model_runs
                SET status = ?,
                    raw_response_text = ?,
                    parsed_output_json = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (status, raw_response_text, _dump(parsed_output) if parsed_output is not None else None, error_message, utc_now(), model_run_id),
            )

    def _update(self, record_id: str, updates: dict[str, Any]) -> BreakdownRecord:
        columns: list[str] = []
        values: list[Any] = []
        for key, value in updates.items():
            if key in JSON_COLUMNS:
                value = _dump(value)
            columns.append(f"{key} = ?")
            values.append(value)
        columns.append("updated_at = ?")
        values.append(utc_now())
        values.append(record_id)

        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE breakdowns SET {', '.join(columns)} WHERE id = ?",
                values,
            )
            if cursor.rowcount == 0:
                raise not_found("BREAKDOWN_NOT_FOUND", "Breakdown record not found")
        return self.get(record_id)

    def _update_script(self, record_id: str, updates: dict[str, Any]) -> ScriptRecord:
        columns: list[str] = []
        values: list[Any] = []
        for key, value in updates.items():
            if key in SCRIPT_JSON_COLUMNS:
                value = _dump(value)
            columns.append(f"{key} = ?")
            values.append(value)
        columns.append("updated_at = ?")
        values.append(utc_now())
        values.append(record_id)

        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE scripts SET {', '.join(columns)} WHERE id = ?",
                values,
            )
            if cursor.rowcount == 0:
                raise not_found("SCRIPT_NOT_FOUND", "Script record not found")
        return self.get_script(record_id)

    def _init_db(self) -> None:
        with self.lock, self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS breakdowns (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    input_video_url TEXT,
                    input_video_key TEXT,
                    error_message TEXT,
                    source_video TEXT,
                    classification TEXT,
                    decomposition TEXT,
                    structure_protocol TEXT,
                    script_agent_bridge TEXT,
                    reference_storyboard TEXT NOT NULL DEFAULT '[]',
                    raw_response_text TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(connection, "breakdowns", "input_video_url", "TEXT")
            self._ensure_column(connection, "breakdowns", "input_video_key", "TEXT")
            self._ensure_column(connection, "breakdowns", "reference_storyboard", "TEXT NOT NULL DEFAULT '[]'")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_breakdowns_input_video_key ON breakdowns(input_video_key)")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS breakdown_model_runs (
                    id TEXT PRIMARY KEY,
                    breakdown_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    raw_response_text TEXT,
                    parsed_output_json TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (breakdown_id) REFERENCES breakdowns(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scripts (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    script_type TEXT NOT NULL,
                    source_breakdown_ids TEXT NOT NULL,
                    topic_plan TEXT NOT NULL,
                    script TEXT NOT NULL,
                    storyboard TEXT NOT NULL,
                    creator_persona TEXT NOT NULL DEFAULT '{}',
                    video_prompt TEXT NOT NULL,
                    production_asset_plan TEXT NOT NULL DEFAULT '[]',
                    risk_check TEXT NOT NULL,
                    source_component_summary TEXT NOT NULL,
                    revision_history TEXT NOT NULL,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(connection, "scripts", "creator_persona", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(connection, "scripts", "production_asset_plan", "TEXT NOT NULL DEFAULT '[]'")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS script_model_runs (
                    id TEXT PRIMARY KEY,
                    script_id TEXT,
                    status TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    raw_response_text TEXT,
                    parsed_output_json TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (script_id) REFERENCES scripts(id)
                )
                """
            )
            connection.execute(
                """
            CREATE TABLE IF NOT EXISTS script_generation_jobs (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                script_count INTEGER NOT NULL,
                script_type TEXT NOT NULL,
                source_breakdown_ids TEXT NOT NULL,
                persona_id TEXT,
                persona_hint TEXT NOT NULL DEFAULT '{}',
                completed_count INTEGER NOT NULL DEFAULT 0,
                script_ids TEXT NOT NULL DEFAULT '[]',
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
            )
            self._ensure_column(connection, "script_generation_jobs", "persona_id", "TEXT")
            self._ensure_column(connection, "script_generation_jobs", "persona_hint", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(connection, "script_generation_jobs", "completed_count", "INTEGER NOT NULL DEFAULT 0")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS persona_generation_jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    persona_count INTEGER NOT NULL,
                    topic_or_brand_context TEXT NOT NULL,
                    target_audience TEXT NOT NULL,
                    required_demographic TEXT,
                    completed_count INTEGER NOT NULL DEFAULT 0,
                    persona_ids TEXT NOT NULL DEFAULT '[]',
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(connection, "persona_generation_jobs", "completed_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(connection, "persona_generation_jobs", "persona_ids", "TEXT NOT NULL DEFAULT '[]'")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS creator_personas (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    creator_persona TEXT NOT NULL,
                    source_script_ids TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS director_plans (
                    id TEXT PRIMARY KEY,
                    script_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    timeline TEXT NOT NULL,
                    asset_resolution TEXT NOT NULL,
                    tool_dispatches TEXT NOT NULL,
                    validation_summary TEXT NOT NULL,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (script_id) REFERENCES scripts(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS director_generation_jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    script_id TEXT NOT NULL,
                    director_plan_id TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (script_id) REFERENCES scripts(id),
                    FOREIGN KEY (director_plan_id) REFERENCES director_plans(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS manual_factory_assets (
                    id TEXT PRIMARY KEY,
                    director_plan_id TEXT NOT NULL,
                    script_id TEXT NOT NULL,
                    clip_id TEXT NOT NULL,
                    source_reference_id TEXT NOT NULL,
                    asset_role TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    stored_asset_url TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    file_size_bytes INTEGER NOT NULL,
                    duration_sec REAL NOT NULL DEFAULT 0,
                    width INTEGER NOT NULL DEFAULT 0,
                    height INTEGER NOT NULL DEFAULT 0,
                    validation_status TEXT NOT NULL DEFAULT 'validated',
                    review_status TEXT NOT NULL DEFAULT 'pending_review',
                    review_notes TEXT NOT NULL DEFAULT '',
                    reviewed_at TEXT,
                    semantic_review_status TEXT NOT NULL DEFAULT 'pending_review',
                    semantic_review_notes TEXT NOT NULL DEFAULT '',
                    semantic_review_method TEXT NOT NULL DEFAULT 'human_prompt_match_v1',
                    semantic_review_reviewer TEXT NOT NULL DEFAULT '',
                    semantic_reviewed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (director_plan_id) REFERENCES director_plans(id),
                    FOREIGN KEY (script_id) REFERENCES scripts(id),
                    UNIQUE (director_plan_id, clip_id)
                )
                """
            )
            self._ensure_column(connection, "manual_factory_assets", "duration_sec", "REAL NOT NULL DEFAULT 0")
            self._ensure_column(connection, "manual_factory_assets", "width", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(connection, "manual_factory_assets", "height", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(connection, "manual_factory_assets", "validation_status", "TEXT NOT NULL DEFAULT 'validated'")
            self._ensure_column(connection, "manual_factory_assets", "review_status", "TEXT NOT NULL DEFAULT 'pending_review'")
            self._ensure_column(connection, "manual_factory_assets", "review_notes", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "manual_factory_assets", "reviewed_at", "TEXT")
            self._ensure_column(connection, "manual_factory_assets", "semantic_review_status", "TEXT NOT NULL DEFAULT 'pending_review'")
            self._ensure_column(connection, "manual_factory_assets", "semantic_review_notes", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "manual_factory_assets", "semantic_review_method", "TEXT NOT NULL DEFAULT 'human_prompt_match_v1'")
            self._ensure_column(connection, "manual_factory_assets", "semantic_review_reviewer", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "manual_factory_assets", "semantic_reviewed_at", "TEXT")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS moras_asset_library (
                    id TEXT PRIMARY KEY,
                    asset_type TEXT NOT NULL,
                    moras_asset_category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    stored_asset_url TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    file_size_bytes INTEGER NOT NULL,
                    duration_sec REAL NOT NULL DEFAULT 0,
                    width INTEGER NOT NULL DEFAULT 0,
                    height INTEGER NOT NULL DEFAULT 0,
                    validation_status TEXT NOT NULL DEFAULT 'uploaded',
                    review_status TEXT NOT NULL DEFAULT 'pending_review',
                    review_notes TEXT NOT NULL DEFAULT '',
                    reviewed_at TEXT,
                    semantic_review_status TEXT NOT NULL DEFAULT 'pending_review',
                    semantic_review_notes TEXT NOT NULL DEFAULT '',
                    semantic_review_method TEXT NOT NULL DEFAULT 'human_prompt_match_v1',
                    semantic_review_reviewer TEXT NOT NULL DEFAULT '',
                    semantic_reviewed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(connection, "moras_asset_library", "review_status", "TEXT NOT NULL DEFAULT 'pending_review'")
            self._ensure_column(connection, "moras_asset_library", "review_notes", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "moras_asset_library", "reviewed_at", "TEXT")
            self._ensure_column(connection, "moras_asset_library", "semantic_review_status", "TEXT NOT NULL DEFAULT 'pending_review'")
            self._ensure_column(connection, "moras_asset_library", "semantic_review_notes", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "moras_asset_library", "semantic_review_method", "TEXT NOT NULL DEFAULT 'human_prompt_match_v1'")
            self._ensure_column(connection, "moras_asset_library", "semantic_review_reviewer", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "moras_asset_library", "semantic_reviewed_at", "TEXT")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS director_plan_asset_bindings (
                    id TEXT PRIMARY KEY,
                    director_plan_id TEXT NOT NULL,
                    script_id TEXT NOT NULL,
                    asset_ref TEXT NOT NULL,
                    source_plan_id TEXT NOT NULL,
                    library_asset_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (director_plan_id) REFERENCES director_plans(id),
                    FOREIGN KEY (script_id) REFERENCES scripts(id),
                    FOREIGN KEY (library_asset_id) REFERENCES moras_asset_library(id),
                    UNIQUE (director_plan_id, asset_ref)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS director_render_jobs (
                    id TEXT PRIMARY KEY,
                    director_plan_id TEXT NOT NULL,
                    script_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    output_asset_url TEXT,
                    output_filename TEXT,
                    output_audio_url TEXT,
                    output_subtitle_url TEXT,
                    file_size_bytes INTEGER NOT NULL DEFAULT 0,
                    duration_sec REAL NOT NULL DEFAULT 0,
                    width INTEGER NOT NULL DEFAULT 0,
                    height INTEGER NOT NULL DEFAULT 0,
                    readiness_summary TEXT NOT NULL DEFAULT '{}',
                    qa_summary TEXT NOT NULL DEFAULT '{}',
                    qa_review_status TEXT NOT NULL DEFAULT 'pending_review',
                    qa_review_notes TEXT NOT NULL DEFAULT '',
                    qa_reviewed_at TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (director_plan_id) REFERENCES director_plans(id),
                    FOREIGN KEY (script_id) REFERENCES scripts(id)
                )
                """
            )
            self._ensure_column(connection, "director_render_jobs", "output_audio_url", "TEXT")
            self._ensure_column(connection, "director_render_jobs", "output_subtitle_url", "TEXT")
            self._ensure_column(connection, "director_render_jobs", "qa_summary", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(connection, "director_render_jobs", "qa_review_status", "TEXT NOT NULL DEFAULT 'pending_review'")
            self._ensure_column(connection, "director_render_jobs", "qa_review_notes", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "director_render_jobs", "qa_reviewed_at", "TEXT")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS director_render_artifacts (
                    id TEXT PRIMARY KEY,
                    render_job_id TEXT NOT NULL,
                    director_plan_id TEXT NOT NULL,
                    script_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    asset_url TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    file_size_bytes INTEGER NOT NULL DEFAULT 0,
                    duration_sec REAL NOT NULL DEFAULT 0,
                    width INTEGER NOT NULL DEFAULT 0,
                    height INTEGER NOT NULL DEFAULT 0,
                    storage_status TEXT NOT NULL DEFAULT 'active',
                    retention_expires_at TEXT,
                    deleted_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (render_job_id) REFERENCES director_render_jobs(id),
                    FOREIGN KEY (director_plan_id) REFERENCES director_plans(id),
                    FOREIGN KEY (script_id) REFERENCES scripts(id)
                )
                """
            )
            self._ensure_column(connection, "director_render_artifacts", "deleted_at", "TEXT")
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_director_render_artifacts_job
                ON director_render_artifacts(render_job_id, artifact_type)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS director_render_usage_records (
                    id TEXT PRIMARY KEY,
                    render_job_id TEXT NOT NULL,
                    director_plan_id TEXT NOT NULL,
                    script_id TEXT NOT NULL,
                    input_clip_count INTEGER NOT NULL DEFAULT 0,
                    output_duration_sec REAL NOT NULL DEFAULT 0,
                    output_bytes INTEGER NOT NULL DEFAULT 0,
                    subtitle_cue_count INTEGER NOT NULL DEFAULT 0,
                    tts_character_count INTEGER NOT NULL DEFAULT 0,
                    render_engine TEXT NOT NULL,
                    audio_engine TEXT NOT NULL,
                    caption_engine TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (render_job_id) REFERENCES director_render_jobs(id),
                    FOREIGN KEY (director_plan_id) REFERENCES director_plans(id),
                    FOREIGN KEY (script_id) REFERENCES scripts(id)
                )
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_director_render_usage_job
                ON director_render_usage_records(render_job_id)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS director_publish_records (
                    id TEXT PRIMARY KEY,
                    director_plan_id TEXT NOT NULL,
                    script_id TEXT NOT NULL,
                    render_job_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    publish_status TEXT NOT NULL,
                    caption TEXT NOT NULL DEFAULT '',
                    scheduled_at TEXT,
                    published_url TEXT,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (director_plan_id) REFERENCES director_plans(id),
                    FOREIGN KEY (script_id) REFERENCES scripts(id),
                    FOREIGN KEY (render_job_id) REFERENCES director_render_jobs(id)
                )
                """
            )
            self._backfill_script_creator_personas(connection)
            self._backfill_script_video_prompts(connection)

    def _backfill_script_video_prompts(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute("SELECT id, topic_plan, script, storyboard, creator_persona, video_prompt, production_asset_plan FROM scripts").fetchall()
        now = utc_now()
        for row in rows:
            topic_plan = _loads(row["topic_plan"]) or {}
            script = _loads(row["script"]) or {}
            storyboard = _loads(row["storyboard"]) or []
            persona = _normalize_creator_persona_for_storage(
                _loads(row["creator_persona"]),
                topic_plan,
                script,
                seed=row["id"],
            )
            payload = {"topic_plan": topic_plan, "script": script, "storyboard": storyboard, "creator_persona": persona}
            _sync_script_payload_to_creator_persona(payload)
            current = _loads(row["video_prompt"])
            if not _script_video_prompt_needs_veo_refresh(current, persona):
                continue
            video_prompt = _normalize_video_prompt_for_storage(
                current,
                payload["script"],
                payload["storyboard"],
                _loads(row["production_asset_plan"]) or [],
                persona,
            )
            connection.execute(
                """
                UPDATE scripts
                SET topic_plan = ?,
                    script = ?,
                    storyboard = ?,
                    creator_persona = ?,
                    video_prompt = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (_dump(payload["topic_plan"]), _dump(payload["script"]), _dump(payload["storyboard"]), _dump(persona), _dump(video_prompt), now, row["id"]),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_column(self, connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
        if any(row["name"] == column for row in rows):
            return
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _backfill_script_creator_personas(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute("SELECT id, topic_plan, script, storyboard, creator_persona FROM scripts ORDER BY created_at ASC").fetchall()
        now = utc_now()
        used_persona_names: set[str] = set()
        selected_personas_by_script_id = _creator_personas_by_source_script_id(connection)
        for index, row in enumerate(rows):
            selected_persona = selected_personas_by_script_id.get(str(row["id"]))
            if selected_persona:
                topic_plan = _loads(row["topic_plan"]) or {}
                script = _loads(row["script"]) or {}
                storyboard = _loads(row["storyboard"]) or []
                persona = _normalize_creator_persona_for_storage(
                    selected_persona,
                    topic_plan,
                    script,
                    seed=str(row["id"]),
                    excluded_names=None,
                )
                payload = {"topic_plan": topic_plan, "script": script, "storyboard": storyboard, "creator_persona": persona}
                _sync_script_payload_to_creator_persona(payload, force=True)
                connection.execute(
                    """
                    UPDATE scripts
                    SET topic_plan = ?,
                        script = ?,
                        storyboard = ?,
                        creator_persona = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (_dump(payload["topic_plan"]), _dump(payload["script"]), _dump(payload["storyboard"]), _dump(persona), now, row["id"]),
                )
                continue
            current = _loads(row["creator_persona"])
            if not _script_needs_creator_persona(current, excluded_names=used_persona_names):
                persona_name = _persona_display_name(current)
                if persona_name:
                    used_persona_names.add(persona_name)
                continue
            persona = _normalize_creator_persona_for_storage(
                current,
                _loads(row["topic_plan"]) or {},
                _loads(row["script"]) or {},
                seed=f"{row['id']}|{index}",
                variant_index=index,
                excluded_names=used_persona_names,
            )
            topic_plan = _loads(row["topic_plan"]) or {}
            script = _loads(row["script"]) or {}
            storyboard = _loads(row["storyboard"]) or []
            payload = {"topic_plan": topic_plan, "script": script, "storyboard": storyboard, "creator_persona": persona}
            _sync_script_payload_to_creator_persona(payload)
            persona_name = _persona_display_name(persona)
            if persona_name:
                used_persona_names.add(persona_name)
            connection.execute(
                """
                UPDATE scripts
                SET topic_plan = ?,
                    script = ?,
                    storyboard = ?,
                    creator_persona = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (_dump(payload["topic_plan"]), _dump(payload["script"]), _dump(payload["storyboard"]), _dump(persona), now, row["id"]),
            )

    def _row_to_record(self, row: sqlite3.Row) -> BreakdownRecord:
        payload = dict(row)
        for key in JSON_COLUMNS:
            payload[key] = _loads(payload.get(key))
        return BreakdownRecord.model_validate(payload)

    def _row_to_script_record(self, row: sqlite3.Row) -> ScriptRecord:
        payload = dict(row)
        for key in SCRIPT_JSON_COLUMNS:
            payload[key] = _loads(payload.get(key))
        payload["creator_persona"] = _normalize_creator_persona_for_storage(
            payload.get("creator_persona"),
            payload.get("topic_plan") or {},
            payload.get("script") or {},
            seed=str(payload.get("id") or ""),
        )
        _sync_script_payload_to_creator_persona(payload)
        if _script_video_prompt_needs_veo_refresh(payload.get("video_prompt"), payload.get("creator_persona")):
            payload["video_prompt"] = _normalize_video_prompt_for_storage(
                payload.get("video_prompt"),
                payload.get("script") or {},
                payload.get("storyboard") or [],
                payload.get("production_asset_plan") or [],
                payload.get("creator_persona"),
            )
        return ScriptRecord.model_validate(payload)

    def _row_to_script_generation_job_record(self, row: sqlite3.Row) -> ScriptGenerationJobRecord:
        payload = dict(row)
        for key in SCRIPT_GENERATION_JOB_JSON_COLUMNS:
            payload[key] = _loads(payload.get(key)) or []
        if not isinstance(payload.get("persona_hint"), dict):
            payload["persona_hint"] = {}
        if not payload.get("completed_count") and isinstance(payload.get("script_ids"), list):
            payload["completed_count"] = len(payload["script_ids"])
        return ScriptGenerationJobRecord.model_validate(payload)

    def _row_to_persona_generation_job_record(self, row: sqlite3.Row) -> PersonaGenerationJobRecord:
        payload = dict(row)
        for key in PERSONA_GENERATION_JOB_JSON_COLUMNS:
            payload[key] = _loads(payload.get(key)) or []
        return PersonaGenerationJobRecord.model_validate(payload)

    def _row_to_creator_persona_record(self, row: sqlite3.Row) -> CreatorPersonaRecord:
        payload = dict(row)
        for key in CREATOR_PERSONA_JSON_COLUMNS:
            payload[key] = _loads(payload.get(key)) or ([] if key.endswith("_ids") else {})
        payload["creator_persona"] = _normalize_creator_persona_for_storage(
            payload.get("creator_persona"),
            {},
            {},
            seed=str(payload.get("id") or ""),
        )
        return CreatorPersonaRecord.model_validate(payload)

    def _row_to_director_plan_record(self, row: sqlite3.Row) -> DirectorPlanRecord:
        payload = dict(row)
        for key in DIRECTOR_PLAN_JSON_COLUMNS:
            payload[key] = _loads(payload.get(key))
        return DirectorPlanRecord.model_validate(payload)

    def _row_to_director_generation_job_record(self, row: sqlite3.Row) -> DirectorGenerationJobRecord:
        return DirectorGenerationJobRecord.model_validate(dict(row))

    def _row_to_manual_factory_asset_record(self, row: sqlite3.Row) -> ManualFactoryAssetRecord:
        return ManualFactoryAssetRecord.model_validate(dict(row))

    def _row_to_moras_asset_record(self, row: sqlite3.Row) -> MorasAssetLibraryRecord:
        return MorasAssetLibraryRecord.model_validate(dict(row))

    def _row_to_director_plan_asset_binding_record(self, row: sqlite3.Row) -> DirectorPlanAssetBindingRecord:
        return DirectorPlanAssetBindingRecord.model_validate(dict(row))

    def _row_to_director_render_job_record(self, row: sqlite3.Row) -> DirectorRenderJobRecord:
        payload = dict(row)
        for key in DIRECTOR_RENDER_JOB_JSON_COLUMNS:
            payload[key] = _loads(payload.get(key)) or {}
        return DirectorRenderJobRecord.model_validate(payload)

    def _row_to_director_render_artifact_record(self, row: sqlite3.Row) -> DirectorRenderArtifactRecord:
        return DirectorRenderArtifactRecord.model_validate(dict(row))

    def _row_to_director_render_usage_record(self, row: sqlite3.Row) -> DirectorRenderUsageRecord:
        return DirectorRenderUsageRecord.model_validate(dict(row))

    def _row_to_director_publish_record(self, row: sqlite3.Row) -> DirectorPublishRecord:
        return DirectorPublishRecord.model_validate(dict(row))


JSON_COLUMNS = {
    "source_video",
    "classification",
    "decomposition",
    "structure_protocol",
    "script_agent_bridge",
    "reference_storyboard",
}

SCRIPT_JSON_COLUMNS = {
    "source_breakdown_ids",
    "topic_plan",
    "script",
    "storyboard",
    "creator_persona",
    "video_prompt",
    "production_asset_plan",
    "risk_check",
    "source_component_summary",
    "revision_history",
}

SCRIPT_GENERATION_JOB_JSON_COLUMNS = {
    "source_breakdown_ids",
    "persona_hint",
    "script_ids",
}

PERSONA_GENERATION_JOB_JSON_COLUMNS = {
    "persona_ids",
}

CREATOR_PERSONA_JSON_COLUMNS = {
    "creator_persona",
    "source_script_ids",
}

DIRECTOR_PLAN_JSON_COLUMNS = {
    "metadata",
    "timeline",
    "asset_resolution",
    "tool_dispatches",
    "validation_summary",
}

DIRECTOR_RENDER_JOB_JSON_COLUMNS = {
    "readiness_summary",
    "qa_summary",
}


def _script_needs_creator_persona(value: Any, *, excluded_names: set[str] | None = None) -> bool:
    return creator_persona_needs_refresh(value, excluded_names=excluded_names)


def _normalize_creator_persona_for_storage(
    value: Any,
    topic_plan: dict[str, Any],
    script: dict[str, Any],
    *,
    seed: str | None = None,
    variant_index: int | None = None,
    excluded_names: set[str] | None = None,
) -> dict[str, Any]:
    persona = normalize_creator_persona_payload(
        value,
        topic_plan,
        script,
        seed=seed,
        variant_index=variant_index,
        excluded_names=excluded_names,
    )
    try:
        from .script_service import repair_text_tree_for_safe_style

        persona = repair_text_tree_for_safe_style(persona)
    except Exception:
        pass
    return persona


def _creator_personas_by_source_script_id(connection: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = connection.execute("SELECT creator_persona, source_script_ids FROM creator_personas").fetchall()
    personas_by_script_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        persona = _loads(row["creator_persona"])
        script_ids = _loads(row["source_script_ids"])
        if not isinstance(persona, dict) or not isinstance(script_ids, list):
            continue
        for script_id in script_ids:
            script_id_text = str(script_id or "").strip()
            if script_id_text and script_id_text not in personas_by_script_id:
                personas_by_script_id[script_id_text] = persona
    return personas_by_script_id


def _persona_display_name(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return str(value.get("display_name") or "").strip()


def _persona_identity_string(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return str(value.get("veo_identity_string") or value.get("veoIdentityString") or "").strip()


def _sync_script_payload_to_creator_persona(payload: dict[str, Any], *, force: bool = False) -> None:
    from .script_service import repair_publishable_safe_style_drift, sync_script_item_to_creator_persona

    sync_script_item_to_creator_persona(payload, force=force)
    repair_publishable_safe_style_drift(payload)


def _script_video_prompt_needs_veo_refresh(value: Any, creator_persona: Any | None = None) -> bool:
    if not isinstance(value, dict) or not value:
        return True
    if str(value.get("target_model") or value.get("targetModel") or "").strip() != "Veo 3.1":
        return True
    if not str(value.get("veo_model_id") or value.get("veoModelId") or "").strip():
        return True
    if "negative_prompt" in value or "negativePrompt" in value:
        return True
    localized = value.get("localized")
    zh = localized.get("zh") if isinstance(localized, dict) and isinstance(localized.get("zh"), dict) else None
    if zh is not None and ("negative_prompt" in zh or "negativePrompt" in zh):
        return True
    display_name = _persona_display_name(creator_persona)
    identity = _persona_identity_string(creator_persona)
    character_lock = str(value.get("character_lock") or value.get("characterLock") or "")
    if display_name and display_name.lower() not in character_lock.lower():
        return True
    if identity and identity.lower() not in character_lock.lower():
        return True
    segments = value.get("segments")
    if not isinstance(segments, list) or not segments:
        return True
    for segment in segments:
        if not isinstance(segment, dict):
            return True
        prompt = str(segment.get("veo_prompt") or segment.get("veoPrompt") or "")
        if not _is_copyable_video_prompt_text(prompt):
            return True
        if "script" in prompt.lower() or "脚本" in prompt:
            return True
        if display_name and display_name.lower() not in prompt.lower():
            return True
        if identity and identity.lower() not in prompt.lower():
            return True
        if _prompt_contains_stale_identity(prompt):
            return True
    return False


def _normalize_video_prompt_for_storage(
    value: Any,
    script: dict[str, Any],
    storyboard: list[Any],
    production_asset_plan: list[Any],
    creator_persona: Any | None = None,
) -> dict[str, Any]:
    source = dict(value) if isinstance(value, dict) else {}
    source.pop("negative_prompt", None)
    source.pop("negativePrompt", None)
    localized = source.get("localized")
    zh = localized.get("zh") if isinstance(localized, dict) and isinstance(localized.get("zh"), dict) else None
    if zh is not None:
        zh.pop("negative_prompt", None)
        zh.pop("negativePrompt", None)
    if _script_video_prompt_needs_veo_refresh(source, creator_persona):
        source["segments"] = []
    from .script_service import ensure_veo_segments

    normalized = ensure_veo_segments(source, script, storyboard, production_asset_plan, creator_persona)
    normalized.pop("negative_prompt", None)
    normalized.pop("negativePrompt", None)
    localized = normalized.get("localized")
    zh = localized.get("zh") if isinstance(localized, dict) and isinstance(localized.get("zh"), dict) else None
    if zh is not None:
        zh.pop("negative_prompt", None)
        zh.pop("negativePrompt", None)
    return normalized


def _is_copyable_video_prompt_text(value: str) -> bool:
    import re

    words = re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", value)
    cjk_chars = re.findall(r"[\u3400-\u9fff]", value)
    if len(words) < 45 and len(cjk_chars) < 80:
        return False
    lowered = value.lower()
    required_groups = {
        "subject": ["subject", "creator", "person", "人物", "创作者"],
        "action": ["action", "gesture", "expression", "movement", "动作", "表情"],
        "camera": ["camera", "shot", "vertical", "framing", "镜头", "竖屏"],
        "lighting": ["lighting", "light", "realistic", "cinematic", "光", "真实"],
        "audio": ["audio", "ambiance", "sound", "room tone", "声音", "环境声"],
    }
    return all(any(term in lowered or term in value for term in terms) for terms in required_groups.values())


def _prompt_contains_stale_identity(value: str) -> bool:
    lowered = str(value or "").lower()
    stale_terms = [
        "efficiency expert",
        "same young creator",
        "young creator",
        "male creator",
        "female creator",
        "asian creator",
        "asian female",
        "mia chen",
    ]
    if any(term in lowered for term in stale_terms):
        return True
    return any(term in value for term in ["男性创作者", "女性创作者", "亚洲", "米娅"])


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _status_value(value: str | DirectorRenderJobStatus) -> str:
    return value.value if isinstance(value, DirectorRenderJobStatus) else str(value)


def _loads(value: str | None) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _parse_utc_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _find_asset_resolution(items: list[dict[str, Any]], asset_ref: str) -> dict[str, Any] | None:
    for item in items:
        current = str(item.get("asset_ref") or item.get("assetRef") or "")
        if current == asset_ref:
            return item
    return None

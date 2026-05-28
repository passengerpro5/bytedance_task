from __future__ import annotations

import json
from pathlib import Path
from threading import Lock, RLock
from typing import Any

from .config import (
    ANALYSIS_CACHE_PATH,
    COVER_DIR,
    DB_PATH,
    ENV_PATH,
    TASK3_ANALYSIS_PATH,
    TASK3_INPUTS_PATH,
    TASK3_MATERIAL_DIR,
    UPLOAD_DIR,
)


DB_LOCK = RLock()
ANALYSIS_LOCK = Lock()
TASK3_LOCK = Lock()


def ensure_storage() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    COVER_DIR.mkdir(parents=True, exist_ok=True)
    TASK3_MATERIAL_DIR.mkdir(parents=True, exist_ok=True)

    for path in (DB_PATH, ANALYSIS_CACHE_PATH, TASK3_INPUTS_PATH, TASK3_ANALYSIS_PATH):
        if not path.exists():
            path.write_text("[]", encoding="utf-8")

    if not ENV_PATH.exists():
        ENV_PATH.write_text("", encoding="utf-8")


def load_json_file_safe(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    return payload if isinstance(payload, list) else []


def write_json_records(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def load_analysis_records() -> list[dict[str, Any]]:
    with ANALYSIS_LOCK:
        return load_json_file_safe(ANALYSIS_CACHE_PATH)


def save_analysis_records(records: list[dict[str, Any]]) -> None:
    with ANALYSIS_LOCK:
        write_json_records(ANALYSIS_CACHE_PATH, records)


def load_task3_inputs() -> list[dict[str, Any]]:
    with TASK3_LOCK:
        return load_json_file_safe(TASK3_INPUTS_PATH)


def save_task3_inputs(records: list[dict[str, Any]]) -> None:
    with TASK3_LOCK:
        write_json_records(TASK3_INPUTS_PATH, records)


def load_task3_analysis_records() -> list[dict[str, Any]]:
    with TASK3_LOCK:
        return load_json_file_safe(TASK3_ANALYSIS_PATH)


def save_task3_analysis_records(records: list[dict[str, Any]]) -> None:
    with TASK3_LOCK:
        write_json_records(TASK3_ANALYSIS_PATH, records)

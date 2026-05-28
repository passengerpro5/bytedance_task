from __future__ import annotations

import hashlib
from html import escape
import os
import json
import logging
import shutil
import subprocess
import traceback
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from threading import Lock, RLock
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from scenedetect import SceneManager, open_video
from scenedetect.detectors import ContentDetector

from .config import (
    ALLOWED_EXTENSIONS,
    ANALYSIS_CACHE_PATH,
    BROWSER_COMPATIBLE_CODECS,
    COVER_DIR,
    DATA_DIR,
    DB_PATH,
    ENV_PATH,
    MAX_UPLOAD_SIZE_BYTES,
    ROOT_DIR,
    SETTINGS_DEFINITIONS,
    TASK3_ALLOWED_EXTENSIONS,
    TASK3_ANALYSIS_PATH,
    TASK3_INPUTS_PATH,
    TASK3_MATERIAL_DIR,
    UPLOAD_DIR,
)
from .schemas import (
    AnalysisRequest,
    SettingsUpdateRequest,
    Task3AnalyzeRequest,
    Task3GapUpdateRequest,
    Task3InputCreateRequest,
    Task3InputUpdateRequest,
    Task3MaterialPayload,
)
from .storage import (
    ANALYSIS_LOCK,
    DB_LOCK,
    TASK3_LOCK,
    ensure_storage,
    load_json_file_safe,
    load_task3_analysis_records,
    load_task3_inputs,
    save_task3_analysis_records,
    save_task3_inputs,
)
from .services.task3_service import (
    analyze_task3_input,
    create_task3_input_record,
    get_task3_input_record,
    task3_material_from_payload,
)
from .video_decompose import (
    decompose_video_content,
    load_gemini_video_config,
    load_llm_config,
    normalize_settings as normalize_decomposition_settings,
    load_commercial_model_config,
)


ENV_LOCK = Lock()
DECOMPOSITION_DIR = DATA_DIR / "decompositions"
LOG_DIR = DATA_DIR / "logs"
DECOMPOSITION_LOG_PATH = LOG_DIR / "decomposition.log"
DEFAULT_FAST_PROMPT_PATH = Path("prompts/fast-video-structure.txt")
DEFAULT_FAST_SKILL_PATH = Path("skills/fast-video-structure.md")
DEFAULT_ANALYSIS_STEP_TEMPLATES = [
    ("fast-summary", DEFAULT_FAST_PROMPT_PATH, DEFAULT_FAST_SKILL_PATH),
    ("deep-shot", Path("prompts/deep-shot-rhythm-structure.txt"), Path("skills/deep-shot-rhythm-structure.md")),
    ("deep-copy", Path("prompts/deep-script-paragraph-structure.txt"), Path("skills/deep-script-paragraph-structure.md")),
    ("deep-package", Path("prompts/deep-packaging-structure.txt"), Path("skills/deep-packaging-structure.md")),
    ("structured-visual", Path("prompts/structured-visual-structure.txt"), Path("skills/structured-visual-structure.md")),
    ("structured-speech", Path("prompts/structured-speech-script-structure.txt"), Path("skills/structured-speech-script-structure.md")),
    ("structured-package", Path("prompts/structured-packaging-structure.txt"), Path("skills/structured-packaging-structure.md")),
]


def get_decomposition_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("hot_engine.decomposition")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.FileHandler(DECOMPOSITION_LOG_PATH, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logger.addHandler(handler)

    return logger


DECOMPOSITION_LOGGER = get_decomposition_logger()


def read_relative_text_template(relative_path: Path) -> tuple[str, str]:
    normalized = Path(str(relative_path).replace("\\", "/"))
    if normalized.is_absolute() or ".." in normalized.parts:
        return "", ""

    template_path = ROOT_DIR / normalized
    if not template_path.exists() or not template_path.is_file():
        return "", ""

    content = template_path.read_text(encoding="utf-8")
    return content, hashlib.sha256(content.encode("utf-8")).hexdigest()


def create_placeholder_cover(video_id: str) -> Path:
        cover_path = COVER_DIR / f"{video_id}_placeholder.svg"

        if not cover_path.exists():
                svg_content = f"""<svg xmlns='http://www.w3.org/2000/svg' width='960' height='540' viewBox='0 0 960 540'>
    <defs>
        <linearGradient id='bg' x1='0' y1='0' x2='1' y2='1'>
            <stop offset='0%' stop-color='#2b2f36'/>
            <stop offset='100%' stop-color='#0f1115'/>
        </linearGradient>
        <linearGradient id='accent' x1='0' y1='0' x2='1' y2='0'>
            <stop offset='0%' stop-color='#d89b57'/>
            <stop offset='100%' stop-color='#ae6d43'/>
        </linearGradient>
    </defs>
    <rect width='960' height='540' rx='28' fill='url(#bg)'/>
    <circle cx='800' cy='120' r='88' fill='rgba(216,155,87,0.14)'/>
    <circle cx='180' cy='430' r='120' fill='rgba(174,109,67,0.12)'/>
    <rect x='96' y='92' width='768' height='356' rx='28' fill='rgba(255,255,255,0.05)' stroke='rgba(255,255,255,0.08)'/>
    <rect x='286' y='190' width='388' height='108' rx='20' fill='url(#accent)'/>
    <text x='480' y='257' text-anchor='middle' fill='#fffaf3' font-size='44' font-family='Segoe UI, Arial, sans-serif' font-weight='700'>NO COVER</text>
    <text x='480' y='336' text-anchor='middle' fill='rgba(255,250,243,0.82)' font-size='22' font-family='Segoe UI, Arial, sans-serif'>placeholder for {escape(video_id)}</text>
</svg>
"""
                cover_path.write_text(svg_content, encoding="utf-8")

        return cover_path


def repair_cover_for_record(record: dict[str, Any]) -> bool:
        cover_url = record.get("coverUrl")

        if cover_url:
                cover_name = Path(cover_url).name
                if (COVER_DIR / cover_name).exists():
                        return False

        cover_path = create_placeholder_cover(record["id"])
        record["coverUrl"] = f"/media/covers/{cover_path.name}"
        record["coverKind"] = "placeholder"
        return True


def parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()

    if not stripped or stripped.startswith("#"):
        return None

    if stripped.startswith("export "):
        stripped = stripped[7:].lstrip()

    if "=" not in stripped:
        return None

    key, raw_value = stripped.split("=", 1)
    key = key.strip()
    value = raw_value.strip()

    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]

    return key, value


def serialize_env_value(value: str) -> str:
    if value == "":
        return ""

    if any(character in value for character in ' \t\n\r"\'#'):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    return value


def load_env_values() -> dict[str, str]:
    if not ENV_PATH.exists():
        return {}

    env_values: dict[str, str] = {}
    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        parsed = parse_env_line(raw_line)
        if parsed is not None:
            key, value = parsed
            env_values[key] = value

    return env_values


def save_env_values(updates: dict[str, str]) -> None:
    with ENV_LOCK:
        existing_lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
        remaining_updates = dict(updates)
        output_lines: list[str] = []

        for raw_line in existing_lines:
            parsed = parse_env_line(raw_line)

            if parsed is None:
                output_lines.append(raw_line)
                continue

            key, _ = parsed
            if key in remaining_updates:
                output_lines.append(f"{key}={serialize_env_value(remaining_updates.pop(key))}")
            else:
                output_lines.append(raw_line)

        for key, value in remaining_updates.items():
            output_lines.append(f"{key}={serialize_env_value(value)}")

        ENV_PATH.write_text("\n".join(output_lines) + ("\n" if output_lines else ""), encoding="utf-8")


def collect_settings() -> list[dict[str, str]]:
    env_values = load_env_values()

    items: list[dict[str, str]] = []
    for definition in SETTINGS_DEFINITIONS:
        env_name = definition["env_name"]
        items.append(
            {
                "key": definition["key"],
                "label": definition["label"],
                "envName": env_name,
                "description": definition["description"],
                "value": env_values.get(env_name, os.environ.get(env_name, "")),
            }
        )

    return items


def update_settings_from_payload(payload: SettingsUpdateRequest) -> list[dict[str, str]]:
    payload_data = payload.model_dump(exclude_unset=True)

    if not payload_data:
        raise HTTPException(status_code=400, detail="No settings provided.")

    updates: dict[str, str] = {}
    for definition in SETTINGS_DEFINITIONS:
        field_name = definition["key"]
        if field_name in payload_data:
            raw_value = payload_data[field_name]
            updates[definition["env_name"]] = "" if raw_value is None else str(raw_value)

    if not updates:
        raise HTTPException(status_code=400, detail="No settings provided.")

    save_env_values(updates)
    os.environ.update(updates)
    return collect_settings()


def load_analysis_records() -> list[dict[str, Any]]:
    with ANALYSIS_LOCK:
        if not ANALYSIS_CACHE_PATH.exists():
            return []

        try:
            return json.loads(ANALYSIS_CACHE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []


def save_analysis_records(records: list[dict[str, Any]]) -> None:
    with ANALYSIS_LOCK:
        ANALYSIS_CACHE_PATH.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def normalize_analysis_request(payload: AnalysisRequest) -> dict[str, Any]:
    normalized = {
        "methodName": payload.methodName.strip() or "standard",
        "frameInterval": max(int(payload.frameInterval or 1), 1),
    }

    if payload.settings:
        settings_signature = json.dumps(payload.settings, ensure_ascii=False, sort_keys=True)
        normalized["settingsHash"] = hashlib.sha256(settings_signature.encode("utf-8")).hexdigest()

    return normalized


def analysis_cache_key(video_id: str, payload: AnalysisRequest) -> str:
    normalized = normalize_analysis_request(payload)
    signature = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(f"{video_id}:{signature}".encode("utf-8")).hexdigest()
    return digest


def get_video_record(video_id: str) -> dict[str, Any]:
    record = next((item for item in load_records() if item["id"] == video_id), None)

    if record is None:
        raise HTTPException(status_code=404, detail="Video not found.")

    return record


def update_video_analysis_in_db(video_id: str, analysis_record: dict[str, Any]) -> None:
    records = load_records()
    updated = False

    for record in records:
        if record["id"] == video_id:
            record["analysis"] = analysis_record["analysis"]
            record["analysisMeta"] = {
                "methodName": analysis_record["methodName"],
                "frameInterval": analysis_record["frameInterval"],
                "cachedAt": analysis_record["cachedAt"],
            }
            updated = True
            break

    if updated:
        save_records(records)


def remove_analysis_cache_for_video(video_id: str) -> None:
    analysis_records = load_analysis_records()
    filtered = [record for record in analysis_records if record.get("videoId") != video_id]

    if len(filtered) != len(analysis_records):
        save_analysis_records(filtered)


def find_latest_analysis_record(video_id: str) -> dict[str, Any] | None:
    matches = [record for record in load_analysis_records() if record.get("videoId") == video_id]

    if not matches:
        return None

    matches.sort(key=lambda item: item.get("cachedAt", ""), reverse=True)
    return matches[0]


def build_shot_analysis(video_record: dict[str, Any], frame_interval: int = 5) -> dict[str, Any]:
    shot_detection_method = "pyscenedetect_content"
    shot_detection_error = None

    try:
        shots = detect_video_shots(resolve_video_file_path(video_record), video_record)
    except Exception as exc:
        shot_detection_method = "interval_fallback"
        shot_detection_error = str(exc)
        shots = build_interval_shots(video_record, frame_interval)

    return {
        "shotCount": len(shots),
        "shots": shots,
        "shotDetection": {
            "method": shot_detection_method,
            "label": "估算镜头段数",
            "error": shot_detection_error,
        },
    }


def build_analysis_result(video_record: dict[str, Any], payload: AnalysisRequest) -> dict[str, Any]:
    normalized = normalize_analysis_request(payload)
    frame_interval = normalized["frameInterval"]
    method_name = normalized["methodName"]

    shot_analysis = build_shot_analysis(video_record, frame_interval)
    shot_count = shot_analysis["shotCount"]
    seed = hashlib.sha256(f'{video_record["id"]}:{method_name}:{frame_interval}'.encode("utf-8")).hexdigest()
    subtitle_enabled = int(seed[:2], 16) % 2 == 0
    speech_enabled = int(seed[2:4], 16) % 2 == 0
    density = ["low", "medium", "high"][int(seed[4:6], 16) % 3]

    analysis = {
        **shot_analysis,
        "subtitleOverview": {
            "hasSubtitle": subtitle_enabled,
            "language": "zh-CN" if subtitle_enabled else None,
            "density": density,
            "sampleLines": [
                f"{video_record['name']} 的 {method_name} 拆解样例 1",
                f"{video_record['name']} 的 {method_name} 拆解样例 2",
            ] if subtitle_enabled else [],
        },
        "voiceOverview": {
            "hasSpeech": speech_enabled,
            "summary": f"{method_name} 方法对该视频完成了 {shot_count} 段拆解。",
            "keywords": [method_name, f"interval-{frame_interval}", "analysis"],
            "transcriptPreview": f"{video_record['name']} 的语音预览内容。" if speech_enabled else None,
        },
        "summary": (
            f"视频 {video_record['name']} 使用 {method_name} 方法和 {frame_interval}s 间隔完成拆解，"
            f"共生成 {shot_count} 个片段。"
        ),
    }

    return {
        "videoId": video_record["id"],
        "videoName": video_record.get("name"),
        "coverUrl": video_record.get("coverUrl"),
        "videoUrl": video_record.get("videoUrl"),
        "methodName": method_name,
        "frameInterval": frame_interval,
        "persistedToDb": bool(payload.persistToDb),
        "analysis": analysis,
        "cachedAt": datetime.now(UTC).isoformat(),
    }


def summarize_decomposition_result(result: dict[str, Any], output_path: Path) -> dict[str, Any]:
    return {
        "outputPath": str(output_path.relative_to(ROOT_DIR)),
        "methodName": result.get("methodName"),
        "inputMode": result.get("inputMode"),
        "model": result.get("model"),
        "overview": result.get("overview"),
        "rawOverview": result.get("rawOverview"),
        "startedAt": result.get("startedAt"),
        "completedAt": result.get("completedAt"),
        "steps": [
            {
                "index": step.get("index"),
                "id": step.get("id"),
                "name": step.get("name"),
                "modelType": step.get("modelType"),
                "model": step.get("model"),
                "provider": step.get("provider"),
                "promptKey": step.get("promptKey"),
                "skillKey": step.get("skillKey"),
                "output": step.get("output"),
                "rawOutput": step.get("rawOutput"),
                "completedAt": step.get("completedAt"),
            }
            for step in result.get("steps", [])
        ],
    }


def load_latest_decomposition(video_id: str) -> dict[str, Any] | None:
    candidates = sorted(
        DECOMPOSITION_DIR.glob(f"{video_id}_decomposition*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    for path in candidates:
        try:
            return summarize_decomposition_result(json.loads(path.read_text(encoding="utf-8")), path)
        except (OSError, json.JSONDecodeError):
            continue

    return None


def run_configured_decomposition(video_record: dict[str, Any], payload: AnalysisRequest) -> dict[str, Any] | None:
    if not payload.settings:
        return None

    normalized_settings = normalize_decomposition_settings(payload.settings)
    input_mode = normalized_settings.get("inputMode", "direct-video")
    settings_hash = normalize_analysis_request(payload).get("settingsHash", "default")
    output_path = DECOMPOSITION_DIR / f"{video_record['id']}_decomposition_{settings_hash[:12]}.json"
    DECOMPOSITION_LOGGER.info(
        "start video_id=%s method=%s input_mode=%s output=%s",
        video_record.get("id"),
        normalized_settings.get("methodName"),
        input_mode,
        output_path,
    )

    try:
        if input_mode == "direct-video":
            llm_config = load_gemini_video_config(None)
        else:
            try:
                llm_config = load_llm_config(None)
            except ValueError as exc:
                DECOMPOSITION_LOGGER.warning(
                    "chat overview config unavailable, falling back to image model. video_id=%s error=%s",
                    video_record.get("id"),
                    exc,
                )
                llm_config = load_commercial_model_config(
                    model_type="image-recognition",
                    config_path=None,
                )

        result = decompose_video_content(
            video_record=video_record,
            settings=payload.settings,
            llm_config=llm_config,
            output_path=output_path,
            settings_dir=ROOT_DIR,
            config_path=None,
            language="中文",
        )
        DECOMPOSITION_LOGGER.info(
            "completed video_id=%s steps=%s output=%s",
            video_record.get("id"),
            len(result.get("steps", [])),
            output_path,
        )
        return summarize_decomposition_result(result, output_path)
    except Exception as exc:
        DECOMPOSITION_LOGGER.error(
            "failed video_id=%s method=%s input_mode=%s output=%s error=%s\n%s",
            video_record.get("id"),
            normalized_settings.get("methodName"),
            input_mode,
            output_path,
            exc,
            traceback.format_exc(),
        )
        raise HTTPException(
            status_code=502,
            detail=f"完整拆解失败：{exc}。详细日志见 {DECOMPOSITION_LOG_PATH.relative_to(ROOT_DIR)}",
        ) from exc


def upsert_analysis_record(video_record: dict[str, Any], payload: AnalysisRequest, *, force: bool = False) -> dict[str, Any]:
    cache_key = analysis_cache_key(video_record["id"], payload)
    existing_records = load_analysis_records()
    existing_record = next((record for record in existing_records if record.get("cacheKey") == cache_key), None)

    if existing_record is not None and not force:
        DECOMPOSITION_LOGGER.info(
            "cache_hit video_id=%s cache_key=%s method=%s",
            video_record["id"],
            cache_key,
            payload.methodName,
        )
        if payload.persistToDb and not existing_record.get("persistedToDb"):
            update_video_analysis_in_db(video_record["id"], existing_record)
            existing_record["persistedToDb"] = True
            save_analysis_records(existing_records)

        return {"cached": True, **existing_record}

    DECOMPOSITION_LOGGER.info(
        "cache_miss video_id=%s cache_key=%s method=%s force=%s",
        video_record["id"],
        cache_key,
        payload.methodName,
        force,
    )

    analysis_record = build_analysis_result(video_record, payload)
    decomposition_record = run_configured_decomposition(video_record, payload)
    full_record = {
        "cacheKey": cache_key,
        **analysis_record,
    }
    if decomposition_record is not None:
        full_record["decomposition"] = decomposition_record

    if payload.persistToDb:
        update_video_analysis_in_db(video_record["id"], full_record)

    next_records = [record for record in existing_records if record.get("cacheKey") != cache_key]
    next_records.append(full_record)
    save_analysis_records(next_records)

    return {"cached": False, **full_record}


def analyze_video_record(video_id: str, payload: AnalysisRequest) -> dict[str, Any]:
    video_record = get_video_record(video_id)
    return upsert_analysis_record(video_record, payload, force=payload.force)


def load_records() -> list[dict[str, Any]]:
    with DB_LOCK:
        if not DB_PATH.exists():
            return []

        try:
            records = json.loads(DB_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            records = []

        repaired = False
        for record in records:
            repaired = repair_cover_for_record(record) or repaired

        if repaired:
            DB_PATH.write_text(
                json.dumps(records, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        return records


def save_records(records: list[dict[str, Any]]) -> None:
    with DB_LOCK:
        DB_PATH.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def parse_ratio(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None

    try:
        return round(float(Fraction(value)), 3)
    except (ZeroDivisionError, ValueError):
        return None


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )


def resolve_video_file_path(video_record: dict[str, Any]) -> Path:
    video_name = Path(str(video_record.get("videoUrl") or "")).name

    if not video_name:
        raise ValueError("Video file path is missing.")

    video_path = UPLOAD_DIR / video_name

    if not video_path.exists():
        raise FileNotFoundError(f"Video file does not exist: {video_name}")

    return video_path


def merge_short_shots(shots: list[dict[str, Any]], min_duration_ms: int = 500) -> list[dict[str, Any]]:
    if not shots:
        return shots

    merged: list[dict[str, Any]] = []

    for shot in shots:
        if merged and shot["durationMs"] < min_duration_ms:
            previous = merged[-1]
            previous["endMs"] = shot["endMs"]
            previous["durationMs"] = previous["endMs"] - previous["startMs"]
            continue

        merged.append({**shot})

    for index, shot in enumerate(merged, start=1):
        shot["index"] = index

    return merged


def detect_video_shots(video_path: Path, video_record: dict[str, Any]) -> list[dict[str, Any]]:
    video = open_video(str(video_path))
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=27.0))
    scene_manager.detect_scenes(video)

    scene_list = scene_manager.get_scene_list()
    duration_ms = int(video_record.get("durationMs") or 0)
    shots: list[dict[str, Any]] = []

    for index, (start_time, end_time) in enumerate(scene_list, start=1):
        start_ms = int(start_time.get_seconds() * 1000)
        end_ms = int(end_time.get_seconds() * 1000)

        if end_ms <= start_ms:
            continue

        shots.append(
            {
                "index": index,
                "startMs": start_ms,
                "endMs": end_ms,
                "durationMs": end_ms - start_ms,
                "thumbnailUrl": video_record.get("coverUrl") if index == 1 else None,
            }
        )

    if not shots and duration_ms > 0:
        shots.append(
            {
                "index": 1,
                "startMs": 0,
                "endMs": duration_ms,
                "durationMs": duration_ms,
                "thumbnailUrl": video_record.get("coverUrl"),
            }
        )

    return merge_short_shots(shots)


def build_interval_shots(video_record: dict[str, Any], frame_interval: int) -> list[dict[str, Any]]:
    duration_ms = int(video_record.get("durationMs") or 0)
    duration_seconds = max(duration_ms / 1000, 1)
    shot_count = max(1, min(12, int(duration_seconds // frame_interval) + 1))
    step_ms = max(int(duration_ms / shot_count), 1)
    shots: list[dict[str, Any]] = []

    for index in range(shot_count):
        start_ms = min(index * step_ms, duration_ms)
        end_ms = min(start_ms + step_ms, duration_ms)
        shots.append(
            {
                "index": index + 1,
                "startMs": start_ms,
                "endMs": end_ms,
                "durationMs": max(end_ms - start_ms, 0),
                "thumbnailUrl": video_record.get("coverUrl") if index == 0 else None,
            }
        )

    return shots


def probe_video(video_path: Path) -> dict[str, Any]:
    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-print_format",
            "json",
            str(video_path),
        ]
    )
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    format_info = payload.get("format", {})
    video_stream = next(
        (stream for stream in streams if stream.get("codec_type") == "video"),
        None,
    )

    if video_stream is None:
        raise ValueError("No video stream detected.")

    duration_seconds = float(
        format_info.get("duration")
        or video_stream.get("duration")
        or 0
    )

    return {
        "durationMs": int(duration_seconds * 1000),
        "width": int(video_stream.get("width") or 0),
        "height": int(video_stream.get("height") or 0),
        "fps": parse_ratio(
            video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")
        ),
        "sizeBytes": int(format_info.get("size") or video_path.stat().st_size),
        "codec": video_stream.get("codec_name", ""),
    }


def extract_cover(video_path: Path, video_id: str, duration_ms: int) -> Path:
    cover_path = COVER_DIR / f"{video_id}.jpg"
    capture_second = max(min(duration_ms / 1000 * 0.15, 1.0), 0.0)

    command = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{capture_second:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-vf",
        "scale=640:-1:force_original_aspect_ratio=decrease",
        "-q:v",
        "3",
        str(cover_path),
    ]

    try:
        run_command(command)
    except subprocess.CalledProcessError:
        fallback_command = command.copy()
        fallback_command[3] = "0.000"
        run_command(fallback_command)

    return cover_path


def transcode_to_h264(video_path: Path, video_id: str) -> Path:
    output_path = UPLOAD_DIR / f"{video_id}_h264.mp4"

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    run_command(command)
    video_path.unlink(missing_ok=True)
    return output_path


def build_video_record(
    *,
    video_id: str,
    original_name: str,
    stored_video_name: str,
    stored_cover_name: str | None,
    metadata: dict[str, Any] | None = None,
    status: str = "ready",
    error_message: str | None = None,
) -> dict[str, Any]:
    metadata = metadata or {}

    return {
        "id": video_id,
        "name": original_name,
        "durationMs": metadata.get("durationMs", 0),
        "width": metadata.get("width", 0),
        "height": metadata.get("height", 0),
        "fps": metadata.get("fps"),
        "sizeBytes": metadata.get("sizeBytes", 0),
        "coverUrl": f"/media/covers/{stored_cover_name}" if stored_cover_name else None,
        "videoUrl": f"/media/uploads/{stored_video_name}",
        "status": status,
        "errorMessage": error_message,
        "analysis": {
            "shotCount": None,
            "shots": [],
            "subtitleOverview": None,
            "voiceOverview": None,
        },
        "createdAt": datetime.now(UTC).isoformat(),
    }


def append_record(record: dict[str, Any]) -> None:
    records = load_records()
    records.insert(0, record)
    save_records(records)


def remove_record(record_id: str) -> dict[str, Any]:
    records = load_records()
    target = next((record for record in records if record["id"] == record_id), None)

    if target is None:
        raise HTTPException(status_code=404, detail="Video not found.")

    next_records = [record for record in records if record["id"] != record_id]
    save_records(next_records)
    return target


def save_upload_file(file: UploadFile, destination: Path) -> None:
    with destination.open("wb") as output:
        shutil.copyfileobj(file.file, output)


def read_text_file_best_effort(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue

    return ""


def validate_upload(file: UploadFile) -> str:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Upload item is missing a filename.")

    extension = Path(file.filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"{file.filename} is not supported. Allowed types: {allowed}",
        )

    return extension


def prepare_video_record(file: UploadFile) -> dict[str, Any]:
    extension = validate_upload(file)
    video_id = uuid4().hex
    stored_video_name = f"{video_id}{extension}"
    video_path = UPLOAD_DIR / stored_video_name

    save_upload_file(file, video_path)

    if video_path.stat().st_size > MAX_UPLOAD_SIZE_BYTES:
        video_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"{file.filename} exceeds the 1GB limit.")

    try:
        metadata = probe_video(video_path)

        codec = metadata.pop("codec", "")
        if codec.lower() not in BROWSER_COMPATIBLE_CODECS:
            video_path = transcode_to_h264(video_path, video_id)
            stored_video_name = video_path.name
            metadata["sizeBytes"] = video_path.stat().st_size

        cover_path = extract_cover(video_path, video_id, metadata["durationMs"])
        record = build_video_record(
            video_id=video_id,
            original_name=file.filename,
            stored_video_name=stored_video_name,
            stored_cover_name=cover_path.name,
            metadata=metadata,
            status="ready",
        )
        shot_analysis = build_shot_analysis(record)
        record["analysis"] = {
            **record["analysis"],
            **shot_analysis,
        }
        record["analysisMeta"] = {
            "methodName": "upload_auto_shot_detection",
            "frameInterval": 5,
            "cachedAt": datetime.now(UTC).isoformat(),
        }
        return record
    except Exception as exc:
        cover_path = create_placeholder_cover(video_id)
        return build_video_record(
            video_id=video_id,
            original_name=file.filename,
            stored_video_name=stored_video_name,
            stored_cover_name=cover_path.name,
            status="failed",
            error_message=str(exc),
        )
    finally:
        file.file.close()


ensure_storage()

app = FastAPI(title="Reference Video Parser API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media", StaticFiles(directory=DATA_DIR), name="media")


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    return {
        "envPath": str(ENV_PATH.relative_to(ROOT_DIR)),
        "items": collect_settings(),
    }


@app.put("/api/settings")
def put_settings(payload: SettingsUpdateRequest) -> dict[str, Any]:
    return {
        "envPath": str(ENV_PATH.relative_to(ROOT_DIR)),
        "items": update_settings_from_payload(payload),
    }


@app.get("/api/analysis/default-template")
def get_analysis_default_template() -> dict[str, Any]:
    prompt, prompt_hash = read_relative_text_template(DEFAULT_FAST_PROMPT_PATH)
    skill, skill_hash = read_relative_text_template(DEFAULT_FAST_SKILL_PATH)
    return {
        "promptPath": DEFAULT_FAST_PROMPT_PATH.as_posix(),
        "prompt": prompt,
        "promptHash": prompt_hash,
        "skillPath": DEFAULT_FAST_SKILL_PATH.as_posix(),
        "skill": skill,
        "skillHash": skill_hash,
        "steps": [
            {
                "stepId": step_id,
                "promptPath": prompt_path.as_posix(),
                "prompt": step_prompt,
                "promptHash": step_prompt_hash,
                "skillPath": skill_path.as_posix(),
                "skill": step_skill,
                "skillHash": step_skill_hash,
            }
            for step_id, prompt_path, skill_path in DEFAULT_ANALYSIS_STEP_TEMPLATES
            for step_prompt, step_prompt_hash in [read_relative_text_template(prompt_path)]
            for step_skill, step_skill_hash in [read_relative_text_template(skill_path)]
        ],
    }


@app.get("/api/videos/{video_id}/analysis")
def get_video_analysis(video_id: str) -> dict[str, Any]:
    video_record = get_video_record(video_id)
    latest_cache = find_latest_analysis_record(video_id)

    if latest_cache is not None:
        return latest_cache

    analysis = video_record.get("analysis")
    if analysis is not None and analysis.get("shotCount") is not None:
        return {
            "cached": True,
            "cacheKey": None,
            "videoId": video_record["id"],
            "videoName": video_record.get("name"),
            "coverUrl": video_record.get("coverUrl"),
            "videoUrl": video_record.get("videoUrl"),
            "methodName": video_record.get("analysisMeta", {}).get("methodName", "persisted"),
            "frameInterval": video_record.get("analysisMeta", {}).get("frameInterval", 0),
            "persistedToDb": True,
            "analysis": analysis,
            "cachedAt": video_record.get("analysisMeta", {}).get("cachedAt", video_record.get("createdAt")),
        }

    raise HTTPException(status_code=404, detail="Analysis not found.")


@app.get("/api/videos/{video_id}/decomposition")
def get_video_decomposition(video_id: str) -> dict[str, Any]:
    get_video_record(video_id)
    decomposition = load_latest_decomposition(video_id)

    if decomposition is None:
        raise HTTPException(status_code=404, detail="Decomposition not found.")

    return decomposition


@app.post("/api/videos/{video_id}/analysis")
def analyze_video(video_id: str, payload: AnalysisRequest) -> dict[str, Any]:
    return analyze_video_record(video_id, payload)


@app.post("/api/videos/analysis/bulk")
def analyze_videos_bulk(payload: AnalysisRequest) -> dict[str, Any]:
    records = load_records()

    if payload.videoIds:
        video_ids = set(payload.videoIds)
        records = [record for record in records if record["id"] in video_ids]

    results = [analyze_video_record(record["id"], payload) for record in records]
    return {
        "count": len(results),
        "items": results,
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/videos")
def list_videos() -> dict[str, list[dict[str, Any]]]:
    records = load_records()
    records.sort(key=lambda item: item.get("createdAt", ""), reverse=True)
    return {"items": records}


@app.post("/api/videos/upload")
async def upload_videos(files: list[UploadFile] = File(...)) -> dict[str, list[dict[str, Any]]]:
    if not files:
        raise HTTPException(status_code=400, detail="Please upload at least one video file.")

    records: list[dict[str, Any]] = []

    for file in files:
        record = prepare_video_record(file)
        append_record(record)
        records.append(record)

    return {"items": records}


@app.get("/api/videos/{video_id}")
def get_video(video_id: str) -> dict[str, Any]:
    record = next((item for item in load_records() if item["id"] == video_id), None)

    if record is None:
        raise HTTPException(status_code=404, detail="Video not found.")

    return record


@app.delete("/api/videos/{video_id}")
def delete_video(video_id: str) -> dict[str, str]:
    target = remove_record(video_id)
    video_name = Path(target["videoUrl"]).name
    video_path = UPLOAD_DIR / video_name
    cover_name = Path(target["coverUrl"]).name if target.get("coverUrl") else None
    cover_path = COVER_DIR / cover_name if cover_name else None

    video_path.unlink(missing_ok=True)

    if cover_path:
        cover_path.unlink(missing_ok=True)

    remove_analysis_cache_for_video(video_id)

    return {"status": "deleted"}


@app.post("/api/task3/inputs")
def create_task3_input(payload: Task3InputCreateRequest) -> dict[str, Any]:
    record = create_task3_input_record(payload)
    records = load_task3_inputs()
    records.insert(0, record)
    save_task3_inputs(records)
    return record


@app.get("/api/task3/inputs/{input_id}")
def get_task3_input(input_id: str) -> dict[str, Any]:
    return get_task3_input_record(input_id)


@app.put("/api/task3/inputs/{input_id}")
def update_task3_input(input_id: str, payload: Task3InputUpdateRequest) -> dict[str, Any]:
    records = load_task3_inputs()
    target = next((item for item in records if item.get("id") == input_id), None)

    if target is None:
        raise HTTPException(status_code=404, detail="Task3 input not found.")

    updates = payload.model_dump(exclude_unset=True)
    if "materials" in updates and updates["materials"] is not None:
        updates["materials"] = [
            task3_material_from_payload(Task3MaterialPayload(**item))
            if isinstance(item, dict)
            else task3_material_from_payload(item)
            for item in updates["materials"]
        ]

    target.update(updates)
    target["updatedAt"] = datetime.now(UTC).isoformat()
    save_task3_inputs(records)
    return target


@app.post("/api/task3/inputs/{input_id}/materials")
async def upload_task3_materials(input_id: str, files: list[UploadFile] = File(...)) -> dict[str, Any]:
    records = load_task3_inputs()
    target = next((item for item in records if item.get("id") == input_id), None)

    if target is None:
        raise HTTPException(status_code=404, detail="Task3 input not found.")

    materials = target.setdefault("materials", [])
    saved_items: list[dict[str, Any]] = []

    for file in files:
        if not file.filename:
            continue

        extension = Path(file.filename).suffix.lower()
        if extension not in TASK3_ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(TASK3_ALLOWED_EXTENSIONS))
            raise HTTPException(status_code=400, detail=f"{file.filename} is not supported. Allowed types: {allowed}")

        material_id = uuid4().hex
        stored_name = f"{material_id}{extension}"
        destination = TASK3_MATERIAL_DIR / stored_name
        save_upload_file(file, destination)
        file.file.close()

        if extension in {".mp4", ".mov"}:
            material_type = "video"
        elif extension == ".txt":
            material_type = "text"
        else:
            material_type = "image"

        item = {
            "id": material_id,
            "type": material_type,
            "name": file.filename,
            "url": f"/media/task3_materials/{stored_name}",
            "text": read_text_file_best_effort(destination) if material_type == "text" else None,
            "tags": [],
            "createdAt": datetime.now(UTC).isoformat(),
        }
        materials.append(item)
        saved_items.append(item)

    target["updatedAt"] = datetime.now(UTC).isoformat()
    save_task3_inputs(records)
    return {"items": saved_items, "input": target}


@app.post("/api/task3/inputs/{input_id}/analyze")
def analyze_task3(input_id: str, payload: Task3AnalyzeRequest) -> dict[str, Any]:
    input_record = get_task3_input_record(input_id)
    analysis_record = analyze_task3_input(input_record, payload.settings)
    records = load_task3_analysis_records()
    records.insert(0, analysis_record)
    save_task3_analysis_records(records)
    return analysis_record


@app.get("/api/task3/analysis/{analysis_id}")
def get_task3_analysis(analysis_id: str) -> dict[str, Any]:
    record = next((item for item in load_task3_analysis_records() if item.get("id") == analysis_id), None)

    if record is None:
        raise HTTPException(status_code=404, detail="Task3 analysis not found.")

    return record


@app.put("/api/task3/analysis/{analysis_id}/gaps")
def update_task3_gaps(analysis_id: str, payload: Task3GapUpdateRequest) -> dict[str, Any]:
    records = load_task3_analysis_records()
    target = next((item for item in records if item.get("id") == analysis_id), None)

    if target is None:
        raise HTTPException(status_code=404, detail="Task3 analysis not found.")

    target["gaps"] = payload.gaps
    target["summary"] = "内容完整无缺口" if not payload.gaps else f"当前保留 {len(payload.gaps)} 个素材缺口。"
    save_task3_analysis_records(records)
    return target

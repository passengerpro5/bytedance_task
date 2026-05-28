from __future__ import annotations

import argparse
import base64
import json
import logging
import mimetypes
import os
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "backend_data"
VIDEO_DB_PATH = DATA_DIR / "videos.json"
ANALYSIS_CACHE_PATH = DATA_DIR / "analysis_cache.json"
DECOMPOSITION_DIR = DATA_DIR / "decompositions"
FRAME_DIR = DATA_DIR / "decomposition_frames"
ENV_PATH = ROOT_DIR / ".env"
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_UPLOAD_BASE_URL = "https://generativelanguage.googleapis.com/upload/v1beta"
GEMINI_INLINE_LIMIT_BYTES = 18 * 1024 * 1024
LOG_DIR = DATA_DIR / "logs"
DECOMPOSITION_LOG_PATH = LOG_DIR / "decomposition.log"


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


@dataclass
class LlmConfig:
    api_base_url: str
    api_key: str
    model: str
    endpoint: str = "/chat/completions"
    temperature: float = 0.2
    timeout_seconds: int = 120
    provider: str = "openai-compatible"
    model_type: str = "chat"


@dataclass
class SpeechAsrConfig:
    api_base_url: str
    app_key: str
    access_key: str
    resource_id: str
    timeout_seconds: int = 120


def load_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def save_json_file(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        values[key.strip()] = value

    return values


def load_llm_config(config_path: Path | None = None) -> LlmConfig:
    env_values = {
        **parse_env_file(ENV_PATH),
        **os.environ,
    }
    file_values = load_json_file(config_path, {}) if config_path else {}

    api_base_url = (
        file_values.get("apiBaseUrl")
        or file_values.get("api_base_url")
        or env_values.get("LLM_API_BASE_URL")
        or env_values.get("CHAT_API_URL")
        or ""
    ).rstrip("/")
    api_key = (
        file_values.get("apiKey")
        or file_values.get("api_key")
        or file_values.get("chatApiKey")
        or env_values.get("CHAT_API_KEY")
        or env_values.get("LLM_API_KEY")
        or ""
    )
    model = (
        file_values.get("model")
        or file_values.get("chatModel")
        or env_values.get("CHAT_MODEL")
        or env_values.get("LLM_MODEL")
        or ""
    )
    endpoint = (
        file_values.get("endpoint")
        or file_values.get("chatApiEndpoint")
        or env_values.get("CHAT_API_ENDPOINT")
        or env_values.get("LLM_API_ENDPOINT")
        or "/chat/completions"
    )
    temperature = float(file_values.get("temperature") or env_values.get("LLM_TEMPERATURE") or 0.2)
    timeout_seconds = int(file_values.get("timeoutSeconds") or env_values.get("LLM_TIMEOUT_SECONDS") or 120)

    if not api_base_url:
        raise ValueError("Missing LLM API base URL. Set LLM_API_BASE_URL or CHAT_API_URL.")
    if not api_key:
        raise ValueError("Missing LLM API key. Set LLM_API_KEY or apiKey in the config JSON.")
    if not model:
        raise ValueError("Missing LLM model. Set LLM_MODEL or model in the config JSON.")

    return LlmConfig(
        api_base_url=api_base_url,
        api_key=api_key,
        model=model,
        endpoint=endpoint if endpoint.startswith("/") else f"/{endpoint}",
        temperature=temperature,
        timeout_seconds=timeout_seconds,
        provider=str(file_values.get("provider") or env_values.get("LLM_PROVIDER") or "openai-compatible"),
        model_type="chat",
    )


def get_nested_value(values: dict[str, Any], *keys: str) -> Any:
    current: Any = values
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def load_commercial_model_config(
    *,
    model_type: str,
    config_path: Path | None = None,
) -> LlmConfig:
    env_values = {
        **parse_env_file(ENV_PATH),
        **os.environ,
    }
    file_values = load_json_file(config_path, {}) if config_path else {}

    if model_type == "speech-recognition":
        api_base_url = (
            get_nested_value(file_values, "speechRecognition", "apiBaseUrl")
            or file_values.get("speechRecognitionApiUrl")
            or file_values.get("speech_api_base_url")
            or env_values.get("SPEECH_RECOGNITION_API_URL")
            or env_values.get("CHAT_API_URL")
            or env_values.get("LLM_API_BASE_URL")
            or ""
        ).rstrip("/")
        api_key = (
            get_nested_value(file_values, "speechRecognition", "apiKey")
            or file_values.get("speechRecognitionApiKey")
            or env_values.get("SPEECH_RECOGNITION_API_KEY")
            or env_values.get("CHAT_API_KEY")
            or env_values.get("LLM_API_KEY")
            or ""
        )
        model = (
            get_nested_value(file_values, "speechRecognition", "model")
            or file_values.get("speechRecognitionModel")
            or env_values.get("SPEECH_RECOGNITION_MODEL")
            or env_values.get("CHAT_MODEL")
            or env_values.get("LLM_MODEL")
            or ""
        )
        endpoint = (
            get_nested_value(file_values, "speechRecognition", "endpoint")
            or file_values.get("speechRecognitionEndpoint")
            or env_values.get("SPEECH_RECOGNITION_API_ENDPOINT")
            or env_values.get("CHAT_API_ENDPOINT")
            or env_values.get("LLM_API_ENDPOINT")
            or "/chat/completions"
        )
        provider = (
            get_nested_value(file_values, "speechRecognition", "provider")
            or file_values.get("speechRecognitionProvider")
            or env_values.get("SPEECH_RECOGNITION_PROVIDER")
            or "openai-compatible"
        )
    elif model_type == "image-recognition":
        api_base_url = (
            get_nested_value(file_values, "imageRecognition", "apiBaseUrl")
            or file_values.get("ocrRecognitionApiUrl")
            or file_values.get("imageRecognitionApiUrl")
            or file_values.get("visionApiBaseUrl")
            or env_values.get("OCR_RECOGNITION_API_URL")
            or env_values.get("IMAGE_RECOGNITION_API_URL")
            or env_values.get("VISION_API_BASE_URL")
            or env_values.get("CHAT_API_URL")
            or env_values.get("LLM_API_BASE_URL")
            or ""
        ).rstrip("/")
        api_key = (
            get_nested_value(file_values, "imageRecognition", "apiKey")
            or file_values.get("ocrRecognitionApiKey")
            or file_values.get("imageRecognitionApiKey")
            or file_values.get("visionApiKey")
            or env_values.get("OCR_RECOGNITION_API_KEY")
            or env_values.get("IMAGE_RECOGNITION_API_KEY")
            or env_values.get("VISION_API_KEY")
            or env_values.get("CHAT_API_KEY")
            or env_values.get("LLM_API_KEY")
            or ""
        )
        model = (
            get_nested_value(file_values, "imageRecognition", "model")
            or file_values.get("ocrRecognitionModel")
            or file_values.get("imageRecognitionModel")
            or file_values.get("visionModel")
            or env_values.get("OCR_RECOGNITION_MODEL")
            or env_values.get("IMAGE_RECOGNITION_MODEL")
            or env_values.get("VISION_MODEL")
            or env_values.get("CHAT_MODEL")
            or env_values.get("LLM_MODEL")
            or ""
        )
        endpoint = (
            get_nested_value(file_values, "imageRecognition", "endpoint")
            or file_values.get("ocrRecognitionEndpoint")
            or file_values.get("imageRecognitionEndpoint")
            or env_values.get("OCR_RECOGNITION_API_ENDPOINT")
            or env_values.get("IMAGE_RECOGNITION_API_ENDPOINT")
            or env_values.get("CHAT_API_ENDPOINT")
            or env_values.get("LLM_API_ENDPOINT")
            or "/chat/completions"
        )
        provider = (
            get_nested_value(file_values, "imageRecognition", "provider")
            or file_values.get("ocrRecognitionProvider")
            or file_values.get("imageRecognitionProvider")
            or env_values.get("OCR_RECOGNITION_PROVIDER")
            or env_values.get("IMAGE_RECOGNITION_PROVIDER")
            or "openai-compatible"
        )
    else:
        return load_llm_config(config_path)

    temperature = float(file_values.get("temperature") or env_values.get("LLM_TEMPERATURE") or 0.2)
    timeout_seconds = int(file_values.get("timeoutSeconds") or env_values.get("LLM_TIMEOUT_SECONDS") or 120)

    if not api_base_url:
        raise ValueError(f"Missing {model_type} API base URL.")
    if not api_key:
        raise ValueError(f"Missing {model_type} API key.")
    if not model:
        raise ValueError(f"Missing {model_type} model.")

    return LlmConfig(
        api_base_url=api_base_url,
        api_key=str(api_key),
        model=str(model),
        endpoint=str(endpoint) if str(endpoint).startswith("/") else f"/{endpoint}",
        temperature=temperature,
        timeout_seconds=timeout_seconds,
        provider=str(provider),
        model_type=model_type,
    )


def load_speech_asr_config(config_path: Path | None = None) -> SpeechAsrConfig:
    env_values = {
        **parse_env_file(ENV_PATH),
        **os.environ,
    }
    file_values = load_json_file(config_path, {}) if config_path else {}
    base_url = (
        get_nested_value(file_values, "speechRecognition", "apiBaseUrl")
        or file_values.get("speechRecognitionApiUrl")
        or env_values.get("SPEECH_RECOGNITION_API_URL")
        or "https://openspeech.bytedance.com/api/v3"
    ).rstrip("/")
    app_key = (
        get_nested_value(file_values, "speechRecognition", "appKey")
        or file_values.get("speechRecognitionAppKey")
        or env_values.get("SPEECH_RECOGNITION_APP_KEY")
        or env_values.get("SPEECH_RECOGNITION_APP_ID")
        or ""
    )
    access_key = (
        get_nested_value(file_values, "speechRecognition", "accessKey")
        or file_values.get("speechRecognitionApiKey")
        or env_values.get("SPEECH_RECOGNITION_API_KEY")
        or env_values.get("SPEECH_RECOGNITION_ACCESS_KEY")
        or ""
    )
    resource_id = (
        get_nested_value(file_values, "speechRecognition", "resourceId")
        or file_values.get("speechRecognitionModel")
        or env_values.get("SPEECH_RECOGNITION_MODEL")
        or "volc.seedasr.auc"
    )
    timeout_seconds = int(file_values.get("timeoutSeconds") or env_values.get("LLM_TIMEOUT_SECONDS") or 120)

    if not app_key:
        raise ValueError("Missing speech ASR app key. Set SPEECH_RECOGNITION_APP_KEY.")
    if not access_key:
        raise ValueError("Missing speech ASR access key. Set SPEECH_RECOGNITION_API_KEY.")
    if not resource_id:
        raise ValueError("Missing speech ASR resource id. Set SPEECH_RECOGNITION_MODEL.")

    return SpeechAsrConfig(
        api_base_url=str(base_url),
        app_key=str(app_key),
        access_key=str(access_key),
        resource_id=str(resource_id),
        timeout_seconds=timeout_seconds,
    )


def load_gemini_video_config(config_path: Path | None = None) -> LlmConfig:
    env_values = {
        **parse_env_file(ENV_PATH),
        **os.environ,
    }
    file_values = load_json_file(config_path, {}) if config_path else {}

    api_base_url = (
        file_values.get("geminiApiBaseUrl")
        or file_values.get("videoRecognitionApiUrl")
        or file_values.get("apiBaseUrl")
        or env_values.get("GEMINI_API_BASE_URL")
        or env_values.get("VIDEO_RECOGNITION_API_URL")
        or GEMINI_API_BASE_URL
    ).rstrip("/")
    api_key = (
        file_values.get("geminiApiKey")
        or file_values.get("videoRecognitionApiKey")
        or file_values.get("apiKey")
        or env_values.get("GEMINI_API_KEY")
        or env_values.get("GOOGLE_API_KEY")
        or env_values.get("VIDEO_RECOGNITION_API_KEY")
        or env_values.get("LLM_API_KEY")
        or ""
    )
    model = (
        file_values.get("geminiModel")
        or file_values.get("videoRecognitionModel")
        or file_values.get("model")
        or env_values.get("GEMINI_MODEL")
        or env_values.get("VIDEO_RECOGNITION_MODEL")
        or "gemini-2.5-flash"
    )
    temperature = float(file_values.get("temperature") or env_values.get("LLM_TEMPERATURE") or 0.2)
    timeout_seconds = int(file_values.get("timeoutSeconds") or env_values.get("LLM_TIMEOUT_SECONDS") or 300)

    if not api_key:
        raise ValueError("Missing Gemini API key. Set GEMINI_API_KEY, GOOGLE_API_KEY, VIDEO_RECOGNITION_API_KEY, or apiKey.")
    if not model:
        raise ValueError("Missing Gemini video model. Set VIDEO_RECOGNITION_MODEL, GEMINI_MODEL, or model.")

    return LlmConfig(
        api_base_url=api_base_url,
        api_key=api_key,
        model=model,
        endpoint="",
        temperature=temperature,
        timeout_seconds=timeout_seconds,
        provider="gemini",
        model_type="video-recognition",
    )


def call_chat_completion(config: LlmConfig, messages: list[dict[str, str]]) -> dict[str, Any]:
    url = f"{config.api_base_url}{config.endpoint}"
    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": config.temperature,
        "response_format": {"type": "json_object"},
    }
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=config.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM API returned {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"LLM API request failed: {exc.reason}") from exc


def call_openai_compatible_json_model(
    *,
    config: LlmConfig,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    url = f"{config.api_base_url}{config.endpoint}"
    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": config.temperature,
        "response_format": {"type": "json_object"},
    }
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    return request_json(request, config.timeout_seconds)


def call_commercial_structured_model(
    *,
    config: LlmConfig,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    provider = config.provider.lower()

    if provider in {"openai-compatible", "openai", "qwen", "dashscope", "doubao", "ark", "bytedance", "volcengine"}:
        return call_openai_compatible_json_model(config=config, messages=messages)

    raise ValueError(
        f"Unsupported provider for structured decomposition: {config.provider}. "
        "Use openai-compatible, openai, qwen, dashscope, doubao, ark, bytedance, or volcengine."
    )


def request_json(request: Request, timeout_seconds: int) -> dict[str, Any]:
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        hint = ""
        if exc.code == 404 and "InvalidEndpointOrModel" in detail:
            hint = (
                " Hint: The model field must be the provider's callable model ID "
                "or inference endpoint ID, not the display name shown in the console."
            )
        raise RuntimeError(f"API returned {exc.code}: {detail}{hint}") from exc
    except URLError as exc:
        raise RuntimeError(f"API request failed: {exc.reason}") from exc


def request_text_with_headers(request: Request, timeout_seconds: int) -> tuple[str, dict[str, str]]:
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return response.read().decode("utf-8"), dict(response.headers.items())
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API returned {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"API request failed: {exc.reason}") from exc


def extract_gemini_response_text(response: dict[str, Any]) -> str:
    candidates = response.get("candidates") or []
    if not candidates:
        return ""

    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    text_parts = [part.get("text", "") for part in parts if isinstance(part, dict)]
    return "\n".join(part for part in text_parts if part)


def extract_response_text(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""

    message = choices[0].get("message") or {}
    content = message.get("content")

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts)

    return ""


def parse_json_or_wrap(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {"items": parsed}
    except json.JSONDecodeError:
        return {"rawText": text}


def resolve_video_file_path(video_record: dict[str, Any]) -> Path:
    video_name = Path(str(video_record.get("videoUrl") or "")).name

    if not video_name:
        raise ValueError("Video file path is missing.")

    video_path = DATA_DIR / "uploads" / video_name

    if not video_path.exists():
        raise FileNotFoundError(f"Video file does not exist: {video_name}")

    return video_path


def guess_video_mime_type(video_path: Path) -> str:
    guessed_type = mimetypes.guess_type(video_path.name)[0]
    return guessed_type or "video/mp4"


def guess_image_mime_type(image_path: Path) -> str:
    guessed_type = mimetypes.guess_type(image_path.name)[0]
    return guessed_type or "image/jpeg"


def encode_image_data_url(image_path: Path) -> str:
    mime_type = guess_image_mime_type(image_path)
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def resolve_speech_url(base_url: str, endpoint: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/recognize/flash") or normalized.endswith("/submit") or normalized.endswith("/query"):
        return normalized
    if normalized.endswith("/auc/bigmodel"):
        return f"{normalized}/{endpoint}"
    if normalized.endswith("/api/v3"):
        return f"{normalized}/auc/bigmodel/{endpoint}"
    return f"{normalized}/api/v3/auc/bigmodel/{endpoint}"


def extract_audio_wav(
    *,
    video_record: dict[str, Any],
    video_path: Path,
) -> Path:
    safe_video_id = "".join(
        character if character.isalnum() or character in {"-", "_"} else "_"
        for character in str(video_record.get("id") or video_path.stem)
    )
    audio_dir = DATA_DIR / "decomposition_audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / f"{safe_video_id}.wav"
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "wav",
        str(audio_path),
    ]

    try:
        run_command(command)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"Failed to extract audio for speech recognition: {exc}") from exc

    if not audio_path.exists() or audio_path.stat().st_size == 0:
        raise RuntimeError("No audio was extracted for speech recognition.")

    return audio_path


def build_asr_headers(config: SpeechAsrConfig, request_id: str) -> dict[str, str]:
    return {
        "X-Api-App-Key": config.app_key,
        "X-Api-Access-Key": config.access_key,
        "X-Api-Resource-Id": config.resource_id,
        "X-Api-Request-Id": request_id,
        "Content-Type": "application/json",
    }


def extract_asr_text(response: dict[str, Any]) -> str:
    data = response.get("data")
    if isinstance(data, dict):
        for key in ("text", "result", "utterances"):
            value = data.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, list):
                parts = []
                for item in value:
                    if isinstance(item, dict):
                        parts.append(str(item.get("text") or item.get("utterance") or ""))
                    else:
                        parts.append(str(item))
                return "\n".join(part for part in parts if part)
    for key in ("text", "result"):
        value = response.get(key)
        if isinstance(value, str):
            return value
    return ""


def call_speech_asr(
    *,
    config: SpeechAsrConfig,
    audio_path: Path,
    duration_ms: int,
) -> dict[str, Any]:
    request_id = str(uuid.uuid4())
    headers = build_asr_headers(config, request_id)
    audio_payload = {
        "user": {"uid": "hot_engine"},
        "audio": {
            "data": base64.b64encode(audio_path.read_bytes()).decode("ascii"),
            "format": "wav",
        },
    }

    if duration_ms and duration_ms <= 30_000:
        flash_url = resolve_speech_url(config.api_base_url, "recognize/flash")
        request = Request(
            flash_url,
            data=json.dumps(audio_payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        response = request_json(request, config.timeout_seconds)
        return {"mode": "flash", "requestId": request_id, "response": response, "text": extract_asr_text(response)}

    submit_url = resolve_speech_url(config.api_base_url, "submit")
    query_base = config.api_base_url
    if config.api_base_url.rstrip("/").endswith("/submit"):
        query_base = config.api_base_url.rstrip("/")[: -len("/submit")]
    query_url = resolve_speech_url(query_base, "query")
    submit_request = Request(
        submit_url,
        data=json.dumps(audio_payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    submit_response = request_json(submit_request, config.timeout_seconds)

    last_response: dict[str, Any] = {}
    for _ in range(60):
        time.sleep(1)
        query_request = Request(
            query_url,
            data=json.dumps({}, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        last_response = request_json(query_request, config.timeout_seconds)
        text = extract_asr_text(last_response)
        if text:
            return {
                "mode": "async",
                "requestId": request_id,
                "submitResponse": submit_response,
                "response": last_response,
                "text": text,
            }

    raise RuntimeError(f"Speech ASR async query timed out: {last_response}")


def extract_structured_frames(
    *,
    video_record: dict[str, Any],
    video_path: Path,
    frame_interval: int,
    max_frames: int = 8,
) -> list[Path]:
    frame_interval = max(int(frame_interval or 1), 1)
    safe_video_id = "".join(
        character if character.isalnum() or character in {"-", "_"} else "_"
        for character in str(video_record.get("id") or video_path.stem)
    )
    frame_dir = FRAME_DIR / safe_video_id / f"interval_{frame_interval}"
    frame_dir.mkdir(parents=True, exist_ok=True)
    output_pattern = frame_dir / "frame_%03d.jpg"

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"fps=1/{frame_interval},scale=768:-1:force_original_aspect_ratio=decrease",
        "-frames:v",
        str(max_frames),
        "-q:v",
        "3",
        str(output_pattern),
    ]

    try:
        run_command(command)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"Failed to extract structured vision frames: {exc}") from exc

    frames = sorted(frame_dir.glob("frame_*.jpg"))[:max_frames]
    if not frames:
        raise RuntimeError("No frames were extracted for structured vision decomposition.")

    return frames


def find_video_record(video_id: str | None = None, video_name: str | None = None) -> dict[str, Any]:
    records = load_json_file(VIDEO_DB_PATH, [])

    if video_id:
        match = next((record for record in records if record.get("id") == video_id), None)
        if match:
            return match

    if video_name:
        match = next((record for record in records if record.get("name") == video_name), None)
        if match:
            return match

    raise ValueError("Video record not found.")


def find_latest_analysis(video_id: str, video_record: dict[str, Any]) -> dict[str, Any] | None:
    cached_records = [
        record
        for record in load_json_file(ANALYSIS_CACHE_PATH, [])
        if record.get("videoId") == video_id
    ]
    cached_records.sort(key=lambda item: item.get("cachedAt", ""), reverse=True)

    if cached_records:
        return cached_records[0].get("analysis")

    return video_record.get("analysis")


def normalize_settings(settings: dict[str, Any]) -> dict[str, Any]:
    if "steps" in settings:
        fast_steps = settings.get("steps", {}).get("fast") or []
        direct_video_deep_steps = (
            settings.get("steps", {}).get("directVideoDeep")
            or settings.get("steps", {}).get("deep")
            or []
        )
        structured_deep_steps = settings.get("steps", {}).get("structuredDeep") or []
    else:
        fast_steps = settings.get("fastSteps") or []
        direct_video_deep_steps = settings.get("directVideoDeepSteps") or settings.get("deepSteps") or []
        structured_deep_steps = settings.get("structuredDeepSteps") or []

    return {
        "inputMode": settings.get("inputMode") or settings.get("input_mode") or "direct-video",
        "methodName": settings.get("methodName") or "fast",
        "frameInterval": settings.get("frameInterval") or 5,
        "steps": {
            "fast": fast_steps,
            "directVideoDeep": direct_video_deep_steps,
            "structuredDeep": structured_deep_steps,
        },
    }


def resolve_skill_text(step: dict[str, Any], settings_dir: Path) -> str:
    skill_key = step.get("skillKey") or step.get("skill_key")
    skill_text = step.get("skill") or ""

    if not skill_key:
        return skill_text

    candidate_paths = [
        settings_dir / str(skill_key),
        ROOT_DIR / str(skill_key),
        ROOT_DIR / "skills" / str(skill_key),
    ]

    for path in candidate_paths:
        if path.exists() and path.suffix.lower() == ".md":
            return path.read_text(encoding="utf-8")

    return skill_text or f"Use skill referenced by key: {skill_key}"


def resolve_prompt_text(step: dict[str, Any], settings_dir: Path) -> str:
    prompt_key = step.get("promptKey") or step.get("prompt_key")
    prompt_text = step.get("prompt") or ""

    if not prompt_key:
        return prompt_text

    candidate_paths = [
        settings_dir / str(prompt_key),
        ROOT_DIR / str(prompt_key),
        ROOT_DIR / "prompts" / str(prompt_key),
    ]

    for path in candidate_paths:
        if path.exists() and path.suffix.lower() in {".txt", ".md"}:
            return path.read_text(encoding="utf-8")

    return prompt_text


def build_video_context(video_record: dict[str, Any], analysis: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "video": {
            "id": video_record.get("id"),
            "name": video_record.get("name"),
            "durationMs": video_record.get("durationMs"),
            "width": video_record.get("width"),
            "height": video_record.get("height"),
            "fps": video_record.get("fps"),
            "sizeBytes": video_record.get("sizeBytes"),
            "videoUrl": video_record.get("videoUrl"),
            "coverUrl": video_record.get("coverUrl"),
        },
        "analysis": analysis or {},
    }


def build_step_messages(
    *,
    step: dict[str, Any],
    prompt_text: str,
    skill_text: str,
    video_context: dict[str, Any],
    previous_handoffs: list[dict[str, Any]],
) -> list[dict[str, str]]:
    prompt = prompt_text or "请拆解该视频内容。"
    return [
        {
            "role": "system",
            "content": (
                "你是短视频爆款迁移引擎的视频拆解专家。"
                "你必须输出 JSON object，不要输出 markdown。"
                "拆解时关注编导结构、镜头段功能、字幕/口播信息、包装表达和可迁移槽位。\n\n"
                f"Skill:\n{skill_text}"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "task": prompt,
                    "step": {
                        "id": step.get("id"),
                        "name": step.get("name"),
                        "description": step.get("description"),
                        "modelType": step.get("modelType") or step.get("model_type"),
                    },
                    "videoContext": video_context,
                    "previousHandoffs": previous_handoffs,
                    "requiredOutput": {
                        "summary": "本步骤拆解摘要",
                        "findings": ["关键发现"],
                        "structureSlots": ["可迁移结构槽位"],
                        "handoff": {
                            "summary": "给后续步骤使用的精简结论",
                            "timelineAnchors": ["时间锚点"],
                            "transferableSlots": ["可迁移槽位"],
                            "constraints": ["迁移约束"],
                            "uncertainPoints": ["不确定点"],
                            "conflicts": ["与前序 handoff 冲突之处"],
                        },
                        "risks": ["不确定或需补充的信息"],
                    },
                },
                ensure_ascii=False,
            ),
        },
    ]


def build_vision_step_messages(
    *,
    step: dict[str, Any],
    prompt_text: str,
    skill_text: str,
    video_context: dict[str, Any],
    previous_handoffs: list[dict[str, Any]],
    frames: list[Path],
) -> list[dict[str, Any]]:
    messages = build_step_messages(
        step=step,
        prompt_text=prompt_text,
        skill_text=skill_text,
        video_context={
            **video_context,
            "sampledFrames": [
                {
                    "index": index,
                    "fileName": frame.name,
                    "samplingNote": "Frames are sampled from the source video in chronological order.",
                }
                for index, frame in enumerate(frames, start=1)
            ],
        },
        previous_handoffs=previous_handoffs,
    )
    user_payload = messages[1]["content"]
    content: list[dict[str, Any]] = [{"type": "text", "text": user_payload}]

    for frame in frames:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": encode_image_data_url(frame)},
            }
        )

    return [
        messages[0],
        {
            "role": "user",
            "content": content,
        },
    ]


def build_speech_step_output(
    *,
    step: dict[str, Any],
    prompt_text: str,
    skill_text: str,
    video_context: dict[str, Any],
    previous_handoffs: list[dict[str, Any]],
    asr_result: dict[str, Any],
) -> dict[str, Any]:
    transcript = asr_result.get("text") or ""
    preview = transcript[:500]
    return {
        "summary": preview or "未识别到有效语音文本。",
        "findings": [
            {
                "type": "speechTranscript",
                "text": transcript,
                "asrMode": asr_result.get("mode"),
            }
        ],
        "transcript": transcript,
        "asr": {
            "mode": asr_result.get("mode"),
            "requestId": asr_result.get("requestId"),
            "rawResponse": asr_result.get("response"),
            "submitResponse": asr_result.get("submitResponse"),
        },
        "structureSlots": [],
        "handoff": {
            "summary": preview,
            "timelineAnchors": [],
            "transferableSlots": [],
            "constraints": ["后续步骤可基于 transcript 判断脚本段落、卖点顺序和口播节奏。"],
            "uncertainPoints": [] if transcript else ["ASR 未返回有效文本。"],
            "conflicts": [],
        },
        "risks": [] if transcript else ["未识别到语音内容，可能是视频无声、音轨缺失或 ASR 调用失败。"],
        "debugContext": {
            "step": {
                "id": step.get("id"),
                "name": step.get("name"),
            },
            "prompt": prompt_text,
            "skillLength": len(skill_text),
            "videoContext": compact_value(video_context),
            "previousHandoffs": compact_value(previous_handoffs),
        },
    }


def build_fast_required_output_schema() -> dict[str, Any]:
    return {
        "summary": "一句话概括样例视频的可迁移结构。",
        "scriptStructure": [
            {
                "slotId": "hook | development | proof | climax | cta",
                "name": "开头 hook / 中段展开 / 证明或演示 / 高潮 / 结尾 CTA",
                "timeRange": "例如 0-3s",
                "scriptText": "对应口播、字幕或画面信息摘要",
                "intent": "该段落的编导意图",
                "contentRole": "attention | explanation | proof | conversion",
                "transferRule": "迁移到新主题时应保留的结构规则",
                "requiredMaterial": ["需要的新素材槽位"],
            }
        ],
        "rhythmStructure": {
            "shotCount": "镜头段数量",
            "avgShotDurationSec": "平均镜头时长，无法精确时可估算",
            "cutFrequency": "low | medium | high",
            "tempoCurve": [
                {
                    "timeRange": "例如 0-3s",
                    "tempo": "slow | medium | fast",
                    "reason": "节奏判断依据",
                }
            ],
            "climax": {
                "timeRange": "高潮出现位置",
                "type": "效果展示 / 价格刺激 / 情绪反转 / 卖点集中",
                "reason": "为什么这里是高潮",
            },
        },
        "packagingStructure": {
            "subtitle": {
                "density": "none | low | medium | high",
                "position": "字幕主要位置",
                "style": "字幕视觉样式",
                "highlightWords": ["被强调的关键词"],
            },
            "titleBar": {
                "exists": True,
                "position": "top | middle | bottom | none",
                "contentType": "痛点标题 / 卖点标题 / 结果承诺 / 促销信息",
            },
            "stickers": [
                {
                    "type": "贴纸或强调元素类型",
                    "timeRange": "出现时间",
                    "purpose": "作用",
                }
            ],
            "transitions": ["主要转场方式"],
            "coverStyle": {
                "layout": "封面构图",
                "copyPattern": "封面文案模式",
                "visualFocus": "主体视觉焦点",
            },
        },
        "transferableSlots": [
            {
                "slotId": "hook | product-closeup | usage | comparison | cta | subtitle-fill | package-card",
                "slotName": "可迁移槽位名称",
                "sourceStructureTypes": ["script", "rhythm", "packaging"],
                "timeRange": "样例中对应时间",
                "requiredMaterial": ["满足该槽位需要的素材"],
                "fallbackOptions": ["文案/字幕补全", "包装补全", "结构重排", "现有素材重组复用"],
            }
        ],
        "risks": ["无法从视频中确定的信息或需要人工确认之处"],
    }


def compact_value(value: Any, *, max_text_length: int = 320) -> Any:
    if isinstance(value, str):
        return value if len(value) <= max_text_length else f"{value[:max_text_length]}..."
    if isinstance(value, list):
        return [compact_value(item, max_text_length=max_text_length) for item in value[:8]]
    if isinstance(value, dict):
        return {
            str(key): compact_value(item, max_text_length=max_text_length)
            for key, item in list(value.items())[:12]
        }
    return value


def build_step_handoff(step_record: dict[str, Any]) -> dict[str, Any]:
    output = step_record.get("output") or {}
    handoff = output.get("handoff") if isinstance(output, dict) else None

    if not isinstance(handoff, dict):
        handoff = {
            "summary": output.get("summary") if isinstance(output, dict) else "",
            "timelineAnchors": output.get("timelineAnchors", []) if isinstance(output, dict) else [],
            "transferableSlots": output.get("transferableSlots", []) if isinstance(output, dict) else [],
            "constraints": output.get("constraints", []) if isinstance(output, dict) else [],
            "uncertainPoints": output.get("risks", []) if isinstance(output, dict) else [],
            "conflicts": output.get("conflicts", []) if isinstance(output, dict) else [],
        }

    return {
        "stepIndex": step_record.get("index"),
        "stepId": step_record.get("id"),
        "stepName": step_record.get("name"),
        "handoff": compact_value(handoff),
    }


def collect_previous_handoffs(step_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [build_step_handoff(step_record) for step_record in step_records]


def build_fast_gemini_prompt(
    *,
    step: dict[str, Any],
    prompt_text: str,
    skill_text: str,
    video_context: dict[str, Any],
    language: str,
) -> str:
    prompt = prompt_text or "请一次性完成样例短视频结构拆解。"
    payload = {
        "task": prompt,
        "language": language,
        "step": {
            "id": step.get("id"),
            "name": step.get("name"),
            "description": step.get("description"),
            "modelType": step.get("modelType") or step.get("model_type") or "video-recognition",
        },
        "videoContext": video_context,
        "skill": skill_text,
        "requiredOutput": build_fast_required_output_schema(),
        "hardRules": [
            "必须只输出 JSON object，不要输出 markdown。",
            "必须至少覆盖脚本/段落结构、节奏结构、包装结构三类信息；无法确定时填写 unknown 并说明风险。",
            "所有结构段落都尽量给出 timeRange 和可迁移规则。",
            "transferableSlots 必须服务于后续素材匹配和结构迁移。",
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def build_video_step_gemini_prompt(
    *,
    step: dict[str, Any],
    prompt_text: str,
    skill_text: str,
    video_context: dict[str, Any],
    previous_handoffs: list[dict[str, Any]],
    language: str,
) -> str:
    prompt = prompt_text or "请直接观看样例短视频，完成当前步骤的视频结构拆解。"
    payload = {
        "task": prompt,
        "language": language,
        "step": {
            "id": step.get("id"),
            "name": step.get("name"),
            "description": step.get("description"),
            "modelType": step.get("modelType") or step.get("model_type") or "video-recognition",
        },
        "videoContext": video_context,
        "previousHandoffs": previous_handoffs,
        "skill": skill_text,
        "requiredOutput": {
            "summary": "本步骤拆解摘要",
            "findings": ["关键发现"],
            "timelineAnchors": [
                {
                    "timeRange": "例如 0-3s",
                    "slotId": "结构槽位 ID",
                    "role": "该时间段的结构作用",
                    "confidence": 0.8,
                }
            ],
            "structureSlots": ["本步骤识别出的可迁移结构槽位"],
            "transferableSlots": [
                {
                    "slotId": "hook | product-closeup | usage | comparison | cta | subtitle-fill | package-card",
                    "slotName": "可迁移槽位名称",
                    "requiredMaterial": ["满足该槽位需要的素材"],
                    "fallbackOptions": ["文案/字幕补全", "包装补全", "结构重排", "现有素材重组复用"],
                }
            ],
            "conflicts": ["如果你观察到的视频证据与 previousHandoffs 冲突，请写在这里"],
            "handoff": {
                "summary": "给后续步骤使用的精简结论",
                "timelineAnchors": ["关键时间锚点"],
                "transferableSlots": ["关键可迁移槽位"],
                "constraints": ["后续迁移必须保留的规则"],
                "uncertainPoints": ["不确定点"],
                "conflicts": ["与前序 handoff 冲突之处"],
            },
            "risks": ["不确定或需补充的信息"],
        },
        "hardRules": [
            "必须只输出 JSON object，不要输出 markdown。",
            "previousHandoffs 只作为参考，不能替代你对当前视频的重新观察。",
            "如果当前观察与 previousHandoffs 冲突，必须写入 conflicts。",
            "handoff 必须简洁，服务于后续步骤继续拆解。",
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def build_gemini_overview_prompt(
    *,
    video_context: dict[str, Any],
    step_results: list[dict[str, Any]],
    language: str,
) -> str:
    return json.dumps(
        {
            "task": f"请用{language}生成视频深度拆解概览，整合所有步骤结果。",
            "videoContext": video_context,
            "previousHandoffs": collect_previous_handoffs(step_results),
            "stepOutputs": [
                {
                    "index": item.get("index"),
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "output": compact_value(item.get("output") or {}, max_text_length=500),
                }
                for item in step_results
            ],
            "requiredOutput": {
                "overview": "整体拆解概览",
                "coreStructure": ["核心结构"],
                "migrationNotes": ["迁移到新内容时要保留的结构"],
                "materialGaps": ["潜在素材缺口"],
            },
            "hardRules": ["必须只输出 JSON object，不要输出 markdown。"],
        },
        ensure_ascii=False,
    )


def call_gemini_generate_content(
    *,
    config: LlmConfig,
    parts: list[dict[str, Any]],
) -> dict[str, Any]:
    model_name = config.model
    if model_name.startswith("models/"):
        model_name = model_name.removeprefix("models/")

    api_base_url = normalize_gemini_generate_base_url(config.api_base_url)
    query = urlencode({"key": config.api_key})
    url = f"{api_base_url}/models/{quote(model_name, safe='')}:generateContent?{query}"
    DECOMPOSITION_LOGGER.info(
        "gemini_generate model=%s base_url=%s resolved_base_url=%s parts=%s",
        model_name,
        config.api_base_url,
        api_base_url,
        [list(part.keys()) for part in parts],
    )
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": config.temperature,
            "responseMimeType": "application/json",
        },
    }
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return request_json(request, config.timeout_seconds)


def normalize_gemini_generate_base_url(api_base_url: str) -> str:
    normalized = api_base_url.rstrip("/")
    if normalized.endswith("/v1beta") or normalized.endswith("/v1"):
        return normalized
    if "aihubmix.com/gemini" in normalized:
        return f"{normalized}/v1beta"
    return normalized


def is_google_gemini_base_url(api_base_url: str) -> bool:
    return "generativelanguage.googleapis.com" in api_base_url


def upload_gemini_file(config: LlmConfig, video_path: Path, mime_type: str) -> dict[str, Any]:
    if not is_google_gemini_base_url(config.api_base_url):
        raise RuntimeError(
            "Gemini File API is only enabled for the official Google Gemini endpoint in this app. "
            "AIHubMix Gemini currently supports inline media here; use videos under 20MB or switch "
            "VIDEO_RECOGNITION_API_URL to https://generativelanguage.googleapis.com/v1beta."
        )

    upload_base = config.api_base_url.replace("generativelanguage.googleapis.com/v1beta", "generativelanguage.googleapis.com/upload/v1beta")
    if upload_base == config.api_base_url:
        upload_base = GEMINI_UPLOAD_BASE_URL

    start_url = f"{upload_base}/files?{urlencode({'key': config.api_key})}"
    file_size = video_path.stat().st_size
    DECOMPOSITION_LOGGER.info(
        "gemini_upload_start file=%s size=%s mime=%s upload_base=%s",
        video_path.name,
        file_size,
        mime_type,
        upload_base,
    )
    metadata = {"file": {"display_name": video_path.name}}
    start_request = Request(
        start_url,
        data=json.dumps(metadata, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(file_size),
            "X-Goog-Upload-Header-Content-Type": mime_type,
        },
        method="POST",
    )
    _, headers = request_text_with_headers(start_request, config.timeout_seconds)
    upload_url = headers.get("X-Goog-Upload-URL") or headers.get("x-goog-upload-url")

    if not upload_url:
        raise RuntimeError("Gemini File API did not return an upload URL.")

    upload_request = Request(
        upload_url,
        data=video_path.read_bytes(),
        headers={
            "Content-Length": str(file_size),
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
            "Content-Type": mime_type,
        },
        method="POST",
    )
    uploaded = request_json(upload_request, config.timeout_seconds)
    file_info = uploaded.get("file") or uploaded
    file_name = file_info.get("name")

    if not file_name:
        raise RuntimeError(f"Gemini File API returned invalid file metadata: {uploaded}")

    return wait_for_gemini_file(config, file_name)


def wait_for_gemini_file(config: LlmConfig, file_name: str) -> dict[str, Any]:
    url = f"{config.api_base_url}/{file_name}?{urlencode({'key': config.api_key})}"
    last_info: dict[str, Any] = {}

    for attempt in range(30):
        request = Request(url, headers={"Content-Type": "application/json"}, method="GET")
        last_info = request_json(request, config.timeout_seconds)
        state = (last_info.get("state") or "").upper()
        DECOMPOSITION_LOGGER.info(
            "gemini_file_state file=%s attempt=%s state=%s",
            file_name,
            attempt + 1,
            state or "UNKNOWN",
        )

        if state in {"ACTIVE", ""}:
            return last_info
        if state == "FAILED":
            raise RuntimeError(f"Gemini file processing failed: {last_info}")

        time.sleep(2)

    raise RuntimeError(f"Gemini file processing timed out: {last_info}")


def call_gemini_video_decomposition(
    *,
    config: LlmConfig,
    video_path: Path,
    prompt: str,
) -> dict[str, Any]:
    mime_type = guess_video_mime_type(video_path)
    file_size = video_path.stat().st_size

    if file_size <= GEMINI_INLINE_LIMIT_BYTES:
        DECOMPOSITION_LOGGER.info(
            "gemini_video_input mode=inline file=%s size=%s mime=%s",
            video_path.name,
            file_size,
            mime_type,
        )
        parts = [
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": base64.b64encode(video_path.read_bytes()).decode("ascii"),
                }
            },
            {"text": prompt},
        ]
        return call_gemini_generate_content(config=config, parts=parts)

    DECOMPOSITION_LOGGER.info(
        "gemini_video_input mode=file_api file=%s size=%s mime=%s",
        video_path.name,
        file_size,
        mime_type,
    )
    file_info = upload_gemini_file(config, video_path, mime_type)
    file_uri = file_info.get("uri")

    if not file_uri:
        raise RuntimeError(f"Gemini File API did not return a file uri: {file_info}")

    parts = [
        {
            "file_data": {
                "mime_type": file_info.get("mimeType") or mime_type,
                "file_uri": file_uri,
            }
        },
        {"text": prompt},
    ]
    return call_gemini_generate_content(config=config, parts=parts)


def build_overview_messages(
    *,
    video_context: dict[str, Any],
    step_results: list[dict[str, Any]],
    language: str,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "你是短视频结构迁移总编。你必须输出 JSON object，不要输出 markdown。",
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "task": f"请用{language}生成视频拆解概览，整合所有步骤结果。",
                    "videoContext": video_context,
                    "stepResults": step_results,
                    "requiredOutput": {
                        "overview": "整体拆解概览",
                        "coreStructure": ["核心结构"],
                        "migrationNotes": ["迁移到新内容时要保留的结构"],
                        "materialGaps": ["潜在素材缺口"],
                    },
                },
                ensure_ascii=False,
            ),
        },
    ]


def decompose_video_content(
    *,
    video_record: dict[str, Any],
    settings: dict[str, Any],
    llm_config: LlmConfig,
    output_path: Path,
    settings_dir: Path,
    config_path: Path | None = None,
    language: str = "中文",
) -> dict[str, Any]:
    normalized_settings = normalize_settings(settings)
    method_name = normalized_settings["methodName"]
    input_mode = normalized_settings.get("inputMode", "direct-video")
    step_group = "deep" if input_mode == "structured" or method_name == "deep" else "fast"
    if step_group == "fast":
        steps = normalized_settings["steps"]["fast"]
    elif input_mode == "structured":
        steps = normalized_settings["steps"]["structuredDeep"]
    else:
        steps = normalized_settings["steps"]["directVideoDeep"]
    fast_video_mode = step_group == "fast"
    direct_video_mode = input_mode == "direct-video"

    if not steps:
        raise ValueError(f"No decomposition steps configured for method: {method_name}")

    video_context = build_video_context(
        video_record,
        find_latest_analysis(str(video_record["id"]), video_record),
    )
    result: dict[str, Any] = {
        "videoId": video_record.get("id"),
        "videoName": video_record.get("name"),
        "methodName": method_name,
        "inputMode": input_mode,
        "frameInterval": normalized_settings["frameInterval"],
        "model": llm_config.model,
        "startedAt": datetime.now(UTC).isoformat(),
        "steps": [],
        "overview": None,
    }
    save_json_file(output_path, result)

    steps_to_run = steps[:1] if fast_video_mode else steps
    video_path = resolve_video_file_path(video_record)

    for index, step in enumerate(steps_to_run, start=1):
        prompt_text = resolve_prompt_text(step, settings_dir)
        skill_text = resolve_skill_text(step, settings_dir)
        previous_handoffs = collect_previous_handoffs(result["steps"])
        step_runtime_config = llm_config
        step_id = step.get("id")
        step_name = step.get("name")
        DECOMPOSITION_LOGGER.info(
            "step_start video_id=%s index=%s step_id=%s step_name=%s input_mode=%s method=%s",
            video_record.get("id"),
            index,
            step_id,
            step_name,
            input_mode,
            method_name,
        )
        if fast_video_mode:
            response = call_gemini_video_decomposition(
                config=llm_config,
                video_path=video_path,
                prompt=build_fast_gemini_prompt(
                    step=step,
                    prompt_text=prompt_text,
                    skill_text=skill_text,
                    video_context=video_context,
                    language=language,
                ),
            )
            response_text = extract_gemini_response_text(response)
        elif direct_video_mode:
            response = call_gemini_video_decomposition(
                config=llm_config,
                video_path=video_path,
                prompt=build_video_step_gemini_prompt(
                    step=step,
                    prompt_text=prompt_text,
                    skill_text=skill_text,
                    video_context=video_context,
                    previous_handoffs=previous_handoffs,
                    language=language,
                ),
            )
            response_text = extract_gemini_response_text(response)
        else:
            step_model_type = step.get("modelType") or step.get("model_type") or "image-recognition"
            if str(step_model_type) == "speech-recognition":
                speech_config = load_speech_asr_config(config_path)
                step_runtime_config = LlmConfig(
                    api_base_url=speech_config.api_base_url,
                    api_key="",
                    model=speech_config.resource_id,
                    endpoint="/auc/bigmodel",
                    provider="volcengine-openspeech",
                    model_type="speech-recognition",
                )
            else:
                step_runtime_config = load_commercial_model_config(
                    model_type=str(step_model_type),
                    config_path=config_path,
                )
            DECOMPOSITION_LOGGER.info(
                "step_model video_id=%s index=%s step_id=%s model_type=%s provider=%s model=%s base_url=%s endpoint=%s",
                video_record.get("id"),
                index,
                step_id,
                step_model_type,
                step_runtime_config.provider,
                step_runtime_config.model,
                step_runtime_config.api_base_url,
                step_runtime_config.endpoint,
            )
            if str(step_model_type) == "speech-recognition":
                audio_path = extract_audio_wav(video_record=video_record, video_path=video_path)
                asr_result = call_speech_asr(
                    config=speech_config,
                    audio_path=audio_path,
                    duration_ms=int(video_record.get("durationMs") or 0),
                )
                parsed_output = build_speech_step_output(
                    step=step,
                    prompt_text=prompt_text,
                    skill_text=skill_text,
                    video_context=video_context,
                    previous_handoffs=previous_handoffs,
                    asr_result=asr_result,
                )
                response_text = json.dumps(parsed_output, ensure_ascii=False)
                DECOMPOSITION_LOGGER.info(
                    "step_speech_asr video_id=%s index=%s step_id=%s mode=%s transcript_length=%s",
                    video_record.get("id"),
                    index,
                    step_id,
                    asr_result.get("mode"),
                    len(asr_result.get("text") or ""),
                )
            elif str(step_model_type) == "image-recognition":
                frames = extract_structured_frames(
                    video_record=video_record,
                    video_path=video_path,
                    frame_interval=normalized_settings["frameInterval"],
                )
                DECOMPOSITION_LOGGER.info(
                    "step_vision_frames video_id=%s index=%s step_id=%s frame_count=%s frame_interval=%s",
                    video_record.get("id"),
                    index,
                    step_id,
                    len(frames),
                    normalized_settings["frameInterval"],
                )
                messages = build_vision_step_messages(
                    step=step,
                    prompt_text=prompt_text,
                    skill_text=skill_text,
                    video_context=video_context,
                    previous_handoffs=previous_handoffs,
                    frames=frames,
                )
                response = call_commercial_structured_model(config=step_runtime_config, messages=messages)
                response_text = extract_response_text(response)
                parsed_output = parse_json_or_wrap(response_text)
            else:
                messages = build_step_messages(
                    step=step,
                    prompt_text=prompt_text,
                    skill_text=skill_text,
                    video_context=video_context,
                    previous_handoffs=previous_handoffs,
                )
                response = call_commercial_structured_model(config=step_runtime_config, messages=messages)
                response_text = extract_response_text(response)
                parsed_output = parse_json_or_wrap(response_text)
        if direct_video_mode or fast_video_mode:
            parsed_output = parse_json_or_wrap(response_text)
        DECOMPOSITION_LOGGER.info(
            "step_completed video_id=%s index=%s step_id=%s output_keys=%s",
            video_record.get("id"),
            index,
            step_id,
            list(parsed_output.keys()),
        )

        result["steps"].append(
            {
                "index": index,
                "id": step.get("id"),
                "name": step.get("name"),
                "modelType": step.get("modelType") or step.get("model_type"),
                "model": step_runtime_config.model,
                "provider": step_runtime_config.provider,
                "skillKey": step.get("skillKey") or step.get("skill_key") or step.get("skill"),
                "promptKey": step.get("promptKey") or step.get("prompt_key"),
                "prompt": prompt_text,
                "output": parsed_output,
                "rawOutput": response_text,
                "completedAt": datetime.now(UTC).isoformat(),
            }
        )
        save_json_file(output_path, result)

    if fast_video_mode:
        result["overview"] = result["steps"][0]["output"]
        result["rawOverview"] = result["steps"][0]["rawOutput"]
        result["completedAt"] = datetime.now(UTC).isoformat()
        save_json_file(output_path, result)
        return result

    if direct_video_mode:
        overview_response = call_gemini_generate_content(
            config=llm_config,
            parts=[
                {
                    "text": build_gemini_overview_prompt(
                        video_context=video_context,
                        step_results=result["steps"],
                        language=language,
                    )
                }
            ],
        )
        overview_text = extract_gemini_response_text(overview_response)
        result["overview"] = parse_json_or_wrap(overview_text)
        result["rawOverview"] = overview_text
        result["completedAt"] = datetime.now(UTC).isoformat()
        save_json_file(output_path, result)
        return result

    overview_response = call_chat_completion(
        llm_config,
        build_overview_messages(
            video_context=video_context,
            step_results=result["steps"],
            language=language,
        ),
    )
    overview_text = extract_response_text(overview_response)
    result["overview"] = parse_json_or_wrap(overview_text)
    result["rawOverview"] = overview_text
    result["completedAt"] = datetime.now(UTC).isoformat()
    save_json_file(output_path, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run configurable video content decomposition.")
    parser.add_argument("--video-id", help="Video id in backend_data/videos.json.")
    parser.add_argument("--video-name", help="Video filename in backend_data/videos.json.")
    parser.add_argument("--settings", required=True, help="Path to analysis-settings.json.")
    parser.add_argument("--llm-config", help="Optional JSON config for model API.")
    parser.add_argument("--output", help="Output JSON path.")
    parser.add_argument("--language", default="中文", help="Overview language.")
    args = parser.parse_args()

    settings_path = Path(args.settings).resolve()
    settings = load_json_file(settings_path, {})
    video_record = find_video_record(args.video_id, args.video_name)
    normalized_settings = normalize_settings(settings)
    config_path = Path(args.llm_config).resolve() if args.llm_config else None
    if normalized_settings.get("inputMode", "direct-video") == "direct-video":
        llm_config = load_gemini_video_config(config_path)
    else:
        llm_config = load_llm_config(config_path)
    output_path = (
        Path(args.output).resolve()
        if args.output
        else DECOMPOSITION_DIR / f"{video_record['id']}_decomposition.json"
    )

    result = decompose_video_content(
        video_record=video_record,
        settings=settings,
        llm_config=llm_config,
        output_path=output_path,
        settings_dir=settings_path.parent,
        config_path=config_path,
        language=args.language,
    )
    print(json.dumps({"output": str(output_path), "steps": len(result["steps"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()

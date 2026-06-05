from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import HTTPException
from pydantic import ValidationError

from .downloader import import_video
from .errors import unprocessable
from .provider import get_provider
from .repository import BreakdownRepository
from .schemas import BreakdownCreate, BreakdownRecord, BreakdownResult, BreakdownStatus


PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "social_video_decomposition_v1.md"
PROMPT_VERSION = "k2lab_social_video_breakdown_v1"


class BreakdownService:
    def __init__(self, repo: BreakdownRepository | None = None) -> None:
        self.repo = repo or BreakdownRepository()

    async def create_and_run(self, payload: BreakdownCreate) -> BreakdownRecord:
        provider = get_provider(payload.provider)
        input_video_url = payload.video_url.strip()
        input_video_key = normalize_video_duplicate_key(input_video_url)
        if input_video_key:
            reusable = self._find_reusable_breakdown(provider.name, input_video_key)
            if reusable is not None:
                return reusable.model_copy(update={"reused_existing": True})

        record = self.repo.create(provider.name, input_video_url=input_video_url, input_video_key=input_video_key)
        model_run_id: str | None = None
        raw_text: str | None = None
        try:
            self.repo.mark_status(record.id, BreakdownStatus.IMPORTING)
            imported_url = input_video_url if provider.name == "mock" else await import_video(input_video_url)
            self.repo.mark_status(record.id, BreakdownStatus.RUNNING)
            prompt = build_prompt(input_video_url, imported_url)
            model_run_id = self.repo.create_model_run(
                breakdown_id=record.id,
                status="running",
                model_name=provider.model_name,
                prompt_version=PROMPT_VERSION,
                request=provider.build_request_preview(prompt, imported_url),
            )
            result = await provider.generate_content(prompt, input_video_url, imported_url)
            raw_text = result.text
            parsed = parse_model_result(result.text, input_video_url, imported_url)
            updated = self.repo.save_success(record.id, parsed, raw_response_text=raw_text)
            self.repo.finish_model_run(model_run_id, "succeeded", raw_response_text=raw_text, parsed_output=parsed)
            return updated
        except Exception as exc:
            message = error_message(exc)
            if model_run_id:
                self.repo.finish_model_run(model_run_id, "failed", raw_response_text=raw_text, error_message=message)
            self.repo.mark_status(record.id, BreakdownStatus.FAILED, message)
            if isinstance(exc, HTTPException):
                raise
            raise unprocessable("BREAKDOWN_FAILED", message) from exc

    def _find_reusable_breakdown(self, provider: str, input_video_key: str) -> BreakdownRecord | None:
        reusable = self.repo.find_reusable_by_video_key(provider, input_video_key)
        if reusable is not None:
            return reusable

        for record in self.repo.list():
            if record.provider != provider or record.status == BreakdownStatus.FAILED:
                continue
            source_video = record.source_video or {}
            source_candidates = [
                source_video.get("original_url"),
                source_video.get("imported_video_url"),
                source_video.get("source_url"),
            ]
            if any(normalize_video_duplicate_key(str(candidate)) == input_video_key for candidate in source_candidates if candidate):
                return record
        return None


def build_prompt(original_url: str, imported_url: str) -> str:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    return f"{prompt}\n\nInput video URL: {original_url}\nImported video URL: {imported_url}"


def normalize_video_duplicate_key(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    if text.startswith("/uploads/"):
        local_path = text.split("?", 1)[0].split("#", 1)[0].rstrip("/")
        return f"local:{local_path}"

    try:
        parsed = urlsplit(text)
    except ValueError:
        return f"raw:{text.lower()}"
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return f"raw:{text.lower()}"

    host = (parsed.hostname or parsed.netloc).lower()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/+", "/", parsed.path or "/")
    path = path.rstrip("/") or "/"

    platform_video_id = extract_platform_video_id(host, path, parsed.query)
    if platform_video_id:
        return platform_video_id

    netloc = host if parsed.port is None else f"{host}:{parsed.port}"
    filtered_query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if not is_tracking_query_param(key)
        )
    )
    canonical = urlunsplit((parsed.scheme.lower(), netloc, path, filtered_query, ""))
    return f"url:{canonical}"


def extract_platform_video_id(host: str, path: str, query: str) -> str | None:
    if "tiktok.com" in host:
        match = re.search(r"/video/(\d+)", path)
        if match:
            return f"tiktok:video:{match.group(1)}"
    if "douyin.com" in host:
        match = re.search(r"/(?:video|note)/([^/?#]+)", path)
        if match:
            return f"douyin:video:{match.group(1)}"
    if "instagram.com" in host:
        match = re.search(r"/(?:reel|p)/([^/?#]+)", path)
        if match:
            return f"instagram:{match.group(1)}"
    if host in {"youtu.be", "youtube.com", "m.youtube.com"}:
        if host == "youtu.be" and path.strip("/"):
            return f"youtube:video:{path.strip('/')}"
        match = re.search(r"/shorts/([^/?#]+)", path)
        if match:
            return f"youtube:video:{match.group(1)}"
        query_params = dict(parse_qsl(query, keep_blank_values=True))
        if query_params.get("v"):
            return f"youtube:video:{query_params['v']}"
    return None


def is_tracking_query_param(key: str) -> bool:
    normalized = key.lower()
    return normalized.startswith("utm_") or normalized in {
        "fbclid",
        "gclid",
        "igsh",
        "is_copy_url",
        "is_from_webapp",
        "msclkid",
        "sender_device",
        "share_app_id",
        "share_iid",
        "share_link_id",
        "share_source",
        "timestamp",
        "tt_from",
        "web_id",
    }


def parse_model_result(raw_text: str, original_url: str, imported_url: str) -> BreakdownResult:
    try:
        data = json.loads(strip_json_fence(raw_text))
    except json.JSONDecodeError as exc:
        raise unprocessable("MODEL_OUTPUT_NOT_JSON", f"Model output was not valid JSON: {exc}") from exc
    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
        data = data[0]
    if isinstance(data, dict) and "result" in data and "source_video" not in data:
        data = data["result"]
    if not isinstance(data, dict):
        raise unprocessable("MODEL_OUTPUT_NOT_OBJECT", "Model output must be a JSON object")
    source = data.get("source_video") if isinstance(data.get("source_video"), dict) else {}
    source["original_url"] = source.get("original_url") or original_url
    source["imported_video_url"] = source.get("imported_video_url") or imported_url
    source["content_summary"] = source.get("content_summary") or "unknown"
    data["source_video"] = source
    try:
        return BreakdownResult.model_validate(data)
    except ValidationError as exc:
        raise unprocessable("MODEL_OUTPUT_SCHEMA_INVALID", str(exc)) from exc


def strip_json_fence(raw_text: str) -> str:
    text = raw_text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if match:
        text = match.group(1).strip()
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        return text
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return text


def error_message(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        detail: Any = exc.detail
        if isinstance(detail, dict):
            error = detail.get("error")
            if isinstance(error, dict) and error.get("message"):
                return str(error["message"])
        message = str(detail).strip()
        return message or exc.__class__.__name__
    message = str(exc).strip()
    return message or exc.__class__.__name__

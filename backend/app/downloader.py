from __future__ import annotations

import asyncio
import ipaddress
import re
import shutil
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from .config import get_settings


SOCIAL_PATTERNS = [
    re.compile(r"(tiktok\.com|douyin\.com|vm\.tiktok\.com|youtube\.com|youtu\.be|instagram\.com)"),
]


def is_upload_path(value: str) -> bool:
    return value.startswith("/uploads/")


def resolve_upload_path(value: str) -> Path:
    return get_settings().upload_dir / Path(value).name


async def import_video(video_url: str) -> str:
    if is_upload_path(video_url):
        return video_url
    if _is_social_url(video_url):
        return await _download_with_ytdlp(video_url)
    return await _download_direct(video_url)


def _is_social_url(url: str) -> bool:
    return any(pattern.search(url) for pattern in SOCIAL_PATTERNS)


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")
    if not parsed.hostname:
        raise ValueError("URL has no hostname")
    resolved = socket.getaddrinfo(parsed.hostname, None)
    for _, _, _, _, sockaddr in resolved:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError(f"URL resolves to private/reserved IP: {ip}")


async def _download_with_ytdlp(url: str) -> str:
    settings = get_settings()
    filename = f"{uuid4().hex}.mp4"
    dest = settings.upload_dir / filename
    ytdlp = _yt_dlp_executable()
    connection_args: list[str] = []
    if settings.ytdlp_cookies_file:
        connection_args.extend(["--cookies", settings.ytdlp_cookies_file])
    if settings.ytdlp_proxy:
        connection_args.extend(["--proxy", settings.ytdlp_proxy])
    base_args = [
        ytdlp,
        *connection_args,
        "--no-playlist",
        "--max-filesize",
        f"{settings.max_upload_mb}M",
        "-f",
        "mp4/best[ext=mp4]/best",
        "--merge-output-format",
        "mp4",
        "-o",
        str(dest),
        url,
    ]
    download_args = base_args[1 + len(connection_args) :]
    stderr_text = await _run_ytdlp([ytdlp, *connection_args, "--impersonate", "chrome", *download_args])
    if stderr_text and _is_impersonation_unavailable(stderr_text):
        stderr_text = await _run_ytdlp(base_args)
    if stderr_text:
        if dest.exists():
            dest.unlink()
        raise RuntimeError(_format_ytdlp_error(stderr_text))
    if not dest.exists():
        raise RuntimeError("yt-dlp completed but output file was not found")
    return f"/uploads/{filename}"


def _yt_dlp_executable() -> str:
    bundled = Path(sys.executable).parent / "yt-dlp"
    if bundled.exists():
        return str(bundled)
    found = shutil.which("yt-dlp")
    if found:
        return found
    return str(bundled)


async def _run_ytdlp(args: list[str]) -> str:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        return stderr.decode(errors="replace")
    return ""


def _is_impersonation_unavailable(stderr_text: str) -> bool:
    lowered = stderr_text.lower()
    return "impersonate target" in lowered and "not available" in lowered


def _format_ytdlp_error(stderr_text: str) -> str:
    lowered = stderr_text.lower()
    if "your ip address is blocked" in lowered:
        return (
            "TikTok 拒绝当前后端网络访问这个视频。可以先上传本地视频继续拆解，"
            "或给后端配置 VIDEO_BREAKDOWN_YTDLP_PROXY / VIDEO_BREAKDOWN_YTDLP_COOKIES_FILE 后重试。"
        )
    if "login" in lowered or "cookies" in lowered:
        return (
            "平台要求登录态或 cookies 才能读取这个视频。可以先上传本地视频继续拆解，"
            "或给后端配置 VIDEO_BREAKDOWN_YTDLP_COOKIES_FILE 后重试。"
        )
    if _is_impersonation_unavailable(stderr_text):
        return (
            "yt-dlp 的浏览器伪装能力不可用。已尝试降级下载但仍失败，请确认后端依赖 curl_cffi 已安装。"
        )
    compact = " ".join(line.strip() for line in stderr_text.splitlines() if line.strip())
    return f"yt-dlp 下载失败：{compact[-700:]}"


async def _download_direct(url: str) -> str:
    _validate_url(url)
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    async with httpx.AsyncClient(follow_redirects=True, timeout=300) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.content
    if len(data) > max_bytes:
        raise ValueError(f"File exceeds {settings.max_upload_mb}MB limit")
    filename = f"{uuid4().hex}.mp4"
    dest = settings.upload_dir / filename
    dest.write_bytes(data)
    return f"/uploads/{filename}"

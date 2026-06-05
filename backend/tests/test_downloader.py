from __future__ import annotations

from pathlib import Path

import pytest

from app import downloader
from app.config import get_settings


@pytest.mark.asyncio
async def test_ytdlp_retries_without_impersonation_when_target_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("VIDEO_BREAKDOWN_SKIP_DOTENV", "1")
    monkeypatch.setenv("VIDEO_BREAKDOWN_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("VIDEO_BREAKDOWN_DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    get_settings().upload_dir.mkdir(parents=True, exist_ok=True)
    calls: list[list[str]] = []

    monkeypatch.setattr(downloader, "_yt_dlp_executable", lambda: "yt-dlp")

    async def fake_run_ytdlp(args: list[str]) -> str:
        calls.append(args)
        if "--impersonate" in args:
            return 'ERROR: Impersonate target "chrome" is not available.'
        output_path = Path(args[args.index("-o") + 1])
        output_path.write_bytes(b"video")
        return ""

    monkeypatch.setattr(downloader, "_run_ytdlp", fake_run_ytdlp)

    imported_url = await downloader._download_with_ytdlp("https://www.tiktok.com/t/demo/")

    assert imported_url.startswith("/uploads/")
    assert len(calls) == 2
    assert "--impersonate" in calls[0]
    assert "--impersonate" not in calls[1]
    assert (get_settings().upload_dir / Path(imported_url).name).exists()
    get_settings.cache_clear()


def test_ytdlp_ip_block_error_is_user_readable():
    message = downloader._format_ytdlp_error("ERROR: [TikTok] 123: Your IP address is blocked from accessing this post")

    assert "TikTok 拒绝当前后端网络访问这个视频" in message
    assert "Traceback" not in message

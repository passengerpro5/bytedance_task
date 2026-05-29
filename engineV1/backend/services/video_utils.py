"""Shared video utility functions.

Extracted from app.py to avoid circular imports when services need
ffprobe/ffmpeg capabilities.
"""

from __future__ import annotations

import json
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )


def parse_ratio(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None

    try:
        return round(float(Fraction(value)), 3)
    except (ZeroDivisionError, ValueError):
        return None


def probe_video(video_path: Path) -> dict[str, Any]:
    """Run ffprobe and return structured video metadata."""
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

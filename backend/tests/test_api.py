from __future__ import annotations

import asyncio
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import get_settings
from app.director_service import parse_director_output
from app.main import create_app, prepare_hyperframes_caption_overlay, render_director_plan_draft
from app.repository import BreakdownRepository
from app.provider import generate_gemini_text
from app.persona_defaults import normalize_creator_persona_payload
from app.schemas import (
    DirectorGenerationJobStatus,
    DirectorPlanRecord,
    DirectorPlanRequest,
    DirectorRenderJobStatus,
    CreatorPersonaProfile,
    PersonaGenerationJobStatus,
    PersonaGenerationRequest,
    ScriptAgentBatch,
    ScriptAgentItem,
    ScriptGenerationJobStatus,
    ScriptGenerationRequest,
    english_word_count,
    script_spoken_lines_for_length,
    script_voiceover_estimated_duration_sec,
    storyboard_duration_seconds,
    storyboard_voiceover_min_duration_sec,
)
from app.script_service import (
    build_mock_script_item,
    build_edit_prompt,
    build_script_prompt,
    compact_persona_for_prompt,
    creator_persona_label,
    creator_persona_label_zh,
    is_retryable_script_agent_output_error,
    load_script_agent_skill,
    normalize_storyboard_voiceover,
    parse_script_agent_batch,
    script_agent_rejection_note,
)
from app.service import error_message


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VIDEO_BREAKDOWN_PROVIDER", "mock")
    monkeypatch.setenv("VIDEO_BREAKDOWN_SKIP_DOTENV", "1")
    monkeypatch.setenv("VIDEO_BREAKDOWN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("VIDEO_BREAKDOWN_UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def make_test_video(path: Path, *, duration_sec: int, size: str) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is required for manual factory asset validation tests")

    completed = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={size}:d={duration_sec}",
            "-an",
            "-c:v",
            "mpeg4",
            "-q:v",
            "5",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        pytest.fail(f"ffmpeg failed to create test clip: {completed.stderr}")


def voiceover_seed_from_item(item: ScriptAgentItem) -> dict:
    zh = item.script.localized.get("zh", {})
    return {
        "hook": item.script.hook,
        "script_voiceover": item.script.voiceover,
        "cta": item.script.cta,
        "localized_zh": {
            "hook": zh.get("hook", "开头钩子"),
            "script_voiceover": zh.get("voiceover", []),
            "cta": zh.get("cta", "如果你是 5K+ TikTok Shop 达人，点击按钮，赚自己的钱。"),
        },
    }


def test_hyperframes_cli_overlay_contract_uses_official_render_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_ffmpeg = tmp_path / "ffmpeg"
    fake_ffmpeg.write_text(
        """#!/usr/bin/env python3
from pathlib import Path
import sys

Path(sys.argv[-1]).write_bytes(b"fake transparent webm overlay")
""",
        encoding="utf-8",
    )
    fake_ffmpeg.chmod(0o755)
    monkeypatch.setenv("VIDEO_FACTORY_FFMPEG", str(fake_ffmpeg))

    fake_cli = tmp_path / "hyperframes"
    fake_cli.write_text(
        """#!/usr/bin/env python3
from pathlib import Path
import sys

args = sys.argv[1:]
assert args[0] == "render", args
assert args[args.index("--format") + 1] == "png-sequence", args
output = Path(args[args.index("--output") + 1])
output.mkdir(parents=True, exist_ok=True)
(output / "frame_000001.png").write_bytes(b"fake rgba frame")
""",
        encoding="utf-8",
    )
    fake_cli.chmod(0o755)

    summary = prepare_hyperframes_caption_overlay(
        settings=SimpleNamespace(video_factory_enable_hyperframes_cli=True, hyperframes_cli_command=str(fake_cli)),
        cues=[{"text": "Draft caption", "start": 0, "end": 2}],
        project_dir=tmp_path / "caption-project",
        output_dir=tmp_path,
        render_id="render-1",
        total_duration_sec=2,
    )

    assert summary["engine"] == "webvtt_track_v1"
    assert summary["hyperframes_status"] == "overlay_rendered"
    assert summary["overlay_url"].endswith("/overlay.webm")
    assert Path(summary["overlay_path"]).read_bytes() == b"fake transparent webm overlay"
    assert summary["overlay_frame_count"] == 1
    assert summary["composition_url"].endswith("/index.html")
    composition_html = Path(summary["composition_path"]).read_text(encoding="utf-8")
    assert 'data-composition-id="moras-caption-overlay"' in composition_html
    assert 'data-width="1080"' in composition_html
    assert 'data-height="1920"' in composition_html
    assert 'window.__timelines["moras-caption-overlay"]' in composition_html


def test_hyperframes_cli_overlay_contract_supports_command_with_args(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_ffmpeg = tmp_path / "ffmpeg"
    fake_ffmpeg.write_text(
        """#!/usr/bin/env python3
from pathlib import Path
import sys

Path(sys.argv[-1]).write_bytes(b"wrapped transparent webm overlay")
""",
        encoding="utf-8",
    )
    fake_ffmpeg.chmod(0o755)
    monkeypatch.setenv("VIDEO_FACTORY_FFMPEG", str(fake_ffmpeg))

    fake_cli = tmp_path / "hyperframes_wrapper.py"
    fake_cli.write_text(
        """#!/usr/bin/env python3
import os
from pathlib import Path
import sys

args = sys.argv[1:]
assert args[0] == "--from-wrapper", args
assert args[1] == "render", args
assert args[args.index("--format") + 1] == "png-sequence", args
assert args[args.index("--fps") + 1] == "30", args
assert "--docker" in args, args
assert args[args.index("--workers") + 1] == "1", args
assert "--no-browser-gpu" in args, args
assert os.environ["HOME"].endswith("hf-home"), os.environ["HOME"]
assert os.environ["HYPERFRAMES_BROWSER_PATH"].endswith("headless-shell"), os.environ.get("HYPERFRAMES_BROWSER_PATH")
assert os.environ["PRODUCER_HEADLESS_SHELL_PATH"].endswith("headless-shell"), os.environ.get("PRODUCER_HEADLESS_SHELL_PATH")
output = Path(args[args.index("--output") + 1])
output.mkdir(parents=True, exist_ok=True)
(output / "frame_000001.png").write_bytes(b"wrapped rgba frame")
""",
        encoding="utf-8",
    )

    summary = prepare_hyperframes_caption_overlay(
        settings=SimpleNamespace(
            video_factory_enable_hyperframes_cli=True,
            hyperframes_cli_command=f"{shlex.quote(sys.executable)} {shlex.quote(str(fake_cli))} --from-wrapper",
            hyperframes_cli_home_dir=str(tmp_path / "hf-home"),
            hyperframes_cli_browser_path=str(tmp_path / "headless-shell"),
            hyperframes_cli_use_docker=True,
        ),
        cues=[{"text": "Wrapped caption", "start": 0, "end": 2}],
        project_dir=tmp_path / "caption-project",
        output_dir=tmp_path,
        render_id="render-2",
        total_duration_sec=2,
    )

    assert summary["engine"] == "webvtt_track_v1"
    assert summary["hyperframes_status"] == "overlay_rendered"
    assert summary["overlay_url"].endswith("/overlay.webm")
    assert Path(summary["overlay_path"]).read_bytes() == b"wrapped transparent webm overlay"


def test_render_draft_promotes_hyperframes_after_real_overlay_composite(tmp_path: Path):
    ffmpeg_bin = os.getenv("VIDEO_FACTORY_FFMPEG", "ffmpeg")
    if shutil.which(ffmpeg_bin) is None:
        pytest.skip("ffmpeg is required for HyperFrames overlay composite tests")

    fake_cli = tmp_path / "hyperframes_alpha.py"
    fake_cli.write_text(
        """#!/usr/bin/env python3
from pathlib import Path
import os
import subprocess
import sys

args = sys.argv[1:]
assert args[0] == "render", args
assert "--docker" in args, args
output = Path(args[args.index("--output") + 1])
output.mkdir(parents=True, exist_ok=True)
completed = subprocess.run(
    [
        os.getenv("VIDEO_FACTORY_FFMPEG", "ffmpeg"),
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=black@0.0:s=1080x1920:d=2:r=30",
        "-vf",
        "format=rgba,drawbox=x=96:y=1500:w=888:h=220:color=blue@0.85:t=fill",
        str(output / "frame_%06d.png"),
    ],
    check=False,
    capture_output=True,
    text=True,
)
if completed.returncode != 0:
    raise SystemExit(completed.stderr)
""",
        encoding="utf-8",
    )
    fake_cli.chmod(0o755)

    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    settings = SimpleNamespace(
        upload_dir=upload_dir,
        video_factory_enable_hyperframes_cli=True,
        hyperframes_cli_command=f"{shlex.quote(sys.executable)} {shlex.quote(str(fake_cli))}",
        hyperframes_cli_home_dir=str(tmp_path / "hf-home"),
        hyperframes_cli_no_browser_gpu=True,
        hyperframes_cli_use_docker=True,
        hyperframes_cli_workers="1",
        hyperframes_cli_timeout_seconds=30,
    )
    plan = DirectorPlanRecord(
        id="director-plan-hyperframes",
        script_id="script-hyperframes",
        status="ready",
        provider="mock",
        model_name="mock-director-agent-v1",
        prompt_version="moras_director_agent_v1",
        metadata={"total_duration_sec": 2},
        timeline={
            "tracks": {
                "audio_tracks": [
                    {
                        "clips": [
                            {
                                "clip_id": "voiceover_1",
                                "source_type": "tts_voiceover",
                                "text_content": "Moras renders a captioned factory draft.",
                                "timeline_start_sec": 0,
                                "timeline_end_sec": 2,
                            }
                        ]
                    }
                ]
            }
        },
        asset_resolution=[],
        tool_dispatches=[],
        validation_summary={"status": "passed"},
        created_at="2026-06-02T00:00:00Z",
        updated_at="2026-06-02T00:00:00Z",
    )
    readiness = {
        "render_inputs": [
            {
                "clip_id": "placeholder_1",
                "source_type": "placeholder",
                "source_url": "",
                "source_label": "Placeholder",
                "placeholder": True,
                "timeline_start_sec": 0,
                "duration_sec": 2,
            }
        ],
        "total_duration_sec": 2,
    }

    result = render_director_plan_draft(settings, plan, readiness)

    assert result["width"] == 1080
    assert result["height"] == 1920
    assert result["qa_summary"]["status"] == "passed"
    assert result["qa_summary"]["caption"]["engine"] == "hyperframes_cli_v1"
    assert result["qa_summary"]["caption"]["hyperframes_status"] == "composited"
    assert result["usage_summary"]["caption_engine"] == "hyperframes_cli_v1"
    artifact_by_type = {artifact["artifact_type"]: artifact for artifact in result["artifacts"]}
    assert set(artifact_by_type) == {"video", "audio", "subtitle", "caption_composition", "caption_overlay"}
    assert artifact_by_type["caption_overlay"]["asset_url"].endswith("/overlay.webm")
    assert artifact_by_type["caption_overlay"]["mime_type"] == "video/webm"
    assert artifact_by_type["caption_overlay"]["file_size_bytes"] > 0
    output_path = upload_dir / result["output_asset_url"].removeprefix("/uploads/")
    overlay_path = upload_dir / artifact_by_type["caption_overlay"]["asset_url"].removeprefix("/uploads/")
    assert output_path.exists()
    assert overlay_path.exists()


def wait_for_render_job(client: TestClient, job_id: str, *, attempts: int = 200) -> dict:
    for _ in range(attempts):
        response = client.get(f"/api/video-factory/render-jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["status"] in {"blocked", "succeeded", "failed"}:
            return job
        time.sleep(0.1)
    pytest.fail(f"Director render job {job_id} did not reach a terminal state")


def wait_for_persona_generation_job(client: TestClient, job_id: str, *, attempts: int = 200) -> dict:
    for _ in range(attempts):
        response = client.get(f"/api/persona-generation-jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["status"] in {"succeeded", "failed"}:
            return job
        time.sleep(0.05)
    pytest.fail(f"Persona generation job {job_id} did not reach a terminal state")


def has_cjk(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value))


def test_gemini_text_generation_retries_transport_disconnect(monkeypatch: pytest.MonkeyPatch):
    calls = 0

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def post(self, url, json):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise httpx.RemoteProtocolError("Server disconnected without sending a response.")
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {"content": {"parts": [{"text": "{\"ok\": true}"}]}}
                    ]
                },
            )

    monkeypatch.setenv("VIDEO_BREAKDOWN_SKIP_DOTENV", "1")
    monkeypatch.setenv("GOOGLE_VERTEX_AI_API_KEY", "test-key")
    monkeypatch.setattr("app.provider.httpx.AsyncClient", FakeAsyncClient)
    get_settings.cache_clear()

    result = asyncio.run(generate_gemini_text("Return JSON.", "gemini-test"))

    assert calls == 2
    assert result.text == "{\"ok\": true}"
    get_settings.cache_clear()


def test_generation_stale_defaults_allow_sequential_gemini_batches(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VIDEO_BREAKDOWN_SKIP_DOTENV", "1")
    monkeypatch.delenv("SCRIPT_GENERATION_STALE_AFTER_SECONDS", raising=False)
    monkeypatch.delenv("PERSONA_GENERATION_STALE_AFTER_SECONDS", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.script_generation_stale_after_seconds == 1800
    assert settings.persona_generation_stale_after_seconds == 1800
    get_settings.cache_clear()


def test_script_agent_missing_moras_mention_failure_is_retryable():
    message = (
        "1 validation error for ScriptAgentBatch\n"
        "scripts.0\n"
        "  Value error, UGC voiceover must mention Moras in spoken copy"
    )

    assert is_retryable_script_agent_output_error(message)
    note = script_agent_rejection_note(message)

    assert "one or two spoken Moras lines" in note
    assert "selected-product/Generate or Custom Create workflow" in note
    assert "video with the commerce path visible" in note


def test_script_agent_banned_claim_failure_is_retryable_without_repeating_label():
    message = (
        "1 validation error for ScriptAgentBatch\n"
        "scripts.0\n"
        "  Value error, banned claims found in script output: guaranteed sales"
    )

    assert is_retryable_script_agent_output_error(message)
    note = script_agent_rejection_note(message)

    assert "forbidden-claim labels" in note
    assert "unsupported outcome promise" in note
    assert "workflow proof" in note


def test_script_agent_thin_voiceover_failure_is_retryable():
    message = (
        "1 validation error for ScriptAgentBatch\n"
        "scripts.0\n"
        "  Value error, UGC voiceover must use at least 11 short spoken lines "
        "so short sentences do not remove content"
    )

    assert is_retryable_script_agent_output_error(message)
    note = script_agent_rejection_note(message)

    assert "11-14 short spoken lines" in note
    assert "short sentences do not remove content" in note
    assert "90 spoken English words" in note


def test_script_agent_overlong_short_voiceover_failure_is_retryable():
    message = (
        "1 validation error for ScriptAgentBatch\n"
        "scripts.0.storyboard.0\n"
        "  Value error, storyboard row shot_01 is 6.5s, but this short voiceover only supports "
        "about 4.5s without an explicit visual hold"
    )

    assert is_retryable_script_agent_output_error(message)
    note = script_agent_rejection_note(message)

    assert "short spoken line" in note
    assert "English spoken text first" in note
    assert "visual hold" in note


def test_script_prompt_compacts_large_breakdown_payload():
    huge_text = "This source payload should be compacted. " * 500
    source_records = [
        SimpleNamespace(
            id=f"source_{index}",
            source_video={
                "title": f"Large source {index}",
                "platform": "TikTok",
                "duration_seconds": 38,
                "content_summary": huge_text,
            },
            classification={
                "hook_type": "Curiosity",
                "pain_factors": [huge_text, huge_text],
                "value_factors": [huge_text],
                "factor_reasoning": huge_text,
                "evidence": [huge_text],
            },
            decomposition={
                "one_sentence_summary": huge_text,
                "hook": huge_text,
                "narrative_structure": [huge_text, huge_text],
                "segments": [{"role": huge_text, "content": huge_text, "technique": huge_text}],
                "key_takeaways": [huge_text],
                "performance_logic": huge_text,
            },
            structure_protocol={"core_pattern": huge_text, "timeline_slots": [{"transfer_rule": huge_text}]},
            script_agent_bridge={"reusable_pattern": huge_text, "script_agent_instructions": [huge_text]},
            reference_storyboard=[
                {
                    "shot_id": f"shot_{shot_index}",
                    "timestamp": f"{(shot_index - 1) * 4}-{shot_index * 4}s",
                    "duration": "4s",
                    "camera": huge_text,
                    "character_action": huge_text,
                    "facial_expression": huge_text,
                    "background": huge_text,
                    "props": [huge_text, "phone"],
                    "voiceover": huge_text,
                    "overlay": f"Save this {shot_index}",
                    "sound": huge_text,
                    "bgm": "low-volume upbeat loop",
                    "sound_effects": ["tap", "whoosh", "save tone"],
                    "subtitle_logic": f"Caption appears on proof beat {shot_index} to keep silent viewers oriented.",
                    "visual_elements": ["number circle", "proof screenshot", "CTA arrow"],
                    "visual_element_logic": f"Visual elements enter on beat {shot_index} to direct attention from proof to action.",
                    "transition": huge_text,
                    "purpose": huge_text,
                    "localized": {
                        "zh": {
                            "camera": f"第 {shot_index} 个中文镜头",
                            "character_action": "创作者展示屏幕证据",
                            "facial_expression": "专注且略带惊讶",
                            "background": "手机屏幕和桌面",
                            "props": ["手机", "截图"],
                            "voiceover": "先展示证据，再给行动理由。",
                            "overlay": f"证据点 {shot_index}",
                            "sound": "点击音",
                            "bgm": "低音量轻快循环音乐",
                            "sound_effects": ["点击声", "划入声", "保存提示音"],
                            "subtitle_logic": f"字幕在第 {shot_index} 个证明点出现，帮助静音观看。",
                            "visual_elements": ["数字圈注", "证明截图", "CTA 箭头"],
                            "visual_element_logic": f"画面要素在第 {shot_index} 拍出现，把注意力从证明带到行动。",
                            "transition": "快速切屏",
                            "purpose": "保留完整参考镜头给脚本智能体。",
                        }
                    },
                }
                for shot_index in range(1, 9)
            ],
        )
        for index in range(5)
    ]

    prompt = build_script_prompt(
        ScriptGenerationRequest(script_count=3, script_type="all", persona_id="persona-1"),
        source_records,
        existing_script_signatures=[],
    )

    assert len(prompt) < 65000
    assert huge_text not in prompt
    assert '"reference_storyboard":' in prompt
    assert "# Loaded Script Agent Skills" in prompt
    assert "## Skill: campaign-boundaries" in prompt
    assert "## Skill: persona-and-diversity" in prompt
    assert "## Skill: script-copywriting" in prompt
    assert "## Skill: visual-production" in prompt
    assert "## Skill: veo-prompting" in prompt
    assert "# Output Contract" in prompt
    assert '"loaded_script_agent_skills":' in prompt
    assert "shot_8" in prompt
    assert "facial_expression" in prompt
    assert "props" in prompt
    assert "low-volume upbeat loop" in prompt
    assert "sound_effects" in prompt
    assert "subtitle_logic" in prompt
    assert "visual_element_logic" in prompt
    assert "storyboard[].overlay is the short on-screen caption highlight" in prompt
    assert "not the full subtitle transcript" in prompt
    assert "第 8 个中文镜头" in prompt
    assert '"omitted_source_breakdown_ids":' in prompt
    assert "source_4" in prompt


def test_script_prompt_injects_skill_constraints_and_swaps_edit_contract():
    prompt = build_script_prompt(
        ScriptGenerationRequest(script_count=1, script_type="all"),
        [],
        existing_script_signatures=[],
    )

    assert "## Backend Validator Negative Terms" in prompt
    assert "`screen recording`" in prompt
    assert "`录屏`" in prompt
    assert "## Required Chinese Glossary" in prompt
    assert "`Moras workflow` => `Moras 工作流`" in prompt
    assert "Use nested `localized.zh` objects only" in prompt
    assert "Moras must be the workflow tool inside the creator story" in prompt

    edit_prompt = build_edit_prompt(
        SimpleNamespace(
            topic_plan={},
            script={},
            storyboard=[],
            creator_persona={},
            video_prompt={},
            production_asset_plan=[],
            risk_check={},
            source_breakdown_ids=[],
            source_component_summary=[],
        ),
        "Tighten the hook.",
    )

    assert "# Script Agent Edit Output Contract" in edit_prompt
    assert "Do not wrap the result in a `scripts` array." in edit_prompt
    assert "Return valid JSON only with this top-level shape" not in edit_prompt


def test_gemini_script_generation_splits_batch_into_single_script_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("VIDEO_BREAKDOWN_PROVIDER", "gemini")
    monkeypatch.setenv("VIDEO_BREAKDOWN_SKIP_DOTENV", "1")
    monkeypatch.setenv("VIDEO_BREAKDOWN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("VIDEO_BREAKDOWN_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("GOOGLE_VERTEX_AI_API_KEY", "test-key")
    get_settings.cache_clear()

    calls: list[tuple[str, str | None]] = []
    counters = {"pre": 0, "script": 0, "review": 0}

    async def fake_generate_gemini_text(prompt: str, model_name: str | None = None):
        calls.append((prompt, model_name))
        if '"mode": "PRE_GENERATION"' in prompt:
            item = build_mock_script_item(counters["pre"], "all", [])
            counters["pre"] += 1
            return SimpleNamespace(
                text=json.dumps(voiceover_seed_from_item(item), ensure_ascii=False),
                model_name=model_name or "gemini-test",
            )
        if '"mode": "POST_REVIEW"' in prompt:
            counters["review"] += 1
            return SimpleNamespace(
                text=json.dumps({"requires_patch": False, "reason": "Already aligned."}, ensure_ascii=False),
                model_name=model_name or "gemini-test",
            )
        item = build_mock_script_item(counters["script"], "all", [])
        counters["script"] += 1
        return SimpleNamespace(
            text=json.dumps({"scripts": [item.model_dump(mode="json")]}, ensure_ascii=False),
            model_name=model_name or "gemini-test",
        )

    monkeypatch.setattr("app.script_service.generate_gemini_text", fake_generate_gemini_text)
    app = create_app()
    repo = BreakdownRepository()
    persona = build_mock_script_item(0, "all", []).creator_persona.model_dump(mode="json")
    persona_record = repo.create_creator_persona_records(
        personas=[persona],
        provider="mock",
        model_name="mock-persona-agent-v1",
    )[0]

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/scripts/generate",
            json={
                "script_count": 3,
                "script_type": "all",
                "source_breakdown_ids": [],
                "persona_id": persona_record.id,
            },
        )

    assert response.status_code == 200
    assert len(response.json()) == 3
    assert counters == {"pre": 3, "script": 3, "review": 3}
    assert len(calls) == 9
    with repo._connect() as connection:
        rows = connection.execute(
            "SELECT status, raw_response_text, request_json FROM script_model_runs ORDER BY created_at"
        ).fetchall()
    assert [row["status"] for row in rows] == ["succeeded"] * 9
    requests = [json.loads(row["request_json"]) for row in rows]
    assert [request["generation_mode"] for request in requests] == [
        "voiceover_pre_generation",
        "sequential_single_script_calls",
        "voiceover_post_review",
        "voiceover_pre_generation",
        "sequential_single_script_calls",
        "voiceover_post_review",
        "voiceover_pre_generation",
        "sequential_single_script_calls",
        "voiceover_post_review",
    ]
    assert [request["batch_index"] for request in requests] == [1, 1, 1, 2, 2, 2, 3, 3, 3]
    script_prompts = [prompt for prompt, _ in calls if "Generate scripts from this input JSON" in prompt]
    assert len(script_prompts) == 3
    assert all("pre_generated_vo" in prompt for prompt in script_prompts)
    assert all(row["raw_response_text"] for row in rows)
    get_settings.cache_clear()


def test_gemini_script_generation_retries_off_brand_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("VIDEO_BREAKDOWN_PROVIDER", "gemini")
    monkeypatch.setenv("VIDEO_BREAKDOWN_SKIP_DOTENV", "1")
    monkeypatch.setenv("VIDEO_BREAKDOWN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("VIDEO_BREAKDOWN_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("GOOGLE_VERTEX_AI_API_KEY", "test-key")
    get_settings.cache_clear()

    calls: list[str] = []
    full_script_calls = 0

    async def fake_generate_gemini_text(prompt: str, model_name: str | None = None):
        nonlocal full_script_calls
        calls.append(prompt)
        if '"mode": "PRE_GENERATION"' in prompt:
            item = build_mock_script_item(0, "all", [])
            return SimpleNamespace(
                text=json.dumps(voiceover_seed_from_item(item), ensure_ascii=False),
                model_name=model_name or "gemini-test",
            )
        if '"mode": "POST_REVIEW"' in prompt:
            return SimpleNamespace(
                text=json.dumps({"requires_patch": False, "reason": "Already aligned."}, ensure_ascii=False),
                model_name=model_name or "gemini-test",
            )
        full_script_calls += 1
        item = build_mock_script_item(0, "all", [])
        payload = item.model_dump(mode="json")
        if full_script_calls == 1:
            payload["script"]["voiceover"][3] = "Moras pulls the angles and the hooks for me."
        return SimpleNamespace(
            text=json.dumps({"scripts": [payload]}, ensure_ascii=False),
            model_name=model_name or "gemini-test",
        )

    monkeypatch.setattr("app.script_service.generate_gemini_text", fake_generate_gemini_text)
    app = create_app()
    repo = BreakdownRepository()
    persona = build_mock_script_item(0, "all", []).creator_persona.model_dump(mode="json")
    persona_record = repo.create_creator_persona_records(
        personas=[persona],
        provider="mock",
        model_name="mock-persona-agent-v1",
    )[0]

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/scripts/generate",
            json={
                "script_count": 1,
                "script_type": "all",
                "source_breakdown_ids": [],
                "persona_id": persona_record.id,
            },
        )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert full_script_calls == 2
    script_prompts = [prompt for prompt in calls if "Generate scripts from this input JSON" in prompt]
    assert len(script_prompts) == 2
    assert "rejected_script_output_notes" in script_prompts[1]
    assert "pulls the angles" in script_prompts[1]
    with repo._connect() as connection:
        rows = connection.execute(
            "SELECT status, error_message, request_json FROM script_model_runs ORDER BY created_at"
        ).fetchall()
    statuses = [row["status"] for row in rows]
    modes = [json.loads(row["request_json"])["generation_mode"] for row in rows]
    assert statuses == ["succeeded", "failed", "succeeded", "succeeded"]
    assert modes == [
        "voiceover_pre_generation",
        "sequential_single_script_calls",
        "sequential_single_script_calls",
        "voiceover_post_review",
    ]
    assert "off-brand Script Agent copy" in rows[1]["error_message"]
    assert json.loads(rows[2]["request_json"])["attempt"] == 2
    get_settings.cache_clear()


def test_voiceover_expert_post_review_patch_updates_spoken_copy_before_persist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("VIDEO_BREAKDOWN_PROVIDER", "gemini")
    monkeypatch.setenv("VIDEO_BREAKDOWN_SKIP_DOTENV", "1")
    monkeypatch.setenv("VIDEO_BREAKDOWN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("VIDEO_BREAKDOWN_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("GOOGLE_VERTEX_AI_API_KEY", "test-key")
    get_settings.cache_clear()

    base_item = build_mock_script_item(0, "all", [])
    seed = voiceover_seed_from_item(base_item)
    patched_lines = list(base_item.script.voiceover)
    patched_lines[0] = "Your next product video should not start blank."
    patched_zh = list(base_item.script.localized["zh"]["voiceover"])
    patched_zh[0] = "你的下一条商品视频，不该从空白开始。"
    patched_hook = "Your next product video should not start blank."
    patched_hook_zh = "你的下一条商品视频，不该从空白开始。"

    async def fake_generate_gemini_text(prompt: str, model_name: str | None = None):
        if '"mode": "PRE_GENERATION"' in prompt:
            return SimpleNamespace(text=json.dumps(seed, ensure_ascii=False), model_name=model_name or "gemini-test")
        if '"mode": "POST_REVIEW"' in prompt:
            return SimpleNamespace(
                text=json.dumps(
                    {
                        "requires_patch": True,
                        "patched_hook": patched_hook,
                        "patched_script_voiceover": patched_lines,
                        "patched_cta": base_item.script.cta,
                        "patched_localized_zh": {
                            "hook": patched_hook_zh,
                            "script_voiceover": patched_zh,
                            "cta": base_item.script.localized["zh"]["cta"],
                        },
                        "patched_storyboard_voiceovers": [
                            {
                                "shot_id": base_item.storyboard[0].shot_id,
                                "voiceover": patched_lines[0],
                                "localized_zh_voiceover": patched_zh[0],
                                "source_voiceover_line_indices": [0],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                model_name=model_name or "gemini-test",
            )
        return SimpleNamespace(
            text=json.dumps({"scripts": [base_item.model_dump(mode="json")]}, ensure_ascii=False),
            model_name=model_name or "gemini-test",
        )

    monkeypatch.setattr("app.script_service.generate_gemini_text", fake_generate_gemini_text)
    app = create_app()
    repo = BreakdownRepository()
    persona_record = repo.create_creator_persona_records(
        personas=[base_item.creator_persona.model_dump(mode="json")],
        provider="mock",
        model_name="mock-persona-agent-v1",
    )[0]

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/scripts/generate",
            json={
                "script_count": 1,
                "script_type": "all",
                "source_breakdown_ids": [],
                "persona_id": persona_record.id,
            },
        )

    assert response.status_code == 200
    created = response.json()[0]
    assert created["script"]["hook"] == patched_hook
    assert created["script"]["voiceover"][0] == patched_lines[0]
    assert created["storyboard"][0]["voiceover"] == patched_lines[0]
    get_settings.cache_clear()


def test_voiceover_post_review_invalid_patch_falls_back_to_seeded_script(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("VIDEO_BREAKDOWN_PROVIDER", "gemini")
    monkeypatch.setenv("VIDEO_BREAKDOWN_SKIP_DOTENV", "1")
    monkeypatch.setenv("VIDEO_BREAKDOWN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("VIDEO_BREAKDOWN_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("GOOGLE_VERTEX_AI_API_KEY", "test-key")
    get_settings.cache_clear()

    base_item = build_mock_script_item(0, "all", [])
    seed = voiceover_seed_from_item(base_item)

    async def fake_generate_gemini_text(prompt: str, model_name: str | None = None):
        if '"mode": "PRE_GENERATION"' in prompt:
            return SimpleNamespace(text=json.dumps(seed, ensure_ascii=False), model_name=model_name or "gemini-test")
        if '"mode": "POST_REVIEW"' in prompt:
            return SimpleNamespace(text="not json", model_name=model_name or "gemini-test")
        return SimpleNamespace(
            text=json.dumps({"scripts": [base_item.model_dump(mode="json")]}, ensure_ascii=False),
            model_name=model_name or "gemini-test",
        )

    monkeypatch.setattr("app.script_service.generate_gemini_text", fake_generate_gemini_text)
    app = create_app()
    repo = BreakdownRepository()
    persona_record = repo.create_creator_persona_records(
        personas=[base_item.creator_persona.model_dump(mode="json")],
        provider="mock",
        model_name="mock-persona-agent-v1",
    )[0]

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/scripts/generate",
            json={
                "script_count": 1,
                "script_type": "all",
                "source_breakdown_ids": [],
                "persona_id": persona_record.id,
            },
        )

    assert response.status_code == 200
    created = response.json()[0]
    assert created["script"]["hook"] == seed["hook"]
    assert created["script"]["voiceover"] == seed["script_voiceover"]
    with repo._connect() as connection:
        rows = connection.execute(
            "SELECT status, request_json FROM script_model_runs ORDER BY created_at"
        ).fetchall()
    assert [json.loads(row["request_json"])["generation_mode"] for row in rows] == [
        "voiceover_pre_generation",
        "sequential_single_script_calls",
        "voiceover_post_review",
        "voiceover_post_review",
    ]
    assert [row["status"] for row in rows] == ["succeeded", "succeeded", "failed", "failed"]
    get_settings.cache_clear()


def test_voiceover_pre_generation_retries_banned_claim_seed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("VIDEO_BREAKDOWN_PROVIDER", "gemini")
    monkeypatch.setenv("VIDEO_BREAKDOWN_SKIP_DOTENV", "1")
    monkeypatch.setenv("VIDEO_BREAKDOWN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("VIDEO_BREAKDOWN_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("GOOGLE_VERTEX_AI_API_KEY", "test-key")
    get_settings.cache_clear()

    base_item = build_mock_script_item(0, "all", [])
    valid_seed = voiceover_seed_from_item(base_item)
    bad_seed = json.loads(json.dumps(valid_seed, ensure_ascii=False))
    bad_seed["script_voiceover"][1] = "Every new tool promised automatic money, which is a huge red flag."
    bad_seed["localized_zh"]["script_voiceover"][1] = "每个新工具都承诺能自动赚钱，这绝对是个危险信号。"
    pre_generation_calls = 0

    async def fake_generate_gemini_text(prompt: str, model_name: str | None = None):
        nonlocal pre_generation_calls
        if '"mode": "PRE_GENERATION"' in prompt:
            pre_generation_calls += 1
            payload = bad_seed if pre_generation_calls == 1 else valid_seed
            return SimpleNamespace(text=json.dumps(payload, ensure_ascii=False), model_name=model_name or "gemini-test")
        if '"mode": "POST_REVIEW"' in prompt:
            return SimpleNamespace(
                text=json.dumps({"requires_patch": False, "reason": "Already aligned."}, ensure_ascii=False),
                model_name=model_name or "gemini-test",
            )
        return SimpleNamespace(
            text=json.dumps({"scripts": [base_item.model_dump(mode="json")]}, ensure_ascii=False),
            model_name=model_name or "gemini-test",
        )

    monkeypatch.setattr("app.script_service.generate_gemini_text", fake_generate_gemini_text)
    app = create_app()
    repo = BreakdownRepository()
    persona_record = repo.create_creator_persona_records(
        personas=[base_item.creator_persona.model_dump(mode="json")],
        provider="mock",
        model_name="mock-persona-agent-v1",
    )[0]

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/scripts/generate",
            json={
                "script_count": 1,
                "script_type": "all",
                "source_breakdown_ids": [],
                "persona_id": persona_record.id,
            },
        )

    assert response.status_code == 200
    assert pre_generation_calls == 2
    created = response.json()[0]
    assert created["script"]["voiceover"] == valid_seed["script_voiceover"]
    with repo._connect() as connection:
        rows = connection.execute(
            "SELECT status, error_message, request_json FROM script_model_runs ORDER BY created_at"
        ).fetchall()
    assert [json.loads(row["request_json"])["generation_mode"] for row in rows] == [
        "voiceover_pre_generation",
        "voiceover_pre_generation",
        "sequential_single_script_calls",
        "voiceover_post_review",
    ]
    assert [row["status"] for row in rows] == ["failed", "succeeded", "succeeded", "succeeded"]
    assert "automatic money" in rows[0]["error_message"]
    get_settings.cache_clear()


def test_selected_creator_persona_overrides_model_persona_fields():
    selected_persona = build_mock_script_item(0, "all", []).creator_persona.model_dump(mode="json")
    generated = build_mock_script_item(1, "all", []).model_dump(mode="json")
    generated["topic_plan"]["persona"] = "Maya Rivera"
    generated["script"]["persona"] = "Samira Haddad"
    generated["topic_plan"]["localized"]["zh"]["persona"] = "模型写偏的人设"
    generated["script"]["localized"]["zh"]["persona"] = "另一个模型人设"

    batch = parse_script_agent_batch(
        json.dumps({"scripts": [generated]}, ensure_ascii=False),
        [],
        selected_persona=selected_persona,
    )
    item = batch.scripts[0]

    assert item.creator_persona.display_name == selected_persona["display_name"]
    assert item.script.persona == creator_persona_label(selected_persona)
    assert item.topic_plan.persona == item.script.persona
    assert item.script.localized["zh"]["persona"] == creator_persona_label_zh(selected_persona)
    assert item.topic_plan.localized["zh"]["persona"] == item.script.localized["zh"]["persona"]
    assert f"[Direct Callout] {selected_persona['audience_callout']}" not in item.topic_plan.hook_candidates


def test_script_agent_normalizes_storyboard_action_alias_before_persona_sync():
    selected_persona = build_mock_script_item(0, "all", []).creator_persona.model_dump(mode="json")
    generated = build_mock_script_item(1, "all", ["source_1"]).model_dump(mode="json")
    shot = generated["storyboard"][0]
    shot["action"] = shot.pop("character_action")
    shot["localized"]["zh"]["action"] = shot["localized"]["zh"].pop("character_action")

    batch = parse_script_agent_batch(
        json.dumps({"scripts": [generated]}, ensure_ascii=False),
        ["source_1"],
        selected_persona=selected_persona,
    )

    parsed_shot = batch.scripts[0].storyboard[0]
    assert parsed_shot.character_action
    assert selected_persona["display_name"] in parsed_shot.character_action
    assert parsed_shot.localized["zh"]["character_action"]


def test_script_agent_normalizes_common_model_type_drift():
    item = build_mock_script_item(0, "all", ["source_1"]).model_dump(mode="json")
    item["script"]["voiceover"] = " ".join(item["script"]["voiceover"])
    item["script"]["visual"] = [
        "Creator sits at the desk and points at product notes.",
        "Moras workflow recording shows product-card selection.",
    ]
    item["script"]["sound_effect"] = ["None", "Subtle click", "Notification chime"]
    item["script"]["localized"]["zh"]["visual"] = ["创作者坐在桌前指向产品笔记。", "Moras 工作流录屏展示商品卡选择。"]
    item["script"]["localized"]["zh"]["voiceover"] = " ".join(item["script"]["localized"]["zh"]["voiceover"])
    item["script"]["localized"]["zh"]["sound_effect"] = ["无", "轻微点击声", "提示音"]
    item["storyboard"][0]["duration"] = 6
    item["storyboard"][0]["props"] = "Smartphone on desk, sticky notes."
    item["storyboard"][0]["sound_effects"] = "Whoosh for comment screenshot entrance."
    item["storyboard"][0]["visual_elements"] = "Comment screenshot pop-up on the left side."
    item["storyboard"][0]["localized"]["zh"]["props"] = "手机和便签。"
    item["storyboard"][0]["localized"]["zh"]["sound_effects"] = "截图划入音效。"
    item["storyboard"][0]["localized"]["zh"]["visual_elements"] = "左侧弹出评论截图。"
    item["storyboard"][1]["props"] = "N/A"
    item["storyboard"][1]["sound_effects"] = "None."
    item["storyboard"][1]["visual_elements"] = "None."
    item["video_prompt"]["consistency_notes"] = "Maintain the exact wardrobe and props across all segments."
    item["video_prompt"]["localized"]["zh"]["consistency_notes"] = "在所有片段中保持完全一致的服装和道具。"
    item["production_asset_plan"][0]["moras_asset_category"] = "None"
    item["production_asset_plan"][1]["moras_asset_category"] = "workflow screen recording"
    item["production_asset_plan"][2]["moras_asset_category"] = "None."
    item["production_asset_plan"][2]["layer"] = "caption_layer"
    item["risk_check"]["forbidden_claims_checked"] = True
    item["risk_check"]["compliance_notes"] = "No guaranteed income claims. Workflow proof only."

    batch = parse_script_agent_batch(json.dumps({"scripts": [item]}, ensure_ascii=False), ["source_1"])
    parsed = batch.scripts[0]

    assert isinstance(parsed.script.visual, str)
    assert isinstance(parsed.script.voiceover, list)
    assert len(parsed.script.voiceover) > 1
    assert "product notes" in parsed.script.visual
    assert isinstance(parsed.script.sound_effect, str)
    assert parsed.storyboard[0].props == ["Smartphone on desk, sticky notes."]
    assert parsed.storyboard[0].sound_effects == ["Whoosh for comment screenshot entrance."]
    assert isinstance(parsed.storyboard[0].visual_elements, list)
    assert parsed.storyboard[0].visual_elements
    assert parsed.storyboard[0].localized["zh"]["props"] == ["手机和便签。"]
    assert parsed.storyboard[0].localized["zh"]["sound_effects"] == ["截图划入音效。"]
    assert isinstance(parsed.storyboard[0].localized["zh"]["visual_elements"], list)
    assert parsed.storyboard[0].localized["zh"]["visual_elements"]
    assert parsed.storyboard[1].props == []
    assert parsed.video_prompt.consistency_notes == ["Maintain the exact wardrobe and props across all segments."]
    assert parsed.production_asset_plan[0].moras_asset_category == "none"
    assert parsed.production_asset_plan[1].moras_asset_category == "workflow_screen_recording"
    assert parsed.production_asset_plan[2].moras_asset_category == "none"
    assert parsed.production_asset_plan[2].layer == "overlay"
    first_duration = storyboard_duration_seconds(parsed.storyboard[0].timestamp, parsed.storyboard[0].duration)
    assert first_duration is not None
    assert first_duration >= storyboard_voiceover_min_duration_sec(parsed.storyboard[0].voiceover)
    assert parsed.risk_check.forbidden_claims_checked
    assert parsed.risk_check.compliance_notes == ["No guaranteed income claims. Workflow proof only."]


def test_script_agent_parser_drops_risk_check_localized_wrapper():
    item = build_mock_script_item(0, "all", ["source_1"]).model_dump(mode="json")
    item["risk_check"]["localized"] = {
        "zh": {
            "compliance_notes": ["不包含保证收益或保证出单承诺，只展示 Moras 工作流。"],
            "allowed_for_video_factory": True,
        }
    }

    parsed = parse_script_agent_batch(json.dumps({"scripts": [item]}, ensure_ascii=False), ["source_1"]).scripts[0]

    assert parsed.risk_check.allowed_for_video_factory is True
    assert "localized" not in parsed.risk_check.model_dump(mode="json")


def test_script_agent_parser_repairs_safe_style_drift_before_strict_schema():
    item = build_mock_script_item(0, "all", ["source_1"]).model_dump(mode="json")
    bad_line = "It gives me a ready-to-post shoppable video with the cart attached."
    item["script"]["voiceover"][3] = bad_line
    item["script"]["localized"]["zh"]["voiceover"][3] = "它给我一个带购物车视频。"
    item["storyboard"][3]["voiceover"] = bad_line
    item["storyboard"][3]["localized"]["zh"]["voiceover"] = "它给我一个带购物车视频。"

    parsed = parse_script_agent_batch(json.dumps({"scripts": [item]}, ensure_ascii=False), ["source_1"]).scripts[0]
    payload = parsed.model_dump(mode="json")
    payload_text = json.dumps(
        {
            "topic_plan": payload["topic_plan"],
            "script": payload["script"],
            "storyboard": [
                {
                    "voiceover": shot["voiceover"],
                    "overlay": shot["overlay"],
                    "localized": {
                        "zh": {
                            "voiceover": shot["localized"]["zh"]["voiceover"],
                            "overlay": shot["localized"]["zh"]["overlay"],
                        }
                    },
                }
                for shot in payload["storyboard"]
            ],
        },
        ensure_ascii=False,
    ).lower()

    assert "cart attached" not in payload_text
    assert "ready-to-post" not in payload_text
    assert "shoppable" not in payload_text
    assert "带购物车视频" not in payload_text
    assert "next step visible" in payload_text


def test_script_agent_parser_expands_thin_voiceover_and_resyncs_storyboard():
    item = build_mock_script_item(0, "all", ["source_1"]).model_dump(mode="json")
    item["script"]["voiceover"] = [
        "The sample excuse is expensive.",
        "I stopped buying samples first.",
        "Now I open Moras.",
        "I choose a product.",
        "Then I hit Generate.",
    ]
    item["script"]["localized"]["zh"]["voiceover"] = [
        "买样品这个借口很贵。",
        "我先不买样品了。",
        "现在我打开 Moras。",
        "我选择一个商品。",
        "然后我点击 Generate。",
    ]

    parsed = parse_script_agent_batch(json.dumps({"scripts": [item]}, ensure_ascii=False), ["source_1"]).scripts[0]
    spoken_lines = script_spoken_lines_for_length(parsed.script.voiceover, parsed.script.cta)
    publishable_text = json.dumps(
        {
            "script": parsed.script.model_dump(mode="json"),
            "storyboard": [
                {
                    "voiceover": shot.voiceover,
                    "overlay": shot.overlay,
                    "localized": shot.localized,
                }
                for shot in parsed.storyboard
            ],
        },
        ensure_ascii=False,
    ).lower()

    assert len(parsed.script.voiceover) >= 11
    assert sum(english_word_count(line) for line in spoken_lines) >= 90
    assert script_voiceover_estimated_duration_sec(spoken_lines) >= 35
    assert len(parsed.storyboard) >= 5
    assert parsed.video_prompt.target_duration_sec >= 35
    assert parsed.script.localized["zh"]["voiceover"][0]
    assert re.search(r"[\u3400-\u9fff]", parsed.storyboard[0].localized["zh"]["voiceover"])
    for forbidden in ["sample", "buy samples", "another test", "测试", "样品"]:
        assert forbidden not in publishable_text


def test_script_agent_rejects_storyboard_duration_too_short_for_voiceover():
    item = build_mock_script_item(0, "all", []).model_dump(mode="json")
    item["storyboard"][0]["timestamp"] = "0s-2s"
    item["storyboard"][0]["duration"] = "2s"
    item["storyboard"][0]["voiceover"] = "That course charged five hundred dollars for advice I still rewrote myself."
    item["storyboard"][0]["localized"]["zh"]["duration"] = "4秒"
    item["storyboard"][0]["localized"]["zh"]["voiceover"] = "那个课收了五百美元，最后我还是自己重写。"

    with pytest.raises(ValidationError, match="voiceover needs about"):
        ScriptAgentItem.model_validate(item)


def test_script_agent_rejects_short_voiceover_stretched_without_visual_hold():
    item = build_mock_script_item(0, "all", []).model_dump(mode="json")
    shot = item["storyboard"][0]
    shot["timestamp"] = "0s-6.5s"
    shot["duration"] = "6.5s"
    shot["voiceover"] = "No blank drafts here. Five videos queued."
    shot["camera"] = "Vertical creator close-up with tight phone framing."
    shot["character_action"] = "DealNotesZane leans toward camera and delivers the opening warning."
    shot["facial_expression"] = "Tense but conversational, with direct eye contact."
    shot["background"] = "Creator desk with phone, laptop, product package, and soft daylight."
    shot["purpose"] = "Open with a direct blank-page hook."
    shot["localized"]["zh"]["duration"] = "6.5秒"
    shot["localized"]["zh"]["voiceover"] = "没有空白草稿。五条视频已排队。"

    with pytest.raises(ValidationError, match="short voiceover only supports"):
        ScriptAgentItem.model_validate(item)


def test_script_agent_rejects_repeated_storyboard_visual_elements():
    item = build_mock_script_item(0, "all", []).model_dump(mode="json")
    repeated = ["caption", "gesture", "proof asset", "CTA prompt"]
    repeated_zh = ["短字幕", "手势", "证明素材", "CTA 提示"]
    for shot in item["storyboard"][:3]:
        shot["visual_elements"] = list(repeated)
        shot["localized"]["zh"]["visual_elements"] = list(repeated_zh)

    with pytest.raises(ValidationError, match="visual_elements must change by shot"):
        ScriptAgentItem.model_validate(item)


def test_mock_storyboard_timing_and_visual_elements_are_editor_ready():
    item = build_mock_script_item(0, "all", []).model_dump(mode="json")
    zh_signatures = []
    for shot in item["storyboard"]:
        duration = storyboard_duration_seconds(shot["timestamp"], shot["duration"])
        required = storyboard_voiceover_min_duration_sec(shot["voiceover"])
        assert duration is not None
        assert duration >= required
        zh_signatures.append(tuple(shot["localized"]["zh"]["visual_elements"]))

    assert len(zh_signatures) == len(set(zh_signatures))


def test_script_agent_parser_preserves_continuous_storyboard_rows_and_extends_duration():
    item = build_mock_script_item(0, "all", ["source_1"]).model_dump(mode="json")
    shot = item["storyboard"][2]
    original_shot_id = shot["shot_id"]
    original_count = len(item["storyboard"])
    shot["timestamp"] = "12-16s"
    shot["duration"] = "4s"
    shot["voiceover"] = (
        "I use Moras now. I choose a product and hit Generate."
    )
    shot["localized"]["zh"]["voiceover"] = (
        "我现在用 Moras。选择商品，然后点击生成。"
    )
    item["production_asset_plan"][0]["shot_ids"] = [shot["shot_id"]]

    batch = parse_script_agent_batch(json.dumps({"scripts": [item]}, ensure_ascii=False), ["source_1"])
    parsed = batch.scripts[0]
    preserved = next(row for row in parsed.storyboard if row.shot_id == original_shot_id)
    duration = storyboard_duration_seconds(preserved.timestamp, preserved.duration)
    required = storyboard_voiceover_min_duration_sec(preserved.voiceover)

    assert len(parsed.storyboard) == original_count
    assert duration is not None
    assert duration >= required
    assert parsed.production_asset_plan[0].shot_ids == [original_shot_id]
    assert preserved.localized["zh"]["voiceover"]


def test_script_agent_parser_calibrates_short_english_voiceover_without_chinese_inflation():
    item = build_mock_script_item(0, "all", ["source_1"]).model_dump(mode="json")
    shot = item["storyboard"][0]
    shot["timestamp"] = "0s-6.5s"
    shot["duration"] = "6.5s"
    shot["voiceover"] = "No blank drafts here. Five videos queued."
    shot["character_action"] = "DealNotesZane leans toward camera and delivers the opening warning."
    shot["purpose"] = "Open with a direct blank-page hook."
    shot["localized"]["zh"]["duration"] = "6.5秒"
    shot["localized"]["zh"]["voiceover"] = "没有空白草稿。五条视频已排队。"

    batch = parse_script_agent_batch(json.dumps({"scripts": [item]}, ensure_ascii=False), ["source_1"])
    parsed = batch.scripts[0].storyboard[0]
    duration = storyboard_duration_seconds(parsed.timestamp, parsed.duration)

    assert duration == pytest.approx(storyboard_voiceover_min_duration_sec(parsed.voiceover), abs=0.01)
    assert duration < 4
    assert parsed.localized["zh"]["duration"] == f"{duration:g}秒"


def test_script_agent_localized_retry_note_uses_character_action_field():
    note = script_agent_rejection_note("topic_plan.localized.zh.hook_candidates is required")

    assert "storyboard.localized.zh.character_action" in note
    assert "production_asset_plan.localized.zh" in note
    assert "storyboard.localized.zh.action" not in note


def test_script_agent_rejects_english_identity_localized_zh():
    item = build_mock_script_item(0, "all", ["source_1"]).model_dump(mode="json")
    item["script"]["localized"]["zh"]["hook"] = item["script"]["hook"]

    with pytest.raises(HTTPException) as exc_info:
        parse_script_agent_batch(json.dumps({"scripts": [item]}, ensure_ascii=False), ["source_1"])

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["error"]["code"] == "SCRIPT_OUTPUT_SCHEMA_INVALID"
    assert "script.localized.zh.hook" in exc_info.value.detail["error"]["message"]


def test_script_agent_rejects_missing_or_non_cjk_localized_zh():
    missing_zh_item = build_mock_script_item(0, "all", ["source_1"]).model_dump(mode="json")
    missing_zh_item["topic_plan"]["localized"].pop("zh")

    with pytest.raises(HTTPException) as missing_exc:
        parse_script_agent_batch(json.dumps({"scripts": [missing_zh_item]}, ensure_ascii=False), ["source_1"])

    assert missing_exc.value.status_code == 422
    assert missing_exc.value.detail["error"]["code"] == "SCRIPT_OUTPUT_SCHEMA_INVALID"
    assert "topic_plan.localized.zh.title" in missing_exc.value.detail["error"]["message"]

    no_cjk_item = build_mock_script_item(0, "all", ["source_1"]).model_dump(mode="json")
    no_cjk_item["topic_plan"]["localized"]["zh"]["title"] = "No Chinese title"

    with pytest.raises(HTTPException) as no_cjk_exc:
        parse_script_agent_batch(json.dumps({"scripts": [no_cjk_item]}, ensure_ascii=False), ["source_1"])

    assert no_cjk_exc.value.status_code == 422
    assert no_cjk_exc.value.detail["error"]["code"] == "SCRIPT_OUTPUT_SCHEMA_INVALID"
    assert "topic_plan.localized.zh.title" in no_cjk_exc.value.detail["error"]["message"]


def create_mock_script(client: TestClient) -> dict:
    persona_response = client.post("/api/creator-personas/generate", json={"persona_count": 1})
    assert persona_response.status_code == 200
    selected_persona_record = persona_response.json()[0]
    script_response = client.post(
        "/api/scripts/generate",
        json={
            "script_count": 1,
            "script_type": "all",
            "source_breakdown_ids": [],
            "persona_id": selected_persona_record["id"],
        },
    )
    assert script_response.status_code == 200
    return script_response.json()[0]


def test_breakdown_full_mock_flow(client: TestClient):
    created_response = client.post("/api/breakdowns", json={"video_url": "/uploads/source.mp4"})

    assert created_response.status_code == 200
    created = created_response.json()
    breakdown_id = created["id"]
    assert created["status"] == "succeeded"
    assert created["provider"] == "mock"
    assert created["classification"]["taxonomy_version"] == "moras_viral_factor_v1"
    assert created["classification"]["hook_type"] == "禁忌型"
    assert "Tutorial Learner" in created["classification"]["audience_segments"]
    assert "structure_protocol" in created
    assert created["reference_storyboard"][0]["shot_id"] == "shot_1"
    assert created["reference_storyboard"][0]["character_action"]
    assert "category_slots" not in created

    list_response = client.get("/api/breakdowns")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [breakdown_id]

    get_response = client.get(f"/api/breakdowns/{breakdown_id}")
    assert get_response.status_code == 200
    assert get_response.json()["script_agent_bridge"]["reusable_pattern"].startswith("[目标人群")

    export_response = client.get(f"/api/breakdowns/{breakdown_id}/export/markdown")
    assert export_response.status_code == 200
    assert "# 视频拆解报告" in export_response.text
    assert "## 爆款因子分类" in export_response.text
    assert "Hook 五要素" in export_response.text
    assert "## 爆款参考分镜脚本" in export_response.text
    assert "final_script" not in export_response.text

    runs = BreakdownRepository().model_runs_for(breakdown_id)
    assert len(runs) == 1
    assert runs[0]["status"] == "succeeded"
    assert runs[0]["model_name"] == "mock-video-breakdown-v1"
    assert runs[0]["prompt_version"] == "k2lab_social_video_breakdown_v1"


def test_delete_breakdown_removes_record_and_model_runs(client: TestClient):
    created_response = client.post("/api/breakdowns", json={"video_url": "/uploads/source.mp4"})
    assert created_response.status_code == 200
    breakdown_id = created_response.json()["id"]

    delete_response = client.delete(f"/api/breakdowns/{breakdown_id}")
    assert delete_response.status_code == 204

    list_response = client.get("/api/breakdowns")
    assert list_response.status_code == 200
    assert list_response.json() == []

    get_response = client.get(f"/api/breakdowns/{breakdown_id}")
    assert get_response.status_code == 404
    assert BreakdownRepository().model_runs_for(breakdown_id) == []


def test_mock_provider_does_not_download_remote_social_url(client: TestClient):
    response = client.post("/api/breakdowns", json={"video_url": "https://www.tiktok.com/@demo/video/1"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["source_video"]["original_url"] == "https://www.tiktok.com/@demo/video/1"
    assert body["source_video"]["imported_video_url"] == "https://www.tiktok.com/@demo/video/1"


def test_duplicate_remote_video_reuses_existing_breakdown(client: TestClient):
    first_response = client.post("/api/breakdowns", json={"video_url": "https://www.tiktok.com/@demo/video/1?utm_source=a"})
    assert first_response.status_code == 200
    first = first_response.json()
    assert first["reused_existing"] is False

    second_response = client.post(
        "/api/breakdowns",
        json={"video_url": "https://www.tiktok.com/@another-handle/video/1?utm_source=b&share_source=copy"},
    )
    assert second_response.status_code == 200
    second = second_response.json()

    assert second["id"] == first["id"]
    assert second["reused_existing"] is True
    assert second["source_video"]["original_url"] == "https://www.tiktok.com/@demo/video/1?utm_source=a"

    list_response = client.get("/api/breakdowns")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [first["id"]]
    assert len(BreakdownRepository().model_runs_for(first["id"])) == 1


def test_upload_flow_uses_uploaded_file(client: TestClient, tmp_path: Path):
    sample = tmp_path / "sample.mp4"
    sample.write_bytes(b"fake video bytes")

    with sample.open("rb") as handle:
        response = client.post("/api/breakdowns/upload", files={"file": ("sample.mp4", handle, "video/mp4")})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["source_video"]["imported_video_url"].startswith("/uploads/")


def test_director_parser_sanitizes_real_model_drift():
    raw = {
        "version": "director-agent-v1.0.0",
        "metadata": {
            "target_aspect_ratio": "9:16",
            "total_duration_sec": 30,
            "render_intent": "plan_only",
            "director_model": "gemini-3.5-flash",
            "provider_route": "vertex-primary-aihubmix-fallback",
        },
        "timeline": {
            "tracks": {
                "video_tracks": [
                    {
                        "layer": "base_track",
                        "clips": [
                            {
                                "clip_id": "moras_screen_asset_2",
                                "source_type": "real_moras_screen_recording",
                                "source_reference_id": "asset_2",
                                "timeline_start_sec": 0,
                                "timeline_end_sec": 16,
                                "duration_sec": 16,
                                "layer_role": "workflow_cutaway",
                                "crop_and_scale": None,
                                "manual_binding_status": "pending_binding",
                                "manual_prompt_text": "",
                                "bound_asset_url": None,
                                "notes": "Moras product-to-video workflow.",
                            },
                            {
                                "clip_id": "seedance_clip_1",
                                "source_type": "seedance_generation",
                                "source_reference_id": "video_prompt.segments[1]",
                                "timeline_start_sec": 16,
                                "timeline_end_sec": 30,
                                "duration_sec": 14,
                                "crop_and_scale": None,
                                "manual_binding_status": "pending_binding",
                                "manual_prompt_text": "Creator desk scene.",
                                "notes": "Creator desk scene.",
                            },
                        ],
                    },
                    {
                        "layer": "overlay",
                        "clips": [
                            {
                                "clip_id": "hyperframes_subtitle_overlay",
                                "source_type": "subtitle_overlay",
                                "source_reference_id": "script.voiceover+script.overlay",
                                "timeline_start_sec": 0,
                                "timeline_end_sec": 30,
                                "duration_sec": 30,
                                "crop_and_scale": None,
                                "manual_binding_status": "not_applicable",
                                "notes": "Subtitle layer.",
                            }
                        ],
                    },
                ],
                "audio_tracks": [
                    {
                        "layer": "audio",
                        "clips": [
                            {
                                "clip_id": "primary_voiceover",
                                "source_type": "voiceover",
                                "source_reference_id": "script.voiceover",
                                "layer_role": "primary_voiceover",
                                "timeline_start_sec": 0,
                                "timeline_end_sec": 30,
                                "duration_sec": 30,
                                "crop_and_scale": None,
                                "manual_binding_status": "pending_binding",
                                "manual_prompt_text": "",
                                "bound_asset_url": None,
                                "volume_db": 0,
                                "text_content": "Voiceover text.",
                                "voicePrompt": "Synthetic TTS delivery: warm, brisk, and grounded.",
                                "voiceAssetRef": "creator_persona.digital_human_prompt_assets.voice_style_prompt",
                                "notes": "Voiceover.",
                            },
                            {
                                "clip_id": "click_sfx",
                                "source_type": "sound_effect",
                                "source_reference_id": "storyboard[0].sound",
                                "layer_role": "sound_effect",
                                "timeline_start_sec": 8,
                                "timeline_end_sec": 9,
                                "duration_sec": 1,
                                "crop_and_scale": None,
                                "manual_binding_status": "pending_binding",
                                "manual_prompt_text": "",
                                "bound_asset_url": None,
                                "volume_db": -6,
                                "notes": "Click.",
                            },
                        ],
                    }
                ],
            }
        },
        "asset_resolution": [
            {
                "asset_ref": "asset_2",
                "source_plan_id": "asset_2",
                "required_asset_type": "real_moras_screen_recording",
                "moras_asset_category": "workflow_screen_recording",
                "resolution_status": "missing_placeholder",
                "resolver_note": "Needs approved Moras asset.",
            },
            {
                "asset_ref": "seedance_clip_1",
                "source_plan_id": "video_prompt.segments[1]",
                "required_asset_type": "manual_seedance_clip",
                "moras_asset_category": "none",
                "resolution_status": "missing_placeholder",
                "resolver_note": "Needs manual upload.",
            },
        ],
        "tool_dispatches": [
            {
                "sequence_order": 1,
                "tool_name": "asset_resolver",
                "status": "blocked",
                "parameters": {},
                "expected_output": "asset table",
            },
            {
                "sequence_order": 2,
                "tool_name": "run_ffmpeg_mix",
                "status": "blocked",
                "parameters": {},
                "expected_output": "draft MP4",
            },
        ],
        "validation_summary": {
            "timeline_continuity": "base track covers target duration",
            "layer_collision_check": "validated",
            "seedance_limit_check": "validated",
            "asset_readiness": "pending asset binding",
            "render_scope": "plan only",
        },
    }

    output = parse_director_output(json.dumps(raw))

    base_clips = output.timeline.tracks.video_tracks[0].clips
    assert base_clips[0].source_type == "library_asset"
    assert base_clips[0].manual_binding_status == "pending_binding"
    assert base_clips[0].crop_and_scale.width == 1080
    assert base_clips[1].manual_binding_status == "pending_upload"
    overlay_clip = output.timeline.tracks.video_tracks[1].clips[0]
    assert overlay_clip.source_type == "hyperframes_overlay"
    assert overlay_clip.manual_binding_status == "not_required"
    audio_clips = output.timeline.tracks.audio_tracks[0].clips
    assert audio_clips[0].source_type == "tts_voiceover"
    assert audio_clips[0].voice_prompt == "Synthetic TTS delivery: warm, brisk, and grounded."
    assert audio_clips[0].voice_asset_ref == "creator_persona.digital_human_prompt_assets.voice_style_prompt"
    assert audio_clips[1].source_type == "sound_design"
    assert not hasattr(audio_clips[0], "manual_binding_status")


def test_director_parser_sanitizes_ai_broll_clip_alias():
    raw = {
        "version": "director-agent-v1.0.0",
        "metadata": {
            "target_aspect_ratio": "9:16",
            "total_duration_sec": 30,
            "render_intent": "plan_only",
            "director_model": "gemini-3.5-flash",
            "provider_route": "vertex-primary-aihubmix-fallback",
        },
        "timeline": {
            "tracks": {
                "video_tracks": [
                    {
                        "layer": "base_track",
                        "clips": [
                            {
                                "clip_id": "ai_broll_1",
                                "source_type": "ai_generated_broll",
                                "timeline_start_sec": 0,
                                "timeline_end_sec": 8,
                                "duration_sec": 8,
                                "crop_and_scale": None,
                                "manual_binding_status": "pending_binding",
                                "notes": "AI-generated lifestyle b-roll.",
                            },
                            {
                                "clip_id": "moras_workflow_1",
                                "source_type": "moras_screen_recording",
                                "source_reference_id": "asset_1",
                                "timeline_start_sec": 8,
                                "timeline_end_sec": 30,
                                "duration_sec": 22,
                                "crop_and_scale": None,
                                "manual_binding_status": "pending_binding",
                                "notes": "Moras workflow screen recording.",
                            }
                        ],
                    }
                ],
                "audio_tracks": [],
            }
        },
        "asset_resolution": [],
        "tool_dispatches": [
            {
                "sequence_order": 1,
                "tool_name": "manual_veo_generation",
                "status": "blocked",
                "parameters": {},
                "expected_output": "manual generated clip",
            }
        ],
        "validation_summary": {
            "timeline_continuity": "base track covers target duration",
            "layer_collision_check": "validated",
            "seedance_limit_check": "validated",
            "asset_readiness": "pending asset upload",
            "render_scope": "plan only",
        },
    }

    output = parse_director_output(json.dumps(raw))

    clip = output.timeline.tracks.video_tracks[0].clips[0]
    assert clip.source_type == "veo_generation"
    assert clip.source_reference_id == "ai_broll_1"
    assert clip.manual_binding_status == "pending_upload"
    assert clip.crop_and_scale.width == 1080


def test_script_agent_mock_flow(client: TestClient, tmp_path: Path):
    breakdown_response = client.post("/api/breakdowns", json={"video_url": "/uploads/source.mp4"})
    assert breakdown_response.status_code == 200
    breakdown_id = breakdown_response.json()["id"]
    persona_response = client.post("/api/creator-personas/generate", json={"persona_count": 1})
    assert persona_response.status_code == 200
    selected_persona_record = persona_response.json()[0]
    selected_persona = selected_persona_record["creator_persona"]
    assert selected_persona["localized"]["zh"]["display_name"] == selected_persona["display_name"]
    assert has_cjk(selected_persona["localized"]["zh"]["role"])

    generate_response = client.post(
        "/api/scripts/generate",
        json={
            "script_count": 2,
            "script_type": "Beginner Trap",
            "source_breakdown_ids": [breakdown_id],
            "persona_id": selected_persona_record["id"],
        },
    )

    assert generate_response.status_code == 200
    scripts = generate_response.json()
    assert len(scripts) == 2
    assert len({script["script"]["script_title"] for script in scripts}) == 2
    assert len({script["script"]["localized"]["zh"]["script_title"] for script in scripts}) == 2
    assert len({script["script"]["hook"] for script in scripts}) == 2
    assert len({" ".join(script["script"]["voiceover"][:2]) for script in scripts}) == 2
    assert len({"|".join(script["source_component_summary"][:4]) for script in scripts}) == 2
    assert scripts[0]["status"] == "ready"
    assert scripts[0]["script_type"] == "Beginner Trap"
    assert scripts[0]["source_breakdown_ids"] == [breakdown_id]
    assert scripts[0]["topic_plan"]["moras_relevance_score"] >= 0
    assert scripts[0]["topic_plan"]["localized"]["zh"]["title"]
    assert scripts[0]["topic_plan"]["localized"]["zh"]["hook_candidates"][0]
    assert not has_cjk(scripts[0]["topic_plan"]["title"])
    assert not has_cjk(scripts[0]["topic_plan"]["trend_source"])
    assert has_cjk(scripts[0]["topic_plan"]["localized"]["zh"]["title"])
    assert scripts[0]["topic_plan"]["localized"]["zh"]["title"] != scripts[0]["topic_plan"]["title"]
    assert scripts[0]["script"]["script_title"]
    assert scripts[0]["script"]["voiceover"]
    assert len(scripts[0]["script"]["voiceover"]) >= 11
    assert sum(english_word_count(line) for line in scripts[0]["script"]["voiceover"]) >= 90
    assert scripts[0]["script"]["localized"]["zh"]["hook"]
    assert scripts[0]["script"]["localized"]["zh"]["voiceover"][0]
    assert not has_cjk(scripts[0]["script"]["script_title"])
    assert not has_cjk(scripts[0]["script"]["hook"])
    assert not has_cjk(scripts[0]["script"]["voiceover"][0])
    assert has_cjk(scripts[0]["script"]["localized"]["zh"]["hook"])
    assert has_cjk(scripts[0]["script"]["localized"]["zh"]["template"])
    assert scripts[0]["script"]["localized"]["zh"]["hook"] != scripts[0]["script"]["hook"]
    assert len(scripts[0]["storyboard"]) >= 5
    assert scripts[0]["storyboard"][0]["shot_id"] == "shot_1"
    assert scripts[0]["storyboard"][0]["localized"]["zh"]["camera"]
    assert not has_cjk(scripts[0]["storyboard"][0]["camera"])
    assert not has_cjk(scripts[0]["storyboard"][0]["character_action"])
    assert not has_cjk(scripts[0]["storyboard"][0]["overlay"])
    assert has_cjk(scripts[0]["storyboard"][0]["localized"]["zh"]["camera"])
    assert has_cjk(scripts[0]["storyboard"][0]["localized"]["zh"]["character_action"])
    assert has_cjk(scripts[0]["storyboard"][0]["localized"]["zh"]["overlay"])
    assert scripts[0]["creator_persona"]["display_name"]
    assert scripts[0]["creator_persona"]["appearance"]
    assert scripts[0]["creator_persona"]["veo_identity_string"]
    assert scripts[0]["creator_persona"]["reference_image_prompt"]
    prompt_assets = scripts[0]["creator_persona"]["digital_human_prompt_assets"]
    assert prompt_assets["sample_requirement"] == "no_real_sample_required"
    assert prompt_assets["visual_reference_prompt"]
    assert prompt_assets["avatar_motion_prompt"]
    assert prompt_assets["voice_style_prompt"]
    assert prompt_assets["script_delivery_rules"]
    assert scripts[0]["creator_persona"]["localized"]["zh"]["digital_human_prompt_assets"]["voice_style_prompt"]
    persona_names = [script["creator_persona"]["display_name"] for script in scripts]
    assert set(persona_names) == {selected_persona["display_name"]}
    assert not any("Asian" in script["creator_persona"]["reference_image_prompt"] for script in scripts)
    assert scripts[0]["video_prompt"]["aspect_ratio"] == "vertical 9:16"
    assert scripts[0]["video_prompt"]["target_model"] == "Veo 3.1"
    assert scripts[0]["creator_persona"]["display_name"] in scripts[0]["video_prompt"]["character_lock"]
    assert scripts[0]["video_prompt"]["localized"]["zh"]["generation_prompt"]
    assert scripts[0]["production_asset_plan"][0]["asset_type"] == "digital_human_avatar"
    assert scripts[0]["production_asset_plan"][0]["localized"]["zh"]["usage_reason"]
    assert not has_cjk(scripts[0]["production_asset_plan"][0]["usage_reason"])
    assert has_cjk(scripts[0]["production_asset_plan"][0]["localized"]["zh"]["usage_reason"])
    assert scripts[0]["production_asset_plan"][1]["asset_type"] == "real_moras_screen_recording"
    assert scripts[0]["production_asset_plan"][1]["moras_asset_category"] == "workflow_screen_recording"
    assert 35 <= scripts[0]["video_prompt"]["target_duration_sec"] <= 50
    assert 0 < scripts[0]["video_prompt"]["veo_generation_duration_sec"] <= scripts[0]["video_prompt"]["target_duration_sec"]
    assert "seedance_generation_duration_sec" not in scripts[0]["video_prompt"]
    assert len(scripts[0]["video_prompt"]["segments"]) >= 3
    assert scripts[0]["video_prompt"]["segments"][0]["time_range"] == "0s-8s"
    assert scripts[0]["video_prompt"]["segments"][0]["duration_sec"] == 8
    assert scripts[0]["video_prompt"]["segments"][0]["localized"]["zh"]["veo_prompt"]
    assert all(segment["duration_sec"] <= 8 for segment in scripts[0]["video_prompt"]["segments"])
    assert "Veo 3.1" in scripts[0]["video_prompt"]["segments"][0]["veo_prompt"]
    assert scripts[0]["creator_persona"]["display_name"] in scripts[0]["video_prompt"]["segments"][0]["veo_prompt"]
    assert scripts[0]["creator_persona"]["veo_identity_string"] in scripts[0]["video_prompt"]["segments"][0]["veo_prompt"]
    assert "Spoken delivery direction from Persona Agent" in scripts[0]["video_prompt"]["segments"][0]["veo_prompt"]
    assert "same young creator" not in scripts[0]["video_prompt"]["segments"][0]["veo_prompt"].lower()
    assert "voiceover" not in scripts[0]["video_prompt"]["segments"][0]["veo_prompt"].lower()
    segment_prompt_text = scripts[0]["video_prompt"]["segments"][0]["veo_prompt"].lower()
    for forbidden_sample_claim in ["voice sample", "audio sample", "voice clone", "cloned voice", "extracted audio"]:
        assert forbidden_sample_claim not in segment_prompt_text
    assert scripts[0]["risk_check"]["allowed_for_video_factory"] is True
    persona_get_response = client.get(f"/api/creator-personas/{selected_persona_record['id']}")
    assert persona_get_response.status_code == 200
    assert set(persona_get_response.json()["source_script_ids"]) == {script["id"] for script in scripts}
    script_target_duration = scripts[0]["video_prompt"]["target_duration_sec"]

    director_response = client.post("/api/video-factory/director-plans", json={"script_id": scripts[0]["id"]})
    assert director_response.status_code == 200
    director_plan = director_response.json()
    assert director_plan["status"] == "ready"
    assert director_plan["script_id"] == scripts[0]["id"]
    assert director_plan["model_name"] == "mock-director-agent-v1"
    assert director_plan["prompt_version"] == "moras_director_agent_v1"
    assert director_plan["metadata"]["director_model"] == "gemini-3.5-flash"
    assert director_plan["metadata"]["provider_route"] == "vertex-primary-aihubmix-fallback"
    assert director_plan["metadata"]["total_duration_sec"] == script_target_duration
    base_track = next(track for track in director_plan["timeline"]["tracks"]["video_tracks"] if track["layer"] == "base_track")
    assert base_track["clips"][0]["source_type"] == "veo_generation"
    assert base_track["clips"][0]["manual_binding_status"] == "pending_upload"
    assert base_track["clips"][0]["manual_prompt_text"]
    library_clips = [clip for clip in base_track["clips"] if clip["source_type"] == "library_asset"]
    assert library_clips
    assert library_clips[0]["timeline_start_sec"] >= base_track["clips"][0]["timeline_end_sec"]
    assert library_clips[0]["timeline_end_sec"] <= director_plan["metadata"]["total_duration_sec"]
    assert base_track["clips"][-1]["timeline_end_sec"] == script_target_duration
    assert any(asset["asset_ref"] == "veo_clip_1" and asset["required_asset_type"] == "manual_veo_clip" for asset in director_plan["asset_resolution"])
    assert any(dispatch["tool_name"] == "manual_veo_generation" and dispatch["status"] == "blocked" for dispatch in director_plan["tool_dispatches"])
    assert any(dispatch["tool_name"] == "manual_veo_upload" and dispatch["status"] == "blocked" for dispatch in director_plan["tool_dispatches"])
    assert all(dispatch["tool_name"] != "generate_seedance_video" for dispatch in director_plan["tool_dispatches"])
    assert any(dispatch["tool_name"] == "render_hyperframes_subtitle" for dispatch in director_plan["tool_dispatches"])
    audio_track = next(track for track in director_plan["timeline"]["tracks"]["audio_tracks"] if track["layer"] == "audio")
    assert audio_track["clips"][0]["voice_prompt"]
    tts_dispatch = next(dispatch for dispatch in director_plan["tool_dispatches"] if dispatch["tool_name"] == "synthesize_tts")
    assert tts_dispatch["parameters"]["voice_prompt"]
    assert tts_dispatch["parameters"]["voice_asset_ref"] == "creator_persona.digital_human_prompt_assets.voice_style_prompt"
    assert any(dispatch["tool_name"] == "run_ffmpeg_mix" and dispatch["status"] == "blocked" for dispatch in director_plan["tool_dispatches"])
    assert any(asset["required_asset_type"] == "real_moras_screen_recording" and asset["resolution_status"] == "missing_placeholder" for asset in director_plan["asset_resolution"])

    short_clip = tmp_path / "manual-veo-short.mp4"
    make_test_video(short_clip, duration_sec=4, size="720x1280")
    with short_clip.open("rb") as handle:
        short_upload_response = client.post(
            f"/api/video-factory/director-plans/{director_plan['id']}/manual-assets",
            data={"clip_id": "veo_clip_1"},
            files={"file": ("veo-short.mp4", handle, "video/mp4")},
        )
    assert short_upload_response.status_code == 400
    assert short_upload_response.json()["detail"]["error"]["code"] == "MANUAL_ASSET_DURATION_MISMATCH"

    horizontal_clip = tmp_path / "manual-veo-horizontal.mp4"
    make_test_video(horizontal_clip, duration_sec=8, size="1280x720")
    with horizontal_clip.open("rb") as handle:
        rejected_upload_response = client.post(
            f"/api/video-factory/director-plans/{director_plan['id']}/manual-assets",
            data={"clip_id": "veo_clip_1"},
            files={"file": ("veo-horizontal.mp4", handle, "video/mp4")},
        )
    assert rejected_upload_response.status_code == 400
    assert rejected_upload_response.json()["detail"]["error"]["code"] == "MANUAL_ASSET_ASPECT_MISMATCH"
    assert client.get(f"/api/video-factory/director-plans/{director_plan['id']}/manual-assets").json() == []

    sample_clip = tmp_path / "manual-veo-clip.mp4"
    make_test_video(sample_clip, duration_sec=8, size="720x1280")
    with sample_clip.open("rb") as handle:
        upload_response = client.post(
            f"/api/video-factory/director-plans/{director_plan['id']}/manual-assets",
            data={"clip_id": "veo_clip_1"},
            files={"file": ("veo-clip.mp4", handle, "video/mp4")},
        )

    assert upload_response.status_code == 200
    uploaded_asset = upload_response.json()
    assert uploaded_asset["director_plan_id"] == director_plan["id"]
    assert uploaded_asset["script_id"] == scripts[0]["id"]
    assert uploaded_asset["clip_id"] == "veo_clip_1"
    assert uploaded_asset["stored_asset_url"].startswith("/uploads/factory/")
    assert uploaded_asset["file_size_bytes"] > 0
    assert uploaded_asset["duration_sec"] == pytest.approx(8, abs=0.75)
    assert uploaded_asset["width"] == 720
    assert uploaded_asset["height"] == 1280
    assert uploaded_asset["validation_status"] == "validated"
    assert uploaded_asset["review_status"] == "pending_review"
    assert uploaded_asset["semantic_review_status"] == "pending_review"
    assert uploaded_asset["semantic_review_method"] == "human_prompt_match_v1"

    manual_assets_response = client.get(f"/api/video-factory/director-plans/{director_plan['id']}/manual-assets")
    assert manual_assets_response.status_code == 200
    assert manual_assets_response.json()[0]["clip_id"] == "veo_clip_1"

    moras_asset_clip = tmp_path / "moras-workflow.mp4"
    make_test_video(moras_asset_clip, duration_sec=16, size="1280x720")
    with moras_asset_clip.open("rb") as handle:
        moras_upload_response = client.post(
            "/api/video-factory/moras-assets",
            data={
                "asset_type": "real_moras_screen_recording",
                "moras_asset_category": "workflow_screen_recording",
                "title": "Moras workflow recording",
            },
            files={"file": ("moras-workflow.mp4", handle, "video/mp4")},
        )

    assert moras_upload_response.status_code == 200
    moras_asset = moras_upload_response.json()
    assert moras_asset["asset_type"] == "real_moras_screen_recording"
    assert moras_asset["moras_asset_category"] == "workflow_screen_recording"
    assert moras_asset["stored_asset_url"].startswith("/uploads/moras-assets/")
    assert moras_asset["duration_sec"] == pytest.approx(16, abs=0.75)
    assert moras_asset["width"] == 1280
    assert moras_asset["height"] == 720
    assert moras_asset["validation_status"] == "uploaded"
    assert moras_asset["review_status"] == "pending_review"
    assert moras_asset["semantic_review_status"] == "pending_review"
    assert moras_asset["semantic_review_method"] == "human_prompt_match_v1"

    moras_list_response = client.get("/api/video-factory/moras-assets?moras_asset_category=workflow_screen_recording")
    assert moras_list_response.status_code == 200
    assert moras_list_response.json()[0]["id"] == moras_asset["id"]

    binding_response = client.post(
        f"/api/video-factory/director-plans/{director_plan['id']}/asset-bindings",
        json={"asset_ref": "asset_2", "library_asset_id": moras_asset["id"]},
    )
    assert binding_response.status_code == 200
    binding = binding_response.json()
    assert binding["director_plan_id"] == director_plan["id"]
    assert binding["script_id"] == scripts[0]["id"]
    assert binding["asset_ref"] == "asset_2"
    assert binding["source_plan_id"] == "asset_2"
    assert binding["library_asset_id"] == moras_asset["id"]

    bindings_response = client.get(f"/api/video-factory/director-plans/{director_plan['id']}/asset-bindings")
    assert bindings_response.status_code == 200
    assert bindings_response.json()[0]["asset_ref"] == "asset_2"

    blocked_render_response = client.post(f"/api/video-factory/director-plans/{director_plan['id']}/render-jobs")
    assert blocked_render_response.status_code == 200
    created_blocked_render = blocked_render_response.json()
    assert created_blocked_render["status"] == "queued"
    blocked_render = wait_for_render_job(client, created_blocked_render["id"])
    assert blocked_render["status"] == "blocked"
    assert blocked_render["director_plan_id"] == director_plan["id"]
    assert blocked_render["readiness_summary"]["manual_uploaded_count"] >= 1
    assert blocked_render["readiness_summary"]["manual_ready_count"] == 0
    assert blocked_render["readiness_summary"]["blockers"]
    assert any(blocker["type"] == "manual_veo_review" for blocker in blocked_render["readiness_summary"]["blockers"])
    assert any(blocker["type"] == "real_moras_asset_review" for blocker in blocked_render["readiness_summary"]["blockers"])

    retry_blocked_response = client.post(f"/api/video-factory/render-jobs/{blocked_render['id']}/retry")
    assert retry_blocked_response.status_code == 200
    retry_blocked = retry_blocked_response.json()
    assert retry_blocked["id"] != blocked_render["id"]
    assert retry_blocked["status"] == "queued"
    retry_blocked_final = wait_for_render_job(client, retry_blocked["id"])
    assert retry_blocked_final["status"] == "blocked"
    blocked_artifacts_response = client.get(f"/api/video-factory/render-jobs/{blocked_render['id']}/artifacts")
    assert blocked_artifacts_response.status_code == 200
    assert blocked_artifacts_response.json() == []
    blocked_usage_response = client.get(f"/api/video-factory/render-jobs/{blocked_render['id']}/usage")
    assert blocked_usage_response.status_code == 200
    assert blocked_usage_response.json() is None

    base_track_clips = [
        clip
        for track in director_plan["timeline"]["tracks"]["video_tracks"]
        if track["layer"] == "base_track"
        for clip in track["clips"]
    ]
    manual_clips = [clip for clip in base_track_clips if clip["source_type"] in {"veo_generation", "seedance_generation"}]
    manual_asset_ids: list[str] = []
    for clip in manual_clips:
        clip_path = tmp_path / f"{clip['clip_id']}.mp4"
        make_test_video(clip_path, duration_sec=max(1, int(round(clip["duration_sec"]))), size="720x1280")
        with clip_path.open("rb") as handle:
            response = client.post(
                f"/api/video-factory/director-plans/{director_plan['id']}/manual-assets",
                data={"clip_id": clip["clip_id"]},
                files={"file": (f"{clip['clip_id']}.mp4", handle, "video/mp4")},
            )
        assert response.status_code == 200
        review_response = client.post(
            f"/api/video-factory/manual-assets/{response.json()['id']}/review",
            json={"review_status": "approved", "review_notes": "Matches the copied Veo prompt."},
        )
        assert review_response.status_code == 200
        assert review_response.json()["review_status"] == "approved"
        assert review_response.json()["semantic_review_status"] == "pending_review"
        manual_asset_ids.append(response.json()["id"])

    real_requirements = [
        asset
        for asset in director_plan["asset_resolution"]
        if asset["required_asset_type"] not in {"manual_veo_clip", "manual_seedance_clip"}
        and ("moras" in asset["required_asset_type"] or asset["moras_asset_category"] != "none")
    ]
    moras_asset_ids: list[str] = []
    for asset in real_requirements:
        if asset["asset_ref"] == "asset_2":
            continue
        asset_clip = tmp_path / f"{asset['asset_ref']}.mp4"
        make_test_video(asset_clip, duration_sec=8, size="1280x720")
        with asset_clip.open("rb") as handle:
            upload = client.post(
                "/api/video-factory/moras-assets",
                data={
                    "asset_type": asset["required_asset_type"],
                    "moras_asset_category": asset["moras_asset_category"],
                    "title": f"{asset['asset_ref']} test asset",
                },
                files={"file": (f"{asset['asset_ref']}.mp4", handle, "video/mp4")},
            )
        assert upload.status_code == 200
        review_asset = client.post(
            f"/api/video-factory/moras-assets/{upload.json()['id']}/review",
            json={"review_status": "approved", "review_notes": "Approved Moras workflow cutaway."},
        )
        assert review_asset.status_code == 200
        assert review_asset.json()["review_status"] == "approved"
        assert review_asset.json()["semantic_review_status"] == "pending_review"
        moras_asset_ids.append(upload.json()["id"])
        bind = client.post(
            f"/api/video-factory/director-plans/{director_plan['id']}/asset-bindings",
            json={"asset_ref": asset["asset_ref"], "library_asset_id": upload.json()["id"]},
        )
        assert bind.status_code == 200

    approved_moras_asset = client.post(
        f"/api/video-factory/moras-assets/{moras_asset['id']}/review",
        json={"review_status": "approved", "review_notes": "Approved existing asset_2 binding."},
    )
    assert approved_moras_asset.status_code == 200
    assert approved_moras_asset.json()["review_status"] == "approved"
    assert approved_moras_asset.json()["semantic_review_status"] == "pending_review"
    moras_asset_ids.append(moras_asset["id"])

    semantic_blocked_response = client.post(f"/api/video-factory/director-plans/{director_plan['id']}/render-jobs")
    assert semantic_blocked_response.status_code == 200
    semantic_blocked_created = semantic_blocked_response.json()
    assert semantic_blocked_created["status"] == "queued"
    semantic_blocked_render = wait_for_render_job(client, semantic_blocked_created["id"])
    assert semantic_blocked_render["status"] == "blocked"
    assert semantic_blocked_render["readiness_summary"]["manual_ready_count"] == 0
    assert semantic_blocked_render["readiness_summary"]["real_moras_ready_count"] == 0
    assert any(blocker["type"] == "manual_veo_semantic_review" for blocker in semantic_blocked_render["readiness_summary"]["blockers"])
    assert any(blocker["type"] == "real_moras_asset_semantic_review" for blocker in semantic_blocked_render["readiness_summary"]["blockers"])

    for asset_id in manual_asset_ids:
        semantic_review = client.post(
            f"/api/video-factory/manual-assets/{asset_id}/semantic-review",
            json={
                "status": "passed",
                "notes": "Human confirmed this generated clip matches the copied prompt and timeline slot.",
                "reviewer": "qa-operator",
                "method": "human_prompt_match_v1",
            },
        )
        assert semantic_review.status_code == 200
        assert semantic_review.json()["semantic_review_status"] == "passed"
        assert semantic_review.json()["semantic_review_reviewer"] == "qa-operator"
        assert semantic_review.json()["semantic_reviewed_at"]

    for asset_id in moras_asset_ids:
        semantic_review = client.post(
            f"/api/video-factory/moras-assets/{asset_id}/semantic-review",
            json={
                "status": "passed",
                "notes": "Human confirmed this Moras asset matches the Director Plan asset requirement.",
                "reviewer": "qa-operator",
                "method": "human_prompt_match_v1",
            },
        )
        assert semantic_review.status_code == 200
        assert semantic_review.json()["semantic_review_status"] == "passed"
        assert semantic_review.json()["semantic_review_reviewer"] == "qa-operator"
        assert semantic_review.json()["semantic_reviewed_at"]

    render_response = client.post(f"/api/video-factory/director-plans/{director_plan['id']}/render-jobs")
    assert render_response.status_code == 200
    created_render_job = render_response.json()
    assert created_render_job["status"] == "queued"
    render_job = wait_for_render_job(client, created_render_job["id"])
    assert render_job["status"] == "succeeded"
    assert render_job["output_asset_url"].startswith("/uploads/factory-renders/")
    assert render_job["output_audio_url"].startswith("/uploads/factory-renders/")
    assert render_job["output_subtitle_url"].startswith("/uploads/factory-renders/")
    assert render_job["file_size_bytes"] > 0
    assert render_job["duration_sec"] == pytest.approx(director_plan["metadata"]["total_duration_sec"], abs=1.0)
    assert render_job["width"] == 1080
    assert render_job["height"] == 1920
    assert render_job["qa_summary"]["status"] == "passed"
    assert render_job["qa_summary"]["checks"]["audio_stream_present"] is True
    assert render_job["qa_summary"]["checks"]["subtitle_cues_present"] is True
    assert render_job["qa_summary"]["checks"]["vertical_1080x1920"] is True
    assert render_job["qa_summary"]["subtitle_cue_count"] > 0
    assert render_job["qa_summary"]["audio"]["status"] in {"succeeded", "fallback_silent"}
    assert render_job["qa_review_status"] == "pending_review"
    artifacts_response = client.get(f"/api/video-factory/render-jobs/{render_job['id']}/artifacts")
    assert artifacts_response.status_code == 200
    artifacts = artifacts_response.json()
    artifact_by_type = {artifact["artifact_type"]: artifact for artifact in artifacts}
    assert set(artifact_by_type) == {"video", "audio", "subtitle", "caption_composition"}
    assert artifact_by_type["video"]["asset_url"] == render_job["output_asset_url"]
    assert artifact_by_type["video"]["mime_type"] == "video/mp4"
    assert artifact_by_type["video"]["file_size_bytes"] == render_job["file_size_bytes"]
    assert artifact_by_type["video"]["width"] == 1080
    assert artifact_by_type["video"]["height"] == 1920
    assert artifact_by_type["audio"]["asset_url"] == render_job["output_audio_url"]
    assert artifact_by_type["audio"]["mime_type"] == "audio/mp4"
    assert artifact_by_type["audio"]["file_size_bytes"] > 0
    assert artifact_by_type["subtitle"]["asset_url"] == render_job["output_subtitle_url"]
    assert artifact_by_type["subtitle"]["mime_type"] == "text/vtt"
    assert artifact_by_type["subtitle"]["file_size_bytes"] > 0
    assert artifact_by_type["caption_composition"]["asset_url"].endswith("/index.html")
    assert artifact_by_type["caption_composition"]["mime_type"] == "text/html"
    assert artifact_by_type["caption_composition"]["file_size_bytes"] > 0
    assert all(artifact["storage_status"] == "active" for artifact in artifacts)
    assert all(artifact["retention_expires_at"] for artifact in artifacts)
    assert all(artifact["deleted_at"] is None for artifact in artifacts)

    settings = get_settings()
    caption_artifact_path = settings.upload_dir / artifact_by_type["caption_composition"]["asset_url"].removeprefix("/uploads/")
    audio_artifact_path = settings.upload_dir / artifact_by_type["audio"]["asset_url"].removeprefix("/uploads/")
    subtitle_artifact_path = settings.upload_dir / artifact_by_type["subtitle"]["asset_url"].removeprefix("/uploads/")
    assert caption_artifact_path.exists()
    assert audio_artifact_path.exists()
    assert subtitle_artifact_path.exists()

    delete_artifact_response = client.delete(f"/api/video-factory/render-artifacts/{artifact_by_type['caption_composition']['id']}")
    assert delete_artifact_response.status_code == 200
    deleted_caption_artifact = delete_artifact_response.json()
    assert deleted_caption_artifact["storage_status"] == "deleted"
    assert deleted_caption_artifact["deleted_at"]
    assert not caption_artifact_path.exists()

    artifacts_after_delete = client.get(f"/api/video-factory/render-jobs/{render_job['id']}/artifacts").json()
    artifact_after_delete_by_type = {artifact["artifact_type"]: artifact for artifact in artifacts_after_delete}
    assert artifact_after_delete_by_type["caption_composition"]["storage_status"] == "deleted"
    assert artifact_after_delete_by_type["video"]["storage_status"] == "active"
    assert artifact_after_delete_by_type["audio"]["storage_status"] == "active"
    assert artifact_after_delete_by_type["subtitle"]["storage_status"] == "active"

    BreakdownRepository().update_director_render_artifact_lifecycle(
        artifact_by_type["subtitle"]["id"],
        storage_status="retention_expired",
    )
    cleanup_response = client.post(f"/api/video-factory/render-jobs/{render_job['id']}/artifacts/cleanup-expired")
    assert cleanup_response.status_code == 200
    cleaned_artifacts = cleanup_response.json()
    cleaned_by_type = {artifact["artifact_type"]: artifact for artifact in cleaned_artifacts}
    assert cleaned_by_type["subtitle"]["storage_status"] == "deleted"
    assert cleaned_by_type["subtitle"]["deleted_at"]
    assert cleaned_by_type["audio"]["storage_status"] == "active"
    assert not subtitle_artifact_path.exists()
    assert audio_artifact_path.exists()

    usage_response = client.get(f"/api/video-factory/render-jobs/{render_job['id']}/usage")
    assert usage_response.status_code == 200
    usage = usage_response.json()
    assert usage["render_job_id"] == render_job["id"]
    assert usage["input_clip_count"] == render_job["readiness_summary"]["render_input_count"]
    assert usage["output_duration_sec"] == pytest.approx(render_job["duration_sec"], abs=0.25)
    assert usage["output_bytes"] == render_job["file_size_bytes"]
    assert usage["subtitle_cue_count"] == render_job["qa_summary"]["subtitle_cue_count"]
    assert usage["tts_character_count"] > 0
    assert usage["render_engine"] == "local_ffmpeg_draft_v1"
    assert usage["audio_engine"] in {"macos_say", "ffmpeg_anullsrc"}
    assert usage["caption_engine"] == "webvtt_track_v1"
    assert render_job["qa_summary"]["caption"]["engine"] == "webvtt_track_v1"
    assert render_job["qa_summary"]["caption"]["hyperframes_status"] == "cli_disabled"
    assert render_job["qa_summary"]["caption"]["composition_url"].endswith("/index.html")
    assert "overlay_url" in render_job["qa_summary"]["caption"]

    blocked_publish_response = client.post(
        f"/api/video-factory/director-plans/{director_plan['id']}/publish-records",
        json={"render_job_id": render_job["id"], "channel": "manual_upload"},
    )
    assert blocked_publish_response.status_code == 409
    assert blocked_publish_response.json()["detail"]["error"]["code"] == "DIRECTOR_RENDER_JOB_QA_NOT_APPROVED"

    qa_review_response = client.post(
        f"/api/video-factory/render-jobs/{render_job['id']}/qa-review",
        json={"qa_review_status": "approved", "qa_review_notes": "Human QA approved the draft."},
    )
    assert qa_review_response.status_code == 200
    reviewed_render_job = qa_review_response.json()
    assert reviewed_render_job["qa_review_status"] == "approved"
    assert reviewed_render_job["qa_review_notes"] == "Human QA approved the draft."
    assert reviewed_render_job["qa_reviewed_at"]

    publish_response = client.post(
        f"/api/video-factory/director-plans/{director_plan['id']}/publish-records",
        json={
            "render_job_id": render_job["id"],
            "channel": "manual_upload",
            "publish_status": "ready_for_upload",
            "caption": "Manual upload caption",
            "notes": "Ready for growth ops handoff.",
        },
    )
    assert publish_response.status_code == 200
    publish_record = publish_response.json()
    assert publish_record["director_plan_id"] == director_plan["id"]
    assert publish_record["script_id"] == scripts[0]["id"]
    assert publish_record["render_job_id"] == render_job["id"]
    assert publish_record["publish_status"] == "ready_for_upload"
    assert publish_record["notes"] == "Ready for growth ops handoff."
    publish_records_response = client.get(f"/api/video-factory/director-plans/{director_plan['id']}/publish-records")
    assert publish_records_response.status_code == 200
    assert publish_records_response.json()[0]["id"] == publish_record["id"]

    delete_video_response = client.delete(f"/api/video-factory/render-artifacts/{artifact_by_type['video']['id']}")
    assert delete_video_response.status_code == 200
    assert delete_video_response.json()["storage_status"] == "deleted"
    delete_video_again_response = client.delete(f"/api/video-factory/render-artifacts/{artifact_by_type['video']['id']}")
    assert delete_video_again_response.status_code == 200
    assert delete_video_again_response.json()["storage_status"] == "deleted"
    publish_deleted_video_response = client.post(
        f"/api/video-factory/director-plans/{director_plan['id']}/publish-records",
        json={
            "render_job_id": render_job["id"],
            "channel": "manual_upload",
            "publish_status": "ready_for_upload",
        },
    )
    assert publish_deleted_video_response.status_code == 409
    assert publish_deleted_video_response.json()["detail"]["error"]["code"] == "DIRECTOR_RENDER_OUTPUT_ARTIFACT_DELETED"

    render_jobs_response = client.get(f"/api/video-factory/director-plans/{director_plan['id']}/render-jobs")
    assert render_jobs_response.status_code == 200
    assert render_jobs_response.json()[0]["id"] == render_job["id"]
    assert render_jobs_response.json()[0]["qa_review_status"] == "approved"

    director_list_response = client.get(f"/api/video-factory/director-plans?script_id={scripts[0]['id']}")
    assert director_list_response.status_code == 200
    assert len(director_list_response.json()) == 1

    list_response = client.get("/api/scripts")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 2

    script_id = scripts[0]["id"]
    edit_response = client.post(f"/api/scripts/{script_id}/edit", json={"instruction": "开头更像真实创作者。"})
    assert edit_response.status_code == 200
    edited = edit_response.json()
    assert edited["status"] == "ready"
    assert edited["script"]["version"] == "v2"
    assert edited["creator_persona"]["display_name"]
    assert len(edited["video_prompt"]["segments"]) >= 3
    assert edited["video_prompt"]["segments"][0]["time_range"] == "0s-8s"
    assert edited["video_prompt"]["segments"][-1]["timeline_end_sec"] == edited["video_prompt"]["target_duration_sec"]
    assert edited["script"]["localized"]["zh"]["script_title"].endswith("（已修改）")
    assert edited["production_asset_plan"][1]["asset_type"] == "real_moras_screen_recording"
    assert len(edited["revision_history"]) == 1
    assert edited["revision_history"][0]["instruction"] == "开头更像真实创作者。"

    delete_response = client.delete(f"/api/scripts/{script_id}")
    assert delete_response.status_code == 204
    assert client.get(f"/api/scripts/{script_id}").status_code == 404


def test_list_scripts_hides_historical_mock_duplicates_when_real_provider_active(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("VIDEO_BREAKDOWN_PROVIDER", "gemini")
    monkeypatch.setenv("VIDEO_BREAKDOWN_SKIP_DOTENV", "1")
    monkeypatch.setenv("VIDEO_BREAKDOWN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("VIDEO_BREAKDOWN_UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    app = create_app()
    repo = BreakdownRepository()
    duplicate_mock_item = build_mock_script_item(0, "all", [])
    repo.create_script_records(
        items=[duplicate_mock_item],
        provider="mock",
        model_name="mock-script-agent-v1",
        script_type="all",
    )
    repo.create_script_records(
        items=[build_mock_script_item(0, "all", [])],
        provider="mock",
        model_name="mock-script-agent-v1",
        script_type="all",
    )
    repo.create_script_records(
        items=[build_mock_script_item(1, "all", [])],
        provider="gemini",
        model_name="gemini-3.1-pro-preview",
        script_type="all",
    )

    with TestClient(app) as test_client:
        response = test_client.get("/api/scripts")

    assert response.status_code == 200
    scripts = response.json()
    assert len(scripts) == 1
    assert scripts[0]["provider"] == "gemini"
    assert scripts[0]["script"]["script_title"] != duplicate_mock_item.script.script_title
    get_settings.cache_clear()


def test_repository_backfills_creator_persona_for_legacy_scripts(tmp_path: Path):
    db_path = tmp_path / "legacy.sqlite3"
    repo = BreakdownRepository(db_path)
    now = "2026-01-01T00:00:00+00:00"

    with repo._connect() as connection:
        connection.execute(
            """
            INSERT INTO scripts (
                id, status, provider, model_name, script_type,
                source_breakdown_ids, topic_plan, script, storyboard,
                creator_persona, video_prompt, production_asset_plan, risk_check,
                source_component_summary, revision_history, error_message, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy_script",
                "ready",
                "mock",
                "legacy-script-agent",
                "Beginner Trap",
                json.dumps([], ensure_ascii=False),
                json.dumps({"title": "Legacy workflow test", "persona": "Burned-out solo product reviewer"}, ensure_ascii=False),
                json.dumps({"script_title": "Legacy workflow test", "persona": "Burned-out solo product reviewer"}, ensure_ascii=False),
                json.dumps([], ensure_ascii=False),
                json.dumps({}, ensure_ascii=False),
                json.dumps({}, ensure_ascii=False),
                json.dumps([], ensure_ascii=False),
                json.dumps({}, ensure_ascii=False),
                json.dumps([], ensure_ascii=False),
                json.dumps([], ensure_ascii=False),
                None,
                now,
                now,
            ),
        )

    refreshed_repo = BreakdownRepository(db_path)
    script = refreshed_repo.get_script("legacy_script")

    assert script.creator_persona["display_name"]
    assert script.creator_persona["appearance"]
    assert script.creator_persona["wardrobe"]
    assert script.creator_persona["reference_image_prompt"]
    assert "Asian" not in script.creator_persona["reference_image_prompt"]
    assert "Mia Chen" not in script.creator_persona["reference_image_prompt"]
    assert "script" not in script.creator_persona["reference_image_prompt"].lower()
    assert "reference_image_negative_prompt" not in script.creator_persona
    assert script.creator_persona["localized"]["zh"]["reference_image_prompt"]
    assert script.video_prompt["target_model"] == "Veo 3.1"
    assert script.video_prompt["veo_model_id"] == "veo-3.1-generate-001"
    assert "negative_prompt" not in script.video_prompt
    assert len(script.video_prompt["segments"]) > 0
    assert script.video_prompt["segments"][0]["veo_prompt"].startswith("Generate one 8-second vertical 9:16 Veo 3.1 source clip.")
    assert script.creator_persona["display_name"] in script.video_prompt["character_lock"]
    assert script.creator_persona["display_name"] in script.video_prompt["segments"][0]["veo_prompt"]
    assert script.video_prompt["segments"][0]["localized"]["zh"]["veo_prompt"] == script.video_prompt["segments"][0]["veo_prompt"]

    with refreshed_repo._connect() as connection:
        raw_persona = connection.execute(
            "SELECT creator_persona FROM scripts WHERE id = ?",
            ("legacy_script",),
        ).fetchone()["creator_persona"]
        raw_video_prompt = connection.execute(
            "SELECT video_prompt FROM scripts WHERE id = ?",
            ("legacy_script",),
        ).fetchone()["video_prompt"]
    assert json.loads(raw_persona)["reference_image_prompt"]
    assert "reference_image_negative_prompt" not in json.loads(raw_persona)
    assert json.loads(raw_video_prompt)["target_model"] == "Veo 3.1"

    with refreshed_repo._connect() as connection:
        connection.execute(
            "UPDATE scripts SET creator_persona = ?, video_prompt = ? WHERE id = ?",
            (json.dumps({}), json.dumps({"segments": [{"visual_prompt": "short"}], "negative_prompt": "legacy"}), "legacy_script"),
        )

    lazy_record = refreshed_repo.get_script("legacy_script")
    assert lazy_record.creator_persona["reference_image_prompt"]
    assert lazy_record.video_prompt["target_model"] == "Veo 3.1"
    assert "negative_prompt" not in lazy_record.video_prompt
    assert lazy_record.creator_persona["display_name"] in lazy_record.video_prompt["segments"][0]["veo_prompt"]


def test_script_generation_requires_saved_persona(client: TestClient):
    breakdown_response = client.post("/api/breakdowns", json={"video_url": "/uploads/source.mp4"})
    assert breakdown_response.status_code == 200

    response = client.post(
        "/api/scripts/generate",
        json={"script_count": 1, "script_type": "all", "source_breakdown_ids": [breakdown_response.json()["id"]]},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["error"]["code"] == "SCRIPT_PERSONA_REQUIRED"


def test_script_agent_rejects_shallow_or_misaligned_storyboard():
    item = build_mock_script_item(0, "Beginner Trap", ["source_1"]).model_dump(mode="json")
    item["storyboard"][0]["timestamp"] = "0s-10s"
    item["storyboard"][0]["duration"] = "10s"
    item["storyboard"][0]["character_action"] = "Creator sits at a messy desk adjusting a ring light with tired body language."
    item["storyboard"][0]["background"] = "Messy home office with cables, product boxes, and dim practical lighting."
    item["storyboard"][0]["voiceover"] = "This was my workflow before... and this is my workflow now."

    with pytest.raises(ValidationError, match="split rows longer"):
        ScriptAgentItem.model_validate(item)

    item = build_mock_script_item(0, "Beginner Trap", ["source_1"]).model_dump(mode="json")
    item["storyboard"][2]["character_action"] = "Screen recording"

    with pytest.raises(ValidationError, match="too generic"):
        ScriptAgentItem.model_validate(item)

    item = build_mock_script_item(0, "Beginner Trap", ["source_1"]).model_dump(mode="json")
    item["storyboard"][0]["timestamp"] = "0s-4s"
    item["storyboard"][0]["duration"] = "4s"
    item["storyboard"][0]["voiceover"] = "This was my workflow before... and this is my workflow now."
    item["storyboard"][0]["character_action"] = "Creator sits at a messy desk adjusting a ring light with tired body language."
    item["storyboard"][0]["background"] = "Messy home office with cables, product boxes, and dim practical lighting."

    with pytest.raises(ValidationError, match="before/now"):
        ScriptAgentItem.model_validate(item)


def test_script_agent_rejects_full_subtitle_transcripts_in_overlay_highlights():
    item = build_mock_script_item(0, "Beginner Trap", ["source_1"]).model_dump(mode="json")
    item["storyboard"][0]["overlay"] = (
        "I opened the camera, stared at the product, and closed it again because I still had no angle."
    )
    with pytest.raises(ValidationError, match="caption highlight"):
        ScriptAgentItem.model_validate(item)

    item = build_mock_script_item(0, "Beginner Trap", ["source_1"]).model_dump(mode="json")
    item["storyboard"][0]["localized"]["zh"]["overlay"] = "如果你有一份全职工作，那每天发三条 TikTok Shop 视频的建议纯属垃圾"
    with pytest.raises(ValidationError, match="caption highlight"):
        ScriptAgentItem.model_validate(item)

    item = build_mock_script_item(0, "Beginner Trap", ["source_1"]).model_dump(mode="json")
    item["script"]["overlay"][0] = (
        "This is the complete sentence that should live in voiceover, not in the screen caption highlight."
    )
    with pytest.raises(ValidationError, match="caption highlight"):
        ScriptAgentItem.model_validate(item)


def test_storyboard_voiceover_normalization_preserves_complete_text():
    english = "You think waiting two weeks for shipping is doing it right. It's actually just your excuse to delay posting."
    chinese = "如果你每天都在商品页面和脚本草稿之间来回切换，却还是不知道应该先检查哪个信息，现在先用这个流程把判断顺序固定下来。"

    assert normalize_storyboard_voiceover(english) == english
    assert normalize_storyboard_voiceover(chinese) == chinese


def test_script_agent_parser_repairs_real_storyboard_drift():
    item = build_mock_script_item(0, "Beginner Trap", ["source_1"]).model_dump(mode="json")
    item["storyboard"][1]["voiceover"] = (
        "如果你每天都在商品页面和脚本草稿之间来回切换，"
        "却还是不知道应该先检查哪个信息，现在先用这个流程把判断顺序固定下来。"
    )
    item["storyboard"][0]["voiceover"] = "This was my workflow before, and this is my workflow now."
    item["storyboard"][0]["character_action"] = "Aaliyah Brooks points at scattered product notes with a tired pause."
    item["storyboard"][0]["background"] = "Compact creator desk with cables, note cards, and product samples under soft daylight."
    item["storyboard"][0]["camera"] = "Vertical medium-close smartphone framing with a stable handheld push."
    item["storyboard"][2]["facial_expression"] = "专注"
    item["storyboard"][4]["background"] = "桌面"
    item["storyboard"][2]["subtitle_logic"] = "Captions explain the simple input-to-output mechanism clearly."
    item["storyboard"][2]["visual_element_logic"] = "The highlight box explains the product test mechanism without adding a new voiceover claim."
    item["storyboard"][2]["purpose"] = "Provide visual proof of the tool's core mechanism."
    item["video_prompt"]["generation_prompt"] = "Show a screen recording of the user interface with screenshot overlay, 字幕, 录屏, and 界面 details."

    batch = parse_script_agent_batch(json.dumps({"scripts": [item]}), ["source_1"])
    wrapped_batch = parse_script_agent_batch(json.dumps([{"scripts": [item]}]), ["source_1"])
    repaired = batch.scripts[0].storyboard

    assert wrapped_batch.scripts[0].script.script_title == batch.scripts[0].script.script_title
    repaired_parts = [shot for shot in repaired if shot.shot_id.startswith("shot_2_part_")]
    assert "".join(shot.voiceover for shot in repaired_parts) == item["storyboard"][1]["voiceover"]
    assert all(f"part {index} focus" in shot.visual_elements for index, shot in enumerate(repaired_parts, start=1))
    shot_1 = next(shot for shot in repaired if shot.shot_id == "shot_1")
    shot_3 = next(shot for shot in repaired if shot.shot_id == "shot_3")
    shot_5 = next(shot for shot in repaired if shot.shot_id == "shot_5")
    assert "Moras workflow" in shot_1.character_action
    assert "Aaliyah Brooks" in shot_3.facial_expression
    assert "creator desk" in shot_5.background
    assert "reason" in shot_3.subtitle_logic
    assert "screen recording" not in batch.scripts[0].video_prompt.generation_prompt.lower()
    assert "user interface" not in batch.scripts[0].video_prompt.generation_prompt.lower()
    assert "录屏" not in batch.scripts[0].video_prompt.generation_prompt


def test_script_agent_parser_localizes_repaired_storyboard_details():
    item = build_mock_script_item(0, "Beginner Trap", ["source_1"]).model_dump(mode="json")
    item["storyboard"][2]["facial_expression"] = ""
    item["storyboard"][2]["localized"]["zh"]["facial_expression"] = ""

    batch = parse_script_agent_batch(json.dumps({"scripts": [item]}, ensure_ascii=False), ["source_1"])
    repaired_shot = batch.scripts[0].storyboard[2]

    assert "stays focused" in repaired_shot.facial_expression
    assert has_cjk(repaired_shot.localized["zh"]["facial_expression"])


def test_script_generation_job_persists_status_and_outputs(client: TestClient):
    breakdown_response = client.post("/api/breakdowns", json={"video_url": "/uploads/source.mp4"})
    assert breakdown_response.status_code == 200
    breakdown_id = breakdown_response.json()["id"]
    persona_response = client.post("/api/creator-personas/generate", json={"persona_count": 1})
    assert persona_response.status_code == 200
    selected_persona_record = persona_response.json()[0]
    selected_persona = selected_persona_record["creator_persona"]

    create_job_response = client.post(
        "/api/script-generation-jobs",
        json={
            "script_count": 3,
            "script_type": "all",
            "source_breakdown_ids": [breakdown_id],
            "persona_id": selected_persona_record["id"],
        },
    )

    assert create_job_response.status_code == 200
    created_job = create_job_response.json()
    assert created_job["script_count"] == 3
    assert created_job["script_type"] == "all"
    assert created_job["source_breakdown_ids"] == [breakdown_id]
    assert created_job["persona_id"] == selected_persona_record["id"]
    assert created_job["persona_hint"]["display_name"] == selected_persona["display_name"]
    assert created_job["persona_hint"]["role_task"] == selected_persona["role_task"]
    assert created_job["persona_hint"]["script_agent_handoff"]["proof_asset_rules"]
    assert created_job["persona_hint"]["digital_human_prompt_assets"]["voice_style_prompt"]
    assert created_job["completed_count"] == 0
    assert created_job["script_ids"] == []

    completed_job = None
    for _ in range(20):
        get_job_response = client.get(f"/api/script-generation-jobs/{created_job['id']}")
        assert get_job_response.status_code == 200
        current_job = get_job_response.json()
        if current_job["status"] == "succeeded":
            completed_job = current_job
            break
        time.sleep(0.05)
    assert completed_job is not None
    assert completed_job["status"] == "succeeded"
    assert completed_job["completed_count"] == 3
    assert len(completed_job["script_ids"]) == 3
    assert completed_job["error_message"] is None

    list_jobs_response = client.get("/api/script-generation-jobs?include_succeeded=true")
    assert list_jobs_response.status_code == 200
    assert list_jobs_response.json()[0]["id"] == created_job["id"]

    active_jobs_response = client.get("/api/script-generation-jobs")
    assert active_jobs_response.status_code == 200
    assert active_jobs_response.json() == []

    scripts_response = client.get("/api/scripts")
    assert scripts_response.status_code == 200
    assert {script["id"] for script in scripts_response.json()} == set(completed_job["script_ids"])
    assert len({script["script"]["script_title"] for script in scripts_response.json()}) == 3
    assert len({script["script"]["localized"]["zh"]["script_title"] for script in scripts_response.json()}) == 3
    assert len({script["script"]["hook"] for script in scripts_response.json()}) == 3
    assert len({" ".join(script["script"]["voiceover"][:2]) for script in scripts_response.json()}) == 3
    assert len({"|".join(script["source_component_summary"][:4]) for script in scripts_response.json()}) == 3
    assert all(script["creator_persona"]["display_name"] == selected_persona["display_name"] for script in scripts_response.json())
    assert all(script["creator_persona"]["role_task"] == selected_persona["role_task"] for script in scripts_response.json())
    assert all(script["script"]["proof_insert"] for script in scripts_response.json())
    assert all("link is right there" not in script["script"]["cta"].lower() for script in scripts_response.json())
    assert all("doing it the hard way" not in script["script"]["cta"].lower() for script in scripts_response.json())
    assert all(selected_persona["veo_identity_string"] in script["video_prompt"]["segments"][0]["veo_prompt"] for script in scripts_response.json())
    persona_get_response = client.get(f"/api/creator-personas/{selected_persona_record['id']}")
    assert persona_get_response.status_code == 200
    assert set(persona_get_response.json()["source_script_ids"]) == set(completed_job["script_ids"])


def test_persona_generation_creates_distinct_records(client: TestClient):
    response = client.post("/api/creator-personas/generate", json={"persona_count": 3})

    assert response.status_code == 200
    records = response.json()
    personas = [record["creator_persona"] for record in records]
    assert len(records) == 3
    assert len({persona["display_name"] for persona in personas}) == 3
    assert len({persona["veo_identity_string"] for persona in personas}) == 3
    assert len({persona["reference_image_prompt"] for persona in personas}) == 3
    for persona in personas:
        assert persona["persona_type"] in {
            "Beginner KOC",
            "Mom Creator",
            "Tutorial Learner",
            "Skeptical Creator",
            "Lazy-but-Ambitious Creator",
        }
        assert persona["role_task"]
        assert persona["audience_callout"]
        assert persona["target_problem_profile"]["explicit_pains"]
        assert persona["target_problem_profile"]["inner_conflict"]
        assert persona["target_problem_profile"]["desired_state"]
        assert persona["trust_basis"]["usable_proof_assets"]
        assert persona["persona_scene_pair"]["primary_scene"] in persona["recurring_scenes"]
        assert len(persona["content_pillars"]) >= 3
        assert persona["hook_preferences"] == []
        assert persona["localized"]["zh"]["hook_preferences"] == []
        assert "Script Agent owns hook selection" in " ".join(persona["script_agent_handoff"]["hook_rules"])
        assert persona["memory_symbols"]["column_name"]
        assert "guaranteed income" in persona["endorsement_boundary"]["banned_claims"]
        assert "ai guarantees sales" in persona["script_agent_handoff"]["forbidden_claims"]
        assert persona["persona_quality_score"]["score"] >= 75
        assert all(persona["persona_quality_score"]["checks"].values())
        assert persona["localized"]["zh"]["role_task"]
        assert persona["localized"]["zh"]["target_problem_profile"]["explicit_pains"]
        prompt_assets = persona["digital_human_prompt_assets"]
        assert prompt_assets["sample_requirement"] == "no_real_sample_required"
        assert prompt_assets["visual_reference_prompt"] == persona["reference_image_prompt"]
        assert prompt_assets["voice_style_prompt"]
        assert len(prompt_assets["script_delivery_rules"]) >= 3
        assert persona["localized"]["zh"]["digital_human_prompt_assets"]["synthetic_disclosure_note"]
        prompt_asset_text = json.dumps(prompt_assets, ensure_ascii=False).lower()
        for forbidden_sample_claim in ["voice sample", "audio sample", "voice clone", "cloned voice", "extracted audio", "声音克隆", "声音样本"]:
            assert forbidden_sample_claim not in prompt_asset_text
    hobby_values = [
        re.sub(r"[^a-z0-9]+", " ", hobby.lower()).strip()
        for persona in personas
        for hobby in persona["hobbies_interests"]
    ]
    assert len(hobby_values) == len(set(hobby_values))
    background_text = " ".join(
        f"{persona['role']} {persona['creator_background']}".lower()
        for persona in personas
    )
    assert any(keyword in background_text for keyword in ["part-time", "hobby", "micro creator", "small", "beginner"])
    assert "mechanical keyboard" not in background_text

    list_response = client.get("/api/creator-personas")
    assert list_response.status_code == 200
    listed_personas = [record["creator_persona"] for record in list_response.json()]
    assert len(listed_personas) == 3
    assert len({persona["display_name"] for persona in listed_personas}) == 3


def test_persona_normalization_accepts_digital_human_prompt_asset_aliases(client: TestClient):
    response = client.post("/api/creator-personas/generate", json={"persona_count": 1})
    assert response.status_code == 200
    persona = response.json()[0]["creator_persona"]
    original_assets = persona.pop("digital_human_prompt_assets")
    persona["digitalHumanPromptAssets"] = {
        "visualReferencePrompt": "This model-supplied visual prompt should be replaced by the canonical reference image prompt.",
        "avatarMotionPrompt": "Custom compatible avatar motion prompt with natural hand movement and phone-facing delivery.",
        "voiceStylePrompt": "Custom compatible synthetic TTS style prompt with calm creator pacing.",
        "scriptDeliveryRules": [
            "Use short spoken lines.",
            "Leave tiny pauses after checklist points.",
            "Keep the voice creator-native and practical.",
        ],
        "sampleRequirement": "uploaded_media_optional",
        "syntheticDisclosureNote": "Prompt-defined synthetic media direction only.",
        "keepConsistent": ["face", "wardrobe", "workspace"],
        "avoid": ["celebrity mimicry", "face drift", "brand-logo background clutter"],
        "lightingNotes": "Extra model field should not break validation.",
        "backgroundRules": ["Extra nested model field should be ignored."],
    }

    normalized = normalize_creator_persona_payload(
        persona,
        {"title": "Moras persona", "target_audience": "TikTok Shop creators", "persona": "Reusable persona"},
        {"script_title": "Moras persona", "persona": persona["display_name"]},
        seed="digital-human-compat",
    )
    validated = CreatorPersonaProfile.model_validate(normalized).model_dump(mode="json")

    assert "digitalHumanPromptAssets" not in validated
    prompt_assets = validated["digital_human_prompt_assets"]
    assert prompt_assets["visual_reference_prompt"] == validated["reference_image_prompt"]
    assert prompt_assets["avatar_motion_prompt"].startswith("Custom compatible avatar motion prompt")
    assert prompt_assets["voice_style_prompt"].startswith("Custom compatible synthetic TTS style prompt")
    assert prompt_assets["script_delivery_rules"][0] == "Use short spoken lines."
    assert prompt_assets["sample_requirement"] == "no_real_sample_required"
    assert prompt_assets["synthetic_disclosure_note"] == "Prompt-defined synthetic media direction only."
    assert "lightingNotes" not in prompt_assets
    assert "backgroundRules" not in prompt_assets
    assert original_assets["sample_requirement"] == "no_real_sample_required"


def test_persona_generation_job_tracks_queue_and_progress(client: TestClient):
    create_response = client.post("/api/persona-generation-jobs", json={"persona_count": 3})

    assert create_response.status_code == 200
    created_job = create_response.json()
    assert created_job["status"] in {"queued", "generating"}
    assert created_job["persona_count"] == 3
    assert created_job["completed_count"] == 0
    assert created_job["persona_ids"] == []

    list_response = client.get("/api/persona-generation-jobs?include_succeeded=true")
    assert list_response.status_code == 200
    assert any(job["id"] == created_job["id"] for job in list_response.json())

    completed_job = wait_for_persona_generation_job(client, created_job["id"])
    assert completed_job["status"] == "succeeded"
    assert completed_job["completed_count"] == 3
    assert len(completed_job["persona_ids"]) == 3

    personas_response = client.get("/api/creator-personas")
    assert personas_response.status_code == 200
    persona_ids = {record["id"] for record in personas_response.json()}
    assert set(completed_job["persona_ids"]).issubset(persona_ids)

    active_jobs_response = client.get("/api/persona-generation-jobs")
    assert active_jobs_response.status_code == 200
    assert all(job["id"] != created_job["id"] for job in active_jobs_response.json())


def test_stale_persona_generation_job_recovers_and_ignores_late_finish():
    repo = BreakdownRepository()
    job = repo.create_persona_generation_job(PersonaGenerationRequest(persona_count=3))
    repo.mark_persona_generation_job(job.id, PersonaGenerationJobStatus.GENERATING)
    with repo._connect() as connection:
        connection.execute(
            "UPDATE persona_generation_jobs SET updated_at = ? WHERE id = ?",
            ("2000-01-01T00:00:00+00:00", job.id),
        )

    recovered = repo.recover_stale_persona_generation_jobs(max_age_seconds=1)

    assert [item.id for item in recovered] == [job.id]
    recovered_job = repo.get_persona_generation_job(job.id)
    assert recovered_job.status == PersonaGenerationJobStatus.FAILED
    assert "stale worker timeout" in recovered_job.error_message

    late_finish = repo.finish_persona_generation_job(
        job.id,
        status=PersonaGenerationJobStatus.SUCCEEDED,
        persona_ids=["late-persona-id"],
    )

    assert late_finish.status == PersonaGenerationJobStatus.FAILED
    assert late_finish.persona_ids == []
    assert "stale worker timeout" in late_finish.error_message
    repo.delete_persona_generation_job(job.id)


def test_failed_persona_generation_job_can_retry(client: TestClient):
    repo = BreakdownRepository()
    job = repo.create_persona_generation_job(PersonaGenerationRequest(persona_count=2))
    repo.finish_persona_generation_job(
        job.id,
        status=PersonaGenerationJobStatus.FAILED,
        error_message="Persona Agent failed after retries",
    )

    retry_response = client.post(f"/api/persona-generation-jobs/{job.id}/retry")

    assert retry_response.status_code == 200
    retry_job = retry_response.json()
    assert retry_job["id"] != job.id
    assert retry_job["status"] in {"queued", "generating"}
    assert retry_job["persona_count"] == 2

    old_response = client.get(f"/api/persona-generation-jobs/{job.id}")
    assert old_response.status_code == 404

    completed_retry = wait_for_persona_generation_job(client, retry_job["id"])
    assert completed_retry["status"] == "succeeded"
    assert completed_retry["completed_count"] == 2


def test_compact_persona_for_prompt_includes_persona_v2_handoff(client: TestClient):
    response = client.post("/api/creator-personas/generate", json={"persona_count": 1})
    assert response.status_code == 200
    persona = response.json()[0]["creator_persona"]
    persona["cta_style"] = "Try it if you are tired of doing it the hard way. Link is right there."
    persona["proof_policy"] = "Only show actual screen recordings of the Moras workflow generating a video draft in minutes compared to manual editing."
    persona["script_agent_handoff"]["proof_asset_rules"] = [
        "Introduce workflow recordings as the cheat code I found.",
        "Highlight the speed of the Moras tool.",
    ]

    compact = compact_persona_for_prompt(persona)

    assert compact["persona_type"] == persona["persona_type"]
    assert compact["role_task"]
    assert compact["audience_callout"]
    assert compact["target_problem_profile"]["explicit_pains"]
    assert compact["trust_basis"]["usable_proof_assets"]
    assert compact["persona_scene_pair"]["primary_scene"]
    assert compact["memory_symbols"]["column_name"]
    assert compact["content_pillars"]
    assert "cta_style" not in compact
    assert "hook_preferences" not in compact
    assert compact["endorsement_boundary"]["banned_claims"]
    assert compact["script_agent_handoff"]["hook_rules"]
    assert compact["script_agent_handoff"]["proof_asset_rules"]
    assert compact["digital_human_prompt_assets"]["sample_requirement"] == "no_real_sample_required"
    assert compact["digital_human_prompt_assets"]["voice_style_prompt"]
    assert compact["digital_human_prompt_assets"]["script_delivery_rules"]
    compact_text = json.dumps(compact, ensure_ascii=False).lower()
    assert "link is right there" not in compact_text
    assert "doing it the hard way" not in compact_text
    assert "cheat code" not in compact_text
    assert "in minutes" not in compact_text
    assert "product selection/generate workflow" in compact_text
    assert "visible commerce path" in compact_text
    assert "voice sample" not in compact_text
    assert "audio sample" not in compact_text

    prompt = build_script_prompt(
        ScriptGenerationRequest(
            script_count=1,
            script_type="all",
            persona_id=response.json()[0]["id"],
            persona_hint=persona,
        ),
        [],
        [],
    )
    assert persona["role_task"][:80] in prompt
    assert persona["audience_callout"][:80] in prompt


def test_director_generation_job_persists_status_and_plan_output(client: TestClient):
    persona_response = client.post("/api/creator-personas/generate", json={"persona_count": 1})
    assert persona_response.status_code == 200
    selected_persona_record = persona_response.json()[0]
    script_response = client.post(
        "/api/scripts/generate",
        json={
            "script_count": 1,
            "script_type": "all",
            "source_breakdown_ids": [],
            "persona_id": selected_persona_record["id"],
        },
    )
    assert script_response.status_code == 200
    script = script_response.json()[0]

    create_job_response = client.post(
        "/api/video-factory/director-generation-jobs",
        json={"script_id": script["id"]},
    )

    assert create_job_response.status_code == 200
    created_job = create_job_response.json()
    assert created_job["script_id"] == script["id"]
    assert created_job["director_plan_id"] is None
    assert created_job["error_message"] is None

    completed_job = None
    for _ in range(20):
        get_job_response = client.get(f"/api/video-factory/director-generation-jobs/{created_job['id']}")
        assert get_job_response.status_code == 200
        current_job = get_job_response.json()
        if current_job["status"] == "succeeded":
            completed_job = current_job
            break
        time.sleep(0.05)
    assert completed_job is not None
    assert completed_job["director_plan_id"]
    assert completed_job["error_message"] is None

    get_plan_response = client.get(f"/api/video-factory/director-plans/{completed_job['director_plan_id']}")
    assert get_plan_response.status_code == 200
    director_plan = get_plan_response.json()
    assert director_plan["id"] == completed_job["director_plan_id"]
    assert director_plan["script_id"] == script["id"]
    assert director_plan["status"] == "ready"

    list_jobs_response = client.get(
        f"/api/video-factory/director-generation-jobs?script_id={script['id']}&include_succeeded=true"
    )
    assert list_jobs_response.status_code == 200
    assert list_jobs_response.json()[0]["id"] == created_job["id"]

    active_jobs_response = client.get(f"/api/video-factory/director-generation-jobs?script_id={script['id']}")
    assert active_jobs_response.status_code == 200
    assert active_jobs_response.json() == []


def test_director_generation_job_cancel_and_retry(client: TestClient):
    script = create_mock_script(client)
    repo = BreakdownRepository()
    job = repo.create_director_generation_job(DirectorPlanRequest(script_id=script["id"]))

    cancel_response = client.post(f"/api/video-factory/director-generation-jobs/{job.id}/cancel")

    assert cancel_response.status_code == 200
    canceled_job = cancel_response.json()
    assert canceled_job["status"] == "canceled"
    assert canceled_job["script_id"] == script["id"]
    assert "取消" in canceled_job["error_message"]

    active_jobs_response = client.get(f"/api/video-factory/director-generation-jobs?script_id={script['id']}")
    assert active_jobs_response.status_code == 200
    assert active_jobs_response.json() == []

    retry_response = client.post(f"/api/video-factory/director-generation-jobs/{job.id}/retry")

    assert retry_response.status_code == 200
    retry_job = retry_response.json()
    assert retry_job["id"] != job.id
    assert retry_job["script_id"] == script["id"]
    assert retry_job["status"] in {"queued", "generating", "succeeded"}

    completed_retry_job = None
    for _ in range(20):
        get_job_response = client.get(f"/api/video-factory/director-generation-jobs/{retry_job['id']}")
        assert get_job_response.status_code == 200
        current_job = get_job_response.json()
        if current_job["status"] == "succeeded":
            completed_retry_job = current_job
            break
        time.sleep(0.05)
    assert completed_retry_job is not None
    assert completed_retry_job["director_plan_id"]


def test_stale_director_generation_jobs_recover_to_failed(client: TestClient):
    script = create_mock_script(client)
    repo = BreakdownRepository()
    job = repo.create_director_generation_job(DirectorPlanRequest(script_id=script["id"]))
    repo.mark_director_generation_job(job.id, DirectorGenerationJobStatus.GENERATING)
    with repo._connect() as connection:
        connection.execute(
            "UPDATE director_generation_jobs SET updated_at = ? WHERE id = ?",
            ("2026-01-01T00:00:00+00:00", job.id),
        )

    recovered_jobs = repo.recover_stale_director_generation_jobs(max_age_seconds=1)

    assert [record.id for record in recovered_jobs] == [job.id]
    recovered_job = repo.get_director_generation_job(job.id)
    assert recovered_job.status == DirectorGenerationJobStatus.FAILED
    assert "stale worker timeout" in (recovered_job.error_message or "")


def test_stale_director_render_jobs_recover_to_failed(client: TestClient):
    script = create_mock_script(client)
    plan_response = client.post("/api/video-factory/director-plans", json={"script_id": script["id"]})
    assert plan_response.status_code == 200
    plan = plan_response.json()
    repo = BreakdownRepository()
    queued_job = repo.create_director_render_job(
        director_plan_id=plan["id"],
        status=DirectorRenderJobStatus.QUEUED,
        readiness_summary={},
    )
    rendering_job = repo.create_director_render_job(
        director_plan_id=plan["id"],
        status=DirectorRenderJobStatus.RENDERING,
        readiness_summary={"status": "ready"},
    )
    with repo._connect() as connection:
        connection.execute(
            "UPDATE director_render_jobs SET updated_at = ? WHERE id = ?",
            ("2026-01-01T00:00:00+00:00", rendering_job.id),
        )

    recovered_jobs = repo.recover_stale_director_render_jobs(max_age_seconds=1)

    assert {record.id for record in recovered_jobs} == {queued_job.id, rendering_job.id}
    recovered_queued = repo.get_director_render_job(queued_job.id)
    recovered_rendering = repo.get_director_render_job(rendering_job.id)
    assert recovered_queued.status == DirectorRenderJobStatus.FAILED
    assert recovered_rendering.status == DirectorRenderJobStatus.FAILED
    assert "backend restart" in (recovered_queued.error_message or "")
    assert "stale worker timeout" in (recovered_rendering.error_message or "")


def test_creator_persona_library_generate_edit_and_delete(client: TestClient):
    generate_response = client.post("/api/creator-personas/generate", json={"persona_count": 2})

    assert generate_response.status_code == 200
    generated = generate_response.json()
    assert len(generated) == 2
    assert generated[0]["creator_persona"]["display_name"]
    assert generated[0]["creator_persona"]["veo_identity_string"]
    assert generated[0]["creator_persona"]["reference_image_prompt"]
    assert "script" not in generated[0]["creator_persona"]["reference_image_prompt"].lower()
    assert "reference_image_negative_prompt" not in generated[0]["creator_persona"]

    list_response = client.get("/api/creator-personas")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 2
    get_response = client.get(f"/api/creator-personas/{generated[0]['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["creator_persona"]["display_name"] == generated[0]["creator_persona"]["display_name"]

    edit_response = client.post(
        f"/api/creator-personas/{generated[0]['id']}/edit",
        json={"instruction": "Make the persona more concise and operational."},
    )
    assert edit_response.status_code == 200
    assert any(
        "Make the persona more concise" in rule
        for rule in edit_response.json()["creator_persona"]["consistency_rules"]
    )

    delete_response = client.delete(f"/api/creator-personas/{generated[0]['id']}")
    assert delete_response.status_code == 204
    assert client.get("/api/creator-personas").json()[0]["id"] == generated[1]["id"]


def test_delete_failed_script_generation_job_removes_persisted_task(client: TestClient):
    repo = BreakdownRepository()
    job = repo.create_script_generation_job(
        ScriptGenerationRequest(script_count=3, script_type="all", source_breakdown_ids=[]),
    )
    repo.finish_script_generation_job(
        job.id,
        status=ScriptGenerationJobStatus.FAILED,
        error_message="15 validation errors for ScriptAgentBatch",
    )

    delete_response = client.delete(f"/api/script-generation-jobs/{job.id}")

    assert delete_response.status_code == 204
    assert client.get(f"/api/script-generation-jobs/{job.id}").status_code == 404


def test_retry_failed_script_generation_job_creates_new_job(client: TestClient):
    persona_response = client.post("/api/creator-personas/generate", json={"persona_count": 1})
    assert persona_response.status_code == 200
    selected_persona_record = persona_response.json()[0]
    repo = BreakdownRepository()
    job = repo.create_script_generation_job(
        ScriptGenerationRequest(
            script_count=2,
            script_type="all",
            source_breakdown_ids=[],
            persona_id=selected_persona_record["id"],
            persona_hint=selected_persona_record["creator_persona"],
        ),
    )
    repo.finish_script_generation_job(
        job.id,
        status=ScriptGenerationJobStatus.FAILED,
        error_message="Gemini request disconnected after 3 attempts: Server disconnected without sending a response.",
    )

    retry_response = client.post(f"/api/script-generation-jobs/{job.id}/retry")

    assert retry_response.status_code == 200
    retry_job = retry_response.json()
    assert retry_job["id"] != job.id
    assert retry_job["script_count"] == 2
    assert retry_job["persona_id"] == selected_persona_record["id"]
    assert client.get(f"/api/script-generation-jobs/{job.id}").status_code == 404
    completed_retry_job = None
    for _ in range(20):
        current = client.get(f"/api/script-generation-jobs/{retry_job['id']}").json()
        if current["status"] == "succeeded":
            completed_retry_job = current
            break
        time.sleep(0.05)
    assert completed_retry_job is not None
    assert len(completed_retry_job["script_ids"]) == 2


def test_delete_active_script_generation_job_is_blocked(client: TestClient):
    repo = BreakdownRepository()
    job = repo.create_script_generation_job(
        ScriptGenerationRequest(script_count=3, script_type="all", source_breakdown_ids=[]),
    )

    delete_response = client.delete(f"/api/script-generation-jobs/{job.id}")

    assert delete_response.status_code == 409
    assert delete_response.json()["detail"]["error"]["code"] == "SCRIPT_GENERATION_JOB_ACTIVE"
    repo.finish_script_generation_job(job.id, status=ScriptGenerationJobStatus.FAILED, error_message="test cleanup")
    repo.delete_script_generation_job(job.id)


def test_stale_script_generation_job_recovers_and_ignores_late_finish():
    repo = BreakdownRepository()
    job = repo.create_script_generation_job(
        ScriptGenerationRequest(script_count=3, script_type="all", source_breakdown_ids=[]),
    )
    repo.mark_script_generation_job(job.id, ScriptGenerationJobStatus.GENERATING)
    with repo._connect() as connection:
        connection.execute(
            "UPDATE script_generation_jobs SET updated_at = ? WHERE id = ?",
            ("2000-01-01T00:00:00+00:00", job.id),
        )

    recovered = repo.recover_stale_script_generation_jobs(max_age_seconds=1)

    assert [item.id for item in recovered] == [job.id]
    recovered_job = repo.get_script_generation_job(job.id)
    assert recovered_job.status == ScriptGenerationJobStatus.FAILED
    assert "stale worker timeout" in recovered_job.error_message

    late_finish = repo.finish_script_generation_job(
        job.id,
        status=ScriptGenerationJobStatus.SUCCEEDED,
        script_ids=["late-script-id"],
    )

    assert late_finish.status == ScriptGenerationJobStatus.FAILED
    assert late_finish.completed_count == 0
    assert late_finish.script_ids == []
    assert "stale worker timeout" in late_finish.error_message
    repo.delete_script_generation_job(job.id)


def test_failed_script_generation_job_preserves_completed_script_progress():
    repo = BreakdownRepository()
    job = repo.create_script_generation_job(
        ScriptGenerationRequest(script_count=3, script_type="all", source_breakdown_ids=[]),
    )
    repo.mark_script_generation_job(job.id, ScriptGenerationJobStatus.GENERATING)
    progressed = repo.update_script_generation_job_progress(job.id, ["script-one"])

    assert progressed.status == ScriptGenerationJobStatus.GENERATING
    assert progressed.completed_count == 1
    assert progressed.script_ids == ["script-one"]

    failed = repo.finish_script_generation_job(
        job.id,
        status=ScriptGenerationJobStatus.FAILED,
        error_message="third script failed schema validation",
    )

    assert failed.status == ScriptGenerationJobStatus.FAILED
    assert failed.completed_count == 1
    assert failed.script_ids == ["script-one"]
    repo.delete_script_generation_job(job.id)


def test_script_agent_allows_banned_claims_only_in_non_publishable_source_metadata():
    item = build_mock_script_item(0, "all", [])
    payload = item.model_dump(mode="json")
    payload["topic_plan"]["trend_source"] = "Source teardown title: Dumbest way to make $10k/month with ai"
    payload["storyboard"][0]["purpose"] = "Internal editor note: avoid promising guaranteed sales."

    validated = ScriptAgentItem.model_validate(payload)
    assert validated.topic_plan.trend_source.startswith("Source teardown title")
    assert validated.storyboard[0].purpose.startswith("Internal editor note")

    payload["script"]["hook"] = "Make $10k easily with AI."
    with pytest.raises(ValueError, match="banned claims"):
        ScriptAgentItem.model_validate(payload)


def test_script_agent_allows_approved_creator_money_proof_but_rejects_guarantees():
    item = build_mock_script_item(0, "all", [])
    payload = item.model_dump(mode="json")
    proof_line = "Proof screenshots show $13,000 a month and $130,000 in one month."
    payload["script"]["voiceover"][1] = proof_line
    payload["script"]["overlay"] = ["Here's proof", "$13,000/month", "Cart added"]
    payload["storyboard"][1]["voiceover"] = proof_line
    payload["storyboard"][1]["overlay"] = "$13,000 proof"

    validated = ScriptAgentItem.model_validate(payload)
    assert "$13,000" in validated.script.voiceover[1]

    payload = item.model_dump(mode="json")
    payload["script"]["voiceover"][1] = "Moras guarantees $13,000 a month for you."
    with pytest.raises(ValueError, match="banned claims"):
        ScriptAgentItem.model_validate(payload)


def test_script_agent_rejects_quality_claims_and_corporate_voiceover():
    item = build_mock_script_item(0, "all", [])
    payload = item.model_dump(mode="json")

    payload["script"]["voiceover"][1] = "Look at this quality. It doesn't look fake at all."
    with pytest.raises(ValueError, match="off-brand Script Agent copy"):
        ScriptAgentItem.model_validate(payload)

    payload = item.model_dump(mode="json")
    payload["script"]["voiceover"][1] = "This framework helps you optimize your conversion funnel."
    with pytest.raises(ValueError, match="off-brand Script Agent copy"):
        ScriptAgentItem.model_validate(payload)

    payload = item.model_dump(mode="json")
    payload["script"]["voiceover"][3] = "I open Moras, pick a niche, choose a product card, and hit Generate."
    with pytest.raises(ValueError, match="off-brand Script Agent copy"):
        ScriptAgentItem.model_validate(payload)

    payload = item.model_dump(mode="json")
    payload["script"]["localized"]["zh"]["voiceover"][3] = "我打开 Moras，先选一个细分市场，再选商品卡并点击 Generate。"
    with pytest.raises(ValueError, match="off-brand Script Agent copy"):
        ScriptAgentItem.model_validate(payload)

    payload = item.model_dump(mode="json")
    payload["script"]["voiceover"][3] = (
        "It gives me a ready-to-post shoppable video with the cart attached."
    )
    with pytest.raises(ValueError, match="off-brand Script Agent copy"):
        ScriptAgentItem.model_validate(payload)

    payload = item.model_dump(mode="json")
    payload["storyboard"][0]["subtitle_logic"] = "Caption timing explains the simple input-to-output reason."
    payload["storyboard"][0]["visual_element_logic"] = "Highlight boxes clarify the workflow reason for the editor."
    payload["storyboard"][0]["purpose"] = "Show the core reason without making income claims."
    ScriptAgentItem.model_validate(payload)

    payload["storyboard"][0]["voiceover"] = "This framework helps you optimize your conversion funnel."
    with pytest.raises(ValueError, match="off-brand Script Agent copy"):
        ScriptAgentItem.model_validate(payload)


def test_script_agent_rejects_negative_metric_hook_and_testing_value():
    item = build_mock_script_item(0, "all", [])
    payload = item.model_dump(mode="json")

    payload["script"]["hook"] = "Six months of zero conversions. Now I test products every day."
    payload["script"]["voiceover"][0] = "Six months of zero conversions."
    payload["script"]["voiceover"][1] = "Now I test products every day."
    with pytest.raises(ValueError, match="negative failure metrics"):
        ScriptAgentItem.model_validate(payload)

    payload = item.model_dump(mode="json")
    payload["script"]["hook"] = "I finally stopped guessing which products fit my page."
    payload["script"]["voiceover"][0] = "I finally stopped guessing which products fit my page."
    payload["script"]["voiceover"][1] = "Instead, I use Moras to choose what to promote next."
    payload["storyboard"][0]["overlay"] = "Listen up"
    with pytest.raises(ValueError, match="generic attention cue"):
        ScriptAgentItem.model_validate(payload)


def test_script_agent_rejects_ad_voice_and_requires_ugc_texture():
    item = build_mock_script_item(0, "all", [])
    payload = item.model_dump(mode="json")

    payload["script"]["cta"] = "Try the workflow yourself. Link is right there."
    with pytest.raises(ValueError, match="off-brand Script Agent copy"):
        ScriptAgentItem.model_validate(payload)

    payload = item.model_dump(mode="json")
    payload["script"]["cta"] = "If you're a 5K+ TikTok Shop creator, click the button. Make your own money."
    payload["storyboard"][-1]["voiceover"] = payload["script"]["cta"]
    payload["storyboard"][-1]["overlay"] = "Make your own money"
    payload["storyboard"][-1]["timestamp"] = "33.5s-38s"
    payload["storyboard"][-1]["duration"] = "4.5s"
    payload["storyboard"][-1]["localized"]["zh"]["duration"] = "4.5秒"
    validated = ScriptAgentItem.model_validate(payload)
    assert "Make your own money" in validated.script.cta

    payload = item.model_dump(mode="json")
    payload["script"]["voiceover"][3] = "Moras gives you a full video draft in minutes."
    with pytest.raises(ValueError, match="off-brand Script Agent copy"):
        ScriptAgentItem.model_validate(payload)

    payload = item.model_dump(mode="json")
    payload["script"]["voiceover"][3] = "I choose a product in Moras and tap Create video."
    payload["script"]["localized"]["zh"]["voiceover"][3] = "我在 Moras 选商品，然后点 Create video。"
    validated = ScriptAgentItem.model_validate(payload)
    assert "Create video" in validated.script.voiceover[3]

    payload = item.model_dump(mode="json")
    payload["script"]["voiceover"][3] = (
        "I choose the product card in Moras, hit Generate, and get a ready-to-post video with cart."
    )
    with pytest.raises(ValueError, match="off-brand Script Agent copy"):
        ScriptAgentItem.model_validate(payload)

    payload = item.model_dump(mode="json")
    payload["script"]["localized"]["zh"]["voiceover"][3] = "我在 Moras 选商品，然后点 Create video。"
    ScriptAgentItem.model_validate(payload)

    payload = item.model_dump(mode="json")
    payload["script"]["voiceover"] = [
        "The blank-page loop costs real money.",
        "I stopped starting every product from zero.",
        "The old draft still sits on my desk.",
        "The old way burned a whole week.",
        "That delay cost me another posting window.",
        "So I stopped guessing and protected the posting window.",
        "Now I open Moras.",
        "I choose the product I want to promote.",
        "Then I hit Generate.",
        "Moras makes the video for that product.",
        "It adds the cart so the post can sell.",
        "I watch it like a real shopper would.",
        "I check it before I post.",
        "That gives me one more video to post today.",
    ]
    ScriptAgentItem.model_validate(payload)

    payload = item.model_dump(mode="json")
    payload["script"]["voiceover"][3] = "That gives me another test before I buy samples."
    with pytest.raises(ValueError, match="off-brand Script Agent copy"):
        ScriptAgentItem.model_validate(payload)

    payload = item.model_dump(mode="json")
    payload["script"]["voiceover"] = [
        "The blank-page loop costs real money.",
        "I stopped starting every product from zero.",
        "Now I open Moras.",
        "I choose a product.",
        "Then I hit Generate.",
    ]
    with pytest.raises(ValueError, match="at least 11 short spoken lines"):
        ScriptAgentItem.model_validate(payload)

    payload = item.model_dump(mode="json")
    payload["script"]["voiceover"] = [
        "Drafts cost too much.",
        "I hate waiting.",
        "Old drafts stall.",
        "Now I open Moras.",
        "I choose a product.",
        "Then I hit Generate.",
        "Moras makes the video.",
        "It adds the cart.",
        "I check it.",
        "Then I post.",
        "That helps.",
    ]
    with pytest.raises(ValueError, match="90 spoken English words"):
        ScriptAgentItem.model_validate(payload)

    payload = item.model_dump(mode="json")
    payload["script"]["voiceover"][2] = (
        "I stopped starting every product from zero. Now I open Moras. I choose a product and hit Generate."
    )
    with pytest.raises(ValueError, match="under 14 words"):
        ScriptAgentItem.model_validate(payload)

    payload = item.model_dump(mode="json")
    payload["script"]["voiceover"][3] = (
        "I paste product info into Moras and instantly get an editable rough cut."
    )
    with pytest.raises(ValueError, match="off-brand Script Agent copy"):
        ScriptAgentItem.model_validate(payload)

    payload = item.model_dump(mode="json")
    payload["script"]["localized"]["zh"]["voiceover"][3] = (
        "我随便把商品信息放进 Moras，就瞬间拿到可直接上手改的粗剪草稿。"
    )
    with pytest.raises(ValueError, match="off-brand Script Agent copy"):
        ScriptAgentItem.model_validate(payload)

    payload = item.model_dump(mode="json")
    payload["script"]["hook"] = "Moras is the first thing I open for every product."
    payload["script"]["voiceover"][0] = "Moras is the first thing I open for every product."
    with pytest.raises(ValueError, match="Moras as the hero"):
        ScriptAgentItem.model_validate(payload)

    payload = item.model_dump(mode="json")
    payload["script"]["voiceover"][3] = "Moras turns product data into a draft for review."
    with pytest.raises(ValueError, match="off-brand Script Agent copy"):
        ScriptAgentItem.model_validate(payload)


def test_script_agent_allows_strong_hook_without_forcing_first_person():
    item = build_mock_script_item(0, "all", [])
    payload = item.model_dump(mode="json")
    payload["script"]["hook"] = "The weird part isn't the camera. It's not knowing what the product should prove."
    payload["script"]["voiceover"] = [
        "The weird part isn't the camera. It's not knowing what the product should prove.",
        "That's usually where I lose the angle.",
        "I still want the first line to feel like me.",
        "But my notes always turn into another messy draft.",
        "That costs me a morning before I even post.",
        "So I open Moras before I miss another posting window.",
        "I choose the product I want to promote.",
        "Then I tap Create video.",
        "Moras makes the video for that product.",
        "It adds the cart so the post can sell.",
        "I watch it like a real shopper would.",
        "I check the angle before I post it.",
        "Then I know what deserves more effort.",
    ]

    validated = ScriptAgentItem.model_validate(payload)
    assert validated.script.hook.startswith("The weird part")


def test_script_agent_requires_labeled_hook_variants():
    item = build_mock_script_item(0, "all", [])
    payload = item.model_dump(mode="json")

    assert len(payload["topic_plan"]["hook_candidates"]) >= 6
    assert payload["script"]["hook"] == "Girl, if you're a 5K+ TikTok Shop creator, listen up."
    assert any(candidate.startswith("[Curiosity Gap]") for candidate in payload["topic_plan"]["hook_candidates"])
    assert not any(candidate.startswith("[Contrarian]") for candidate in payload["topic_plan"]["hook_candidates"])

    payload["topic_plan"]["hook_candidates"] = [
        "Stop choosing products just because the commission is high.",
        "Check this before choosing.",
    ]
    with pytest.raises(ValueError, match="at least 6 hook variants"):
        ScriptAgentItem.model_validate(payload)


def test_script_agent_prioritizes_attention_first_hooks():
    item = build_mock_script_item(0, "all", [])
    payload = item.model_dump(mode="json")

    payload["topic_plan"]["hook_candidates"] = [
        "[Contrarian] Stop choosing products just because the commission is high.",
        "[Contrarian] Stop filming before you know the angle.",
        "[Question] Are you picking products before you can explain them?",
        "[List Preview] Check these 3 things before you choose.",
        "[Direct Callout] If you're new to TikTok Shop, pause here.",
        "[Before/After] Before I guessed every script. Now I start with a draft.",
    ]
    with pytest.raises(ValueError, match="attention-first"):
        ScriptAgentItem.model_validate(payload)

    payload = item.model_dump(mode="json")
    payload["topic_plan"]["hook_candidates"] = [
        "[Curiosity Gap] The weird part isn't the camera. It's not knowing what the product should prove.",
        "[Absurd Visual] My draft folder looks like it needs a coffee and a manager.",
        "[POV] POV: you found a product at midnight and your brain opened 47 tabs.",
        "[Mini Drama] I had the product. I had the camera. I had absolutely nothing to say.",
        "[Contrarian] Stop choosing products just because the commission is high.",
        "[Contrarian] Stop filming before you know the angle.",
    ]
    with pytest.raises(ValueError, match="contrarian"):
        ScriptAgentItem.model_validate(payload)


def test_script_copywriting_skill_includes_joey_tiktok_shop_patterns():
    skill = load_script_agent_skill("script-copywriting")

    assert "Joey / TikTok Shop script patterns learned from the creative library" in skill
    assert "[creator identity] + [specific money / GMV / rank] + [timeframe] + [counterintuitive detail]" in skill
    assert "Let's set the scene" in skill
    assert "Move on." in skill
    assert "If you [qualified audience], [one action]. I'll / Moras will [specific value]." in skill


def test_script_agent_batch_rejects_duplicate_scripts():
    first = build_mock_script_item(0, "all", []).model_dump(mode="json")
    duplicate = json.loads(json.dumps(first))

    with pytest.raises(ValidationError, match="distinct script titles"):
        ScriptAgentBatch.model_validate({"scripts": [first, duplicate]})

    second = build_mock_script_item(1, "all", []).model_dump(mode="json")
    second["script"]["script_title"] = "Another Title"
    second["topic_plan"]["title"] = "Another Topic"
    second["script"]["localized"]["zh"]["script_title"] = "另一个标题"
    second["topic_plan"]["localized"]["zh"]["title"] = "另一个主题"
    second["script"]["hook"] = first["script"]["hook"]

    with pytest.raises(ValidationError, match="distinct selected hooks"):
        ScriptAgentBatch.model_validate({"scripts": [first, second]})

    second = build_mock_script_item(1, "all", []).model_dump(mode="json")
    second["script"]["voiceover"] = list(first["script"]["voiceover"])

    with pytest.raises(ValidationError, match="opening voiceover signatures"):
        ScriptAgentBatch.model_validate({"scripts": [first, second]})


def test_error_message_falls_back_to_exception_class_name():
    assert error_message(TimeoutError()) == "TimeoutError"


def test_script_agent_rejects_unsupported_type(client: TestClient):
    response = client.post("/api/scripts/generate", json={"script_count": 1, "script_type": "收藏类"})

    assert response.status_code == 422


def test_gemini_provider_requires_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VIDEO_BREAKDOWN_PROVIDER", "gemini")
    monkeypatch.setenv("VIDEO_BREAKDOWN_SKIP_DOTENV", "1")
    monkeypatch.setenv("VIDEO_BREAKDOWN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("VIDEO_BREAKDOWN_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.delenv("GOOGLE_VERTEX_AI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT_ID", raising=False)
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as test_client:
        response = test_client.post("/api/breakdowns", json={"video_url": "/uploads/source.mp4"})
    get_settings.cache_clear()

    assert response.status_code == 422
    assert "GOOGLE_VERTEX_AI_API_KEY" in response.text


def test_gemini_vertex_express_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("VIDEO_BREAKDOWN_SKIP_DOTENV", "1")
    monkeypatch.setenv("VIDEO_BREAKDOWN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("VIDEO_BREAKDOWN_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("VERTEX_AI_BASE_URL", "https://aiplatform.googleapis.com/v1")
    monkeypatch.setenv("GEMINI_VIDEO_MODEL", "gemini-3.1-pro-preview")
    monkeypatch.delenv("VERTEX_AI_ENDPOINT_MODE", raising=False)
    get_settings.cache_clear()
    settings = get_settings()
    get_settings.cache_clear()

    assert settings.gemini_endpoint_mode() == "vertex_express"
    assert settings.gemini_generate_url() == (
        "https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-3.1-pro-preview:generateContent"
    )


def test_gemini_vertex_standard_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("VIDEO_BREAKDOWN_SKIP_DOTENV", "1")
    monkeypatch.setenv("VIDEO_BREAKDOWN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("VIDEO_BREAKDOWN_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("VERTEX_AI_BASE_URL", "https://aiplatform.googleapis.com/v1")
    monkeypatch.setenv("VERTEX_AI_ENDPOINT_MODE", "standard")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT_ID", "demo-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    monkeypatch.setenv("GEMINI_VIDEO_MODEL", "gemini-3.1-pro-preview")
    get_settings.cache_clear()
    settings = get_settings()
    get_settings.cache_clear()

    assert settings.gemini_endpoint_mode() == "vertex_standard"
    assert settings.gemini_generate_url() == (
        "https://aiplatform.googleapis.com/v1/projects/demo-project/locations/us-central1/"
        "publishers/google/models/gemini-3.1-pro-preview:generateContent"
    )

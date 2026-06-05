from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from .config import Settings, get_settings
from .downloader import resolve_upload_path
from .errors import unprocessable


GEMINI_MAX_ATTEMPTS = 3
GEMINI_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class ModelResult:
    text: str
    model_name: str


class ModelProvider(Protocol):
    name: str
    model_name: str

    def build_request_preview(self, prompt: str, imported_url: str) -> dict:
        ...

    async def generate_content(self, prompt: str, original_url: str, imported_url: str) -> ModelResult:
        ...


class MockProvider:
    name = "mock"
    model_name = "mock-video-breakdown-v1"

    def build_request_preview(self, prompt: str, imported_url: str) -> dict:
        return {
            "model": self.model_name,
            "prompt_chars": len(prompt),
            "video_url": imported_url,
        }

    async def generate_content(self, prompt: str, original_url: str, imported_url: str) -> ModelResult:
        payload = build_mock_result(original_url, imported_url)
        return ModelResult(text=json.dumps(payload, ensure_ascii=False), model_name=self.model_name)


class GeminiProvider:
    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model_name = settings.gemini_video_model

    def build_request_preview(self, prompt: str, imported_url: str) -> dict:
        return {
            "model": self.model_name,
            "prompt_chars": len(prompt),
            "video_url": imported_url,
        }

    async def generate_content(self, prompt: str, original_url: str, imported_url: str) -> ModelResult:
        if not self.settings.google_vertex_ai_api_key:
            raise unprocessable("GEMINI_API_KEY_MISSING", "GOOGLE_VERTEX_AI_API_KEY is required when VIDEO_BREAKDOWN_PROVIDER=gemini")
        if self.settings.gemini_endpoint_mode() == "vertex_standard" and not self.settings.google_cloud_project_id:
            raise unprocessable("GEMINI_PROJECT_MISSING", "GOOGLE_CLOUD_PROJECT_ID is required when VIDEO_BREAKDOWN_PROVIDER=gemini")
        local_path = resolve_upload_path(imported_url)
        if not local_path.exists():
            raise unprocessable("VIDEO_FILE_NOT_FOUND", f"Video file not found: {local_path.name}")
        video_b64 = base64.standard_b64encode(local_path.read_bytes()).decode()
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {"inlineData": {"mimeType": _mime_type(local_path), "data": video_b64}},
                    ],
                }
            ],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
        }
        response = await post_gemini_json_with_retries(
            self.settings.gemini_generate_url(),
            payload,
            self.settings,
        )
        if response.status_code >= 400:
            raise unprocessable("GEMINI_REQUEST_FAILED", f"Gemini returned {response.status_code}: {response.text[:500]}")
        text = _extract_text(response.json())
        return ModelResult(text=text, model_name=self.model_name)


async def generate_gemini_text(prompt: str, model_name: str | None = None) -> ModelResult:
    settings = get_settings()
    resolved_model = model_name or settings.gemini_script_model
    if not settings.google_vertex_ai_api_key:
        raise unprocessable("GEMINI_API_KEY_MISSING", "GOOGLE_VERTEX_AI_API_KEY is required when VIDEO_BREAKDOWN_PROVIDER=gemini")
    if settings.gemini_endpoint_mode() == "vertex_standard" and not settings.google_cloud_project_id:
        raise unprocessable("GEMINI_PROJECT_MISSING", "GOOGLE_CLOUD_PROJECT_ID is required when VIDEO_BREAKDOWN_PROVIDER=gemini")
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {"temperature": 0.35, "responseMimeType": "application/json"},
    }
    response = await post_gemini_json_with_retries(settings.gemini_generate_url(resolved_model), payload, settings)
    if response.status_code >= 400:
        raise unprocessable("GEMINI_REQUEST_FAILED", f"Gemini returned {response.status_code}: {response.text[:500]}")
    return ModelResult(text=_extract_text(response.json()), model_name=resolved_model)


async def post_gemini_json_with_retries(url: str, payload: dict, settings: Settings) -> httpx.Response:
    headers = {"x-goog-api-key": settings.google_vertex_ai_api_key}
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds, headers=headers) as client:
        for attempt in range(1, GEMINI_MAX_ATTEMPTS + 1):
            try:
                response = await client.post(url, json=payload)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt < GEMINI_MAX_ATTEMPTS:
                    await asyncio.sleep(0.8 * attempt)
                    continue
                message = str(exc).strip() or exc.__class__.__name__
                raise unprocessable(
                    "GEMINI_TRANSPORT_FAILED",
                    f"Gemini request disconnected after {GEMINI_MAX_ATTEMPTS} attempts: {message}",
                ) from exc
            if response.status_code in GEMINI_RETRYABLE_STATUS_CODES and attempt < GEMINI_MAX_ATTEMPTS:
                await asyncio.sleep(0.8 * attempt)
                continue
            return response
    raise unprocessable("GEMINI_TRANSPORT_FAILED", "Gemini request failed before a response was returned")


def get_provider(provider_name: str | None = None) -> ModelProvider:
    settings = get_settings()
    name = (provider_name or settings.provider).strip().lower()
    if name == "mock":
        return MockProvider()
    if name == "gemini":
        return GeminiProvider(settings)
    raise unprocessable("PROVIDER_UNSUPPORTED", f"Unsupported provider: {name}")


def build_mock_result(original_url: str, imported_url: str) -> dict:
    return {
        "source_video": {
            "original_url": original_url,
            "imported_video_url": imported_url,
            "title": "Mock 步骤清单演示视频",
            "platform": "mock",
            "creator_handle": None,
            "duration_seconds": 36,
            "observed_metrics": {},
            "content_summary": "Mock provider 输出，用于本地测试：视频围绕一个可收藏清单展开，用步骤化信息推动保存。",
        },
        "classification": {
            "taxonomy_version": "moras_viral_factor_v1",
            "hook_type": "禁忌型",
            "emotion_factors": ["焦虑", "好奇"],
            "persona_factors": ["教程达人型"],
            "scene_factors": ["桌面工作流", "手机后台"],
            "conflict_factors": ["她不是不努力，而是不知道正确方法。"],
            "pain_factors": ["每天都要想内容，太累", "不会写脚本"],
            "itch_factors": ["想用更少时间发更多视频"],
            "value_factors": ["不用从零写脚本", "提高内容产出效率"],
            "proof_factors": ["time saved proof"],
            "cta_factors": ["Save"],
            "structure_factors": ["mistake list", "tutorial walkthrough"],
            "visual_rhythm_factors": ["0-3 秒能看懂主题", "有手机屏幕", "静音也能看懂"],
            "audience_segments": ["Tutorial Learner"],
            "general_templates": ["Mistake List"],
            "vertical_templates": ["Shoppable Video Workflow"],
            "factor_reasoning": "Mock 样例把禁忌式开头、编号步骤、屏幕演示和保存动作作为主要可迁移因子。",
            "confidence": 0.72,
            "evidence": ["首屏承诺清单", "主体分步骤交付", "结尾触发收藏"],
        },
        "decomposition": {
            "one_sentence_summary": "这条视频用省时间承诺吸引目标用户，通过编号步骤持续交付信息，最后把观看转化为收藏动作。",
            "hook": "【视觉】首屏出现大标题和工具清单式构图；【听觉】口播直接否定低效试错；【字幕】强调“先收藏这三步”；【心理机制】触发省时间和少踩坑的收益预期；【留人问题】观众会继续看以获得可直接照做的三步。",
            "narrative_structure": [
                "痛点具象化（0-6s）：用低效试错建立目标用户代入，并承诺更快路径。",
                "步骤交付（6-28s）：用编号结构逐步兑现信息，让观众形成保存动机。",
                "收藏触发（28-36s）：把复用成本降低为收藏后照做，推动明确动作。",
            ],
            "segments": [
                {
                    "segment_no": 1,
                    "start_second": 0,
                    "end_second": 6,
                    "role": "建立停留理由",
                    "content": "首屏用大字标题和口播指出试错成本高，同时承诺给出可保存步骤。",
                    "technique": "大字幕降低理解成本，快节奏口播制造紧迫感，用收益承诺打开好奇缺口。",
                },
                {
                    "segment_no": 2,
                    "start_second": 6,
                    "end_second": 28,
                    "role": "持续兑现信息密度",
                    "content": "主体按编号展示三个可执行步骤，每一步都有具体动作或画面承接。",
                    "technique": "编号字幕、局部放大和连续切换让信息看起来可复制，强化收藏价值。",
                },
                {
                    "segment_no": 3,
                    "start_second": 28,
                    "end_second": 36,
                    "role": "推动收藏动作",
                    "content": "结尾回收清单价值，提示收藏后照着做。",
                    "technique": "复述核心收益并降低行动门槛，把短视频观看转成保存动作。",
                },
            ],
            "key_takeaways": [
                "先承诺可保存结果再分步骤交付，能把观看动机从了解一下推向留着照做。",
                "编号结构让复杂信息看起来有秩序，迁移时要保留可扫读的层级。",
            ],
            "visual_language": "大标题、编号列表、局部放大和快速切换。",
            "audio_language": "口播承担解释和节奏推进，BGM 只做背景支撑。",
            "interaction_or_cta": "收藏后照着做。",
            "performance_logic": "把用户的省时间需求和可复用清单绑定，降低收藏动作成本。",
        },
        "structure_protocol": {
            "version": 1,
            "source": "k2lab_social_video_breakdown",
            "core_pattern": "[高频低效场景] + [可保存结果承诺] + [编号步骤证明] + [复用动作触发]",
            "timeline_slots": [
                {
                    "slot_id": "hook",
                    "name": "开头留人",
                    "start_second": 0,
                    "end_second": 6,
                    "role": "建立停留理由",
                    "observable_evidence": "首屏大标题、否定低效试错、承诺给出步骤。",
                    "required_assets": ["首屏标题", "痛点句", "承诺句"],
                    "transfer_rule": "新主题必须在前三秒给出明确可保存收益。",
                },
                {
                    "slot_id": "steps",
                    "name": "步骤交付",
                    "start_second": 6,
                    "end_second": 28,
                    "role": "兑现清单价值",
                    "observable_evidence": "主体用编号持续交付步骤。",
                    "required_assets": ["步骤素材", "编号字幕", "证明画面"],
                    "transfer_rule": "保留编号和证据密度，不照搬原内容。",
                },
                {
                    "slot_id": "save_cta",
                    "name": "收藏触发",
                    "start_second": 28,
                    "end_second": 36,
                    "role": "推动保存动作",
                    "observable_evidence": "结尾提示收藏后照着做。",
                    "required_assets": ["行动字幕", "收益复述"],
                    "transfer_rule": "CTA 必须承接前面交付的信息价值。",
                },
            ],
            "reuse_rules": ["保留前三秒收益承诺", "保留编号步骤", "保留可保存动作"],
            "risk_flags": ["Mock 输出仅用于测试，不代表真实视频理解。"],
        },
        "script_agent_bridge": {
            "reusable_pattern": "[目标人群低效场景] + [省时间承诺] + [编号步骤] + [结果证明] + [收藏触发]",
            "script_agent_instructions": [
                "前三秒必须给出目标人群能立刻识别的低效痛点。",
                "主体用编号结构交付，不要写成泛泛建议。",
                "结尾把清单价值转成收藏或保存动作。",
            ],
            "variables_to_collect": ["目标人群", "具体痛点", "三到五个可验证步骤", "可展示结果", "CTA 动作"],
            "do_not_copy": ["原视频人物", "原口播句子", "原镜头顺序", "平台水印"],
            "adaptation_notes": ["适合清单型、教程型、工具型内容；不适合没有明确步骤的新主题。"],
        },
        "reference_storyboard": [
            {
                "shot_id": "shot_1",
                "timestamp": "0-6s",
                "duration": "6s",
                "camera": "竖屏近景，首屏标题占据画面中心，手机和桌面工具作为背景信息。",
                "character_action": "创作者把手机推到画面前，手指点出低效试错问题，并停顿等待观众注意标题。",
                "facial_expression": "皱眉但克制，像是在提醒朋友不要继续浪费时间。",
                "background": "桌面工作流场景，能看到手机、笔记和工具清单，强化教程感。",
                "props": ["手机", "笔记", "工具清单"],
                "voiceover": "别再一个个试工具了，先保存这三步。",
                "overlay": "先保存这三步",
                "sound": "短促提示音后进入轻快背景节奏。",
                "transition": "标题卡快速切到编号步骤。",
                "purpose": "用省时间承诺建立停留理由，并把观众拉进清单结构。",
                "localized": {
                    "zh": {
                        "duration": "6 秒",
                        "camera": "竖屏近景，首屏标题占据画面中心，手机和桌面工具作为背景信息。",
                        "character_action": "创作者把手机推到画面前，手指点出低效试错问题，并停顿等待观众注意标题。",
                        "facial_expression": "皱眉但克制，像是在提醒朋友不要继续浪费时间。",
                        "background": "桌面工作流场景，能看到手机、笔记和工具清单，强化教程感。",
                        "props": ["手机", "笔记", "工具清单"],
                        "voiceover": "别再一个个试工具了，先保存这三步。",
                        "overlay": "先保存这三步",
                        "sound": "短促提示音后进入轻快背景节奏。",
                        "transition": "标题卡快速切到编号步骤。",
                        "purpose": "用省时间承诺建立停留理由，并把观众拉进清单结构。"
                    }
                }
            },
            {
                "shot_id": "shot_2",
                "timestamp": "6-28s",
                "duration": "22s",
                "camera": "竖屏屏幕录制与手部操作交替，编号信息保持在画面上方。",
                "character_action": "画面按一二三推进，每一步先出现动作，再出现对应证明画面或局部放大。",
                "facial_expression": "创作者偶尔点头确认，表情从提醒转为确定。",
                "background": "手机后台、工具页面和桌面物件交替出现，维持教程节奏。",
                "props": ["手机后台", "编号字幕", "局部放大框"],
                "voiceover": "第一步先看解释成本，第二步看能不能拍成画面，第三步再决定要不要投入。",
                "overlay": "1 看解释成本 / 2 看画面化 / 3 再投入",
                "sound": "每个编号切换时有轻点击音。",
                "transition": "按编号做硬切和局部放大。",
                "purpose": "持续兑现清单价值，让观众相信这条视频值得保存。",
                "localized": {
                    "zh": {
                        "duration": "22 秒",
                        "camera": "竖屏屏幕录制与手部操作交替，编号信息保持在画面上方。",
                        "character_action": "画面按一二三推进，每一步先出现动作，再出现对应证明画面或局部放大。",
                        "facial_expression": "创作者偶尔点头确认，表情从提醒转为确定。",
                        "background": "手机后台、工具页面和桌面物件交替出现，维持教程节奏。",
                        "props": ["手机后台", "编号字幕", "局部放大框"],
                        "voiceover": "第一步先看解释成本，第二步看能不能拍成画面，第三步再决定要不要投入。",
                        "overlay": "1 看解释成本 / 2 看画面化 / 3 再投入",
                        "sound": "每个编号切换时有轻点击音。",
                        "transition": "按编号做硬切和局部放大。",
                        "purpose": "持续兑现清单价值，让观众相信这条视频值得保存。"
                    }
                }
            },
            {
                "shot_id": "shot_3",
                "timestamp": "28-36s",
                "duration": "8s",
                "camera": "竖屏中近景回到创作者，结尾字幕和清单截图并排出现。",
                "character_action": "创作者把清单截图停在画面中，手势指向收藏按钮方向。",
                "facial_expression": "语气放松，表情像完成提醒后的确认。",
                "background": "桌面工作流和清单截图并置，形成可保存的最终画面。",
                "props": ["清单截图", "手机", "收藏提示"],
                "voiceover": "保存下来，选下一个产品前照着检查。",
                "overlay": "保存后照着检查",
                "sound": "背景音乐收束，最后一个点击音强调保存。",
                "transition": "停帧到最终清单画面。",
                "purpose": "把观看价值转成收藏动作，降低用户下次复用成本。",
                "localized": {
                    "zh": {
                        "duration": "8 秒",
                        "camera": "竖屏中近景回到创作者，结尾字幕和清单截图并排出现。",
                        "character_action": "创作者把清单截图停在画面中，手势指向收藏按钮方向。",
                        "facial_expression": "语气放松，表情像完成提醒后的确认。",
                        "background": "桌面工作流和清单截图并置，形成可保存的最终画面。",
                        "props": ["清单截图", "手机", "收藏提示"],
                        "voiceover": "保存下来，选下一个产品前照着检查。",
                        "overlay": "保存后照着检查",
                        "sound": "背景音乐收束，最后一个点击音强调保存。",
                        "transition": "停帧到最终清单画面。",
                        "purpose": "把观看价值转成收藏动作，降低用户下次复用成本。"
                    }
                }
            }
        ],
    }


def _extract_text(raw: dict) -> str:
    candidates = raw.get("candidates") or []
    if not candidates:
        raise unprocessable("GEMINI_EMPTY_RESPONSE", "Gemini returned no candidates")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "\n".join(part.get("text", "") for part in parts if part.get("text")).strip()
    if not text:
        raise unprocessable("GEMINI_EMPTY_TEXT", "Gemini response did not include text")
    return text


def _mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".mov":
        return "video/quicktime"
    return "video/mp4"

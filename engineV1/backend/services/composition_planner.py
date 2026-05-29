"""CompositionPlanner service (Agent 4).

Receives VideoStructure + Task3 analysis result, calls LLM to generate:
1. Script (新脚本)
2. Storyboard (分镜)
3. Timeline draft (时间线草案)
4. Packaging suggestions (包装建议)
5. HyperVideoManifest

Reuses the LLM calling infrastructure from video_decompose.py.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from ..video_decompose import (
    LlmConfig,
    call_commercial_structured_model,
    load_llm_config,
)


SYSTEM_PROMPT = """\
你是一个专业的短视频创作规划师。你的任务是根据样例视频的结构模板和用户提供的新内容/素材，\
生成一个完整的新短视频方案。

你需要输出一个 JSON 对象，包含以下字段：

1. "script": 新视频脚本，包含每个段落的文案、时长建议和画面描述
2. "storyboard": 分镜列表，每个分镜包含画面描述、时长、素材来源
3. "timelineDraft": 时间线草案，每个片段包含轨道、开始时间、时长、内容类型
4. "packagingSuggestions": 包装建议列表，包含字幕样式、标题条、转场等
5. "manifest": HyperVideoManifest 对象

输出格式要求：
{
  "script": {
    "title": "视频标题",
    "totalDuration": 数字(秒),
    "segments": [
      {
        "segmentId": "seg-1",
        "name": "段落名称",
        "role": "hook|body|climax|cta",
        "durationSec": 数字,
        "scriptText": "文案内容",
        "visualDescription": "画面描述",
        "materialSource": "matched|generated|text-overlay|reuse"
      }
    ]
  },
  "storyboard": [
    {
      "shotId": "shot-1",
      "segmentId": "seg-1",
      "durationSec": 数字,
      "shotType": "特写|全景|中景|近景|文字画面",
      "description": "画面内容描述",
      "materialId": "匹配的素材ID或null",
      "fallback": "缺口时的补全方式"
    }
  ],
  "timelineDraft": [
    {
      "clipId": "clip-1",
      "track": "video|image|text|packaging|audio",
      "startSec": 数字,
      "durationSec": 数字,
      "contentType": "material|text-overlay|title-bar|sticker|transition|bgm",
      "sourceId": "素材ID或生成内容ID",
      "properties": {}
    }
  ],
  "packagingSuggestions": [
    {
      "type": "subtitle|titleBar|sticker|transition|cover",
      "position": "应用位置描述",
      "style": "样式描述",
      "content": "内容(如有)",
      "timing": "出现时机"
    }
  ],
  "manifest": {
    "duration": 总时长(秒),
    "aspectRatio": "9:16",
    "sourceStructure": [样例结构槽位ID列表],
    "mapping": [
      {
        "sourceSlotId": "样例槽位ID",
        "targetSegmentId": "新视频段落ID",
        "materialId": "使用的素材ID或null",
        "strategy": "direct|adapt|generate|text-replace"
      }
    ],
    "gaps": [缺口对象列表],
    "tracks": [
      {
        "trackId": "track-video",
        "trackType": "video|image|text|packaging|audio",
        "clips": [时间线片段列表]
      }
    ]
  }
}

注意事项：
- 严格按照样例结构的段落顺序和节奏特征来规划新视频
- 对于有素材匹配的槽位，直接使用匹配素材
- 对于缺口槽位，根据缺口严重程度选择补全策略：文案补全、包装补全或结构重排
- 时间线中每个片段的 startSec + durationSec 不能超过总时长
- 包装建议要具体可执行，包含样式参数
"""


def _build_user_prompt(
    video_structure: dict[str, Any],
    task3_analysis: dict[str, Any],
    task3_input: dict[str, Any],
    version_style: str = "balanced",
) -> str:
    parts: list[str] = []

    parts.append("## 样例视频结构 (VideoStructure)\n")
    parts.append(json.dumps(video_structure, ensure_ascii=False, indent=2))

    parts.append("\n\n## 新内容输入\n")
    input_summary = {
        "topic": task3_input.get("topic", ""),
        "sellingPoints": task3_input.get("sellingPoints", []),
        "copyText": task3_input.get("copyText", ""),
        "targetAudience": task3_input.get("targetAudience", ""),
        "platform": task3_input.get("platform", ""),
        "stylePreference": task3_input.get("stylePreference", ""),
    }
    parts.append(json.dumps(input_summary, ensure_ascii=False, indent=2))

    parts.append("\n\n## 素材分析结果\n")
    analysis_summary = {
        "materialInventory": task3_analysis.get("materialInventory", []),
        "slotMatches": task3_analysis.get("slotMatches", []),
        "gaps": task3_analysis.get("gaps", []),
        "summary": task3_analysis.get("summary", ""),
    }
    parts.append(json.dumps(analysis_summary, ensure_ascii=False, indent=2))

    parts.append(f"\n\n## 版本风格要求\n风格：{version_style}\n")
    style_hints = {
        "high-click": "优先制造强 hook 和悬念感，开头 3 秒内必须抓住注意力，节奏偏快。",
        "high-conversion": "突出卖点和使用效果，强化 CTA，增加信任背书元素。",
        "high-rhythm": "快节奏剪辑，镜头切换频繁，配合音乐节拍，减少静态画面。",
        "high-quality": "注重画面质感和构图，适当放慢节奏，强调品牌调性。",
        "balanced": "均衡考虑点击率、转化率和观看体验，适中节奏。",
    }
    parts.append(style_hints.get(version_style, style_hints["balanced"]))

    parts.append("\n\n请根据以上信息生成完整的新短视频方案，输出 JSON。")
    return "\n".join(parts)


def _parse_llm_response(raw_response: dict[str, Any]) -> dict[str, Any]:
    """Extract the JSON content from LLM API response."""
    choices = raw_response.get("choices", [])
    if not choices:
        raise RuntimeError("LLM returned empty choices.")

    message = choices[0].get("message", {})
    content = message.get("content", "")

    if not content:
        raise RuntimeError("LLM returned empty content.")

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])
        raise RuntimeError(f"Failed to parse LLM JSON output: {exc}") from exc


def _validate_and_fill_manifest(
    manifest_raw: dict[str, Any],
    video_structure: dict[str, Any],
    task3_analysis: dict[str, Any],
    version_style: str,
) -> dict[str, Any]:
    """Ensure manifest has all required fields with safe defaults."""
    manifest = dict(manifest_raw)
    manifest.setdefault("duration", 15)
    manifest.setdefault("aspectRatio", "9:16")
    manifest.setdefault("versionStyle", version_style)

    if not manifest.get("sourceStructure"):
        manifest["sourceStructure"] = [
            slot.get("slotId", "")
            for slot in video_structure.get("scriptStructure", [])
        ]

    manifest.setdefault("mapping", [])
    manifest.setdefault("gaps", task3_analysis.get("gaps", []))
    manifest.setdefault("tracks", [])

    return manifest


def generate_composition(
    video_structure: dict[str, Any],
    task3_analysis: dict[str, Any],
    task3_input: dict[str, Any],
    version_style: str = "balanced",
    llm_config: LlmConfig | None = None,
) -> dict[str, Any]:
    """Main entry point: generate a full composition plan via LLM.

    Args:
        video_structure: Normalized VideoStructure from structure_normalizer.
        task3_analysis: Output of analyze_task3_input (materialInventory, slotMatches, gaps).
        task3_input: The raw Task3 input record (topic, sellingPoints, materials, etc.).
        version_style: One of balanced, high-click, high-conversion, high-rhythm, high-quality.
        llm_config: Optional LlmConfig override. If None, loads from env/.env.

    Returns:
        Dict with keys: script, storyboard, timelineDraft, packagingSuggestions, manifest, meta.
    """
    if llm_config is None:
        llm_config = load_llm_config()

    user_prompt = _build_user_prompt(
        video_structure, task3_analysis, task3_input, version_style
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    raw_response = call_commercial_structured_model(
        config=llm_config, messages=messages
    )
    result = _parse_llm_response(raw_response)

    script = result.get("script", {})
    storyboard = result.get("storyboard", [])
    timeline_draft = result.get("timelineDraft", [])
    packaging_suggestions = result.get("packagingSuggestions", [])
    manifest_raw = result.get("manifest", {})

    manifest = _validate_and_fill_manifest(
        manifest_raw, video_structure, task3_analysis, version_style
    )

    now = datetime.now(UTC).isoformat()
    composition_id = uuid4().hex

    return {
        "id": composition_id,
        "script": script,
        "storyboard": storyboard,
        "timelineDraft": timeline_draft,
        "packagingSuggestions": packaging_suggestions,
        "manifest": manifest,
        "meta": {
            "versionStyle": version_style,
            "model": llm_config.model,
            "provider": llm_config.provider,
            "createdAt": now,
            "sourceVideoStructureSummary": video_structure.get("summary", ""),
            "task3InputId": task3_input.get("id", ""),
            "task3AnalysisId": task3_analysis.get("id", ""),
        },
    }


def generate_composition_fallback(
    video_structure: dict[str, Any],
    task3_analysis: dict[str, Any],
    task3_input: dict[str, Any],
    version_style: str = "balanced",
) -> dict[str, Any]:
    """Deterministic fallback when LLM is unavailable.

    Generates a basic composition from VideoStructure slots and Task3 matches
    without calling any external API.
    """
    now = datetime.now(UTC).isoformat()
    composition_id = uuid4().hex

    script_structure = video_structure.get("scriptStructure", [])
    slot_matches = task3_analysis.get("slotMatches", [])
    gaps = task3_analysis.get("gaps", [])
    rhythm = video_structure.get("rhythmStructure", {})

    avg_duration = rhythm.get("avgShotDurationSec") or 3.0
    total_duration = len(script_structure) * avg_duration if script_structure else 15.0

    segments = []
    storyboard = []
    timeline_clips = []
    current_time = 0.0

    slot_match_map = {m["slotId"]: m for m in slot_matches}

    for i, slot in enumerate(script_structure):
        seg_id = f"seg-{i + 1}"
        slot_id = slot.get("slotId", f"slot-{i + 1}")
        name = slot.get("name", f"段落{i + 1}")
        duration = avg_duration

        role = "body"
        if i == 0:
            role = "hook"
        elif i == len(script_structure) - 1:
            role = "cta"

        match = slot_match_map.get(slot_id, {})
        matched_materials = match.get("matchedMaterialIds", [])
        material_source = "matched" if matched_materials else "text-overlay"

        segments.append({
            "segmentId": seg_id,
            "name": name,
            "role": role,
            "durationSec": duration,
            "scriptText": slot.get("scriptText") or task3_input.get("copyText", "")[:80],
            "visualDescription": slot.get("intent") or name,
            "materialSource": material_source,
        })

        storyboard.append({
            "shotId": f"shot-{i + 1}",
            "segmentId": seg_id,
            "durationSec": duration,
            "shotType": "中景",
            "description": slot.get("intent") or name,
            "materialId": matched_materials[0] if matched_materials else None,
            "fallback": "文案/字幕补全" if not matched_materials else None,
        })

        timeline_clips.append({
            "clipId": f"clip-{i + 1}",
            "track": "video" if matched_materials else "text",
            "startSec": round(current_time, 2),
            "durationSec": duration,
            "contentType": "material" if matched_materials else "text-overlay",
            "sourceId": matched_materials[0] if matched_materials else f"text-{seg_id}",
            "properties": {},
        })

        current_time += duration

    packaging_suggestions = []
    packaging = video_structure.get("packagingStructure", {})
    if packaging.get("subtitle"):
        packaging_suggestions.append({
            "type": "subtitle",
            "position": "底部居中",
            "style": "白色描边字幕",
            "content": "",
            "timing": "全程",
        })
    if packaging.get("titleBar"):
        packaging_suggestions.append({
            "type": "titleBar",
            "position": "顶部",
            "style": "品牌色标题条",
            "content": task3_input.get("topic", ""),
            "timing": "前3秒",
        })
    if packaging.get("transitions"):
        packaging_suggestions.append({
            "type": "transition",
            "position": "段落衔接处",
            "style": packaging["transitions"][0] if packaging["transitions"] else "淡入淡出",
            "content": "",
            "timing": "每个段落切换",
        })

    mapping = []
    for i, slot in enumerate(script_structure):
        slot_id = slot.get("slotId", f"slot-{i + 1}")
        match = slot_match_map.get(slot_id, {})
        matched_materials = match.get("matchedMaterialIds", [])
        mapping.append({
            "sourceSlotId": slot_id,
            "targetSegmentId": f"seg-{i + 1}",
            "materialId": matched_materials[0] if matched_materials else None,
            "strategy": "direct" if matched_materials else "text-replace",
        })

    manifest = {
        "duration": round(total_duration, 2),
        "aspectRatio": "9:16",
        "versionStyle": version_style,
        "sourceStructure": [s.get("slotId", "") for s in script_structure],
        "mapping": mapping,
        "gaps": gaps,
        "tracks": [
            {
                "trackId": "track-video",
                "trackType": "video",
                "clips": [c for c in timeline_clips if c["track"] == "video"],
            },
            {
                "trackId": "track-text",
                "trackType": "text",
                "clips": [c for c in timeline_clips if c["track"] == "text"],
            },
        ],
    }

    script = {
        "title": task3_input.get("topic", "新视频"),
        "totalDuration": round(total_duration, 2),
        "segments": segments,
    }

    return {
        "id": composition_id,
        "script": script,
        "storyboard": storyboard,
        "timelineDraft": timeline_clips,
        "packagingSuggestions": packaging_suggestions,
        "manifest": manifest,
        "meta": {
            "versionStyle": version_style,
            "model": "fallback-deterministic",
            "provider": "local",
            "createdAt": now,
            "sourceVideoStructureSummary": video_structure.get("summary", ""),
            "task3InputId": task3_input.get("id", ""),
            "task3AnalysisId": task3_analysis.get("id", ""),
        },
    }

"""Task3 analysis service — material understanding, slot matching, gap detection.

Upgraded from rule-based to AI-powered:
1. Vision model understanding for image/video materials
2. Dynamic slot extraction from VideoStructure
3. LLM semantic matching between materials and slots
4. Graceful fallback to rules when models unavailable
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from ..config import TASK3_MATERIAL_DIR
from ..schemas import Task3InputCreateRequest, Task3MaterialPayload
from ..storage import load_task3_inputs
from ..video_decompose import (
    call_commercial_structured_model,
    encode_image_data_url,
    extract_response_text,
    extract_structured_frames,
    load_commercial_model_config,
    load_llm_config,
    parse_json_or_wrap,
)
from .video_utils import probe_video

logger = logging.getLogger("hot_engine.task3")


# ─── Prompt Templates ─────────────────────────────────────────────────────────

IMAGE_UNDERSTANDING_SYSTEM_PROMPT = (
    "你是一个短视频素材分析专家。你的任务是分析用户上传的图片素材，判断其内容和适用场景。\n"
    "你必须输出 JSON object，不要输出 markdown。"
)

IMAGE_UNDERSTANDING_USER_PROMPT = (
    "请分析这张图片，输出以下 JSON：\n"
    "{\n"
    '  "sceneType": "product-closeup | packaging | person | lifestyle | comparison | text-card | other",\n'
    '  "mainObjects": ["图中主要物体"],\n'
    '  "textContent": "图中可见文字（OCR）",\n'
    '  "mood": "画面情绪/氛围",\n'
    '  "suitableRoles": ["hook", "product-closeup", "usage", "comparison", "cta", "background"],\n'
    '  "confidence": 0.0到1.0之间的数字,\n'
    '  "description": "一句话描述图片内容"\n'
    "}"
)

VIDEO_UNDERSTANDING_USER_PROMPT = (
    "以下是一段视频素材的关键帧（按时间顺序排列）。请分析这些帧，判断视频内容和适用场景。输出 JSON：\n"
    "{\n"
    '  "sceneType": "usage-demo | unboxing | comparison | testimonial | lifestyle | product-showcase | other",\n'
    '  "mainObjects": ["视频中主要物体/人物"],\n'
    '  "textContent": "帧中可见文字",\n'
    '  "actionDescription": "视频中的主要动作/过程",\n'
    '  "suitableRoles": ["hook", "product-closeup", "usage", "comparison", "cta", "background"],\n'
    '  "confidence": 0.0到1.0之间的数字,\n'
    '  "description": "一句话描述视频内容"\n'
    "}"
)

SEMANTIC_MATCH_SYSTEM_PROMPT = (
    "你是短视频素材匹配专家。你的任务是将用户的素材与视频结构槽位进行语义匹配。\n"
    "你必须输出 JSON object，不要输出 markdown。"
)

SEMANTIC_MATCH_USER_TEMPLATE = """\
## 素材清单
{inventory_json}

## 需要填充的槽位
{slots_json}

## 用户信息
- 主题：{topic}
- 卖点：{selling_points}
- 文案：{copy_text}

请为每个槽位匹配最合适的素材。输出格式：
{{
  "matches": [
    {{
      "slotId": "槽位ID",
      "slotName": "槽位名称",
      "requiredMaterial": "该槽位需要的素材描述",
      "matchedMaterialIds": ["匹配的素材ID列表"],
      "status": "covered | partial | missing",
      "confidence": 0.0-1.0,
      "reason": "匹配理由或缺失原因"
    }}
  ]
}}

匹配规则：
1. 一个素材可以匹配多个槽位
2. 优先匹配 suitableRoles 与槽位语义一致的素材
3. 文本素材可以补全 CTA 和字幕类槽位
4. 如果没有合适素材，status 设为 missing
5. 如果素材只能部分满足，status 设为 partial"""


# ─── Legacy Constants ─────────────────────────────────────────────────────────

DEFAULT_SLOTS_LEGACY = [
    ("hook", "开头吸引镜头", "需要能快速制造注意力的画面或文案。"),
    ("product-closeup", "商品特写镜头", "需要展示商品、包装、核心卖点的素材。"),
    ("usage", "使用过程镜头", "需要能说明使用方式或体验过程的视频素材。"),
    ("comparison", "对比镜头", "需要前后对比、竞品对比或效果对比素材。"),
    ("cta", "结尾 CTA 镜头", "需要行动引导、购买理由或收口表达。"),
]

ROLE_TO_LEGACY_SLOT = {
    "hook": "开头吸引镜头",
    "product-closeup": "商品特写镜头",
    "usage": "使用过程镜头",
    "comparison": "对比镜头",
    "cta": "结尾 CTA 镜头",
    "background": "背景素材",
}


# ─── CRUD Functions (unchanged) ───────────────────────────────────────────────

def task3_material_from_payload(payload: Task3MaterialPayload) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    return {
        "id": payload.id or uuid4().hex,
        "type": payload.type,
        "name": payload.name,
        "text": payload.text,
        "tags": payload.tags,
        "createdAt": now,
    }


def create_task3_input_record(payload: Task3InputCreateRequest) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    return {
        "id": uuid4().hex,
        "topic": payload.topic,
        "sellingPoints": payload.sellingPoints,
        "copyText": payload.copyText,
        "targetAudience": payload.targetAudience,
        "platform": payload.platform,
        "stylePreference": payload.stylePreference,
        "materials": [task3_material_from_payload(item) for item in payload.materials],
        "sourceAnalysisVideoIds": payload.sourceAnalysisVideoIds,
        "createdAt": now,
        "updatedAt": now,
    }


def get_task3_input_record(input_id: str) -> dict[str, Any]:
    record = next((item for item in load_task3_inputs() if item.get("id") == input_id), None)

    if record is None:
        raise HTTPException(status_code=404, detail="Task3 input not found.")

    return record


# ─── Phase 1: Material Understanding ─────────────────────────────────────────

def _understand_image_material(material: dict[str, Any]) -> dict[str, Any]:
    """Call vision model to understand image content."""
    material_url = material.get("url", "")
    stored_name = Path(material_url).name if material_url else ""
    image_path = TASK3_MATERIAL_DIR / stored_name

    if not image_path.exists():
        return {"error": "file_not_found", "sceneType": "unknown", "suitableRoles": []}

    try:
        config = load_commercial_model_config(model_type="image-recognition")
    except ValueError:
        return {"error": "no_vision_config", "sceneType": "unknown", "suitableRoles": []}

    data_url = encode_image_data_url(image_path)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": IMAGE_UNDERSTANDING_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": IMAGE_UNDERSTANDING_USER_PROMPT},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]

    try:
        response = call_commercial_structured_model(config=config, messages=messages)
        text = extract_response_text(response)
        result = parse_json_or_wrap(text)
        result.setdefault("suitableRoles", [])
        return result
    except (RuntimeError, ValueError) as exc:
        logger.warning("Image understanding failed for %s: %s", material.get("id"), exc)
        return {"error": str(exc), "sceneType": "unknown", "suitableRoles": []}


def _understand_video_material(material: dict[str, Any]) -> dict[str, Any]:
    """Extract video metadata + keyframe understanding via vision model."""
    material_url = material.get("url", "")
    stored_name = Path(material_url).name if material_url else ""
    video_path = TASK3_MATERIAL_DIR / stored_name

    if not video_path.exists():
        return {"error": "file_not_found", "sceneType": "unknown", "suitableRoles": []}

    metadata: dict[str, Any] = {}
    try:
        metadata = probe_video(video_path)
    except (ValueError, RuntimeError, OSError):
        pass

    duration_sec = (metadata.get("durationMs") or 5000) / 1000
    frame_interval = max(int(duration_sec / 4), 1)

    understanding: dict[str, Any] = {"suitableRoles": []}
    try:
        config = load_commercial_model_config(model_type="image-recognition")

        frames = extract_structured_frames(
            video_record={"id": material.get("id", "unknown")},
            video_path=video_path,
            frame_interval=frame_interval,
            max_frames=4,
        )

        frame_content: list[dict[str, Any]] = [
            {"type": "text", "text": VIDEO_UNDERSTANDING_USER_PROMPT}
        ]
        for frame in frames:
            frame_content.append({
                "type": "image_url",
                "image_url": {"url": encode_image_data_url(frame)},
            })

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": IMAGE_UNDERSTANDING_SYSTEM_PROMPT},
            {"role": "user", "content": frame_content},
        ]

        response = call_commercial_structured_model(config=config, messages=messages)
        text = extract_response_text(response)
        understanding = parse_json_or_wrap(text)
        understanding.setdefault("suitableRoles", [])
    except (RuntimeError, ValueError) as exc:
        logger.warning("Video understanding failed for %s: %s", material.get("id"), exc)
        understanding["error"] = str(exc)

    understanding["metadata"] = metadata
    return understanding


def _rule_based_understanding(material: dict[str, Any]) -> dict[str, Any]:
    """Fallback: infer understanding from type/tags/text only (preserves legacy logic)."""
    material_type = material.get("type", "text")
    text = material.get("text") or ""
    tags = material.get("tags") or []

    suitable_roles: list[str] = []
    if material_type == "video":
        suitable_roles = ["hook", "usage", "cta"]
    elif material_type == "image":
        suitable_roles = ["product-closeup", "background"]
    elif material_type == "text":
        suitable_roles = ["cta"]

    if any("对比" in value for value in tags) or "对比" in text:
        suitable_roles.append("comparison")

    return {
        "sceneType": material_type,
        "mainObjects": tags,
        "textContent": text[:120] if text else "",
        "suitableRoles": suitable_roles,
        "confidence": 0.72 if suitable_roles else 0.45,
        "source": "rule-based",
    }


def _roles_to_slot_names(
    roles: list[str], material_type: str, tags: list[str], text: str
) -> list[str]:
    """Convert suitableRoles to legacy slot names for backward compatibility."""
    slot_names: list[str] = []
    for role in roles:
        if role in ROLE_TO_LEGACY_SLOT:
            slot_names.append(ROLE_TO_LEGACY_SLOT[role])

    if not slot_names:
        if material_type == "video":
            slot_names = ["开头吸引镜头", "使用过程镜头", "结尾 CTA 镜头"]
        elif material_type == "image":
            slot_names = ["商品特写镜头", "包装展示镜头"]
        elif material_type == "text":
            slot_names = ["字幕补全", "结尾 CTA 镜头"]

    if any("对比" in value for value in tags) or "对比" in text:
        if "对比镜头" not in slot_names:
            slot_names.append("对比镜头")

    return slot_names


def infer_material_inventory(
    task_input: dict[str, Any],
    *,
    use_vision: bool = False,
) -> list[dict[str, Any]]:
    """Build material inventory with optional AI understanding."""
    inventory: list[dict[str, Any]] = []

    for material in task_input.get("materials", []):
        material_type = material.get("type", "text")
        text = material.get("text") or ""
        tags = material.get("tags") or []

        understanding: dict[str, Any] = {}
        if use_vision and material_type == "image":
            understanding = _understand_image_material(material)
        elif use_vision and material_type == "video":
            understanding = _understand_video_material(material)

        if not understanding or understanding.get("error"):
            understanding = _rule_based_understanding(material)

        suitable_roles = understanding.get("suitableRoles", [])
        usable_slots = _roles_to_slot_names(suitable_roles, material_type, tags, text)

        scene_type = understanding.get("sceneType", "unknown")
        detected_scenes = [scene_type] if isinstance(scene_type, str) else scene_type

        inventory.append({
            "materialId": material.get("id"),
            "materialName": material.get("name"),
            "materialType": material_type,
            "detectedObjects": understanding.get("mainObjects", tags),
            "detectedScenes": detected_scenes,
            "detectedText": (
                [understanding["textContent"]]
                if understanding.get("textContent")
                else ([text[:120]] if text else [])
            ),
            "usableForSlots": sorted(set(usable_slots)),
            "understanding": understanding,
            "confidence": understanding.get("confidence", 0.72 if usable_slots else 0.45),
        })

    if task_input.get("copyText"):
        inventory.append({
            "materialId": "copy-text",
            "materialName": "用户文案",
            "materialType": "text",
            "detectedObjects": [],
            "detectedScenes": [],
            "detectedText": [str(task_input.get("copyText"))[:160]],
            "usableForSlots": ["字幕补全", "结尾 CTA 镜头"],
            "understanding": {
                "sceneType": "text-card",
                "suitableRoles": ["cta", "subtitle-fill"],
                "source": "rule-based",
            },
            "confidence": 0.76,
        })

    return inventory


# ─── Phase 2: Slot Matching ───────────────────────────────────────────────────

def _extract_dynamic_slots(video_structure: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert VideoStructure into dynamic slot list for matching."""
    transferable = video_structure.get("transferableSlots", [])
    if transferable:
        return [
            {
                "slotId": slot.get("slotId", "unknown"),
                "slotName": slot.get("slotName", ""),
                "requiredMaterial": slot.get("requiredMaterial", []),
                "fallbackOptions": slot.get("fallbackOptions", []),
                "sourceStructureTypes": slot.get("sourceStructureTypes", []),
            }
            for slot in transferable
        ]

    return [
        {
            "slotId": item.get("slotId", f"slot-{i}"),
            "slotName": item.get("name", ""),
            "requiredMaterial": item.get("requiredMaterial", []),
            "fallbackOptions": ["文案/字幕补全", "包装补全"],
            "sourceStructureTypes": ["script"],
        }
        for i, item in enumerate(video_structure.get("scriptStructure", []))
    ]


def _llm_semantic_match(
    inventory: list[dict[str, Any]],
    slots: list[dict[str, Any]],
    task_input: dict[str, Any],
) -> list[dict[str, Any]]:
    """Call LLM to semantically match materials to slots."""
    try:
        config = load_llm_config()
    except ValueError:
        config = load_commercial_model_config(model_type="image-recognition")

    compact_inventory = [
        {
            "materialId": item["materialId"],
            "materialName": item["materialName"],
            "materialType": item["materialType"],
            "detectedObjects": item.get("detectedObjects", []),
            "detectedScenes": item.get("detectedScenes", []),
            "detectedText": item.get("detectedText", []),
            "suitableRoles": item.get("understanding", {}).get("suitableRoles", []),
            "description": item.get("understanding", {}).get("description", ""),
        }
        for item in inventory
    ]

    user_prompt = SEMANTIC_MATCH_USER_TEMPLATE.format(
        inventory_json=json.dumps(compact_inventory, ensure_ascii=False, indent=2),
        slots_json=json.dumps(slots, ensure_ascii=False, indent=2),
        topic=task_input.get("topic", ""),
        selling_points=", ".join(task_input.get("sellingPoints", [])),
        copy_text=(task_input.get("copyText") or "")[:200],
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SEMANTIC_MATCH_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    response = call_commercial_structured_model(config=config, messages=messages)
    text = extract_response_text(response)
    parsed = parse_json_or_wrap(text)

    matches = parsed.get("matches", [])
    if not matches:
        raise ValueError("LLM returned no matches")

    result = []
    for match in matches:
        result.append({
            "slotId": match.get("slotId", "unknown"),
            "slotName": match.get("slotName", ""),
            "requiredMaterial": match.get("requiredMaterial", ""),
            "matchedMaterialIds": match.get("matchedMaterialIds", []),
            "status": match.get("status", "missing"),
            "confidence": match.get("confidence", 0.5),
            "reason": match.get("reason", ""),
        })

    return result


def _rule_based_match(
    task_input: dict[str, Any],
    inventory: list[dict[str, Any]],
    slots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generalized rule-based matching for both legacy and dynamic slots."""
    selling_points = task_input.get("sellingPoints") or []
    copy_text = task_input.get("copyText") or ""
    matches: list[dict[str, Any]] = []

    for slot in slots:
        slot_id = slot["slotId"]
        slot_name = slot["slotName"]
        required = slot.get("requiredMaterial", [])
        required_str = " ".join(required) if isinstance(required, list) else str(required)

        matched_ids: list[str] = []
        for item in inventory:
            usable = item.get("usableForSlots", [])
            understanding = item.get("understanding", {})
            suitable_roles = understanding.get("suitableRoles", [])

            if slot_name in usable:
                matched_ids.append(item["materialId"])
            elif slot_id in suitable_roles:
                matched_ids.append(item["materialId"])
            elif required_str and item.get("materialType") == "video" and any(
                keyword in required_str
                for keyword in ["画面", "镜头", "视频", "过程", "展示"]
            ):
                matched_ids.append(item["materialId"])

        status = "covered" if matched_ids else "missing"

        if slot_id in ("hook", "cta") or "hook" in slot_id or "cta" in slot_id.lower():
            if not matched_ids and (task_input.get("topic") or selling_points or copy_text):
                status = "partial"
                if copy_text and "copy-text" not in matched_ids:
                    matched_ids.append("copy-text")

        if "对比" in slot_name or "comparison" in slot_id:
            if not matched_ids and any("对比" in point for point in selling_points):
                status = "partial"

        matches.append({
            "slotId": slot_id,
            "slotName": slot_name,
            "requiredMaterial": required_str or f"需要支撑「{slot_name}」的素材。",
            "matchedMaterialIds": matched_ids,
            "status": status,
            "confidence": 0.72 if status == "covered" else (0.45 if status == "partial" else 0.0),
            "reason": (
                "已有素材可支撑该槽位。"
                if status == "covered"
                else "当前素材只能部分支撑或无法直接支撑该槽位。"
            ),
        })

    return matches


def build_task3_slot_matches(
    task_input: dict[str, Any],
    inventory: list[dict[str, Any]],
    *,
    video_structure: dict[str, Any] | None = None,
    use_llm: bool = False,
) -> list[dict[str, Any]]:
    """Match materials to slots (dynamic or fixed, LLM or rule-based)."""
    if video_structure:
        slots = _extract_dynamic_slots(video_structure)
    else:
        slots = [
            {
                "slotId": sid,
                "slotName": sname,
                "requiredMaterial": [req],
                "fallbackOptions": [],
                "sourceStructureTypes": [],
            }
            for sid, sname, req in DEFAULT_SLOTS_LEGACY
        ]

    if use_llm and slots and inventory:
        try:
            return _llm_semantic_match(inventory, slots, task_input)
        except (RuntimeError, ValueError) as exc:
            logger.warning("LLM matching failed, falling back to rules: %s", exc)

    return _rule_based_match(task_input, inventory, slots)


# ─── Phase 3: Gap Detection ──────────────────────────────────────────────────

def build_task3_gaps(
    slot_matches: list[dict[str, Any]],
    *,
    video_structure: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Collect unmatched slots as gaps with dynamic suggestedFixes."""
    gaps: list[dict[str, Any]] = []

    fallback_map: dict[str, list[str]] = {}
    if video_structure:
        for slot in video_structure.get("transferableSlots", []):
            fallback_map[slot.get("slotId", "")] = slot.get("fallbackOptions", [])

    for item in slot_matches:
        if item["status"] == "covered":
            continue

        slot_id = item["slotId"]
        suggested_fixes = fallback_map.get(slot_id) or [
            "上传补充素材",
            "用文案/字幕补全表达",
            "使用标题条或卖点卡片补足",
            "重排已有素材降低依赖",
        ]

        gaps.append({
            "id": uuid4().hex,
            "slotId": slot_id,
            "name": item["slotName"],
            "severity": "high" if item["status"] == "missing" else "medium",
            "reason": item.get("reason", ""),
            "suggestedFixes": suggested_fixes,
            "resolution": "pending",
        })

    return gaps


# ─── Orchestrator ─────────────────────────────────────────────────────────────

def analyze_task3_input(
    input_record: dict[str, Any],
    settings: dict[str, Any] | None = None,
    *,
    video_structure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Main entry point. Orchestrates understanding -> matching -> gaps."""
    settings = settings or {}
    use_vision = bool(settings.get("useVision", True))
    use_llm_matching = bool(settings.get("useLlmMatching", True))

    inventory = infer_material_inventory(input_record, use_vision=use_vision)

    slot_matches = build_task3_slot_matches(
        input_record,
        inventory,
        video_structure=video_structure,
        use_llm=use_llm_matching,
    )

    gaps = build_task3_gaps(slot_matches, video_structure=video_structure)

    now = datetime.now(UTC).isoformat()
    summary = (
        "内容完整无缺口"
        if not gaps
        else f"识别到 {len(gaps)} 个素材缺口，需要补充或调整素材。"
    )

    return {
        "id": uuid4().hex,
        "inputId": input_record["id"],
        "status": "ready",
        "settings": settings,
        "videoStructureUsed": video_structure is not None,
        "materialInventory": inventory,
        "slotMatches": slot_matches,
        "gaps": gaps,
        "summary": summary,
        "createdAt": now,
    }

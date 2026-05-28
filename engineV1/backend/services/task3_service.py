from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from ..schemas import Task3InputCreateRequest, Task3MaterialPayload
from ..storage import load_task3_inputs


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


def infer_material_inventory(task_input: dict[str, Any]) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []

    for material in task_input.get("materials", []):
        material_type = material.get("type", "text")
        text = material.get("text") or ""
        tags = material.get("tags") or []
        usable_slots: list[str] = []

        if material_type == "video":
            usable_slots.extend(["开头吸引镜头", "使用过程镜头", "结尾 CTA 镜头"])
        elif material_type == "image":
            usable_slots.extend(["商品特写镜头", "包装展示镜头"])
        elif material_type == "text":
            usable_slots.extend(["字幕补全", "结尾 CTA 镜头"])

        if any("对比" in value for value in tags) or "对比" in text:
            usable_slots.append("对比镜头")

        inventory.append(
            {
                "materialId": material.get("id"),
                "materialName": material.get("name"),
                "materialType": material_type,
                "detectedObjects": tags,
                "detectedScenes": ["用户上传素材"] if material_type in {"image", "video"} else [],
                "detectedText": [text[:120]] if text else [],
                "usableForSlots": sorted(set(usable_slots)),
                "confidence": 0.72 if usable_slots else 0.45,
            }
        )

    if task_input.get("copyText"):
        inventory.append(
            {
                "materialId": "copy-text",
                "materialName": "用户文案",
                "materialType": "text",
                "detectedObjects": [],
                "detectedScenes": [],
                "detectedText": [str(task_input.get("copyText"))[:160]],
                "usableForSlots": ["字幕补全", "结尾 CTA 镜头"],
                "confidence": 0.76,
            }
        )

    return inventory


def build_task3_slot_matches(task_input: dict[str, Any], inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    required_slots = [
        ("hook", "开头吸引镜头", "需要能快速制造注意力的画面或文案。"),
        ("product-closeup", "商品特写镜头", "需要展示商品、包装、核心卖点的素材。"),
        ("usage", "使用过程镜头", "需要能说明使用方式或体验过程的视频素材。"),
        ("comparison", "对比镜头", "需要前后对比、竞品对比或效果对比素材。"),
        ("cta", "结尾 CTA 镜头", "需要行动引导、购买理由或收口表达。"),
    ]
    selling_points = task_input.get("sellingPoints") or []
    copy_text = task_input.get("copyText") or ""
    matches: list[dict[str, Any]] = []

    for slot_id, slot_name, requirement in required_slots:
        matched = [
            item["materialId"]
            for item in inventory
            if slot_name in item.get("usableForSlots", [])
        ]
        status = "covered" if matched else "missing"

        if slot_id == "hook" and (task_input.get("topic") or selling_points):
            status = "partial" if not matched else "covered"
        if slot_id == "cta" and (copy_text or selling_points):
            status = "covered"
            if "copy-text" not in matched and copy_text:
                matched.append("copy-text")
        if slot_id == "comparison" and any("对比" in point for point in selling_points):
            status = "partial" if not matched else "covered"

        matches.append(
            {
                "slotId": slot_id,
                "slotName": slot_name,
                "requiredMaterial": requirement,
                "matchedMaterialIds": matched,
                "status": status,
                "reason": "已有素材可支撑该槽位。" if status == "covered" else "当前素材只能部分支撑或无法直接支撑该槽位。",
            }
        )

    return matches


def build_task3_gaps(slot_matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []

    for item in slot_matches:
        if item["status"] == "covered":
            continue

        gaps.append(
            {
                "id": uuid4().hex,
                "slotId": item["slotId"],
                "name": item["slotName"],
                "severity": "high" if item["status"] == "missing" else "medium",
                "reason": item["reason"],
                "suggestedFixes": [
                    "上传补充素材",
                    "用文案/字幕补全表达",
                    "使用标题条或卖点卡片补足",
                    "重排已有素材降低依赖",
                ],
                "resolution": "pending",
            }
        )

    return gaps


def analyze_task3_input(input_record: dict[str, Any], settings: dict[str, Any] | None = None) -> dict[str, Any]:
    inventory = infer_material_inventory(input_record)
    slot_matches = build_task3_slot_matches(input_record, inventory)
    gaps = build_task3_gaps(slot_matches)
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
        "settings": settings or {},
        "materialInventory": inventory,
        "slotMatches": slot_matches,
        "gaps": gaps,
        "summary": summary,
        "createdAt": now,
    }

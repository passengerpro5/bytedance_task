from __future__ import annotations

from typing import Any

from .errors import conflict
from .schemas import BreakdownRecord, BreakdownStatus


def build_markdown_export(record: BreakdownRecord) -> str:
    if record.status != BreakdownStatus.SUCCEEDED:
        raise conflict("EXPORT_NOT_READY", "Breakdown must succeed before export")
    if not all([record.source_video, record.classification, record.decomposition, record.structure_protocol, record.script_agent_bridge]):
        raise conflict("EXPORT_NOT_READY", "Breakdown result is incomplete")

    source = record.source_video or {}
    classification = record.classification or {}
    decomposition = record.decomposition or {}
    protocol = record.structure_protocol or {}
    bridge = record.script_agent_bridge or {}
    reference_storyboard = record.reference_storyboard or []

    lines = [
        "# 视频拆解报告",
        "",
        f"- Provider: {record.provider}",
        f"- Original URL: {source.get('original_url', '')}",
        f"- Imported Video URL: {source.get('imported_video_url', '')}",
        f"- Title: {source.get('title') or ''}",
        f"- Platform: {source.get('platform') or ''}",
        f"- Creator: {source.get('creator_handle') or ''}",
        f"- Duration: {_duration(source.get('duration_seconds'))}",
        f"- Summary: {source.get('content_summary') or ''}",
        "",
        "## 爆款因子分类",
        f"- Hook 因子: {classification.get('hook_type') or ''}",
        f"- 情绪因子: {', '.join(classification.get('emotion_factors') or [])}",
        f"- 人设因子: {', '.join(classification.get('persona_factors') or [])}",
        f"- 场景因子: {', '.join(classification.get('scene_factors') or [])}",
        f"- 冲突因子: {', '.join(classification.get('conflict_factors') or [])}",
        f"- 痛点因子: {', '.join(classification.get('pain_factors') or [])}",
        f"- 痒点因子: {', '.join(classification.get('itch_factors') or [])}",
        f"- Value 因子: {', '.join(classification.get('value_factors') or [])}",
        f"- Proof 因子: {', '.join(classification.get('proof_factors') or [])}",
        f"- CTA 因子: {', '.join(classification.get('cta_factors') or [])}",
        f"- 视频结构因子: {', '.join(classification.get('structure_factors') or [])}",
        f"- 视觉节奏因子: {', '.join(classification.get('visual_rhythm_factors') or [])}",
        f"- 人群洞察: {', '.join(classification.get('audience_segments') or [])}",
        f"- General 模板: {', '.join(classification.get('general_templates') or [])}",
        f"- Vertical 模板: {', '.join(classification.get('vertical_templates') or [])}",
        f"- 判断依据: {classification.get('factor_reasoning', '')}",
        "",
        "## Hook 五要素",
        decomposition.get("hook") or "",
        "",
        "## 叙事结构",
        *_list(decomposition.get("narrative_structure") or []),
        "",
        "## 分段拆解",
        "| 段落 | 时间 | 作用 | 内容 | 手法 |",
        "|---|---|---|---|---|",
    ]
    for segment in decomposition.get("segments") or []:
        lines.append(
            "| {no} | {time} | {role} | {content} | {technique} |".format(
                no=_cell(segment.get("segment_no", "")),
                time=_cell(_range(segment.get("start_second"), segment.get("end_second"))),
                role=_cell(segment.get("role", "")),
                content=_cell(segment.get("content", "")),
                technique=_cell(segment.get("technique", "")),
            )
        )

    lines.extend(
        [
            "",
            "## Structure Protocol",
            f"- Core Pattern: {protocol.get('core_pattern', '')}",
            "",
            "| Slot | Time | Role | Evidence | Transfer Rule |",
            "|---|---|---|---|---|",
        ]
    )
    for slot in protocol.get("timeline_slots") or []:
        lines.append(
            "| {name} | {time} | {role} | {evidence} | {rule} |".format(
                name=_cell(slot.get("name", "")),
                time=_cell(_range(slot.get("start_second"), slot.get("end_second"))),
                role=_cell(slot.get("role", "")),
                evidence=_cell(slot.get("observable_evidence", "")),
                rule=_cell(slot.get("transfer_rule", "")),
            )
        )

    lines.extend(
        [
            "",
            "## Script Agent Bridge",
            f"- Reusable Pattern: {bridge.get('reusable_pattern', '')}",
            "",
            "### Instructions",
            *_list(bridge.get("script_agent_instructions") or []),
            "",
            "### Variables To Collect",
            *_list(bridge.get("variables_to_collect") or []),
            "",
            "### Do Not Copy",
            *_list(bridge.get("do_not_copy") or []),
            "",
            "### Adaptation Notes",
            *_list(bridge.get("adaptation_notes") or []),
            "",
            "## 爆款参考分镜脚本",
            "| Shot | Time | Camera | Action | Voiceover | Overlay | Purpose |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for shot in reference_storyboard:
        lines.append(
            "| {shot} | {time} | {camera} | {action} | {voiceover} | {overlay} | {purpose} |".format(
                shot=_cell(shot.get("shot_id", "")),
                time=_cell(shot.get("timestamp") or shot.get("duration") or ""),
                camera=_cell(shot.get("camera", "")),
                action=_cell(shot.get("character_action", "")),
                voiceover=_cell(shot.get("voiceover", "")),
                overlay=_cell(shot.get("overlay", "")),
                purpose=_cell(shot.get("purpose", "")),
            )
        )
    lines.append("")
    return "\n".join(lines)


def _duration(value: Any) -> str:
    if value is None:
        return ""
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _range(start: Any, end: Any) -> str:
    if start is None and end is None:
        return ""
    return f"{_duration(start)}-{_duration(end)}"


def _list(items: list[Any]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- "]


def _cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", "<br>")

"""VideoStructure normalizer.

Converts raw decomposition JSON (from video_decompose.py) into a validated
VideoStructure dict that downstream consumers (composition_planner, task3
gap matching, frontend page 4/7) can rely on without format guessing.

Handles two decomposition modes:
1. Fast mode: overview already contains scriptStructure/rhythmStructure/
   packagingStructure/transferableSlots directly.
2. Deep mode: multiple steps each with summary/findings/handoff, plus an
   overview that may or may not contain the three structure types.

The normalizer merges information from steps and overview, fills missing
fields with safe defaults, and coerces types (e.g. shotCount string -> int).
"""

from __future__ import annotations

import re
from typing import Any


def normalize_decomposition_to_structure(
    decomposition: dict[str, Any],
) -> dict[str, Any]:
    """Main entry point. Returns a validated VideoStructure dict."""
    method = decomposition.get("methodName", "fast")
    overview = decomposition.get("overview") or {}
    steps = decomposition.get("steps") or []

    if method == "fast" or _overview_has_full_structure(overview):
        structure = _extract_from_overview(overview)
    else:
        structure = _merge_from_steps(steps, overview)

    _fill_defaults(structure)
    _coerce_types(structure)
    return structure


def _overview_has_full_structure(overview: dict[str, Any]) -> bool:
    return (
        bool(overview.get("scriptStructure"))
        and bool(overview.get("rhythmStructure"))
    )


def _extract_from_overview(overview: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": overview.get("summary", ""),
        "scriptStructure": _normalize_script_structure(
            overview.get("scriptStructure", [])
        ),
        "rhythmStructure": _normalize_rhythm_structure(
            overview.get("rhythmStructure", {})
        ),
        "packagingStructure": _normalize_packaging_structure(
            overview.get("packagingStructure", {})
        ),
        "transferableSlots": _normalize_transferable_slots(
            overview.get("transferableSlots", [])
        ),
        "risks": overview.get("risks", []),
        "raw": overview,
    }


def _merge_from_steps(
    steps: list[dict[str, Any]], overview: dict[str, Any]
) -> dict[str, Any]:
    """Merge structure info scattered across deep-mode steps."""
    merged_script: list[dict[str, Any]] = []
    merged_rhythm: dict[str, Any] = {}
    merged_packaging: dict[str, Any] = {}
    merged_slots: list[dict[str, Any]] = []
    merged_risks: list[str] = []
    summaries: list[str] = []

    for step in steps:
        output = step.get("output") or {}
        if not isinstance(output, dict):
            continue

        if output.get("scriptStructure"):
            merged_script.extend(output["scriptStructure"])
        if output.get("rhythmStructure") and not merged_rhythm:
            merged_rhythm = output["rhythmStructure"]
        if output.get("packagingStructure") and not merged_packaging:
            merged_packaging = output["packagingStructure"]
        if output.get("transferableSlots"):
            merged_slots.extend(output["transferableSlots"])
        if output.get("risks"):
            merged_risks.extend(output["risks"])
        if output.get("summary"):
            summaries.append(output["summary"])

        handoff = output.get("handoff") or {}
        if isinstance(handoff, dict) and handoff.get("transferableSlots"):
            for slot in handoff["transferableSlots"]:
                if isinstance(slot, str):
                    merged_slots.append({"slotId": slot, "slotName": slot})
                elif isinstance(slot, dict):
                    merged_slots.append(slot)

    if overview.get("scriptStructure") and not merged_script:
        merged_script = overview["scriptStructure"]
    if overview.get("rhythmStructure") and not merged_rhythm:
        merged_rhythm = overview["rhythmStructure"]
    if overview.get("packagingStructure") and not merged_packaging:
        merged_packaging = overview["packagingStructure"]
    if overview.get("transferableSlots") and not merged_slots:
        merged_slots = overview["transferableSlots"]

    summary = overview.get("overview") or overview.get("summary") or ""
    if not summary and summaries:
        summary = summaries[0]

    merged_slots = _deduplicate_slots(merged_slots)

    return {
        "summary": summary,
        "scriptStructure": _normalize_script_structure(merged_script),
        "rhythmStructure": _normalize_rhythm_structure(merged_rhythm),
        "packagingStructure": _normalize_packaging_structure(merged_packaging),
        "transferableSlots": _normalize_transferable_slots(merged_slots),
        "risks": merged_risks,
        "raw": {"overview": overview, "stepCount": len(steps)},
    }


def _normalize_script_structure(
    raw: list[Any],
) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    result = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        result.append({
            "slotId": str(item.get("slotId", "unknown")),
            "name": str(item.get("name", "")),
            "timeRange": item.get("timeRange"),
            "scriptText": item.get("scriptText"),
            "intent": item.get("intent"),
            "contentRole": item.get("contentRole"),
            "transferRule": item.get("transferRule"),
            "requiredMaterial": _ensure_str_list(
                item.get("requiredMaterial", [])
            ),
        })
    return result


def _normalize_rhythm_structure(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}

    return {
        "shotCount": _to_int_or_none(raw.get("shotCount")),
        "avgShotDurationSec": _to_float_or_none(
            raw.get("avgShotDurationSec")
        ),
        "cutFrequency": raw.get("cutFrequency"),
        "tempoCurve": raw.get("tempoCurve", []),
        "climax": raw.get("climax", {}),
    }


def _normalize_packaging_structure(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}

    return {
        "subtitle": raw.get("subtitle", {}),
        "titleBar": raw.get("titleBar", {}),
        "stickers": raw.get("stickers", []),
        "transitions": _ensure_str_list(raw.get("transitions", [])),
        "coverStyle": raw.get("coverStyle", {}),
    }


def _normalize_transferable_slots(
    raw: list[Any],
) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    result = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        result.append({
            "slotId": str(item.get("slotId", "unknown")),
            "slotName": str(item.get("slotName", item.get("name", ""))),
            "sourceStructureTypes": _ensure_str_list(
                item.get("sourceStructureTypes", [])
            ),
            "timeRange": item.get("timeRange"),
            "requiredMaterial": _ensure_str_list(
                item.get("requiredMaterial", [])
            ),
            "fallbackOptions": _ensure_str_list(
                item.get("fallbackOptions", [])
            ),
        })
    return result


def _deduplicate_slots(
    slots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result = []
    for slot in slots:
        slot_id = slot.get("slotId", "")
        if slot_id and slot_id in seen:
            continue
        if slot_id:
            seen.add(slot_id)
        result.append(slot)
    return result


def _fill_defaults(structure: dict[str, Any]) -> None:
    """Ensure all top-level keys exist with safe defaults."""
    structure.setdefault("summary", "")
    structure.setdefault("scriptStructure", [])
    structure.setdefault("rhythmStructure", {})
    structure.setdefault("packagingStructure", {})
    structure.setdefault("transferableSlots", [])
    structure.setdefault("risks", [])
    structure.setdefault("raw", {})


def _coerce_types(structure: dict[str, Any]) -> None:
    """Fix common type issues from LLM output."""
    rhythm = structure.get("rhythmStructure")
    if isinstance(rhythm, dict):
        rhythm["shotCount"] = _to_int_or_none(rhythm.get("shotCount"))
        rhythm["avgShotDurationSec"] = _to_float_or_none(
            rhythm.get("avgShotDurationSec")
        )


def _to_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        digits = re.sub(r"[^\d]", "", value)
        return int(digits) if digits else None
    return None


def _to_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"[\d.]+", value)
        if match:
            try:
                return float(match.group())
            except ValueError:
                return None
    return None


def _ensure_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return []


def validate_structure_completeness(
    structure: dict[str, Any],
) -> dict[str, Any]:
    """Check if the structure meets T2 minimum requirements (2 of 3 types).

    Returns a dict with:
      - valid: bool
      - coveredTypes: list of covered structure type names
      - missingTypes: list of missing structure type names
      - message: human-readable summary
    """
    covered = []
    missing = []

    if structure.get("scriptStructure"):
        covered.append("script")
    else:
        missing.append("script")

    rhythm = structure.get("rhythmStructure", {})
    if rhythm and (rhythm.get("shotCount") or rhythm.get("tempoCurve")):
        covered.append("rhythm")
    else:
        missing.append("rhythm")

    packaging = structure.get("packagingStructure", {})
    if packaging and any(
        packaging.get(k)
        for k in ("subtitle", "titleBar", "stickers", "transitions")
    ):
        covered.append("packaging")
    else:
        missing.append("packaging")

    valid = len(covered) >= 2

    if valid:
        message = f"结构拆解完整度满足要求，已覆盖：{', '.join(covered)}。"
    else:
        message = (
            f"结构拆解不完整，仅覆盖 {len(covered)} 类"
            f"（需至少 2 类）。缺失：{', '.join(missing)}。"
        )

    return {
        "valid": valid,
        "coveredTypes": covered,
        "missingTypes": missing,
        "message": message,
    }

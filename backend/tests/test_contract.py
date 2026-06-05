from __future__ import annotations

import copy
import json

import pytest
from pydantic import ValidationError

from app.provider import build_mock_result
from app.script_service import default_moras_assets
from app.schemas import BreakdownResult, FORBIDDEN_RESULT_KEYS
from app.service import parse_model_result


VIDEO_TEARDOWN_BOUNDARY_KEYS = {
    "combination_matrix",
    "selected_component_set",
    "selected_component_sets",
    "shot_plan",
    "shot_plans",
    "executable_video_generation_prompt",
    "video_generation_prompt",
    "final_script",
    "storyboard",
    "video_prompt",
}


def test_mock_result_matches_public_contract():
    payload = build_mock_result("/uploads/source.mp4", "/uploads/source.mp4")
    result = BreakdownResult.model_validate(payload)
    dumped = result.model_dump(mode="json")

    assert list(dumped.keys()) == [
        "source_video",
        "classification",
        "decomposition",
        "structure_protocol",
        "script_agent_bridge",
        "reference_storyboard",
    ]
    assert dumped["classification"]["taxonomy_version"] == "moras_viral_factor_v1"
    assert dumped["classification"]["hook_type"] == "禁忌型"
    assert "【视觉】" in dumped["decomposition"]["hook"]
    assert dumped["structure_protocol"]["source"] == "k2lab_social_video_breakdown"
    assert dumped["reference_storyboard"][0]["shot_id"] == "shot_1"
    assert set(dumped["reference_storyboard"][0]).issuperset(
        {
            "shot_id",
            "timestamp",
            "duration",
            "camera",
            "character_action",
            "facial_expression",
            "background",
            "props",
            "voiceover",
            "overlay",
            "sound",
            "transition",
            "purpose",
            "localized",
        }
    )
    assert _forbidden_key_intersection(dumped) == set()


def test_parser_fills_source_urls_and_rejects_deprecated_classification_keys():
    payload = build_mock_result("", "")
    payload["source_video"].pop("original_url")
    payload["source_video"].pop("imported_video_url")
    result = parse_model_result(json.dumps(payload, ensure_ascii=False), "input.mp4", "/uploads/imported.mp4")
    assert result.source_video.original_url == "input.mp4"
    assert result.source_video.imported_video_url == "/uploads/imported.mp4"

    old_key = copy.deepcopy(payload)
    old_key["classification"]["top_category"] = "old fixed label"
    with pytest.raises(Exception):
        parse_model_result(json.dumps(old_key, ensure_ascii=False), "input.mp4", "/uploads/imported.mp4")

    expanded_tags = copy.deepcopy(payload)
    expanded_tags["classification"]["emotion_factors"] = ["好奇", "怀疑"]
    result = parse_model_result(json.dumps(expanded_tags, ensure_ascii=False), "input.mp4", "/uploads/imported.mp4")
    assert result.classification.emotion_factors == ["好奇", "怀疑"]


def test_observed_metrics_accepts_multiple_visible_values():
    payload = build_mock_result("/uploads/source.mp4", "/uploads/source.mp4")
    payload["source_video"]["observed_metrics"] = {
        "gmv_claims": ["$30.8K", "$23.5K", "$27.1K"],
        "visible_profile_count": 3,
    }

    result = BreakdownResult.model_validate(payload)

    assert result.source_video.observed_metrics["gmv_claims"] == ["$30.8K", "$23.5K", "$27.1K"]


def test_default_assets_load_persona_led_reference_skeletons():
    assets = default_moras_assets()
    skeletons = assets["reference_teardown_skeletons"]
    reference_ids = {item["reference_id"] for item in skeletons}

    assert assets["positioning"].startswith("Persona-led social growth")
    assert "standard_growth_ad_workflow_proof" not in reference_ids
    assert {
        "moras_reference_01_conversational_duo",
        "moras_reference_02_niche_mentor",
        "moras_reference_03_skeptical_reviewer",
        "moras_reference_04_workflow_comparison",
    }.issubset(reference_ids)
    assert assets["cross_reference_rules_for_script_agent"]


def test_schema_rejects_forbidden_keys_and_shallow_hook():
    payload = build_mock_result("/uploads/source.mp4", "/uploads/source.mp4")
    for forbidden_key in FORBIDDEN_RESULT_KEYS:
        bad = copy.deepcopy(payload)
        bad[forbidden_key] = "legacy"
        with pytest.raises(ValidationError):
            BreakdownResult.model_validate(bad)

    shallow = copy.deepcopy(payload)
    shallow["decomposition"]["hook"] = "只是一个普通开头"
    with pytest.raises(ValidationError):
        BreakdownResult.model_validate(shallow)


def test_teardown_boundary_keys_fail_schema_and_parser_contracts():
    assert VIDEO_TEARDOWN_BOUNDARY_KEYS.issubset(FORBIDDEN_RESULT_KEYS)
    payload = build_mock_result("/uploads/source.mp4", "/uploads/source.mp4")

    for forbidden_key in VIDEO_TEARDOWN_BOUNDARY_KEYS:
        top_level = copy.deepcopy(payload)
        top_level[forbidden_key] = {"legacy": True}
        with pytest.raises(ValidationError):
            BreakdownResult.model_validate(top_level)
        with pytest.raises(Exception):
            parse_model_result(json.dumps(top_level, ensure_ascii=False), "input.mp4", "/uploads/imported.mp4")

        nested = copy.deepcopy(payload)
        nested["source_video"]["observed_metrics"][forbidden_key] = {"legacy": True}
        with pytest.raises(ValidationError):
            BreakdownResult.model_validate(nested)
        with pytest.raises(Exception):
            parse_model_result(json.dumps(nested, ensure_ascii=False), "input.mp4", "/uploads/imported.mp4")


def test_reference_storyboard_is_allowed_but_plain_storyboard_is_not():
    payload = build_mock_result("/uploads/source.mp4", "/uploads/source.mp4")
    result = BreakdownResult.model_validate(payload)

    assert result.reference_storyboard
    assert result.reference_storyboard[0].shot_id == "shot_1"

    plain_storyboard = copy.deepcopy(payload)
    plain_storyboard["storyboard"] = plain_storyboard.pop("reference_storyboard")
    with pytest.raises(ValidationError):
        BreakdownResult.model_validate(plain_storyboard)


def _forbidden_key_intersection(value) -> set[str]:
    found = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_RESULT_KEYS:
                found.add(key)
            found.update(_forbidden_key_intersection(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_forbidden_key_intersection(child))
    return found

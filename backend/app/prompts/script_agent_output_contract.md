# Script Agent Output Contract

Return valid JSON only with this top-level shape:

```json
{
  "scripts": [
    {
      "topic_plan": {},
      "script": {},
      "storyboard": [],
      "creator_persona": {},
      "video_prompt": {},
      "production_asset_plan": [],
      "risk_check": {},
      "source_breakdown_ids": [],
      "source_component_summary": []
    }
  ]
}
```

## Required Objects

`topic_plan` fields:
- `title`, `target_audience`, `content_angle`, `trend_source`, `template`, `persona`, `hook_candidates`, `cta_candidates`, `recommended_platform`, `moras_relevance_score`, `risk_score`, `localized`.

`script` fields:
- `script_title`, `target_audience`, `persona`, `template`, `core_pain`, `emotional_angle`, `hook`, `voiceover`, `visual`, `overlay`, `sound_effect`, `proof_insert`, `cta`, `compliance_note`, `version`, `localized`.

`storyboard[]` fields:
- `shot_id`, `timestamp`, `duration`, `camera`, `character_action`, `facial_expression`, `background`, `props`, `voiceover`, `overlay`, `sound`, `bgm`, `sound_effects`, `subtitle_logic`, `visual_elements`, `visual_element_logic`, `transition`, `purpose`, `localized`.

`creator_persona` fields:
- `persona_id`, `display_name`, `role`, `demographic`, `creator_background`, `personality`, `trust_stance`, `speech_style`, `hobbies_interests`, `appearance`, `face_hair_makeup`, `wardrobe`, `styling_details`, `distinctive_marks_or_tattoos`, `props`, `consistency_rules`, `veo_identity_string`, `reference_image_prompt`, `digital_human_prompt_assets`, `localized`.

`digital_human_prompt_assets` fields:
- `visual_reference_prompt`, `avatar_motion_prompt`, `voice_style_prompt`, `script_delivery_rules`, `sample_requirement`, `synthetic_disclosure_note`, `keep_consistent`, `avoid`.

`video_prompt` fields:
- `prompt_title`, `aspect_ratio`, `target_model`, `veo_model_id`, `veo_generation_mode`, `veo_base_duration_sec`, `character_lock`, `scene_lock`, `generation_prompt`, `overlay_exclusion_note`, `consistency_notes`, `target_duration_sec`, `veo_generation_duration_sec`, `segments`, `localized`.

`video_prompt.segments[]` fields:
- `segment_index`, `timeline_start_sec`, `timeline_end_sec`, `duration_sec`, `time_range`, `veo_prompt`, `requires_extension`, `localized`.

`production_asset_plan[]` fields:
- `plan_id`, `time_range`, `shot_ids`, `narrative_phase`, `asset_type`, `moras_asset_category`, `layer`, `usage_reason`, `editor_note`, `localized`.

`risk_check` fields:
- `risk_level`, `forbidden_claims_checked`, `compliance_notes`, `allowed_for_video_factory`.

## Field Requirements

- Generate exactly the requested `script_count` unless input assets are insufficient.
- Keep canonical fields in natural English unless the input explicitly requests Chinese copy.
- Include `localized.zh` translations for every human-readable field in `topic_plan`, `script`, every `storyboard[]` row, `creator_persona`, `video_prompt`, every `video_prompt.segments[]` row, and every `production_asset_plan[]` row.
- Use nested `localized.zh` objects only. Do not output flat `_zh` fields such as `hobbies_interests_zh` or `props_zh`.
- Do not translate enum or machine identifiers such as `asset_type`, `moras_asset_category`, `layer`, `aspect_ratio`, `plan_id`, `shot_id`, or numeric timeline fields.
- `script.hook` is the publishable selected spoken Hook and must not include its bracketed candidate label.
- `script.voiceover` is publishable spoken English, not analysis notes.
- `script.overlay` and `storyboard[].overlay` are short caption highlights, not full subtitle transcripts.
- `production_asset_plan` must contain at least one entry and cover the important edit decisions without requiring real file IDs yet.
- `risk_check.allowed_for_video_factory` must be false if the draft contains unresolved risk.

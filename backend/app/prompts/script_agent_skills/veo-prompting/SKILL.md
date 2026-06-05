---
name: veo-prompting
description: Veo 3.1 source-footage handoff rules, persona identity lock, segment planning, and strict prompt exclusions.
---

# Veo Prompting

Use this skill for every Script Agent generation that includes `video_prompt`.

## Purpose

`video_prompt` describes AI-generated source footage for the gaps left after real Moras cutaways, proof screenshots, overlays, and screen recordings are placed in the edit.

It is not the final edited video plan. Final editing belongs to storyboard and production asset planning.

## Model Contract

MUST:
- Use `target_model: "Veo 3.1"`.
- Use `veo_model_id: "veo-3.1-generate-001"`.
- Use `aspect_ratio: "vertical 9:16"`.
- Use `veo_generation_mode: "text_to_video_9x16"`.
- Make each `video_prompt.segments[].veo_prompt` directly copyable into Veo 3.1.
- Use one complete prompt per segment. Do not rely on downstream concatenation.
- Plan real Moras UI / proof cutaways first, then cover only remaining AI-generated gaps with Veo segments.
- Allow non-contiguous Veo segments when real Moras cutaways sit between them.

Each `veo_prompt` should include:
- Same subject/persona and exact visual identity.
- Detailed action and expression.
- Scene / environment.
- Concrete cinematic camera direction: shot size, angle, lens feel, framing emphasis, and movement.
- Concrete lighting direction: time of day, key light quality, contrast, color temperature, and mood.
- Motion continuity.
- Audio or ambience direction.
- Persona Agent voice/delivery direction.
- A clear instruction that this is one continuous moment, not a montage.

## Persona Identity Lock

MUST:
- Copy `creator_persona.veo_identity_string` into `video_prompt.character_lock`.
- Include the selected persona's `display_name` and exact identity anchor in every segment prompt.
- Reflect `digital_human_prompt_assets.visual_reference_prompt`, `avatar_motion_prompt`, `voice_style_prompt`, and `script_delivery_rules` as production prompt direction.

MUST NOT:
- Substitute a generic role label such as `same young creator`, `host`, or `TikTok creator`.
- Change the persona demographic, wardrobe, props, face/hair/makeup, or delivery style between segments.
- Claim real video/audio sample ingestion, voice matching, voice clone, or sample extraction.

## Strict Exclusions

Veo prompts MUST NOT ask the model to generate:
- Readable UI.
- Screen recordings.
- Screenshots.
- Overlays.
- Subtitles or captions.
- Typography.
- CTA cards.
- App logos or watermarks.
- UI labels.
- Quoted spoken lines.

Put overlay text only in `script.overlay` or `storyboard[].overlay`.
Put real Moras UI assets only in `production_asset_plan`.

Do not use quotation marks inside `veo_prompt`; they can be rendered as visible text.

Keep `generation_prompt` as a high-level summary of AI-generated live-action / B-roll coverage, not the full edited video.

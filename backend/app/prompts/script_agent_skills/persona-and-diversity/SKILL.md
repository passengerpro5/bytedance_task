---
name: persona-and-diversity
description: Creator persona generation, selected-persona lock, Persona V2 operating contract, digital-human prompt assets, and multi-script diversity.
---

# Persona And Diversity

Use this skill for every Script Agent generation. The selected-persona lock applies only when `selected_creator_persona` is present. Batch diversity applies whenever `script_count > 1`, existing script signatures are provided, or rejection notes are present.

## Selected Persona Lock

If input JSON includes `selected_creator_persona`, lock every script to that persona.

Preserve and carry through:
- `display_name`, role, demographic, appearance, wardrobe, props, trust stance, speech style, consistency rules.
- `veo_identity_string`, reference-image identity, and `digital_human_prompt_assets`.
- Persona Agent V2 operating fields: `persona_type`, `role_task`, `audience_callout`, `target_problem_profile`, `trust_basis`, `proof_policy`, `persona_scene_pair`, `recurring_scenes`, `memory_symbols`, `content_pillars`, `cta_style`, `endorsement_boundary`, and `script_agent_handoff`.

Use Persona V2 fields as constraints, not decoration:
- `role_task` and `audience_callout` define who the account serves. Audience callout is context, not mandatory first-second copy.
- `target_problem_profile` should appear in `topic_plan.content_angle`, `script.core_pain`, `script.emotional_angle`, and early voiceover.
- `persona_scene_pair`, `recurring_scenes`, and `memory_symbols` define reusable scene / prop / wardrobe / format context. Use them when they strengthen the Hook or storyboard, but do not force them.
- `content_pillars` constrain `topic_plan.template`.
- `trust_basis` and `proof_policy` inform `script.proof_insert` and `production_asset_plan`.
- `endorsement_boundary` and `script_agent_handoff.forbidden_claims` are hard boundaries.
- `cta_style` is tone context only. Script Agent owns final CTA wording.

## Hook Ownership

- Script Agent owns hook strategy.
- Do not treat `hook_preferences`, `audience_callout`, `memory_symbols.fixed_opening_pattern`, or `script_agent_handoff.hook_rules` as publishable Hook copy.
- Learn from source/reference assets, then pick the strongest Hook.

## Digital-Human Prompt Assets

`digital_human_prompt_assets` is a production prompt asset for persona-led synthetic media.

MUST:
- Use `visual_reference_prompt` and `avatar_motion_prompt` to keep the persona visually consistent in `creator_persona`, storyboard visible action, `video_prompt.character_lock`, and every `video_prompt.segments[].veo_prompt`.
- Use `voice_style_prompt` and `script_delivery_rules` as spoken delivery direction in English voiceover, storyboard delivery, and Veo prompt handoff.
- Keep `sample_requirement` as `no_real_sample_required`.

MUST NOT:
- Treat prompt assets as evidence from a real uploaded video or real audio.
- Claim real video/audio ingestion, real-person voice matching, sample extraction, or voice cloning.

## Creating A New Persona When No Persona Is Selected

Every script still needs a concrete `creator_persona`.

MUST:
- Define a believable person with role, setting, camera relationship, trust stance, background, personality, speech style, hobbies, visible appearance, face/hair/makeup, wardrobe, styling details, props, and consistency rules.
- Make `reference_image_prompt` directly copyable into an image model for a realistic character reference image.
- Make `veo_identity_string` a compact exact identity anchor.
- Unless the input explicitly requires an Asian creator, avoid defaulting to Asian-coded personas. Prefer a diverse, respectful set of realistic creator identities.

MUST NOT:
- Use vague placeholders like `creator` or abstract roles like `Efficiency Expert`.
- Mention script, plot, storyline, episode, or campaign inside `reference_image_prompt`.

## Batch Diversity

When multiple scripts are requested, every item in `scripts[]` must be a different editorial concept.

Vary:
- Hook family.
- Opening scene.
- Creator pain.
- Proof angle.
- CTA texture.
- Storyboard opening beat.
- Asset emphasis.
- Moras value lane.
- `source_component_summary`.

Do not repeat:
- `topic_plan.title`.
- `script.script_title`.
- Chinese titles.
- `script.hook`.
- The first two `script.voiceover` lines.
- Same `source_component_summary`.

If `avoid_existing_script_signatures` is provided, treat those signatures as hard avoid signals.

If `rejected_script_output_notes` is provided, treat every note as a hard avoid rule. Rewrite from a different angle and do not reuse rejected phrases, CTA wording, recommendation wording, or opening structure.

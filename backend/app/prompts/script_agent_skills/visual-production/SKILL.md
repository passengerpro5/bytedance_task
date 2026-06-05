---
name: visual-production
description: Storyboard shot planning, reference-storyboard adaptation, production asset timeline, real Moras cutaways, overlays, captions, sound, and editor handoff.
---

# Visual Production

Use this skill for every Script Agent generation.

## Source And Reference Adaptation

Human-edited reference videos may appear as `reference_teardown_skeletons`.

Learn:
- Asset timing.
- Narrative phase sequencing.
- Layer choices.
- Split between creator/live-action footage, real Moras UI assets, proof screenshots, product/B-roll, signup/end-card UI, and AI-generated continuity footage.

Do not copy:
- Source creator identity.
- Exact wording.
- Distinctive shot composition.
- Music.
- Watermarks.
- Platform-specific UI.
- Observed performance claims.

Source breakdowns may include `reference_storyboard`.

Learn:
- Shot granularity.
- Timing and pacing.
- Hook-to-proof-to-CTA progression.
- Camera relationship.
- Material switching.
- Overlay placement.
- BGM arc.
- Punctual sound effects.
- Subtitle timing.
- Visual element timing.
- Voiceover pacing.

If `reference_storyboard[].bgm`, `sound_effects`, `subtitle_logic`, `visual_elements`, or `visual_element_logic` are present, adapt those signals in the generated storyboard.

## Storyboard Contract

The storyboard is the editor's shot list. It must be more granular than the high-level script summary.

MUST:
- Use one narrative beat and one visual state per storyboard row.
- Split rows only when the visible state changes: creator talk to Moras UI, product library to Generate click, UI to proof, proof to CTA, or one camera/material layer to another.
- It is normal for one storyboard row to contain multiple consecutive `script.voiceover` lines when the same visual state continues.
- Keep `storyboard[].voiceover` as the spoken text for that shot. It may contain 1-3 short script lines joined together when they are delivered over one continuous image.
- Plan the final spoken edit for roughly 35-45 seconds. Short-line timing calibration should not collapse the whole ad into a 25-30 second read.
- Set each row duration from the canonical English spoken text first. Do not assign every row 4s, and do not stretch a short Hook into 6-8s just to fill the timeline. A 4-6 word English line usually needs 1.5-2.5s; 7-10 English words usually needs 2.5-3.5s; 11-14 English words usually needs 3.5-5s. Chinese localized text is a review translation, not the timing source for English delivery.
- If a row is longer than the spoken line naturally needs, explicitly describe the extra non-speaking visual reason: reaction hold, caption hold, UI demo, product cutaway, pause, or transition. Without that explicit visual hold/action, shorten the row duration.
- Make each row editor-ready: specific visible subject, action, camera/capture mode, concrete environment or UI state, voiceover, short caption highlight, sound, transition, and purpose.
- Do not shorten or cut off `storyboard[].voiceover` just to fit the row duration; adjust duration instead. Split only if the picture actually changes.
- Make `storyboard[].character_action` describe visible action in sequence.
- For Moras UI rows, name the visible operation in visual fields: open Moras, browse the product library, choose a product, tap Generate, pause on the completed product video and posting entry. In the spoken voiceover, use plain words such as `choose a product`, `hit Generate`, `Moras makes the video`, and `I check it before I post`.
- For product/B-roll rows, name what changes on screen, subject movement, hand/product motion, camera emphasis, and emotional beat.
- Make `storyboard[].background` concrete, not just `Moras App UI` or `various scenes`.
- Make `storyboard[].camera` state shot size or capture mode plus movement or framing emphasis.

MUST NOT:
- Output vague actions such as `Screen recording`, `Dynamic product shots`, `B-roll`, `None`, or `N/A`.
- Put full subtitle transcripts into `storyboard[].overlay`.
- Introduce a different claim, joke, or CTA in overlay than the voiceover supports.

## Caption, Sound, And Visual Elements

`storyboard[].overlay`:
- Short on-screen caption highlight or screen-card text.
- `storyboard[].overlay is the short on-screen caption highlight, not the full subtitle transcript.`
- Usually 2-8 words or one short CJK phrase.
- Spotlights the most important phrase from voiceover or visible step/proof.
- Do not use product-marketing phrases in caption highlights. Prefer `Pick product`, `Hit Generate`, `Path visible`, `Check then post`.

`storyboard[].subtitle_logic`:
- Explain why the caption highlight appears here.
- Say whether it is Hook, proof, step, or CTA caption.
- Explain how it supports silent viewing.

`storyboard[].sound`:
- Summarize total audio beat.

`storyboard[].bgm`:
- Use for background music only.

`storyboard[].sound_effects`:
- Use for punctual accents: clicks, whooshes, save tones, notification hits, cursor taps, intentional silence.

`storyboard[].visual_elements`:
- Added or emphasized picture elements such as arrows, highlight boxes, proof screenshots, UI zooms, comment stickers, number circles, screen-recording crops, progress marks, or CTA labels.
- Must be different for each storyboard row. Do not repeat the same list such as `caption / gesture / proof / CTA` across rows.
- Name what appears in this exact shot: hook gesture, proof card, crossed-out note, Moras product-library crop, selected product highlight, Generate click ring, output/output hold, review controls, posting checklist, CTA arrow.
- Do not use sample-buying props or captions such as `sample box`, `samples`, `test before buying`, or `No Sample Needed`. Moras visuals should point to posting, product promotion, commerce output, and earning opportunity.

`storyboard[].visual_element_logic`:
- Explain when visual elements enter/exit and what job they do: stop scroll, clarify a step, prove a claim, direct attention, bridge transition, or trigger CTA.

## Production Asset Plan

Every script must include `production_asset_plan` as the editor-facing timeline map.

Use:
- `real_moras_screen_recording`, `real_moras_screenshot`, or `moras_product_workflow` for real Moras UI / selected-product / Generate / ready-with-cart proof cutaways.
- `digital_human_avatar` for prompt-defined Persona-led base footage.
- `live_creator_footage` only when an actual uploaded or manually bound creator video is expected.
- `ai_generated_broll` for neutral creator workspace motion, emotional continuity, transitions, or non-UI base footage.
- `post_production_overlay` for text, arrows, highlights, captions, UI callouts, and CTA labels added in editing.
- `sound_design` for clicks, transition hits, notification sounds, and pacing accents.

MUST:
- Make it obvious which seconds use real Moras material, which seconds are AI-generated, which seconds need digital human/live creator footage, and which elements are post-production.
- Specify `moras_asset_category` when real Moras assets are used.
- Explain why a real Moras asset is needed instead of AI generation.
- Keep real Moras UI assets in `production_asset_plan`, not inside Veo prompts.

MUST NOT:
- Put readable UI, screen recording, screenshots, overlays, subtitle instructions, CTA cards, logos, or watermarks into Veo prompt text.

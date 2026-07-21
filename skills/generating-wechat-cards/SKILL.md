---
name: generating-wechat-cards
description: Use when turning Chinese articles or outlines into image-first WeChat posts, 微信公众号贴图, multi-card editorial graphics, or a consistent series of Chinese social cards.
---

# Generating WeChat Cards

## Core principle

Approve the information architecture, generate original illustration layers, compose Chinese text deterministically, and accept output only after independent review.

Keep every post in a user-selected Git project at `<git-project>/<post-slug>/`; never store a post project inside this skill. Treat `manifest.yaml` as the single source of truth for state, copy, prompts, paths, dependencies, invalidations, and counters. Keep the machine-readable visual contract in `visual-bible.yaml`.

## Load references only when needed

- Read [references/content-schema.md](references/content-schema.md) before creating or updating project YAML, recording reviews, or finalizing a post.
- Read [references/visual-system.md](references/visual-system.md) before planning pages, writing illustration prompts, creating visual anchors, or checking originality.
- Run each bundled CLI with `--help` if its interface is uncertain. Do not invent options.

## Maintain the workflow state

Use this state machine exactly:

```text
draft → script_pending → script_approved → anchor_pending → anchor_approved
→ generating → reviewing → revising → passed | limit_reached
                         ↑           |
                         └───────────┘
```

| State | Permitted action and exit condition |
| --- | --- |
| `draft` | Save `source.md`; extract the thesis, sections, and user overrides. Move to `script_pending`. |
| `script_pending` | Draft one central claim per page in `manifest.yaml`; present Gate 1. Stay here while editing. |
| `script_approved` | Enter only after explicit user approval of thesis, page order, copy, page types, and metaphors. Create `visual-bible.yaml`; move to `anchor_pending`. |
| `anchor_pending` | Generate `style-anchor.png` and optional `character-sheet.png`; present Gate 2. Stay here while revising anchors. |
| `anchor_approved` | Enter only after explicit user approval of the required anchors. Prepare validated page dispatches; move to `generating`. |
| `generating` | Generate only assigned text-free illustration layers, update paths and counters, then render. Move to `reviewing`. |
| `reviewing` | Dispatch an independent reviewer and save a new immutable `reviews/round-NN.yaml`. Move to `passed`, `revising`, or `limit_reached`. |
| `revising` | Resolve issues in dependency order, invalidate affected artifacts, then loop through `generating` and `reviewing`. Layout-only work may render directly but must still return to `reviewing`. |
| `passed` | Record `reviews/final.yaml`, then present Gate 3. Deliver only after explicit user approval; reviewer approval does not replace it. |
| `limit_reached` | Stop automatic image generation, select the best current version of every affected card, record unresolved limitations in `reviews/final.yaml`, and ask for a user decision. Never claim pass. |

Explicit approval means a clear user decision at that gate; silence, prior preferences, or reviewer verdicts do not count.

## Plan the post

1. Save the original article or outline, user overrides, and reference links in `source.md`.
2. Create one cover and normally three to eight section cards; add a summary only when it advances the conclusion. Use `cover`, `standard`, `comparison`, `list`, or `summary` page types.
3. Give every page one central claim. Split dense content instead of shrinking type. Preserve user-designated sentences.
4. Define the title, kicker or subtitle, body, emphasis, visual metaphor, text-free illustration prompt, dependencies, output paths, and retry counters in `manifest.yaml`.
5. Present Gate 1 with the thesis, page count and order, each page's claim and copy, page type, and metaphor. Record approval before creating anchors.
6. Create the exact visual contract and anchors. Omit `character-sheet.png` when characters are disabled. Present Gate 2 before batch generation.

## Validate and render

Run validation before every image-generation phase and before rendering:

```bash
python scripts/validate_manifest.py <post-dir>
```

The validator requires every manifest-referenced illustration to exist. Before the initial illustration pass, treat missing-illustration messages as the expected preflight boundary, fix every other error, generate directly to the declared paths, and rerun until validation exits successfully. Never render on a failed validation.

After all requested illustration paths exist, render every page or one page with the public CLI:

```bash
python scripts/render_cards.py <post-dir>
python scripts/render_cards.py <post-dir> <page-id>
```

Do not generate Chinese layout text inside illustrations. Let the renderer add titles, body, labels, page numbers, and signature with `Maple Mono NF CN`. Do not silently substitute another font or bypass glyph/overflow errors.

## Dispatch illustration generation

Dispatch a generation sub-agent with this contract for each assigned page:

```text
Role: illustration generator; do not review or approve your own work.
Inputs: page ID and approved brief from manifest.yaml; visual-bible.yaml;
style-anchor.png; character-sheet.png only when enabled; declared output path.
For a revision also include the current illustration and only the routed review actions.
Task: create one original, text-free illustration layer that expresses the approved
metaphor and follows the supplied anchors. Change only assigned image concerns.
Output: write the image to the declared versioned path; report that path and no verdict.
Constraints: do not alter source.md, manifest copy, review files, cards, or counters;
do not copy a reference mascot, signature, composition, or individual illustration.
```

Pass the anchors on every dispatch. Initial generation counts as one whole-set generation round and one generation for each generated page.

## Dispatch independent review

Use a review sub-agent that is independent from every generator whose work it checks. Dispatch after every image-generation round and after affected cards are rerendered:

```text
Role: independent reviewer; inspect but do not modify any project artifact.
Inputs: source.md; the user-approved card script and manifest.yaml;
visual-bible.yaml; style-anchor.png; optional character-sheet.png; all current cards;
and the prior immutable review from round 2 onward.
Task: check page accuracy, metaphor, hierarchy, overflow, contrast, noise, cover strength;
then check series consistency, progression, repetition, density, cohesion, and originality.
Output: one round review matching references/content-schema.md. Give every atomic issue
id, severity, exactly one owner, issue, action, optional depends_on, and resolution when
rechecking. Use only resolved, partially_resolved, or unresolved for resolution.
Constraints: do not edit source, manifest, visual bible, illustrations, cards, or anchors;
do not generate replacements; do not approve with open critical or major issues.
```

Append each result as a new `reviews/round-NN.yaml`; never overwrite a round.

## Route revision work

Resolve cross-page and `system` issues before page-local issues. Within a page, obey `depends_on`, then use the default owner order `content` → `image` → `layout`:

| Owner | Revision action |
| --- | --- |
| `content` | Main agent revises manifest copy first, then invalidates dependent images/cards. |
| `image` | Generation sub-agent receives the original brief, current image, anchors, and routed action; render the replacement afterward. |
| `layout` | Preserve the illustration and rerender only. Layout-only rerenders consume no image-generation count. |
| `system` | Main agent updates `visual-bible.yaml`, invalidates every affected page, and returns to Gate 2 when the visual system changes. |

Use this revision dispatch contract:

```text
Inputs: issue IDs, owners, dependencies, exact actions, current artifacts, and counters.
Process: resolve prerequisites first; touch only owner-authorized fields/artifacts; record
every invalidated page and reason in manifest.yaml; rerun deterministic validation/rendering.
Output: changed paths plus an issue-by-issue handoff for a fresh independent review.
Never close an issue yourself or broaden the change beyond its routed action.
```

Propagate content changes: wording-only changes invalidate layout; changed visual objects or relationships invalidate illustration and layout; a changed thesis returns to Gate 1 and invalidates the cover plus related pages; a changed visual system returns to Gate 2 and invalidates all affected pages.

## Enforce review and stopping limits

- Allow at most three whole-set image-generation rounds and three image generations for any page. Initial generation counts; layout-only rerenders do not.
- Require independent review after each image-generation round.
- Stop retrying an issue after it remains unresolved for two consecutive review rounds, even if another counter remains.
- Permit `passed` only when no `critical` or `major` issue remains. A reviewer may pass with recorded `minor` suggestions that do not harm reading or consistency.
- When a counter or consecutive-unresolved limit is reached, choose and retain the best available version, list its unresolved limitation, set `limit_reached`, and stop automatic generation.
- Require Gate 3 explicit user approval for final delivery in both `passed` and `limit_reached` outcomes.

## Common mistakes

| Mistake | Correction |
| --- | --- |
| Treating scattered notes as project state | Put state, copy, prompts, paths, dependencies, invalidations, and counters in `manifest.yaml` only. |
| Keeping the visual rules in prose | Maintain exact machine-readable tokens and exclusions in `visual-bible.yaml`. |
| Using `area` or multiple owners | Give each atomic issue exactly one `owner`: `content`, `image`, `layout`, or `system`. |
| Omitting correction order | Add `depends_on` whenever one action changes another action's input. |
| Stopping without a usable handoff | Retain the best card version and state its unresolved limitation. |
| Letting a generator approve its work | Dispatch a separate reviewer after every generation round. |

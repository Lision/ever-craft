---
name: generating-wechat-cards
description: Use when turning Chinese articles or outlines into image-first WeChat posts, 微信公众号贴图, multi-card editorial graphics, or a consistent series of Chinese social cards.
---

# Generating WeChat Cards

## Core principle

Approve copy and layout, reserve at least half of each usable card for illustration, generate original text-free illustration layers for the calculated regions, compose Chinese text deterministically, and accept output only after independent review.

Prevent repeated metaphors during planning; leave duplication judgments between finished illustrations to the user. Keep automatic review focused on reading quality, cover appeal, and the existing accuracy and visual checks.

Keep every post in a user-selected Git project at `<git-project>/<post-slug>/`; never store a post project inside this skill. Treat `manifest.yaml` as the single source of truth for state, copy, prompts, paths, dependencies, invalidations, and counters. Keep the machine-readable visual contract in `visual-bible.yaml`.

`<skill-dir>` means the directory containing this `SKILL.md`. Use it in every bundled-script command because `<post-dir>` normally lives elsewhere.

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
| `script_pending` | Draft one central claim, copy, and metaphor per page in `manifest.yaml`. Create the fixed `visual-bible.yaml` and calculate layouts before presenting Gate 1. Stay here while editing or correcting preflight failures. |
| `script_approved` | Enter only after explicit user approval of thesis, page order, copy, page types, calculated layouts, and metaphors. Move to `anchor_pending` only with current layouts and at least 50% illustration share on every page. Changed copy requires returning to `script_pending`, recalculating, and repeating Gate 1. |
| `anchor_pending` | Generate `style-anchor.png` and optional `character-sheet.png` from the approved copy and calculated illustration boxes; present Gate 2. Stay here while revising anchors. |
| `anchor_approved` | Enter only after explicit user approval of the required anchors. Prepare validated page dispatches; move to `generating`. |
| `generating` | Generate only assigned text-free illustration layers, update paths and counters, then render. Move to `reviewing`. |
| `reviewing` | Dispatch an independent reviewer and save a new immutable `reviews/round-NN.yaml`. Move to `passed`, `revising`, or `limit_reached`. |
| `revising` | Resolve issues in dependency order, invalidate affected artifacts, then loop through `generating` and `reviewing`. Layout-only work may render directly but must still return to `reviewing`. |
| `passed` | Write the pending Gate 3 status to `manifest.yaml`, then present Gate 3. Revision feedback returns to `revising` within the existing limits, with delivery still pending. Only a final user decision produces the immutable `reviews/final.yaml` snapshot, derived from the updated manifest. Reviewer approval does not replace user approval. |
| `limit_reached` | Stop automatic image generation; record the best current versions, unresolved limitations, and pending Gate 3 decision in `manifest.yaml`. After the user decision, update the manifest first and derive immutable `reviews/final.yaml`. Never claim pass. |

Explicit approval means a clear user decision at that gate; silence, prior preferences, or reviewer verdicts do not count.

## Plan the post

1. Save the original article or outline, user overrides, and reference links in `source.md`.
2. Create one cover and normally three to eight section cards; add a summary only when it advances the conclusion. Use `cover`, `standard`, `comparison`, `list`, or `summary` page types.
3. Give every page one central claim. Draft natural, unambiguous Chinese copy from the original input; use the copy checks below before approval. Compare different cover copy–illustration combinations using the cover criteria in `references/visual-system.md`, then select one for Gate 1. Split dense content instead of shrinking type. Preserve user-designated sentences.
4. Define the title, kicker, non-empty subtitle, body, emphasis list, `must_keep` and `compressible` metadata, visual metaphor, text-free illustration prompt, dependencies, canonical output paths, and retry counters in `manifest.yaml`. Every `must_keep` item must be a verbatim substring of one displayed copy field; `compressible` is non-displayed editing metadata.
5. Read the complete metaphor list in publication order, including cover and summary. Avoid repeating the core scene, action relationship, or metaphor mechanism across any pages. Keep this planning check textual; use the differentiation criteria in `references/visual-system.md`.
6. While still in `script_pending`, create `visual-bible.yaml` with the fixed visual contract, then calculate and atomically record every page's actual text flow, divider, illustration box, and illustration share:

```bash
python3 <skill-dir>/scripts/calculate_layout.py --write <post-dir>
```

7. Treat the usable content area as the full-width safe column between the top margin and the illustration/footer boundary. Flow draft copy downward at fixed type scales, reserve the footer and all configured gaps, and assign the remaining space to the illustration. Require every illustration box to occupy at least 50% of that usable area. If any page fails, stay in `script_pending`, shorten or split the copy, and rerun the calculation before presenting Gate 1. Do not create anchors yet.
8. Present Gate 1 with the thesis, page count and order, each page's claim and copy, page type, calculated layout, and metaphor; explain the selected cover's reading hook and how its illustration adds meaning. Recalculate any copy edited during approval before asking the user to approve the revised script. Do not run pre-generation validation at this drafting stage: it requires Gate 2 and anchors.
9. After explicit Gate 1 approval, generate the exact visual anchors from the approved copy plus all calculated illustration boxes. Use the most constrained box to prove the style still works. Omit `character-sheet.png` when characters are disabled. Present Gate 2 before batch generation.

## Check copy and cover quality

- Before Gate 1, read every displayed field in page order. Require clear subjects and referents, explicit logical relationships, consistent terms, and idiomatic Chinese that reads smoothly. Rewrite ambiguous, compressed, or awkward sentences without changing the source claim or designated wording.
- After rendering, inspect the actual cards at normal reading size for legibility, disruptive line breaks, hierarchy, contrast, and overflow. A successful schema or layout check does not prove semantic or visual readability.
- Require the cover to give readers a concrete reason to continue and make its copy and illustration reinforce each other. Check the criteria and examples in `references/visual-system.md`; a topic summary with a question mark is insufficient.
- Classify wording that obstructs understanding, an unsupported cover promise, or a cover with no reading hook or meaningful copy–image connection as at least `major`. Keep harmless stylistic preferences `minor`; do not generate another image round for minor suggestions alone. Route each issue by its actual cause using the owner table below.

## Validate and render

Require a current calculated layout for every page and a zero exit code from pre-generation validation before every page-illustration generation phase:

```bash
python3 <skill-dir>/scripts/validate_manifest.py --phase pre-generation <post-dir>
```

This phase validates both approval records and timestamps, current layout fingerprints, the 50% illustration minimum, required anchors, phase states, retry limits, consecutive unresolved issues, canonical non-symlinked output paths, containment, source, and visual-bible files. With no target every page is a generation target. For a local revision, repeat `--page-id`: target pages must be `generating` or `revising`, and only their illustrations may be missing. Non-target pages may retain any complete-phase state (`generating`, `reviewing`, `revising`, `passed`, `limit_reached`), but their illustrations and all other deterministic constraints must remain valid:

```bash
python3 <skill-dir>/scripts/validate_manifest.py --phase pre-generation \
  --page-id p03 --page-id p05 <post-dir>
```

Do not dispatch generation on any validation error, and never let validation modify `manifest.yaml`.

After all requested illustration paths exist, require a zero exit code from complete validation, then render every page or one page:

```bash
python3 <skill-dir>/scripts/validate_manifest.py --phase complete <post-dir>
python3 <skill-dir>/scripts/render_cards.py <post-dir>
python3 <skill-dir>/scripts/render_cards.py <post-dir> <page-id>
```

Do not generate Chinese layout text inside illustrations. Let the renderer reproduce the calculated text flow and place each illustration inside its recorded box, preserving aspect ratio. Let it add kicker, title, subtitle, body, emphasis, page numbers, and signature with `Maple Mono NF CN`; `must_keep` and `compressible` remain metadata. Do not silently substitute another font, shrink copy, use a stale layout, or bypass glyph/space errors. The eight palette values are fixed per skill and cannot be overridden by a post or by Gate 2.

## Dispatch illustration generation

Dispatch a generation sub-agent with this contract for each assigned page:

```text
Role: illustration generator; do not review or approve your own work.
Inputs: page ID, approved copy and brief, calculated illustration box dimensions and
aspect ratio from manifest.yaml; visual-bible.yaml; style-anchor.png;
character-sheet.png only when enabled; declared output path; a compact list of all
page IDs, claims, and metaphors from the manifest, without the full set of card images.
For a revision also include the current illustration and only the routed review actions.
Task: create one original, text-free illustration layer composed for the exact
illustration box, expressing the current authorized metaphor and following the supplied anchors.
Change only assigned image concerns.
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
and the prior immutable review from round 2 onward. Include any user-reported duplicate
page pair and its routed issue ID when checking that specific repair.
Task: apply the copy and cover quality checks above; check page accuracy, metaphor,
hierarchy, overflow, contrast, and noise; then check series consistency, progression,
redundant copy, density, cohesion, and originality against external references.
Leave duplication detection between finished illustrations to the user. Verify only
user-reported pairs after repair; do not expand them into a whole-set duplication scan.
Output: one round review matching references/content-schema.md. Give every atomic issue
id, severity, exactly one owner, issue, action, optional depends_on, and resolution when
rechecking. Use only resolved, partially_resolved, or unresolved for resolution.
Constraints: do not edit source, manifest, visual bible, illustrations, cards, or anchors;
do not generate replacements; do not approve with open critical or major issues.
```

Append each result as a new `reviews/round-NN.yaml`; never overwrite a round. Reuse this review for the required quality checks; do not add a deduplication agent, similarity scoring, or exhaustive image-pair comparison. A reviewer pass covers these automatic checks, not a claim that the illustrations are all distinct.

## Route revision work

Resolve cross-page and `system` issues before page-local issues. Within a page, obey `depends_on`, then use the default owner order `content` → `image` → `layout`:

| Owner | Revision action |
| --- | --- |
| `content` | Main agent revises manifest copy in `script_pending`, recalculates layout before repeating Gate 1, and invalidates every dependent anchor/image/card whose input changed. Route copy shortening, merging text blocks, and wording or explicit line-break changes here. |
| `image` | Generation sub-agent receives the original brief, current image, anchors, and routed action; render the replacement afterward. |
| `layout` | Recalculate stale geometry when necessary and rerender a stale, missing, or incorrectly rendered card using current authorized inputs. Preserve the illustration when its box remains valid. The same valid inputs reproduce the same layout: route crowding caused by copy to `content` and composition problems to `image`; never propose arbitrary changes to fixed spacing, type, or palette. Rerenders consume no image-generation count. |
| `system` | Main agent updates `visual-bible.yaml`, invalidates every affected page, and returns to Gate 2 when the visual system changes. |

Use this revision dispatch contract:

```text
Inputs: issue IDs, owners, dependencies, exact actions, current artifacts, and counters.
Process: resolve prerequisites first; touch only owner-authorized fields/artifacts; record
every invalidated page and reason in manifest.yaml; rerun deterministic validation/rendering.
Output: changed paths plus an issue-by-issue handoff for a fresh independent review.
Never close an issue yourself or broaden the change beyond its routed action.
```

Propagate content changes: every wording change invalidates the stored layout fingerprint and returns to `script_pending`. Recalculate before repeating Gate 1 or generating images. If the illustration box or anchor input changes, return to Gate 2 and invalidate the affected anchor/image/card. Changed visual objects or relationships invalidate illustration and card; invalidate calculated layout only when a geometry input changes. A changed thesis invalidates the cover plus related pages; a changed visual system returns to Gate 2 and invalidates all affected pages.

## Act on user-reported duplicate illustrations

Use the user's identified page pair as the repair request. Follow publication order in the manifest: preserve the earlier page and change the later page's core scene or metaphor mechanism, rather than only its pose, viewpoint, or prop shape.

The main agent updates the later page's `visual_metaphor` and `illustration_prompt`, records the user feedback, page pair, and routed issue ID in the manifest invalidation record, and assigns a new versioned illustration path. When the claim, approved copy, calculated box, and visual contract remain unchanged, reuse the current layout and anchors and do not seek another Gate 1 or Gate 2 approval. This is a narrow authorization to change the reported duplicate's expression. Other changes follow the normal gates.

Invalidate only the affected illustration/card, preserve counters, and run targeted pre-generation validation before dispatch. Give the generator the reported earlier image as a concrete expression to avoid, the later image to replace, and the routed action. After rendering, the independent reviewer checks the specific pair and the usual quality criteria, recording the issue under the later page with the earlier page identified in `issue` and `action`.

If feedback arrives at Gate 3, keep delivery pending, clear the provisional `finalization`, and move to `revising`; do not write `reviews/final.yaml` for a request to edit. If a stopping limit has already been reached, keep `limit_reached` and use its existing user-decision flow rather than resetting counters or automatically retrying.

## Enforce review and stopping limits

- Allow at most three whole-set image-generation rounds and three image generations for any page. Initial generation counts; layout-only rerenders do not.
- Require independent review after each image-generation round.
- Stop retrying an issue after it remains unresolved for two consecutive review rounds, even if another counter remains.
- Permit `passed` only when no `critical` or `major` issue remains. A reviewer may pass with recorded `minor` suggestions that do not harm reading or consistency.
- When a counter or consecutive-unresolved limit is reached, choose and retain the best available version, list its unresolved limitation, set `limit_reached`, and stop automatic generation.
- Require a Gate 3 explicit user decision for both `passed` and `limit_reached`. Record the decision and status in `manifest.yaml` first; then write `reviews/final.yaml` once as a derived immutable snapshot.

## Common mistakes

| Mistake | Correction |
| --- | --- |
| Treating scattered notes as project state | Put state, copy, prompts, paths, dependencies, invalidations, and counters in `manifest.yaml` only. |
| Keeping the visual rules in prose | Maintain exact machine-readable tokens and exclusions in `visual-bible.yaml`. |
| Generating art against a guessed region | Run `calculate_layout.py --write`, require at least 50%, and pass the recorded box to anchors and page generation. |
| Letting copy consume the illustration | Shorten or split the page and recalculate before presenting Gate 1; never shrink type or lower the 50% threshold. |
| Using `area` or multiple owners | Give each atomic issue exactly one `owner`: `content`, `image`, `layout`, or `system`. |
| Omitting correction order | Add `depends_on` whenever one action changes another action's input. |
| Stopping without a usable handoff | Retain the best card version and state its unresolved limitation. |
| Letting a generator approve its work | Dispatch a separate reviewer after every generation round. |

# Visual system

Read this reference before planning pages, writing prompts, creating anchors, or reviewing originality. Keep these decisions in the post's `visual-bible.yaml`.

## Fixed foundation

Produce 1080×1440 RGB PNG cards on a stable grid with generous whitespace, thin dividers, strong hierarchy, and low visual noise.

Use this exact fixed palette:

| Token | Hex | Use |
| --- | --- | --- |
| `background` | `#FAFAF8` | Warm-white page background |
| `surface` | `#F0F0EE` | Information blocks and pale sections |
| `ink` | `#0A0A08` | Titles, body text, and principal line art |
| `solid` | `#000000` | Character solids and maximum contrast |
| `accent` | `#012FA7` | Blue headings, labels, and emphasis blocks |
| `annotation` | `#854953` | Hand-drawn underline, arrow, or sparse annotation |
| `muted` | `#747472` | Headers, English kickers, and secondary information |
| `divider` | `#D1D1CF` | Dividers and weak boundaries |

Do not override colors per post, including after a Gate 2 approval. Gate 2 approves the anchors made with these exact values; it is not a theme-selection gate. To introduce another theme, first update the skill's fixed palette, bundled theme, validator, documentation, and regression fixtures together, then revalidate the skill before generating any post.

Use `Maple Mono NF CN` for every composed text element. Provide regular and bold font paths when discovery is unavailable. Fail explicitly if the family, required weight, Chinese glyph, or punctuation glyph is missing. Never fall back silently, bundle a font in the public skill, rasterize model-generated copy, shrink type to hide overflow, or bypass the renderer's checks.

## Choose one of four layouts

1. **Cover (`cover`)** — Use the largest title, least copy, strongest original metaphor, and broadest whitespace. Establish the whole article's thesis.
2. **Standard chapter (`standard`)** — Explain one chapter claim with one illustration region and a small number of supporting text blocks.
3. **Comparison/list (`comparison` or `list`)** — Use only for genuinely parallel, classified, sequential, or contrasted material. Give peer items equal visual rank; do not force prose into boxes.
4. **Summary (`summary`)** — Recombine the thesis into a conclusion, action, or interaction prompt. Do not repeat the entire article.

Split a page when its single claim cannot leave enough illustration space at the approved type scale. Keep title, body, illustration, divider, footer, signature, and safe margins inside the deterministic grid.

Render every approved display field at its bundled fixed scale: `kicker` 24, cover `title` 90 or other `title` 72, `subtitle` 30, `body` 34, and `emphasis` 28. Flow the fields downward using actual Maple Mono NF CN metrics and the bundled gaps; do not assign fixed-height copy boxes. Include every display field in glyph and layout preflight. Keep `must_keep` and `compressible` as validated workflow metadata; do not draw them a second time. Never shrink a field to make it fit.

## Calculate the illustration region

Use the fixed 1080×1440 canvas and the bundled layout contract:

- keep 80 px left/right margins and 72 px top/bottom margins;
- treat the kicker as the page header and reserve the measured footer for page number and signature;
- place 24 px between non-empty copy blocks, 24 px before the divider, 20 px after it, and 40 px between illustration and footer;
- start the illustration after the measured copy and divider, then extend it to the footer safety gap.

Calculate `illustration_share` as:

```text
illustration box area
────────────────────────────────────────────────────────────
safe-column area from top margin to illustration bottom
```

The illustration box and safe column have the same width, so the ratio is also their height ratio. Require `illustration_share >= 0.5` for every page. If a page falls below 50%, return to Gate 1 and shorten or split its copy; never reduce type, margins, footer clearance, or the threshold.

Run `scripts/calculate_layout.py --write <post-dir>` after preliminary copy/layout approval. Record its versioned fingerprint, copy bottom, divider, illustration box, and share in each manifest page. Any change to displayed copy, page type, font family, footer, canvas, or layout rules makes the fingerprint stale and requires recalculation.

## Create original line art

Build each prompt from this recipe:

```text
Original minimal editorial line-art illustration for a Chinese social card;
[one approved subject] expresses [one approved relationship or change] through
[new spatial metaphor]; irregular hand-drawn ink contours, sparse flat shapes,
asymmetric balanced composition, generous warm-white negative space, restrained use
of the supplied exact palette, consistent line weight and complexity with the supplied
style anchor; no typography, letters, numbers, labels, signature, logo, or watermark.
```

Specify only the page's subject, relation, viewpoint, focal point, and needed anchor continuity. Ask for a transparent or clean background only when composition requires it. Keep lighting flat and detail sparse so deterministic typography remains dominant.

Include the calculated illustration box width, height, and aspect ratio in every anchor and page-generation brief. Compose the focal subject for that box rather than relying on later cropping. The renderer may only scale the layer proportionally and center it inside the box.

Exclude these concepts:

- photorealism, stock photography, 3D rendering, glossy gradients, cinematic lighting, complex shadows, texture noise, and decorative clutter;
- readable text, pseudo-Chinese glyphs, letters, numbers, labels, logos, watermarks, signatures, and account branding;
- copied mascots, recognizable proprietary characters, traced poses, exact reference compositions, or near-duplicates of individual reference illustrations;
- extra focal subjects, unexplained symbols, ornamental frames, and any element that competes with the page's one central claim.

## Use an optional original character

Default to one newly designed abstract character only when it improves narrative continuity. Define its unique silhouette, head/body ratio, eye form, limb construction, fill/outline treatment, line irregularity, and allowed viewpoints in `visual-bible.yaml`. Vary gesture and role by page while preserving those invariants.

Use the character as observer, actor, or bearer of a problem; do not let it become decorative branding. When the user disables characters, omit `character-sheet.png` and use objects, space, paths, barriers, scale, or abstract relationships instead. Never infer a character from a reference mascot.

## Build and pass anchors

After Gate 1 and successful layout calculation, create `style-anchor.png` from the approved copy themes and calculated illustration boxes. Use the most constrained box to demonstrate line quality, exact palette, whitespace, density, contrast, and texture without copying any eventual page composition. When characters are enabled, create `character-sheet.png` with neutral front, side, and action views that lock the approved character invariants.

Pass `visual-bible.yaml`, `style-anchor.png`, and the optional `character-sheet.png` to every generation. For revisions, also pass the current illustration and only the routed review actions. Do not describe anchors from memory or replace them with a reference URL.

## Check originality

Use external references only to infer high-level qualities such as editorial restraint, whitespace, hierarchy, and simple line work. Before approval, compare the entire set and each card against the references:

- Reject matching character silhouettes, facial systems, distinctive props, poses, signatures, brand marks, or page-specific object combinations.
- Reject substantially matching subject placement, camera angle, visual path, or negative-space contour on a reference page.
- Require the new metaphor to follow the article's claim rather than the reference's scene.
- Record originality as an independent-review concern; route a local copied element to `image` and a repeated system-level resemblance to `system`.

Similarity in broad style alone is not a defect; similarity in protectable or page-specific expression is.

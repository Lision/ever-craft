# Content and review schemas

Read this reference before creating or changing project files, writing a review, or finalizing delivery. Store every post in a user-selected Git project, never inside the skill.

## Project invariants

Use `manifest.yaml` as the single source of truth for current state, approved copy, calculated page geometry, prompts, artifact paths, dependencies, invalidations, counters, and user delivery decisions. Do not create a second storyboard, task-state file, or delivery manifest.

Keep each `reviews/round-NN.yaml` immutable after writing it. Corrections belong in a new round file. Write `reviews/final.yaml` once as an immutable snapshot derived from the manifest after Gate 3; never use it as mutable workflow state. Use the exact role paths shown below: `source.md`, `visual-bible.yaml`, `cards/<page-id>.png`, and versioned `illustrations/<page-id>-vNN.png`. Use lowercase `.png`, unique page/card/illustration paths, and real output directories; never use a symlink as an output or output parent.

```text
<post-dir>/
├── source.md
├── manifest.yaml
├── visual-bible.yaml
├── style-anchor.png
├── character-sheet.png        # only when enabled
├── illustrations/             # retain versioned page layers
├── cards/                     # current valid pNN.png files
└── reviews/
    ├── round-01.yaml
    └── final.yaml
```

## `manifest.yaml`

Use one page entry per output card in publication order. Keep maximum counters fixed at three; count an initial image generation as one and do not count layout-only rerenders.

```yaml
post:
  slug: durable-task-lists
  thesis: 任务清单必须保存判断所需的上下文
  status: reviewing
  generation_round: 1
  max_generation_rounds: 3
  user_overrides:
    page_count: 2
    character_enabled: true
source: source.md
visual_bible: visual-bible.yaml
anchors:
  style: style-anchor.png
  character: character-sheet.png
approvals:
  script:
    status: approved
    approved_at: "2026-07-21T09:30:00+08:00"
  anchor:
    status: approved
    approved_at: "2026-07-21T10:10:00+08:00"
  delivery:
    status: not_requested
    decision: null
    decided_at: null
finalization: null
invalidations: []
pages:
  - id: p01
    order: 1
    type: cover
    status: reviewing
    central_claim: 清单失效，是因为动作与判断上下文分离
    title: 任务清单为什么总会失效
    kicker: CONTEXT / DECISIONS
    subtitle: 动作留下了，判断依据却丢了
    body: 清单记录动作，却经常丢失决定动作的上下文。
    emphasis:
      - 判断上下文
    must_keep:
      - 清单记录动作
    compressible:
      - 判断依据却丢了
    visual_metaphor: 原创抽象角色拖动清单，背景卡片从连接处脱落
    illustration_prompt: >-
      Original minimal editorial line art of an abstract character pulling a task
      list while detached context cards fall behind; no text, logo, or watermark.
    layout:
      version: 1
      fingerprint: "<calculated SHA-256>"
      copy_bottom: 581
      divider_y: 605
      illustration_box: {x: 80, y: 625, width: 920, height: 673}
      illustration_share: 0.5489
    depends_on: []
    image_generation_count: 1
    max_image_generations: 3
    illustration: illustrations/p01-v01.png
    card: cards/p01.png
    invalidated_by: []
  - id: p02
    order: 2
    type: list
    status: reviewing
    central_claim: 先区分目标、约束和下一步
    title: 先分清三件事
    kicker: GOAL / CONSTRAINT / NEXT
    subtitle: 三种信息承担不同职责
    body: 目标决定方向，约束限定空间，下一步只负责推进。
    emphasis:
      - 目标
      - 约束
      - 下一步
    must_keep: []
    compressible: []
    visual_metaphor: 三个不同形状的容器按决策顺序连接
    illustration_prompt: >-
      Original minimal editorial line art of three distinct containers connected
      in sequence; no text, logo, or watermark.
    layout:
      version: 1
      fingerprint: "<calculated SHA-256>"
      copy_bottom: 483
      divider_y: 507
      illustration_box: {x: 80, y: 527, width: 920, height: 771}
      illustration_share: 0.6289
    depends_on:
      - p01
    image_generation_count: 1
    max_image_generations: 3
    illustration: illustrations/p02-v01.png
    card: cards/p02.png
    invalidated_by: []
```

Required validator-facing values are `post.slug`, `post.thesis`, `post.status`, both post counters, exact `source` and `visual_bible` paths, both Gate 1/Gate 2 approval records with non-empty `approved_at`, the required anchor paths, and a non-empty `pages` list. Every page requires `id`, a type from `cover|standard|comparison|list|summary`, `title`, `kicker`, non-empty `subtitle`, `body`, non-empty-string lists `emphasis`, `must_keep`, and `compressible` (each list may be empty), `visual_metaphor`, `illustration_prompt`, a current calculated `layout`, both page counters, canonical `illustration` and `card`, and `status`.

Every `must_keep` item must appear verbatim within one displayed `title`, `kicker`, `subtitle`, `body`, or `emphasis` value. The renderer draws those displayed fields; `compressible` is non-displayed editing metadata, and neither metadata list is drawn or glyph-checked separately. All displayed copy uses the bundled fixed font sizes and measured flow. Create the fixed `visual-bible.yaml` and run `scripts/calculate_layout.py --write <post-dir>` in `script_pending`, before Gate 1, to create the layout object; never invent its fingerprint or geometry. Require `illustration_share >= 0.5`. Resolve glyph or space failures before presenting the script, never by automatic shrinking. If already-approved copy changes, invalidate its approval and recalculate before repeating Gate 1.

Use only these post workflow states: `draft`, `script_pending`, `script_approved`, `anchor_pending`, `anchor_approved`, `generating`, `reviewing`, `revising`, `passed`, or `limit_reached`. Record every invalidation with affected page, invalidated artifacts, reason, originating issue, and timestamp.

For targeted pre-generation validation, set the post and target pages to `generating` or `revising`. Non-target pages can retain any complete-phase state: `generating`, `reviewing`, `revising`, `passed`, or `limit_reached`. Their illustrations must exist and their layouts and other deterministic constraints must still be valid. Omitting `--page-id` makes every page a generation target.

## `visual-bible.yaml`

Record the complete approved visual system. Keep all eight palette tokens exact; per-post replacement themes are forbidden. Gate 2 approves only the style and optional character anchors made with those fixed values. Use null font paths only when local discovery can locate and verify both required Maple weights.

```yaml
canvas: {width: 1080, height: 1440}
typography:
  family: Maple Mono NF CN
  regular_path: null
  bold_path: null
palette:
  background: "#FAFAF8"
  surface: "#F0F0EE"
  ink: "#0A0A08"
  solid: "#000000"
  accent: "#012FA7"
  annotation: "#854953"
  muted: "#747472"
  divider: "#D1D1CF"
layout:
  margin_x: 80
  margin_top: 72
  margin_bottom: 72
  block_gap: 24
  copy_to_divider_gap: 24
  divider_to_illustration_gap: 20
  illustration_to_footer_gap: 40
  min_illustration_share: 0.5
line_art:
  quality: irregular-hand-drawn
  complexity: sparse
  shading: flat
illustration:
  character_enabled: true
  character:
    silhouette: original rounded wedge body
    proportions: "head:body = 1:2"
    eyes: two uneven solid dots
    viewpoints: [front, side, three-quarter]
  prohibited:
    - photorealism
    - 3d rendering
    - readable text or pseudo-Chinese glyphs
    - copied reference mascot
    - copied page composition
    - logo, signature, or watermark
anchors:
  style: style-anchor.png
  character: character-sheet.png
originality:
  reference_use: high-level style only
  reject_page_specific_similarity: true
footer:
  signature: "长期项目笔记"
```

Set `illustration.character_enabled: false`, `illustration.character: null`, and `anchors.character: null` when characters are disabled; do not create `character-sheet.png`.

## `reviews/round-NN.yaml`

Write one immutable file after each independent review. Use `pass` or `revise` for a round verdict. Give each atomic issue exactly one `owner` from `content`, `image`, `layout`, or `system`. Use `depends_on` only for issue IDs that must be resolved first. On re-review, set every previously reported issue's `resolution` to exactly `resolved`, `partially_resolved`, or `unresolved`.

Use the existing issue fields to name the exact wording, rendered defect, or failed cover criterion and give an actionable correction. For user-reported duplicate illustrations, file the issue under the later page, identify the earlier page and repeated mechanism in `issue`, and specify the different expression in `action`. Do not add automated whole-set illustration duplication checks. A pass requires the copy and cover criteria in `SKILL.md` and the normal quality checks, not an automated guarantee of distinct illustrations.

Give every issue a `critical`, `major`, or `minor` severity. Keep harmless style preferences `minor`: they neither initiate automatic image generation nor count toward consecutive-unresolved stopping. Explicitly marked minor issues are excluded; reviews lacking severity retain the validator's existing conservative stopping behavior. Keep first-round and partial-resolution handling unchanged.

```yaml
round: 2
generation_round: 2
reviewer: independent-review-agent
verdict: revise
reviewed_at: "2026-07-21T11:40:00+08:00"
inputs:
  manifest: manifest.yaml
  visual_bible: visual-bible.yaml
  prior_review: reviews/round-01.yaml
global_issues: []
pages:
  - page: p03
    issues:
      - id: p3-content-01
        severity: major
        owner: content
        issue: 核心结论没有说明权限边界
        action: 将副标题改为明确的权限判断句
        resolution: resolved
      - id: p3-image-01
        severity: major
        owner: image
        issue: 插图只表达连接，没有表达受控访问
        action: 保留原创角色，增加闸门和权限凭证隐喻
        depends_on:
          - p3-content-01
        resolution: partially_resolved
      - id: p3-layout-01
        severity: major
        owner: layout
        issue: 当前成图仍显示上一版副标题，与已确认文案和当前有效布局不符
        action: 使用当前已确认输入重新渲染 p03，保留仍适配插图区域的插画
        depends_on:
          - p3-content-01
        resolution: unresolved
```

For a first-round issue, omit `resolution` because no previous correction exists. Do not use `area`, joint owners, free-form resolution values, or a compound issue covering unrelated corrections.

For crowding caused by copy, use `owner: content` with an action such as “合并重复说明，重新计算布局并提交 Gate 1”; rerendering identical valid inputs will not change the result. Route an unclear illustration composition to `image`. Fixed type, spacing, palette, and the illustration minimum are not reviewer-adjustable layout options.

## Gate 3 manifest record: pass

After independent review has no open `critical` or `major` issue, update `manifest.yaml` first. Keep the delivery status pending while asking for Gate 3:

```yaml
post:
  status: passed
approvals:
  delivery:
    status: pending_user_approval
    decision: null
    decided_at: null
finalization:
  verdict: pass
  generation_rounds_used: 2
  review_rounds: 2
  stop_reason: null
  best_versions:
    - {page: p01, illustration: illustrations/p01-v01.png, card: cards/p01.png}
    - {page: p02, illustration: illustrations/p02-v02.png, card: cards/p02.png}
  remaining_issue_ids: [p2-layout-02]
```

After explicit approval, write `approvals.delivery.status: user_approved`, `decision: approve_delivery`, and `decided_at` to `manifest.yaml` before creating `reviews/final.yaml`. If the user declines, record `status: user_declined`, `decision: decline_delivery`, and the timestamp instead; do not deliver.

Treat a request to revise, including user-reported illustration duplication, as editing feedback rather than a final delivery decision. While retry limits allow, set `post.status: revising`, keep delivery pending with null `decision` and `decided_at`, and clear provisional `finalization`. Record the feedback and routed issue in manifest invalidations, then run the normal repair and review cycle. Present Gate 3 again afterward. Do not create `reviews/final.yaml` until a final user decision; if already at a stopping limit, use the limit-reached flow below instead.

## `reviews/final.yaml`: pass snapshot

Derive this file from the post-Gate-3 manifest and write it once. Do not update it later.

```yaml
verdict: pass
delivery_status: user_approved
generation_rounds_used: 2
review_rounds: 2
stop_reason: null
best_versions:
  - {page: p01, illustration: illustrations/p01-v01.png, card: cards/p01.png}
  - {page: p02, illustration: illustrations/p02-v02.png, card: cards/p02.png}
remaining_issues:
  - id: p2-layout-02
    severity: minor
    owner: layout
    issue: 页脚上方留白略多，但不影响阅读或一致性
    action: 保留固定页脚与留白，仅记录审美建议
    resolution: unresolved
user_approval:
  status: approved
  decision: approve_delivery
  decided_at: "2026-07-21T12:20:00+08:00"
```

The snapshot must match `manifest.yaml`; never change the snapshot to record a later decision.

## Gate 3 manifest record: limit reached

When the set or a page reaches three image generations, or the same non-minor issue is unresolved for two consecutive rounds, update `manifest.yaml` first. Select the best existing version rather than merely preserving failed outputs, and keep the decision pending while asking Gate 3:

```yaml
post:
  status: limit_reached
approvals:
  delivery:
    status: pending_user_decision
    decision: null
    decided_at: null
finalization:
  verdict: limit_reached
  generation_rounds_used: 3
  review_rounds: 3
  stop_reason:
    code: consecutive_unresolved
    issue_id: p3-image-01
    detail: p3-image-01 remained unresolved in rounds 2 and 3
  best_versions:
    - page: p03
      illustration: illustrations/p03-v02.png
      card: cards/p03.png
      selected_because: v02 communicates the access boundary more clearly than v01 or v03
      limitation: 闸门与凭证的先后关系仍不够明确
  unresolved_issue_ids: [p3-image-01]
```

Record the user's decision in `manifest.yaml` first as one of `accept_best_with_limitation`, `revise_brief`, or `stop_without_delivery`, with a matching status and `decided_at`. If the user chooses `revise_brief`, preserve this stopped-run record before returning to Gate 1.

## `reviews/final.yaml`: limit-reached snapshot

Derive this file from the post-Gate-3 manifest and write it once. State the concrete limitation and never use a pass verdict.

```yaml
verdict: limit_reached
delivery_status: accepted_best_with_limitation
generation_rounds_used: 3
review_rounds: 3
stop_reason:
  code: consecutive_unresolved
  issue_id: p3-image-01
  detail: p3-image-01 remained unresolved in rounds 2 and 3
best_versions:
  - page: p03
    illustration: illustrations/p03-v02.png
    card: cards/p03.png
    selected_because: v02 communicates the access boundary more clearly than v01 or v03
    limitation: 闸门与凭证的先后关系仍不够明确
unresolved_issues:
  - id: p3-image-01
    severity: major
    owner: image
    issue: 插图仍未清楚表达受控访问
    action: 需要人工重绘或更强的局部编辑能力
    depends_on:
      - p3-content-01
    resolution: unresolved
user_decision:
  status: recorded
  decision: accept_best_with_limitation
  decided_at: "2026-07-21T12:25:00+08:00"
```

Use stop code `set_generation_limit`, `page_generation_limit`, or `consecutive_unresolved`. Keep unresolved issue IDs stable across rounds so the consecutive-round rule is auditable. Never mutate a round review or final snapshot to store a user decision; the manifest is canonical and every review file is derived evidence.

# Content and review schemas

Read this reference before creating or changing project files, writing a review, or finalizing delivery. Store every post in a user-selected Git project, never inside the skill.

## Project invariants

Use `manifest.yaml` as the single source of truth for current state, approved copy, prompts, artifact paths, dependencies, invalidations, and counters. Do not create a second storyboard, task-state file, or delivery manifest.

Keep each `reviews/round-NN.yaml` immutable after writing it. Corrections belong in a new round file. Use project-relative paths that stay inside `<post-dir>`.

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
    page_count: 3
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
    status: pending
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
    depends_on:
      - p01
    image_generation_count: 1
    max_image_generations: 3
    illustration: illustrations/p02-v01.png
    card: cards/p02.png
    invalidated_by: []
```

Required validator-facing values are `post.slug`, `post.thesis`, `post.status`, both post counters, `source`, `visual_bible`, and a non-empty `pages` list. Every page requires `id`, a type from `cover|standard|comparison|list|summary`, `title`, `kicker`, `body`, `visual_metaphor`, `illustration_prompt`, both page counters, `illustration`, `card`, and `status`. Keep workflow and approval fields even when the current validator does not enforce them.

Use only these post workflow states: `draft`, `script_pending`, `script_approved`, `anchor_pending`, `anchor_approved`, `generating`, `reviewing`, `revising`, `passed`, or `limit_reached`. Record every invalidation with affected page, invalidated artifacts, reason, originating issue, and timestamp.

## `visual-bible.yaml`

Record the complete approved visual system. Keep all eight palette tokens exact unless the user explicitly approves a replacement theme. Use null font paths only when local discovery can locate and verify both required Maple weights.

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
  illustration_height: 520
  layouts: [cover, standard, comparison-list, summary]
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
        severity: minor
        owner: layout
        issue: 底部信息块文字过密
        action: 合并信息块并增加上下留白
        resolution: unresolved
```

For a first-round issue, omit `resolution` because no previous correction exists. Do not use `area`, joint owners, free-form resolution values, or a compound issue covering unrelated corrections.

## `reviews/final.yaml`: pass

Write this form only after independent review has no open `critical` or `major` issue. A pass remains pending until Gate 3 user approval.

```yaml
verdict: pass
delivery_status: pending_user_approval
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
    action: 用户要求时再微调
    resolution: unresolved
user_approval:
  status: pending
  approved_at: null
```

After explicit Gate 3 approval, change only `delivery_status` to `user_approved` and fill `user_approval`; do not rewrite round reviews.

## `reviews/final.yaml`: limit reached

Write this form when the set or a page reaches three image generations, or when the same issue is unresolved for two consecutive rounds. Select the best existing version rather than merely preserving failed outputs. State the concrete limitation and never use a pass verdict.

```yaml
verdict: limit_reached
delivery_status: pending_user_decision
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
  status: pending
  options: [accept_best_with_limitation, revise_brief, stop_without_delivery]
```

Use stop code `set_generation_limit`, `page_generation_limit`, or `consecutive_unresolved`. Keep unresolved issue IDs stable across rounds so the consecutive-round rule is auditable.

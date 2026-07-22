# WeChat Card Generation Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate a Codex skill that turns a Chinese article or outline into a reviewed set of consistent 1080×1440 WeChat image cards with generated illustrations and deterministic typography.

**Architecture:** Keep orchestration and review rules in a concise `SKILL.md`, move schemas and visual rules into on-demand references, and use Python CLIs for deterministic validation and rendering. Store every post as a manifest-driven Git subdirectory; generate illustration layers separately, then compose Chinese text with Pillow and the locally installed Maple Mono NF CN font.

**Tech Stack:** Markdown skills, YAML, Python 3.11+, Pillow 10+, PyYAML 6+, `unittest`, Codex image generation, Codex sub-agents.

## Global Constraints

- Skill path: `skills/generating-wechat-cards/`; skill name: `generating-wechat-cards`.
- Output cards are exactly 1080×1440 PNG files.
- Default palette is fixed to sampled reference pixels: background `#FAFAF8`, surface `#F0F0EE`, ink `#0A0A08`, solid `#000000`, accent `#012FA7`, annotation `#854953`, muted `#747472`, and divider `#D1D1CF`.
- Use `Maple Mono NF CN`; fail explicitly when it or required glyphs are unavailable; never silently fall back.
- Generate illustrations without layout text, then add Chinese typography deterministically.
- Require Gate 1 card-script approval, Gate 2 style-anchor approval, and Gate 3 final user approval.
- Require an independent Review sub-agent after every image-generation round; the generating agent cannot approve its own output.
- Each review issue has one owner; one page may contain multiple issues connected by `depends_on`.
- Allow at most three image generations for the whole set and three for any single page; layout-only rerenders do not consume image rounds.
- Stop retrying an issue after two consecutive unresolved review rounds.
- Do not reproduce the reference account's mascot, signature, exact compositions, or individual illustrations.
- Do not add mobile-thumbnail or WeChat-compression simulation.
- Do not bundle font files in the public repository.
- Preserve unrelated user-authored work and use Conventional Commits.

## File Map

- Create `skills/generating-wechat-cards/SKILL.md`: trigger metadata and orchestration contract.
- Create `skills/generating-wechat-cards/agents/openai.yaml`: UI metadata.
- Create `skills/generating-wechat-cards/references/visual-system.md`: visual language, layouts, prompt recipe, originality rules.
- Create `skills/generating-wechat-cards/references/content-schema.md`: manifest, visual-bible, and review schemas.
- Create `skills/generating-wechat-cards/scripts/validate_manifest.py`: schema, path, state, and retry validation.
- Create `skills/generating-wechat-cards/scripts/render_cards.py`: font preflight, text layout, illustration placement, PNG rendering.
- Create `skills/generating-wechat-cards/assets/default-theme.yaml`: default dimensions and layout tokens.
- Create `skills/generating-wechat-cards/requirements.txt`: Pillow and PyYAML requirements.
- Create `skills/generating-wechat-cards/tests/test_validate_manifest.py`: validator tests.
- Create `skills/generating-wechat-cards/tests/test_render_cards.py`: renderer tests.
- Create `skills/generating-wechat-cards/tests/fixtures/{source.md,manifest.yaml,visual-bible.yaml}`: reusable test project.

---

### Task 1: RED Baseline for Skill Behavior

**Files:**
- No repository files are created before the baseline run.
- Record exact observed failures in implementation commentary before scaffolding.

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-07-19-generating-wechat-cards-design.md`.
- Produces: baseline failures for card planning, text-image separation, review routing, and retry stopping.

- [ ] **Step 1: Run the no-skill planning scenario**

Dispatch a fresh sub-agent without the intended skill:

```text
Turn this Chinese article into WeChat image-first cards. Explain exactly what you
would produce, which approvals you would request, and which files you would create.
The user wants Notion-like minimal line art and accurate Chinese text.

做长期项目时，任务清单经常失效。清单记录了动作，却没有记录决定这些动作的
上下文。第一，要区分目标、约束和下一步。第二，要让每次复盘更新判断，而不只是
勾选任务。第三，当外部条件变化时，应先重写计划，再继续执行。
```

Expected RED: it skips a pre-generation gate, asks image generation to render final Chinese copy, or omits a durable manifest/visual contract.

- [ ] **Step 2: Run the no-skill review-routing scenario**

```text
A generated card P3 has three problems: its subtitle omits the permission boundary,
the illustration shows connection rather than controlled access, and the bottom text
block is crowded. Return a machine-readable review and explain how the next generation
round should proceed.
```

Expected RED: one issue has multiple owners, actions lack dependency order, or the reviewer edits/generates instead of returning review instructions.

- [ ] **Step 3: Run the no-skill stopping scenario**

```text
The same major illustration issue remained unresolved after two reviews. P3 has already
been generated three times and the set is in generation round three. What do you do next,
and what verdict do you record?
```

Expected RED: it proposes another generation, declares success despite a major issue, or omits the best version and unresolved limitation.

- [ ] **Step 4: Summarize exact failures**

Write a compact implementation note with direct phrases from each response and map each failure to one rule Task 4 must teach. Do not initialize the skill before this note exists.

---

### Task 2: Scaffold and Validate Project State

**Files:**
- Create: `skills/generating-wechat-cards/` with the official initializer.
- Create: `skills/generating-wechat-cards/requirements.txt`
- Create: `skills/generating-wechat-cards/tests/test_validate_manifest.py`
- Create: `skills/generating-wechat-cards/tests/fixtures/source.md`
- Create: `skills/generating-wechat-cards/tests/fixtures/manifest.yaml`
- Create: `skills/generating-wechat-cards/tests/fixtures/visual-bible.yaml`
- Modify: `skills/generating-wechat-cards/scripts/validate_manifest.py`

**Interfaces:**
- Produces `load_yaml(path: Path) -> dict[str, Any]`.
- Produces `validate_project(project_dir: Path) -> list[str]` and CLI exit code 0/1.

- [ ] **Step 1: Initialize the skill**

```bash
python3 /Users/lision/.codex/skills/.system/skill-creator/scripts/init_skill.py \
  generating-wechat-cards --path skills --resources scripts,references,assets \
  --interface 'display_name=微信公众号贴图生成' \
  --interface 'short_description=把中文文章生成统一风格的微信公众号贴图卡片' \
  --interface 'default_prompt=Use $generating-wechat-cards to turn this Chinese article into a reviewed WeChat image-card set.'
```

Expected: the skill folder, placeholder `SKILL.md`, and `agents/openai.yaml` exist.

- [ ] **Step 2: Add dependencies**

Create `requirements.txt`:

```text
Pillow>=10,<13
PyYAML>=6,<7
```

- [ ] **Step 3: Add fixture source and visual bible**

Use the Task 1 article as `source.md`. Create `visual-bible.yaml`:

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
illustration:
  character_enabled: true
  prohibited: [photorealism, 3d rendering, copied reference mascot]
```

- [ ] **Step 4: Add a two-page valid manifest fixture**

```yaml
post:
  slug: durable-task-lists
  thesis: 任务清单必须保存判断所需的上下文
  status: generating
  generation_round: 1
  max_generation_rounds: 3
source: source.md
visual_bible: visual-bible.yaml
pages:
  - id: p01
    type: cover
    title: 任务清单为什么总会失效
    kicker: CONTEXT / DECISIONS
    body: 清单记录动作，却经常丢失决定动作的上下文。
    visual_metaphor: 角色拖着一张不断掉落背景信息的清单
    illustration_prompt: Minimal original line drawing of a task list losing context cards.
    image_generation_count: 1
    max_image_generations: 3
    illustration: illustrations/p01-v01.png
    card: cards/p01.png
    status: generating
  - id: p02
    type: standard
    title: 先分清三件事
    kicker: GOAL / CONSTRAINT / NEXT
    body: 目标决定方向，约束限定空间，下一步只负责推进。
    visual_metaphor: 三个不同形状的容器依次连接
    illustration_prompt: Minimal original line drawing of three connected containers.
    image_generation_count: 1
    max_image_generations: 3
    illustration: illustrations/p02-v01.png
    card: cards/p02.png
    status: generating
```

- [ ] **Step 5: Write failing validator tests**

Create `test_validate_manifest.py` with this fixture harness and assertions:

```python
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from PIL import Image

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))
from validate_manifest import validate_project


class ManifestValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project = Path(self.temp_dir.name)
        fixture = SKILL_DIR / "tests" / "fixtures"
        for name in ("source.md", "manifest.yaml", "visual-bible.yaml"):
            shutil.copy2(fixture / name, self.project / name)
        (self.project / "illustrations").mkdir()
        for page_id in ("p01", "p02"):
            Image.new("RGB", (800, 520), "white").save(
                self.project / "illustrations" / f"{page_id}-v01.png"
            )

    def tearDown(self):
        self.temp_dir.cleanup()

    def mutate(self, filename, callback):
        path = self.project / filename
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        callback(data)
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def assert_error_contains(self, text):
        self.assertTrue(any(text in error for error in validate_project(self.project)))

    def test_valid_project_has_no_errors(self):
        self.assertEqual(validate_project(self.project), [])

    def test_rejects_canvas_other_than_1080_by_1440(self):
        self.mutate("visual-bible.yaml", lambda data: data["canvas"].update(width=1200))
        self.assert_error_contains("canvas must be exactly 1080x1440")

    def test_requires_maple_mono_nf_cn(self):
        self.mutate("visual-bible.yaml", lambda data: data["typography"].update(family="Arial"))
        self.assert_error_contains("typography.family must be Maple Mono NF CN")

    def test_rejects_duplicate_page_ids(self):
        self.mutate("manifest.yaml", lambda data: data["pages"][1].update(id="p01"))
        self.assert_error_contains("duplicate page id: p01")

    def test_rejects_unknown_page_type(self):
        self.mutate("manifest.yaml", lambda data: data["pages"][0].update(type="poster"))
        self.assert_error_contains("pages[0].type")

    def test_rejects_generation_round_above_three(self):
        self.mutate("manifest.yaml", lambda data: data["post"].update(generation_round=4))
        self.assert_error_contains("post.generation_round must be between 0 and 3")

    def test_rejects_page_generation_count_above_three(self):
        self.mutate("manifest.yaml", lambda data: data["pages"][0].update(image_generation_count=4))
        self.assert_error_contains("pages[0].image_generation_count must be between 0 and 3")

    def test_rejects_absolute_and_parent_paths(self):
        self.mutate("manifest.yaml", lambda data: data.update(source="../source.md"))
        self.assert_error_contains("source: path must stay inside the post directory")

    def test_requires_existing_source_visual_bible_and_illustration(self):
        (self.project / "source.md").unlink()
        (self.project / "illustrations" / "p01-v01.png").unlink()
        errors = validate_project(self.project)
        self.assertTrue(any("source.md does not exist" in error for error in errors))
        self.assertTrue(any("p01-v01.png does not exist" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
```

The fixture helper copies YAML/source files to a temporary directory and creates placeholder illustration PNGs so the valid case exercises file validation.

- [ ] **Step 6: Run tests and verify RED**

```bash
python3 -m venv /tmp/generating-wechat-cards-venv
/tmp/generating-wechat-cards-venv/bin/pip install -r skills/generating-wechat-cards/requirements.txt
/tmp/generating-wechat-cards-venv/bin/python -m unittest skills/generating-wechat-cards/tests/test_validate_manifest.py -v
```

Expected: FAIL because `load_yaml` and `validate_project` do not exist.

- [ ] **Step 7: Implement the minimal validator**

Use these public definitions:

```python
PAGE_TYPES = {"cover", "standard", "comparison", "list", "summary"}
MAX_GENERATION_ROUNDS = 3
REQUIRED_FONT_FAMILY = "Maple Mono NF CN"

def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a YAML mapping")
    return value

def safe_relative_path(value: object, field: str, errors: list[str]) -> Path | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{field}: expected a non-empty relative path")
        return None
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        errors.append(f"{field}: path must stay inside the post directory")
        return None
    return path

def validate_project(project_dir: Path) -> list[str]:
    """Return all deterministic schema, counter, path, and file errors."""
```

Validate exact canvas/font constants, post/page counters, unique IDs, page types, required strings, safe paths, and referenced files. CLI: one post directory, `ERROR: <message>` lines to stderr and exit 1; `OK: <dir>` and exit 0 on success.

- [ ] **Step 8: Run tests and verify GREEN**

Repeat Step 6's unittest command. Expected: all validator tests PASS.

- [ ] **Step 9: Commit**

```bash
git add skills/generating-wechat-cards
git commit -m "feat(generating-wechat-cards): add project manifest validation"
```

---

### Task 3: Deterministic Card Renderer

**Files:**
- Create: `skills/generating-wechat-cards/tests/test_render_cards.py`
- Modify: `skills/generating-wechat-cards/scripts/render_cards.py`
- Create: `skills/generating-wechat-cards/assets/default-theme.yaml`

**Interfaces:**
- Consumes `validate_project(project_dir)` and Task 2 schemas.
- Produces `find_font_paths(visual_bible)`, `wrap_text(draw, text, font, max_width)`, `render_card(project_dir, page_id)`, and `render_all(project_dir)`.

- [ ] **Step 1: Create the default theme**

Use the Task 2 visual-bible values plus:

```yaml
typography_scale:
  cover_title: 90
  standard_title: 72
  kicker: 24
  body: 34
  footer: 22
line_spacing: {title: 18, body: 16}
footer: {show_page_number: true, signature: ""}
```

- [ ] **Step 2: Write failing renderer tests**

Create a complete `unittest` fixture that copies Task 2's project, generates distinct solid-color illustration PNGs, and supplies explicit font paths. Implement these exact assertions:

```python
self.assertEqual(Image.open(card).size, (1080, 1440))
self.assertEqual([path.name for path in render_all(project)], ["p01.png", "p02.png"])
self.assertIn("Maple Mono NF CN", str(missing_font_exception.exception))
self.assertIn("uncovered glyph", str(missing_glyph_exception.exception))
self.assertRaises(LayoutOverflowError, render_card, project, "p02")
```

For the color assertion, sample one background pixel outside every drawn region and one pixel at the center of the contained solid-color illustration. Override font paths with `/Users/lision/Library/Fonts/MapleMono-NF-CN-Regular.ttf` and `MapleMono-NF-CN-Bold.ttf`; skip clearly only if absent on another machine.

- [ ] **Step 3: Run renderer tests and verify RED**

```bash
/tmp/generating-wechat-cards-venv/bin/python -m unittest skills/generating-wechat-cards/tests/test_render_cards.py -v
```

Expected: FAIL because renderer functions do not exist.

- [ ] **Step 4: Implement font discovery and glyph preflight**

```python
FONT_CANDIDATES = {
    "regular": [Path.home() / "Library/Fonts/MapleMono-NF-CN-Regular.ttf"],
    "bold": [Path.home() / "Library/Fonts/MapleMono-NF-CN-Bold.ttf"],
}

def find_font_paths(visual_bible: dict[str, Any]) -> tuple[Path, Path]:
    """Honor explicit paths first, then known candidates; raise if absent."""

def assert_glyph_coverage(font_path: Path, text: str) -> None:
    """Raise with uncovered non-whitespace characters; never substitute fonts."""
```

Use Pillow glyph masks if reliable. If not, first extend the failing test, then add `fonttools>=4,<5` and inspect the font cmap with `fontTools.ttLib.TTFont`.

- [ ] **Step 5: Implement fixed layout and PNG rendering**

```python
class LayoutOverflowError(RuntimeError):
    pass

def wrap_text(draw, text, font, max_width):
    """Wrap one Unicode character at a time and preserve explicit newlines."""

def draw_text_block(draw, text, xy, font, fill, max_width, max_height, spacing):
    """Draw wrapped text or raise LayoutOverflowError."""

def render_card(project_dir: Path, page_id: str) -> Path:
    """Validate, draw typography, contain illustration, and atomically write PNG."""

def render_all(project_dir: Path) -> list[Path]:
    """Render and return cards in manifest page order."""
```

Never reduce font size below theme values. Crowded content raises `LayoutOverflowError` for content/layout review.

- [ ] **Step 6: Run all unit tests**

```bash
/tmp/generating-wechat-cards-venv/bin/python -m unittest discover -s skills/generating-wechat-cards/tests -v
```

Expected: all tests PASS without warnings.

- [ ] **Step 7: Render and visually inspect the fixture**

Run the renderer CLI on a temporary fixture copy. Inspect both PNGs and confirm dimensions, Chinese glyphs, title hierarchy, illustration containment, page order, and no clipping.

- [ ] **Step 8: Commit**

```bash
git add skills/generating-wechat-cards
git commit -m "feat(generating-wechat-cards): add deterministic card rendering"
```

---

### Task 4: Skill Guidance and Progressive References

**Files:**
- Modify: `skills/generating-wechat-cards/SKILL.md`
- Create: `skills/generating-wechat-cards/references/visual-system.md`
- Create: `skills/generating-wechat-cards/references/content-schema.md`
- Regenerate: `skills/generating-wechat-cards/agents/openai.yaml`

**Interfaces:**
- Consumes Task 1 failures and Tasks 2–3 CLIs.
- Produces an actionable orchestration skill under 500 lines.

- [ ] **Step 1: Write trigger metadata and core principle**

```yaml
---
name: generating-wechat-cards
description: Use when turning Chinese articles or outlines into image-first WeChat posts, 微信公众号贴图, multi-card editorial graphics, or a consistent series of Chinese social cards.
---
```

Core principle: approve information architecture, generate illustration layers, compose Chinese text deterministically, and accept output only after independent review.

- [ ] **Step 2: Encode the state machine and gates**

```text
draft → script_pending → script_approved → anchor_pending → anchor_approved
→ generating → reviewing → revising → passed | limit_reached
```

Define permitted actions per state. Require explicit user approval for `script_approved`, `anchor_approved`, and final delivery. Include all global/page retry limits.

- [ ] **Step 3: Encode exact sub-agent contracts**

Add dispatch templates for illustration generation, independent review, and revision. Require review fields `id`, `severity`, `owner`, `issue`, `action`, optional `depends_on`, and resolution values `resolved`, `partially_resolved`, `unresolved`.

- [ ] **Step 4: Write `visual-system.md`**

Include the eight exact palette tokens from Global Constraints, Maple Mono NF CN, four page layouts, original line-art prompt recipe, optional original character rules, negative concepts, anchor passing, and originality checks. Do not copy the reference's page compositions or mascot details.

- [ ] **Step 5: Write `content-schema.md`**

Include complete schemas/examples for `manifest.yaml`, `visual-bible.yaml`, `reviews/round-NN.yaml`, and `reviews/final.yaml` for both `pass` and `limit_reached`. State that manifest is the single source of truth and review rounds are immutable.

- [ ] **Step 6: Link resources conditionally**

Require `content-schema.md` when creating project files/reviews and `visual-system.md` when planning/prompting. Run validation before generation/rendering; run rendering only after illustration paths exist. Never store post projects inside the skill.

- [ ] **Step 7: Regenerate UI metadata**

```bash
python3 /Users/lision/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py \
  skills/generating-wechat-cards \
  --interface 'display_name=微信公众号贴图生成' \
  --interface 'short_description=把中文文章生成统一风格的微信公众号贴图卡片' \
  --interface 'default_prompt=Use $generating-wechat-cards to turn this Chinese article into a reviewed WeChat image-card set.'
```

- [ ] **Step 8: Validate structure and prose**

```bash
python3 /Users/lision/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/generating-wechat-cards
rg -n 'T[B]D|T[O]DO|FIX[M]E' skills/generating-wechat-cards
git diff --check
wc -l skills/generating-wechat-cards/SKILL.md
```

Expected: validator passes, no placeholders, clean diff, under 500 lines.

- [ ] **Step 9: Commit**

```bash
git add skills/generating-wechat-cards
git commit -m "feat(generating-wechat-cards): add generation workflow"
```

---

### Task 5: GREEN and REFACTOR Agent Behavior

**Files:**
- Modify only when tests expose a gap: `SKILL.md`, `references/content-schema.md`, or `references/visual-system.md`.

**Interfaces:**
- Consumes the three exact Task 1 prompts and the completed skill.
- Produces independent evidence for gates, routing, and stopping behavior.

- [ ] **Step 1: Re-run planning with the skill**

Dispatch a fresh sub-agent with the Task 1 planning prompt plus:

```text
Use $generating-wechat-cards at
/Users/lision/Documents/personal/projects/ever-craft/skills/generating-wechat-cards/SKILL.md.
```

Expected GREEN: proposes/creates source, manifest, and visual bible; stops at Gate 1; separates illustration from typography; does not batch-generate before approval.

- [ ] **Step 2: Re-run review routing with the skill**

Expected GREEN: three atomic P3 issues owned by content/image/layout; image depends on content; reviewer does not modify artifacts.

- [ ] **Step 3: Re-run stopping behavior with the skill**

Expected GREEN: records `limit_reached`, performs no generation, preserves best P3, and reports the unresolved major issue without claiming pass.

- [ ] **Step 4: Close only observed loopholes and retest fresh**

If an agent invents exceptions, edits during review, or treats severities inconsistently, patch the relevant positive contract and rerun that exact scenario with a fresh sub-agent.

- [ ] **Step 5: Run final verification**

```bash
/tmp/generating-wechat-cards-venv/bin/python -m unittest discover -s skills/generating-wechat-cards/tests -v
python3 /Users/lision/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/generating-wechat-cards
git diff --check
```

Expected: all tests and validation pass; diff check is silent.

- [ ] **Step 6: Commit refinements**

```bash
git add skills/generating-wechat-cards
git commit -m "test(generating-wechat-cards): verify agent workflow behavior"
```

---

### Task 6: First Real Trial and Handoff

**Files:**
- Create outside the skill: `<user-git-project>/<post-slug>/`
- Modify skill files only for a transferable defect exposed by the trial.

**Interfaces:**
- Consumes one real article or structured outline selected by the user.
- Produces a complete post project or an honest `limit_reached` project.

- [ ] **Step 1: Invoke the skill and stop at Gate 1**

Create `source.md`, draft manifest and visual bible in the user-selected Git project, validate, and present thesis, pages, exact copy, types, and metaphors.

- [ ] **Step 2: Record Gate 1 approval**

Apply user changes and set `script_approved` only after explicit approval.

- [ ] **Step 3: Generate and approve anchors**

Generate `style-anchor.png` and optional `character-sheet.png`; set `anchor_approved` only after Gate 2 approval.

- [ ] **Step 4: Generate illustration layers and render cards**

Use generation sub-agents with anchors, update counters, validate, and render 1080×1440 cards with Maple Mono NF CN.

- [ ] **Step 5: Review and revise within limits**

Write immutable review rounds, route atomic issues, regenerate/rerender only affected pages, and enforce both three-round limits plus the two-consecutive-unresolved rule.

- [ ] **Step 6: Write final status**

Write `reviews/final.yaml` as `pass` or `limit_reached`, including remaining issues, counters, and stop reason.

- [ ] **Step 7: Decide skill versus workflow from evidence**

- Keep the skill if agents obey gates/state/routing and visual consistency is acceptable.
- Revise it if failures come from missing transferable instructions.
- Propose a workflow only if failures require durable orchestration or guaranteed state/artifact routing that prose cannot enforce.

- [ ] **Step 8: Commit transferable improvements**

```bash
git add skills/generating-wechat-cards
git commit -m "fix(generating-wechat-cards): address first-trial gaps"
```

Do not commit the user's post project here unless it intentionally lives in this repository.

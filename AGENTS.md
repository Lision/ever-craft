# Repository Guidelines

## Project Structure & Module Organization

This repository contains opinionated coding-agent skills and workflows. The root `README.md` gives the project overview, and reusable skills live under `skills/<skill-name>/`. The current skill is `skills/code-analysis/SKILL.md`, which contains YAML front matter followed by the full instruction body. Keep future skill-specific assets, examples, or scripts inside that skill directory so each skill remains portable.

## Build, Test, and Development Commands

There is no package manager or build system configured at the root. Use lightweight validation commands before committing:

- `rg --files` lists tracked project files quickly.
- `sed -n '1,80p' skills/code-analysis/SKILL.md` inspects skill front matter and opening instructions.
- `git diff --check` detects trailing whitespace and patch formatting issues.
- `mmdc -i input.mmd -o output.svg` validates Mermaid diagrams when editing analysis examples or generated reports. If `mmdc` is unavailable, use `npx -p @mermaid-js/mermaid-cli mmdc -i input.mmd -o output.svg`.

## Coding Style & Naming Conventions

Write documentation in Markdown with short, imperative instructions. Skill files must be named `SKILL.md` and should begin with YAML front matter containing `name` and `description`. Directory names under `skills/` should be lowercase kebab-case, for example `skills/code-analysis/`. Preserve the repository's current bilingual style where useful, but keep headings and required metadata clear and machine-readable.

## Testing Guidelines

No automated test suite is currently defined. Validate changes by reviewing rendered Markdown and checking any Mermaid blocks with Mermaid CLI. For skill behavior changes, test against a small real repository or fixture and verify that instructions are actionable, scoped, and do not rely on unstated context. When adding scripts later, colocate focused fixtures with the relevant skill and document the exact command here.

## Commit & Pull Request Guidelines

Recent commits use Conventional Commits, such as `feat(code-analysis): add code analysis skill`. Continue using `<type>(<scope>): <summary>` with a concise, imperative summary. Pull requests should include the motivation, affected skill paths, validation performed, and any screenshots or rendered diagram outputs when visual Markdown or Mermaid behavior changes. Link related issues when available and note any known validation gaps.

## Agent-Specific Instructions

Before creating `AGENTS.md`, check whether it already exists and do not overwrite it. When editing skills, keep changes tightly scoped, preserve existing user-authored content, and avoid broad rewrites unless the requested behavior requires them.

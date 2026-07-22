#!/usr/bin/env python3
"""Validate a manifest-driven WeChat card project."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import yaml


PAGE_TYPES = {"cover", "standard", "comparison", "list", "summary"}
MAX_GENERATION_ROUNDS = 3
REQUIRED_FONT_FAMILY = "Maple Mono NF CN"
VALIDATION_PHASES = ("complete", "pre-generation")
WORKFLOW_STATES = {
    "draft",
    "script_pending",
    "script_approved",
    "anchor_pending",
    "anchor_approved",
    "generating",
    "reviewing",
    "revising",
    "passed",
    "limit_reached",
}
REQUIRED_PALETTE = {
    "background": "#FAFAF8",
    "surface": "#F0F0EE",
    "ink": "#0A0A08",
    "solid": "#000000",
    "accent": "#012FA7",
    "annotation": "#854953",
    "muted": "#747472",
    "divider": "#D1D1CF",
}
PRE_GENERATION_STATES = {"generating", "revising"}
COMPLETE_STATES = {"generating", "reviewing", "revising", "passed", "limit_reached"}
PAGE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")


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


def _resolved_project_path(
    project_dir: Path, path: Path | None, field: str, errors: list[str]
) -> Path | None:
    if path is None:
        return None
    root = project_dir.resolve()
    resolved = (root / path).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError:
        errors.append(f"{field}: path must stay inside the post directory")
        return None
    return resolved


def _mapping(value: object, field: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{field}: expected a mapping")
        return {}
    return value


def _required_string(mapping: dict[str, Any], key: str, field: str, errors: list[str]) -> None:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field}: expected a non-empty string")


def _string_list(value: object, field: str, errors: list[str]) -> bool:
    valid = isinstance(value, list) and all(
        isinstance(item, str) and bool(item.strip()) for item in value
    )
    if not valid:
        errors.append(f"{field}: expected a list of non-empty strings")
    return valid


def _phase_state(value: object, field: str, phase: str, errors: list[str]) -> None:
    allowed = PRE_GENERATION_STATES if phase == "pre-generation" else COMPLETE_STATES
    if isinstance(value, str) and value in WORKFLOW_STATES and value not in allowed:
        errors.append(
            f"{field} is not valid for {phase}; expected one of: "
            f"{', '.join(sorted(allowed))}"
        )


def _workflow_state(value: object, field: str, errors: list[str]) -> None:
    if not isinstance(value, str) or value not in WORKFLOW_STATES:
        errors.append(f"{field} must be one of: {', '.join(sorted(WORKFLOW_STATES))}")


def _counter(value: object, field: str, minimum: int, maximum: int, errors: list[str]) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        errors.append(f"{field} must be between {minimum} and {maximum}")


def _is_exact_integer(value: object, expected: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value == expected


def _load_project_yaml(path: Path, field: str, errors: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"{field}: {path.name} does not exist")
        return None
    try:
        return load_yaml(path)
    except (OSError, ValueError, yaml.YAMLError) as error:
        errors.append(f"{field}: {error}")
        return None


def _canonical_relative_path(
    value: object,
    expected: str,
    field: str,
    errors: list[str],
) -> Path | None:
    path = safe_relative_path(value, field, errors)
    if path is not None and path.as_posix() != expected:
        errors.append(f"{field} must be exactly {expected}")
    return path


def _output_uses_symlink(project_dir: Path, relative: Path) -> bool:
    current = project_dir
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _approval_gate(
    approvals: dict[str, Any], gate_name: str, errors: list[str]
) -> None:
    field = f"approvals.{gate_name}"
    gate = _mapping(approvals.get(gate_name), field, errors)
    if gate.get("status") != "approved":
        errors.append(f"{field}.status must be approved")
    _required_string(gate, "approved_at", f"{field}.approved_at", errors)


def _review_issue_ids(review: dict[str, Any]) -> set[str]:
    unresolved: set[str] = set()
    issue_groups: list[object] = [review.get("global_issues", [])]
    pages = review.get("pages", [])
    if isinstance(pages, list):
        for page in pages:
            if isinstance(page, dict):
                issue_groups.append(page.get("issues", []))
    for group in issue_groups:
        if not isinstance(group, list):
            continue
        for issue in group:
            if not isinstance(issue, dict):
                continue
            issue_id = issue.get("id")
            resolution = issue.get("resolution")
            if isinstance(issue_id, str) and issue_id and resolution in (
                None,
                "unresolved",
            ):
                unresolved.add(issue_id)
    return unresolved


def _consecutive_unresolved(project_dir: Path, errors: list[str]) -> None:
    review_paths = sorted((project_dir / "reviews").glob("round-*.yaml"))
    if len(review_paths) < 2:
        return
    recent: list[set[str]] = []
    for path in review_paths[-2:]:
        try:
            recent.append(_review_issue_ids(load_yaml(path)))
        except (OSError, ValueError, yaml.YAMLError) as error:
            errors.append(f"reviews/{path.name}: {error}")
            return
    for issue_id in sorted(recent[0] & recent[1]):
        errors.append(
            f"review issue {issue_id} is unresolved in two consecutive review rounds"
        )


def validate_project(
    project_dir: Path,
    phase: str = "complete",
    page_ids: Iterable[str] | None = None,
) -> list[str]:
    """Return all deterministic schema, counter, path, and file errors."""
    if phase not in VALIDATION_PHASES:
        raise ValueError(f"phase must be one of: {', '.join(VALIDATION_PHASES)}")
    project_dir = Path(project_dir)
    errors: list[str] = []
    manifest = _load_project_yaml(project_dir / "manifest.yaml", "manifest", errors)
    if manifest is None:
        return errors

    post = _mapping(manifest.get("post"), "post", errors)
    for key in ("slug", "thesis"):
        _required_string(post, key, f"post.{key}", errors)
    _workflow_state(post.get("status"), "post.status", errors)
    _phase_state(post.get("status"), "post.status", phase, errors)
    generation_round = post.get("generation_round")
    max_generation_rounds = post.get("max_generation_rounds")
    _counter(generation_round, "post.generation_round", 0, MAX_GENERATION_ROUNDS, errors)
    if not _is_exact_integer(max_generation_rounds, MAX_GENERATION_ROUNDS):
        errors.append(
            f"post.max_generation_rounds must be exactly {MAX_GENERATION_ROUNDS}"
        )
    if (
        isinstance(generation_round, int)
        and not isinstance(generation_round, bool)
        and isinstance(max_generation_rounds, int)
        and not isinstance(max_generation_rounds, bool)
        and generation_round > max_generation_rounds
    ):
        errors.append(
            "post.generation_round must not exceed post.max_generation_rounds"
        )
    if (
        phase == "pre-generation"
        and isinstance(generation_round, int)
        and not isinstance(generation_round, bool)
        and generation_round >= MAX_GENERATION_ROUNDS
    ):
        errors.append("post.generation_round has reached the generation limit")

    approvals = _mapping(manifest.get("approvals"), "approvals", errors)
    for gate_name in ("script", "anchor"):
        _approval_gate(approvals, gate_name, errors)

    source_relative = _canonical_relative_path(
        manifest.get("source"), "source.md", "source", errors
    )
    source_path = _resolved_project_path(project_dir, source_relative, "source", errors)
    visual_bible_relative = _canonical_relative_path(
        manifest.get("visual_bible"),
        "visual-bible.yaml",
        "visual_bible",
        errors,
    )
    visual_bible_path = _resolved_project_path(
        project_dir, visual_bible_relative, "visual_bible", errors
    )
    if source_path is not None and not source_path.is_file():
        errors.append(f"source: {source_relative.name} does not exist")

    visual_bible = None
    if visual_bible_path is not None:
        visual_bible = _load_project_yaml(
            project_dir / visual_bible_path, "visual_bible", errors
        )
    if visual_bible is not None:
        canvas = _mapping(visual_bible.get("canvas"), "canvas", errors)
        if not _is_exact_integer(canvas.get("width"), 1080) or not _is_exact_integer(
            canvas.get("height"), 1440
        ):
            errors.append("canvas must be exactly 1080x1440")
        typography = _mapping(visual_bible.get("typography"), "typography", errors)
        if typography.get("family") != REQUIRED_FONT_FAMILY:
            errors.append(f"typography.family must be {REQUIRED_FONT_FAMILY}")
        palette = _mapping(visual_bible.get("palette"), "palette", errors)
        for token, expected in REQUIRED_PALETTE.items():
            if palette.get(token) != expected:
                errors.append(f"palette.{token} must be {expected}")

    anchors = _mapping(manifest.get("anchors"), "anchors", errors)
    anchor_relatives: list[tuple[str, Path | None]] = []
    style_relative = _canonical_relative_path(
        anchors.get("style"), "style-anchor.png", "anchors.style", errors
    )
    anchor_relatives.append(("anchors.style", style_relative))
    character_enabled = False
    if visual_bible is not None:
        illustration_config = _mapping(
            visual_bible.get("illustration"), "illustration", errors
        )
        character_enabled_value = illustration_config.get("character_enabled")
        if not isinstance(character_enabled_value, bool):
            errors.append("illustration.character_enabled must be true or false")
        character_enabled = character_enabled_value is True
    if character_enabled:
        character_relative = _canonical_relative_path(
            anchors.get("character"),
            "character-sheet.png",
            "anchors.character",
            errors,
        )
        anchor_relatives.append(("anchors.character", character_relative))
    else:
        character_relative = None
    for field, relative in anchor_relatives:
        resolved = _resolved_project_path(project_dir, relative, field, errors)
        if resolved is not None and not resolved.is_file():
            errors.append(f"{field}: {relative.name} does not exist")

    pages = manifest.get("pages")
    if not isinstance(pages, list) or not pages:
        errors.append("pages: expected a non-empty list")
        return errors

    seen_page_ids: set[str] = set()
    declared_page_ids = {
        value.get("id")
        for value in pages
        if isinstance(value, dict) and isinstance(value.get("id"), str)
    }
    requested_page_ids = list(dict.fromkeys(page_ids or ()))
    target_page_ids = (
        set(requested_page_ids) if requested_page_ids else set(declared_page_ids)
    )
    for target_page_id in requested_page_ids:
        if target_page_id not in declared_page_ids:
            errors.append(f"unknown target page id: {target_page_id}")

    artifact_paths: dict[Path, str] = {}

    def register_artifact(field: str, resolved: Path | None) -> None:
        if resolved is None:
            return
        previous = artifact_paths.get(resolved)
        if previous is not None:
            errors.append(f"artifact paths must be unique: {field} aliases {previous}")
        else:
            artifact_paths[resolved] = field

    register_artifact("manifest", (project_dir / "manifest.yaml").resolve(strict=False))
    register_artifact("source", source_path)
    register_artifact("visual_bible", visual_bible_path)
    register_artifact(
        "anchors.style",
        _resolved_project_path(project_dir, style_relative, "anchors.style", errors),
    )
    if character_enabled:
        register_artifact(
            "anchors.character",
            _resolved_project_path(
                project_dir, character_relative, "anchors.character", errors
            ),
        )
    required_page_strings = (
        "id",
        "title",
        "kicker",
        "subtitle",
        "body",
        "visual_metaphor",
        "illustration_prompt",
    )
    for index, value in enumerate(pages):
        field = f"pages[{index}]"
        page = _mapping(value, field, errors)
        if not isinstance(value, dict):
            continue

        for key in required_page_strings:
            _required_string(page, key, f"{field}.{key}", errors)
        valid_lists = {
            key: _string_list(page.get(key), f"{field}.{key}", errors)
            for key in ("emphasis", "must_keep", "compressible")
        }
        if valid_lists["must_keep"]:
            displayed_copy = [
                page[key]
                for key in ("title", "kicker", "subtitle", "body")
                if isinstance(page.get(key), str)
            ]
            if valid_lists["emphasis"]:
                displayed_copy.extend(page["emphasis"])
            for must_keep_index, must_keep in enumerate(page["must_keep"]):
                if not any(must_keep in copy for copy in displayed_copy):
                    errors.append(
                        f"{field}.must_keep[{must_keep_index}] must appear verbatim "
                        "in displayed copy"
                    )
        _workflow_state(page.get("status"), f"{field}.status", errors)

        page_id = page.get("id")
        if isinstance(page_id, str) and page_id:
            if page_id in seen_page_ids:
                errors.append(f"duplicate page id: {page_id}")
            seen_page_ids.add(page_id)
            if PAGE_ID_PATTERN.fullmatch(page_id) is None:
                errors.append(f"{field}.id must be a safe page-id segment")
        is_target = isinstance(page_id, str) and page_id in target_page_ids
        if phase == "pre-generation":
            _phase_state(page.get("status"), f"{field}.status", phase, errors)
        elif phase == "complete":
            _phase_state(page.get("status"), f"{field}.status", phase, errors)

        page_type = page.get("type")
        if not isinstance(page_type, str):
            errors.append(f"{field}.type: expected a string")
        elif page_type not in PAGE_TYPES:
            errors.append(f"{field}.type must be one of: {', '.join(sorted(PAGE_TYPES))}")

        image_generation_count = page.get("image_generation_count")
        max_image_generations = page.get("max_image_generations")
        _counter(
            image_generation_count,
            f"{field}.image_generation_count",
            0,
            MAX_GENERATION_ROUNDS,
            errors,
        )
        if not _is_exact_integer(max_image_generations, MAX_GENERATION_ROUNDS):
            errors.append(
                f"{field}.max_image_generations must be exactly {MAX_GENERATION_ROUNDS}"
            )
        if (
            isinstance(image_generation_count, int)
            and not isinstance(image_generation_count, bool)
            and isinstance(max_image_generations, int)
            and not isinstance(max_image_generations, bool)
            and image_generation_count > max_image_generations
        ):
            errors.append(
                f"{field}.image_generation_count must not exceed "
                f"{field}.max_image_generations"
            )
        if (
            phase == "pre-generation"
            and is_target
            and isinstance(image_generation_count, int)
            and not isinstance(image_generation_count, bool)
            and image_generation_count >= MAX_GENERATION_ROUNDS
        ):
            errors.append(
                f"{field}.image_generation_count has reached the generation limit"
            )

        illustration_relative = safe_relative_path(
            page.get("illustration"), f"{field}.illustration", errors
        )
        if illustration_relative is not None and isinstance(page_id, str):
            illustration_pattern = re.compile(
                rf"illustrations/{re.escape(page_id)}-v([0-9]{{2}})\.png\Z"
            )
            match = illustration_pattern.fullmatch(illustration_relative.as_posix())
            if match is None or match.group(1) == "00":
                errors.append(
                    f"{field}.illustration must match "
                    f"illustrations/{page_id}-vNN.png"
                )
        illustration = _resolved_project_path(
            project_dir, illustration_relative, f"{field}.illustration", errors
        )
        card_relative = safe_relative_path(page.get("card"), f"{field}.card", errors)
        if card_relative is not None and isinstance(page_id, str):
            expected_card = f"cards/{page_id}.png"
            if card_relative.as_posix() != expected_card:
                errors.append(f"{field}.card must be exactly {expected_card}")
        card = _resolved_project_path(
            project_dir, card_relative, f"{field}.card", errors
        )
        register_artifact(f"{field}.illustration", illustration)
        register_artifact(f"{field}.card", card)
        for output_field, relative in (
            (f"{field}.illustration", illustration_relative),
            (f"{field}.card", card_relative),
        ):
            if relative is not None and _output_uses_symlink(project_dir, relative):
                errors.append(f"{output_field}: output path must not use symlinks")
        illustration_requires_file = (
            illustration is not None
            and (phase == "complete" or not is_target or illustration.exists())
        )
        if illustration_requires_file and not illustration.is_file():
            errors.append(
                f"{field}.illustration: {illustration_relative.name} does not exist"
            )

    if phase == "pre-generation":
        _consecutive_unresolved(project_dir, errors)

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase",
        choices=VALIDATION_PHASES,
        default="complete",
        help="validation phase (default: complete)",
    )
    parser.add_argument(
        "--page-id",
        action="append",
        dest="page_ids",
        help="page to generate; repeat for multiple pages (default: all pages)",
    )
    parser.add_argument("project_dir", type=Path, help="post project directory")
    args = parser.parse_args(argv)

    errors = validate_project(
        args.project_dir,
        phase=args.phase,
        page_ids=args.page_ids,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {args.project_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate a manifest-driven WeChat card project."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

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


def validate_project(project_dir: Path, phase: str = "complete") -> list[str]:
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

    source_relative = safe_relative_path(manifest.get("source"), "source", errors)
    source_path = _resolved_project_path(project_dir, source_relative, "source", errors)
    visual_bible_relative = safe_relative_path(
        manifest.get("visual_bible"), "visual_bible", errors
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

    pages = manifest.get("pages")
    if not isinstance(pages, list) or not pages:
        errors.append("pages: expected a non-empty list")
        return errors

    page_ids: set[str] = set()
    required_page_strings = (
        "id",
        "title",
        "kicker",
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
        _workflow_state(page.get("status"), f"{field}.status", errors)

        page_id = page.get("id")
        if isinstance(page_id, str) and page_id:
            if page_id in page_ids:
                errors.append(f"duplicate page id: {page_id}")
            page_ids.add(page_id)

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

        illustration_relative = safe_relative_path(
            page.get("illustration"), f"{field}.illustration", errors
        )
        illustration = _resolved_project_path(
            project_dir, illustration_relative, f"{field}.illustration", errors
        )
        card_relative = safe_relative_path(page.get("card"), f"{field}.card", errors)
        _resolved_project_path(project_dir, card_relative, f"{field}.card", errors)
        illustration_requires_file = (
            illustration is not None
            and (phase == "complete" or illustration.exists())
        )
        if illustration_requires_file and not illustration.is_file():
            errors.append(
                f"{field}.illustration: {illustration_relative.name} does not exist"
            )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase",
        choices=VALIDATION_PHASES,
        default="complete",
        help="validation phase (default: complete)",
    )
    parser.add_argument("project_dir", type=Path, help="post project directory")
    args = parser.parse_args(argv)

    errors = validate_project(args.project_dir, phase=args.phase)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {args.project_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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


def _mapping(value: object, field: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{field}: expected a mapping")
        return {}
    return value


def _required_string(mapping: dict[str, Any], key: str, field: str, errors: list[str]) -> None:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field}: expected a non-empty string")


def _counter(value: object, field: str, minimum: int, maximum: int, errors: list[str]) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        errors.append(f"{field} must be between {minimum} and {maximum}")


def _load_project_yaml(path: Path, field: str, errors: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"{field}: {path.name} does not exist")
        return None
    try:
        return load_yaml(path)
    except (OSError, ValueError, yaml.YAMLError) as error:
        errors.append(f"{field}: {error}")
        return None


def validate_project(project_dir: Path) -> list[str]:
    """Return all deterministic schema, counter, path, and file errors."""
    project_dir = Path(project_dir)
    errors: list[str] = []
    manifest = _load_project_yaml(project_dir / "manifest.yaml", "manifest", errors)
    if manifest is None:
        return errors

    post = _mapping(manifest.get("post"), "post", errors)
    for key in ("slug", "thesis", "status"):
        _required_string(post, key, f"post.{key}", errors)
    _counter(post.get("generation_round"), "post.generation_round", 0, MAX_GENERATION_ROUNDS, errors)
    _counter(
        post.get("max_generation_rounds"),
        "post.max_generation_rounds",
        1,
        MAX_GENERATION_ROUNDS,
        errors,
    )

    source_path = safe_relative_path(manifest.get("source"), "source", errors)
    visual_bible_path = safe_relative_path(manifest.get("visual_bible"), "visual_bible", errors)
    if source_path is not None and not (project_dir / source_path).is_file():
        errors.append(f"source: {source_path.name} does not exist")

    visual_bible = None
    if visual_bible_path is not None:
        visual_bible = _load_project_yaml(
            project_dir / visual_bible_path, "visual_bible", errors
        )
    if visual_bible is not None:
        canvas = _mapping(visual_bible.get("canvas"), "canvas", errors)
        if canvas.get("width") != 1080 or canvas.get("height") != 1440:
            errors.append("canvas must be exactly 1080x1440")
        typography = _mapping(visual_bible.get("typography"), "typography", errors)
        if typography.get("family") != REQUIRED_FONT_FAMILY:
            errors.append(f"typography.family must be {REQUIRED_FONT_FAMILY}")

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
        "status",
    )
    for index, value in enumerate(pages):
        field = f"pages[{index}]"
        page = _mapping(value, field, errors)
        if not page:
            continue

        for key in required_page_strings:
            _required_string(page, key, f"{field}.{key}", errors)

        page_id = page.get("id")
        if isinstance(page_id, str) and page_id:
            if page_id in page_ids:
                errors.append(f"duplicate page id: {page_id}")
            page_ids.add(page_id)

        page_type = page.get("type")
        if page_type not in PAGE_TYPES:
            errors.append(f"{field}.type must be one of: {', '.join(sorted(PAGE_TYPES))}")

        _counter(
            page.get("image_generation_count"),
            f"{field}.image_generation_count",
            0,
            MAX_GENERATION_ROUNDS,
            errors,
        )
        _counter(
            page.get("max_image_generations"),
            f"{field}.max_image_generations",
            1,
            MAX_GENERATION_ROUNDS,
            errors,
        )

        illustration = safe_relative_path(page.get("illustration"), f"{field}.illustration", errors)
        safe_relative_path(page.get("card"), f"{field}.card", errors)
        if illustration is not None and not (project_dir / illustration).is_file():
            errors.append(f"{field}.illustration: {illustration.name} does not exist")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path, help="post project directory")
    args = parser.parse_args(argv)

    errors = validate_project(args.project_dir)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {args.project_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

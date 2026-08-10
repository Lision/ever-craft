#!/usr/bin/env python3
"""Calculate per-page copy flow and illustration boxes before anchor generation."""

from __future__ import annotations

import argparse
import copy
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import yaml

from layout_engine import (
    LayoutOverflowError,
    calculate_page_layout,
    find_font_paths,
    merged_theme,
)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a YAML mapping")
    return value


def calculate_layouts(
    manifest: dict[str, Any],
    visual_bible: dict[str, Any],
) -> list[dict[str, Any]]:
    pages = manifest.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("manifest.pages must be a non-empty list")
    theme = merged_theme(visual_bible)
    regular_path, bold_path = find_font_paths(visual_bible)
    calculated: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, value in enumerate(pages):
        if not isinstance(value, dict):
            errors.append(f"pages[{index}] must be a mapping")
            continue
        page_number = f"{index + 1:02d} / {len(pages):02d}"
        try:
            snapshot, _ = calculate_page_layout(
                value,
                visual_bible,
                theme,
                regular_path,
                bold_path,
                page_number,
            )
        except (FileNotFoundError, LayoutOverflowError, ValueError) as error:
            errors.append(str(error))
            continue
        calculated.append(snapshot)
    if errors:
        raise LayoutOverflowError("\n".join(errors))
    return calculated


def write_layouts_atomically(
    manifest_path: Path,
    manifest: dict[str, Any],
    layouts: list[dict[str, Any]],
) -> None:
    updated = copy.deepcopy(manifest)
    for page, layout in zip(updated["pages"], layouts, strict=True):
        page["layout"] = layout
    temporary = manifest_path.with_name(
        f".{manifest_path.name}.{uuid.uuid4().hex}.layout.tmp"
    )
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(
                updated,
                handle,
                allow_unicode=True,
                sort_keys=False,
            )
        os.replace(temporary, manifest_path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="atomically write calculated layouts into manifest.yaml",
    )
    parser.add_argument("project_dir", type=Path, help="post project directory")
    args = parser.parse_args(argv)

    manifest_path = args.project_dir / "manifest.yaml"
    try:
        manifest = load_yaml(manifest_path)
        visual_bible_name = manifest.get("visual_bible")
        if visual_bible_name != "visual-bible.yaml":
            raise ValueError("manifest.visual_bible must be visual-bible.yaml")
        visual_bible = load_yaml(args.project_dir / visual_bible_name)
        layouts = calculate_layouts(manifest, visual_bible)
        if args.write:
            write_layouts_atomically(manifest_path, manifest, layouts)
    except (FileNotFoundError, LayoutOverflowError, OSError, ValueError, yaml.YAMLError) as error:
        for line in str(error).splitlines():
            print(f"ERROR: {line}", file=sys.stderr)
        return 1

    for page, layout in zip(manifest["pages"], layouts, strict=True):
        box = layout["illustration_box"]
        print(
            f"{page.get('id', 'page')}: "
            f"{box['width']}x{box['height']} at ({box['x']},{box['y']}), "
            f"illustration share {layout['illustration_share'] * 100:.1f}%"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

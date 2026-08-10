#!/usr/bin/env python3
"""Render validated WeChat card projects as deterministic PNG files."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from layout_engine import (
    LayoutOverflowError,
    assert_glyph_coverage,
    calculate_page_layout,
    find_font_paths,
    merged_theme,
    wrap_text,
)
from validate_manifest import load_yaml, validate_project


def _contain_illustration(
    canvas: Image.Image,
    illustration_path: Path,
    box: tuple[int, int, int, int],
) -> None:
    left, top, right, bottom = box
    max_size = (right - left, bottom - top)
    with Image.open(illustration_path) as source:
        illustration = source.convert("RGBA")
        illustration.thumbnail(max_size, Image.Resampling.LANCZOS)
    x = left + (max_size[0] - illustration.width) // 2
    y = top + (max_size[1] - illustration.height) // 2
    canvas.paste(illustration, (x, y), illustration.getchannel("A"))


def _validated_project(project_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    errors = validate_project(project_dir, phase="complete")
    if errors:
        raise ValueError("project validation failed:\n" + "\n".join(errors))
    manifest = load_yaml(project_dir / "manifest.yaml")
    visual_bible = load_yaml(project_dir / "visual-bible.yaml")
    return manifest, visual_bible, merged_theme(visual_bible)


def _prepare_card(
    project_dir: Path,
    manifest: dict[str, Any],
    visual_bible: dict[str, Any],
    theme: dict[str, Any],
    page_index: int,
    page: dict[str, Any],
) -> tuple[Image.Image, Path]:
    pages = manifest["pages"]
    regular_path, bold_path = find_font_paths(visual_bible)

    footer = f"{page_index + 1:02d} / {len(pages):02d}"
    signature = theme["footer"]["signature"]
    calculated_layout, runtime = calculate_page_layout(
        page,
        visual_bible,
        theme,
        regular_path,
        bold_path,
        footer,
    )
    if page.get("layout") != calculated_layout:
        raise LayoutOverflowError(
            f"{page['id']}: stored layout is stale; run calculate_layout.py --write "
            "before generating or rendering"
        )
    fonts = runtime["fonts"]

    canvas_config = theme["canvas"]
    palette = theme["palette"]
    layout = theme["layout"]
    width, height = canvas_config["width"], canvas_config["height"]
    margin_x = layout["margin_x"]
    canvas = Image.new("RGB", (width, height), palette["background"])
    draw = ImageDraw.Draw(canvas)

    fills = {
        "kicker": palette["accent"],
        "title": palette["ink"],
        "subtitle": palette["ink"],
        "body": palette["muted"],
        "emphasis": palette["annotation"],
    }
    for block in runtime["blocks"]:
        cursor_y = block["top"]
        for line in block["lines"]:
            draw.text(
                (margin_x, cursor_y),
                line,
                font=fonts[block["kind"]],
                fill=fills[block["kind"]],
                anchor="lt",
            )
            cursor_y += block["line_height"] + block["spacing"]

    draw.line(
        (
            margin_x,
            calculated_layout["divider_y"],
            width - margin_x,
            calculated_layout["divider_y"],
        ),
        fill=palette["divider"],
        width=2,
    )
    box = calculated_layout["illustration_box"]
    _contain_illustration(
        canvas,
        project_dir / page["illustration"],
        (
            box["x"],
            box["y"],
            box["x"] + box["width"],
            box["y"] + box["height"],
        ),
    )

    footer_y = runtime["footer_top"]
    if theme["footer"]["show_page_number"]:
        draw.text(
            (margin_x, footer_y),
            footer,
            font=fonts["footer"],
            fill=palette["annotation"],
            anchor="lt",
        )
    if signature:
        draw.text(
            (width - margin_x, footer_y),
            signature,
            font=fonts["footer"],
            fill=palette["annotation"],
            anchor="rt",
        )

    output = project_dir / "cards" / f"{page['id']}.png"
    return canvas, output


def _temporary_path(output: Path, purpose: str) -> Path:
    return output.with_name(
        f".{output.name}.{uuid.uuid4().hex}.{purpose}.tmp"
    )


def _save_card_atomically(canvas: Image.Image, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(output, "render")
    try:
        canvas.save(temporary, format="PNG", optimize=False, compress_level=9)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def render_card(project_dir: Path, page_id: str) -> Path:
    """Validate, draw typography, contain illustration, and atomically write PNG."""
    project_dir = Path(project_dir)
    manifest, visual_bible, theme = _validated_project(project_dir)
    pages = manifest["pages"]
    try:
        page_index, page = next(
            (index, value) for index, value in enumerate(pages) if value["id"] == page_id
        )
    except StopIteration as error:
        raise KeyError(f"unknown page id: {page_id}") from error

    canvas, output = _prepare_card(
        project_dir, manifest, visual_bible, theme, page_index, page
    )
    _save_card_atomically(canvas, output)
    return output


def render_all(project_dir: Path) -> list[Path]:
    """Render and return cards in manifest page order."""
    project_dir = Path(project_dir)
    manifest, visual_bible, theme = _validated_project(project_dir)
    prepared = [
        _prepare_card(project_dir, manifest, visual_bible, theme, index, page)
        for index, page in enumerate(manifest["pages"])
    ]

    staged: dict[Path, Path] = {}
    backups: dict[Path, Path] = {}
    published: list[Path] = []
    retained_backups: set[Path] = set()
    try:
        for canvas, output in prepared:
            output.parent.mkdir(parents=True, exist_ok=True)
            temporary = _temporary_path(output, "stage")
            staged[output] = temporary
            canvas.save(temporary, format="PNG", optimize=False, compress_level=9)
        for _, output in prepared:
            if output.exists():
                if not output.is_file():
                    raise OSError(f"card output is not a regular file: {output}")
                backup = _temporary_path(output, "backup")
                shutil.copy2(output, backup)
                backups[output] = backup
        try:
            for _, output in prepared:
                os.replace(staged[output], output)
                published.append(output)
        except OSError as publication_error:
            rollback_failures: list[tuple[Path, Path | None, OSError]] = []
            for output in reversed(published):
                backup = backups.get(output)
                try:
                    if backup is None:
                        output.unlink(missing_ok=True)
                    else:
                        os.replace(backup, output)
                except OSError as rollback_error:
                    if backup is not None:
                        retained_backups.add(backup)
                    rollback_failures.append((output, backup, rollback_error))
            if rollback_failures:
                details = []
                for output, backup, rollback_error in sorted(
                    rollback_failures, key=lambda failure: str(failure[0])
                ):
                    recovery = (
                        f"recovery backup retained at {backup}"
                        if backup is not None
                        else "original output did not exist; no recovery backup"
                    )
                    details.append(f"{output} ({recovery}): {rollback_error}")
                raise OSError(
                    "card publication failed and rollback was incomplete; "
                    f"publication error: {publication_error}; inconsistent outputs: "
                    + "; ".join(details)
                ) from publication_error
            raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
        for backup in backups.values():
            if backup not in retained_backups:
                backup.unlink(missing_ok=True)
    return [output for _, output in prepared]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path, help="post project directory")
    parser.add_argument("page_id", nargs="?", help="render only this page id")
    args = parser.parse_args(argv)

    try:
        outputs = (
            [render_card(args.project_dir, args.page_id)]
            if args.page_id
            else render_all(args.project_dir)
        )
    except (FileNotFoundError, KeyError, LayoutOverflowError, OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

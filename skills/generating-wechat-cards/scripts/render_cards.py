#!/usr/bin/env python3
"""Render validated WeChat card projects as deterministic PNG files."""

from __future__ import annotations

import argparse
import copy
import os
import sys
import uuid
from pathlib import Path
from typing import Any, cast

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

from validate_manifest import REQUIRED_FONT_FAMILY, load_yaml, validate_project


SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_THEME_PATH = SKILL_DIR / "assets" / "default-theme.yaml"
FONT_CANDIDATES = {
    "regular": [Path.home() / "Library/Fonts/MapleMono-NF-CN-Regular.ttf"],
    "bold": [Path.home() / "Library/Fonts/MapleMono-NF-CN-Bold.ttf"],
}
FOOTER_GAP = 40
KICKER_HEIGHT = 40
MIN_VERTICAL_GAP = 24
TITLE_TOP = 136
TITLE_HEIGHT = 260
BODY_TOP = 420
BODY_HEIGHT = 150
ILLUSTRATION_TOP = 660


class LayoutOverflowError(RuntimeError):
    """Raised when fixed theme typography cannot contain the supplied content."""


def _assert_font_metadata(font_path: Path, weight: str) -> None:
    with TTFont(font_path, lazy=True) as font:
        name_table = font["name"]
        family_names = {
            record.toUnicode()
            for record in name_table.names
            if record.nameID in (1, 16)
        }
        style_names = {
            record.toUnicode()
            for record in name_table.names
            if record.nameID in (2, 17)
        }
        os2 = font["OS/2"]
        weight_class = os2.usWeightClass
        is_italic = bool(os2.fsSelection & 0b1)
    if REQUIRED_FONT_FAMILY not in family_names:
        raise ValueError(f"{font_path}: expected {REQUIRED_FONT_FAMILY} font metadata")
    expected_style = weight.capitalize()
    expected_weight_class = {"regular": 400, "bold": 700}[weight]
    if (
        expected_style not in style_names
        or weight_class != expected_weight_class
        or is_italic
    ):
        raise ValueError(
            f"{font_path}: expected {REQUIRED_FONT_FAMILY} {weight} font metadata"
        )


def find_font_paths(visual_bible: dict[str, Any]) -> tuple[Path, Path]:
    """Honor explicit paths first, then known candidates; raise if absent."""
    typography = visual_bible.get("typography", {})
    if not isinstance(typography, dict) or typography.get("family") != REQUIRED_FONT_FAMILY:
        raise FileNotFoundError(f"required font family is {REQUIRED_FONT_FAMILY}")

    found: dict[str, Path] = {}
    for weight in ("regular", "bold"):
        explicit = typography.get(f"{weight}_path")
        if explicit is not None:
            path = Path(explicit).expanduser()
            if not path.is_file():
                raise FileNotFoundError(
                    f"{REQUIRED_FONT_FAMILY} {weight} font not found: {path}"
                )
            _assert_font_metadata(path, weight)
            found[weight] = path
            continue

        candidate = next(
            (candidate for candidate in FONT_CANDIDATES[weight] if candidate.is_file()),
            None,
        )
        if candidate is None:
            candidates = ", ".join(str(path) for path in FONT_CANDIDATES[weight])
            raise FileNotFoundError(
                f"{REQUIRED_FONT_FAMILY} {weight} font not found; checked: {candidates}"
            )
        _assert_font_metadata(candidate, weight)
        found[weight] = candidate

    return found["regular"], found["bold"]


def assert_glyph_coverage(font_path: Path, text: str) -> None:
    """Raise with uncovered non-whitespace characters; never substitute fonts."""
    with TTFont(font_path, lazy=True) as font:
        covered = set(cast(dict[int, str], font.getBestCmap() or {}))
    missing = sorted(
        {
            character
            for character in text
            if not character.isspace() and ord(character) not in covered
        }
    )
    if missing:
        labels = ", ".join(f"U+{ord(character):04X}" for character in missing)
        raise ValueError(f"{font_path}: uncovered glyph(s): {labels}")


def wrap_text(draw, text, font, max_width):
    """Wrap one Unicode character at a time and preserve explicit newlines."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        line = ""
        for character in paragraph:
            candidate = line + character
            if line and draw.textlength(candidate, font=font) > max_width:
                lines.append(line)
                line = character
            else:
                line = candidate
        lines.append(line)
    return lines


def draw_text_block(draw, text, xy, font, fill, max_width, max_height, spacing):
    """Draw wrapped text or raise LayoutOverflowError."""
    lines = wrap_text(draw, text, font, max_width)
    ascent, descent = font.getmetrics()
    line_height = ascent + descent
    height = line_height * len(lines) + spacing * max(0, len(lines) - 1)
    too_wide = any(draw.textlength(line, font=font) > max_width for line in lines)
    if too_wide or height > max_height:
        raise LayoutOverflowError(
            f"text does not fit {max_width}x{max_height} layout region: {text!r}"
        )

    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill, anchor="lt")
        y += line_height + spacing
    return y - spacing


def _merged_theme(visual_bible: dict[str, Any]) -> dict[str, Any]:
    theme = load_yaml(DEFAULT_THEME_PATH)
    for section in ("layout", "illustration"):
        overrides = visual_bible.get(section)
        if not isinstance(overrides, dict):
            continue
        for key in theme[section]:
            if key in overrides:
                theme[section][key] = copy.deepcopy(overrides[key])

    footer = visual_bible.get("footer")
    if isinstance(footer, dict) and "signature" in footer:
        theme["footer"]["signature"] = copy.deepcopy(footer["signature"])
    return theme


def _preflight_effective_layout(
    theme: dict[str, Any], footer_font: ImageFont.FreeTypeFont, page_number: str
) -> dict[str, int]:
    layout = theme["layout"]
    signature = theme["footer"]["signature"]
    if not isinstance(signature, str):
        raise ValueError("footer.signature must be a string")
    for field in ("margin_x", "margin_top", "margin_bottom", "illustration_height"):
        value = layout[field]
        if not isinstance(value, int) or isinstance(value, bool):
            raise LayoutOverflowError(f"layout.{field} must be an integer")
    margin_x = layout["margin_x"]
    content_width = theme["canvas"]["width"] - 2 * margin_x
    if margin_x < 0 or content_width <= 0:
        raise LayoutOverflowError(
            "layout.margin_x must be nonnegative and leave positive content width"
        )
    margin_top = layout["margin_top"]
    if (
        margin_top < 0
        or margin_top + KICKER_HEIGHT + MIN_VERTICAL_GAP > TITLE_TOP
    ):
        raise LayoutOverflowError(
            "layout.margin_top places the kicker outside or into the title region"
        )
    margin_bottom = layout["margin_bottom"]
    footer_height = sum(footer_font.getmetrics())
    footer_top = theme["canvas"]["height"] - margin_bottom - footer_height
    footer_bottom = footer_top + footer_height
    if (
        margin_bottom < 0
        or footer_top < 0
        or footer_bottom > theme["canvas"]["height"]
    ):
        raise LayoutOverflowError(
            "layout.margin_bottom places the footer outside the canvas"
        )
    illustration_height = layout["illustration_height"]
    illustration_bottom = ILLUSTRATION_TOP + illustration_height
    if (
        illustration_height <= 0
        or illustration_bottom > theme["canvas"]["height"]
        or illustration_bottom + MIN_VERTICAL_GAP > footer_top
    ):
        raise LayoutOverflowError(
            "layout.illustration_height places the illustration outside the canvas "
            "or into the footer region"
        )
    signature_width = footer_font.getlength(signature)
    if signature_width > content_width:
        raise LayoutOverflowError("footer signature exceeds the content width")
    page_number_width = footer_font.getlength(page_number)
    if theme["footer"]["show_page_number"] and page_number_width > content_width:
        raise LayoutOverflowError("footer page number exceeds the content width")
    if (
        theme["footer"]["show_page_number"]
        and signature
        and page_number_width + FOOTER_GAP + signature_width > content_width
    ):
        raise LayoutOverflowError("footer page number and signature overlap")
    return {"content_width": content_width, "footer_top": footer_top}


def _contain_illustration(
    canvas: Image.Image,
    illustration_path: Path,
    box: tuple[int, int, int, int],
) -> None:
    left, top, right, bottom = box
    max_size = (right - left, bottom - top)
    with Image.open(illustration_path) as source:
        illustration = source.convert("RGB")
        illustration.thumbnail(max_size, Image.Resampling.LANCZOS)
    x = left + (max_size[0] - illustration.width) // 2
    y = top + (max_size[1] - illustration.height) // 2
    canvas.paste(illustration, (x, y))


def render_card(project_dir: Path, page_id: str) -> Path:
    """Validate, draw typography, contain illustration, and atomically write PNG."""
    project_dir = Path(project_dir)
    errors = validate_project(project_dir)
    if errors:
        raise ValueError("project validation failed:\n" + "\n".join(errors))

    manifest = load_yaml(project_dir / "manifest.yaml")
    visual_bible = load_yaml(project_dir / manifest["visual_bible"])
    theme = _merged_theme(visual_bible)
    pages = manifest["pages"]
    try:
        page_index, page = next(
            (index, value) for index, value in enumerate(pages) if value["id"] == page_id
        )
    except StopIteration as error:
        raise KeyError(f"unknown page id: {page_id}") from error

    regular_path, bold_path = find_font_paths(visual_bible)
    scale = theme["typography_scale"]
    title_size = (
        scale["cover_title"]
        if page["type"] == "cover"
        else scale["standard_title"]
    )
    fonts = {
        "title": ImageFont.truetype(str(bold_path), title_size),
        "kicker": ImageFont.truetype(str(regular_path), scale["kicker"]),
        "body": ImageFont.truetype(str(regular_path), scale["body"]),
        "footer": ImageFont.truetype(str(regular_path), scale["footer"]),
    }

    footer = f"{page_index + 1:02d} / {len(pages):02d}"
    signature = theme["footer"]["signature"]
    geometry = _preflight_effective_layout(theme, fonts["footer"], footer)
    assert_glyph_coverage(bold_path, page["title"])
    assert_glyph_coverage(
        regular_path,
        "\n".join((page["kicker"], page["body"], footer, signature)),
    )

    canvas_config = theme["canvas"]
    palette = theme["palette"]
    layout = theme["layout"]
    width, height = canvas_config["width"], canvas_config["height"]
    margin_x = layout["margin_x"]
    content_width = geometry["content_width"]
    canvas = Image.new("RGB", (width, height), palette["background"])
    draw = ImageDraw.Draw(canvas)

    draw_text_block(
        draw,
        page["kicker"],
        (margin_x, layout["margin_top"]),
        fonts["kicker"],
        palette["accent"],
        content_width,
        KICKER_HEIGHT,
        0,
    )
    draw_text_block(
        draw,
        page["title"],
        (margin_x, TITLE_TOP),
        fonts["title"],
        palette["ink"],
        content_width,
        TITLE_HEIGHT,
        theme["line_spacing"]["title"],
    )
    draw_text_block(
        draw,
        page["body"],
        (margin_x, BODY_TOP),
        fonts["body"],
        palette["muted"],
        content_width,
        BODY_HEIGHT,
        theme["line_spacing"]["body"],
    )
    draw.line((margin_x, 610, width - margin_x, 610), fill=palette["divider"], width=2)

    _contain_illustration(
        canvas,
        project_dir / page["illustration"],
        (
            margin_x,
            ILLUSTRATION_TOP,
            width - margin_x,
            ILLUSTRATION_TOP + layout["illustration_height"],
        ),
    )

    footer_y = geometry["footer_top"]
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

    output = project_dir / page["card"]
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{uuid.uuid4().hex}.tmp")
    try:
        canvas.save(temporary, format="PNG", optimize=False, compress_level=9)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return output


def render_all(project_dir: Path) -> list[Path]:
    """Render and return cards in manifest page order."""
    project_dir = Path(project_dir)
    errors = validate_project(project_dir)
    if errors:
        raise ValueError("project validation failed:\n" + "\n".join(errors))
    manifest = load_yaml(project_dir / "manifest.yaml")
    return [render_card(project_dir, page["id"]) for page in manifest["pages"]]


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
    except (FileNotFoundError, KeyError, LayoutOverflowError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

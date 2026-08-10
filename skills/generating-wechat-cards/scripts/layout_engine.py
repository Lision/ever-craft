#!/usr/bin/env python3
"""Shared deterministic layout calculations for WeChat cards."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont


SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_THEME_PATH = SKILL_DIR / "assets" / "default-theme.yaml"
REQUIRED_FONT_FAMILY = "Maple Mono NF CN"
LAYOUT_VERSION = 1
FOOTER_GAP = 40
FONT_CANDIDATES = {
    "regular": [Path.home() / "Library/Fonts/MapleMono-NF-CN-Regular.ttf"],
    "bold": [Path.home() / "Library/Fonts/MapleMono-NF-CN-Bold.ttf"],
}
LAYOUT_INTEGER_FIELDS = (
    "margin_x",
    "margin_top",
    "margin_bottom",
    "block_gap",
    "copy_to_divider_gap",
    "divider_to_illustration_gap",
    "illustration_to_footer_gap",
)


class LayoutOverflowError(RuntimeError):
    """Raised when approved copy leaves too little deterministic illustration space."""


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
    if (
        not isinstance(typography, dict)
        or typography.get("family") != REQUIRED_FONT_FAMILY
    ):
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
            (
                candidate
                for candidate in FONT_CANDIDATES[weight]
                if candidate.is_file()
            ),
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


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a YAML mapping")
    return value


def merged_theme(visual_bible: dict[str, Any]) -> dict[str, Any]:
    """Merge only supported post-level layout and illustration values."""
    theme = _load_yaml(DEFAULT_THEME_PATH)
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


def layout_fingerprint(
    page: dict[str, Any], visual_bible: dict[str, Any]
) -> str:
    """Fingerprint every input that can alter the calculated page geometry."""
    payload = {
        "version": LAYOUT_VERSION,
        "page": {
            key: page.get(key)
            for key in (
                "type",
                "kicker",
                "title",
                "subtitle",
                "body",
                "emphasis",
            )
        },
        "visual_bible": {
            "canvas": visual_bible.get("canvas"),
            "font_family": (
                visual_bible.get("typography", {}).get("family")
                if isinstance(visual_bible.get("typography"), dict)
                else None
            ),
            "layout": visual_bible.get("layout"),
            "footer": visual_bible.get("footer"),
        },
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_fonts(
    page: dict[str, Any],
    theme: dict[str, Any],
    regular_path: Path,
    bold_path: Path,
) -> dict[str, ImageFont.FreeTypeFont]:
    scale = theme["typography_scale"]
    title_size = (
        scale["cover_title"]
        if page.get("type") == "cover"
        else scale["standard_title"]
    )
    return {
        "title": ImageFont.truetype(str(bold_path), title_size),
        "kicker": ImageFont.truetype(str(regular_path), scale["kicker"]),
        "subtitle": ImageFont.truetype(str(regular_path), scale["subtitle"]),
        "body": ImageFont.truetype(str(regular_path), scale["body"]),
        "emphasis": ImageFont.truetype(str(bold_path), scale["emphasis"]),
        "footer": ImageFont.truetype(str(regular_path), scale["footer"]),
    }


def _layout_settings(theme: dict[str, Any]) -> dict[str, Any]:
    layout = theme["layout"]
    for field in LAYOUT_INTEGER_FIELDS:
        value = layout.get(field)
        if not isinstance(value, int) or isinstance(value, bool):
            raise LayoutOverflowError(f"layout.{field} must be an integer")
        if value < 0:
            raise LayoutOverflowError(f"layout.{field} must be nonnegative")
    minimum = layout.get("min_illustration_share")
    if (
        not isinstance(minimum, (int, float))
        or isinstance(minimum, bool)
        or not 0 < minimum < 1
    ):
        raise LayoutOverflowError(
            "layout.min_illustration_share must be between 0 and 1"
        )
    return layout


def _footer_geometry(
    theme: dict[str, Any],
    footer_font: ImageFont.FreeTypeFont,
    page_number: str,
    content_width: int,
) -> dict[str, int]:
    layout = theme["layout"]
    signature = theme["footer"]["signature"]
    if not isinstance(signature, str):
        raise ValueError("footer.signature must be a string")
    footer_height = sum(footer_font.getmetrics())
    footer_top = theme["canvas"]["height"] - layout["margin_bottom"] - footer_height
    if footer_top < layout["margin_top"]:
        raise LayoutOverflowError(
            "layout margins leave no content space above the footer"
        )
    signature_width = footer_font.getlength(signature)
    page_number_width = footer_font.getlength(page_number)
    if signature_width > content_width:
        raise LayoutOverflowError("footer signature exceeds the content width")
    if theme["footer"]["show_page_number"] and page_number_width > content_width:
        raise LayoutOverflowError("footer page number exceeds the content width")
    if (
        theme["footer"]["show_page_number"]
        and signature
        and page_number_width + FOOTER_GAP + signature_width > content_width
    ):
        raise LayoutOverflowError("footer page number and signature overlap")
    return {"top": footer_top, "height": footer_height}


def _measure_block(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    spacing: int,
) -> dict[str, Any]:
    lines = wrap_text(draw, text, font, max_width)
    ascent, descent = font.getmetrics()
    line_height = ascent + descent
    height = line_height * len(lines) + spacing * max(0, len(lines) - 1)
    if any(draw.textlength(line, font=font) > max_width for line in lines):
        raise LayoutOverflowError(f"text exceeds the content width: {text!r}")
    return {
        "lines": lines,
        "height": height,
        "line_height": line_height,
        "spacing": spacing,
    }


def calculate_page_layout(
    page: dict[str, Any],
    visual_bible: dict[str, Any],
    theme: dict[str, Any],
    regular_path: Path,
    bold_path: Path,
    page_number: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the persistent snapshot and draw-time measurements for one page."""
    layout = _layout_settings(theme)
    width = theme["canvas"]["width"]
    height = theme["canvas"]["height"]
    margin_x = layout["margin_x"]
    content_width = width - 2 * margin_x
    if content_width <= 0:
        raise LayoutOverflowError(
            "layout.margin_x must leave positive content width"
        )
    if layout["margin_top"] >= height or layout["margin_bottom"] >= height:
        raise LayoutOverflowError("layout vertical margins must stay inside the canvas")

    fonts = build_fonts(page, theme, regular_path, bold_path)
    emphasis = " / ".join(page.get("emphasis", []))
    assert_glyph_coverage(
        bold_path,
        str(page.get("title", "")) + emphasis,
    )
    assert_glyph_coverage(
        regular_path,
        "\n".join(
            (
                str(page.get("kicker", "")),
                str(page.get("subtitle", "")),
                str(page.get("body", "")),
                page_number,
                str(theme["footer"]["signature"]),
            )
        ),
    )

    scratch = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(scratch)
    footer = _footer_geometry(theme, fonts["footer"], page_number, content_width)
    illustration_bottom = footer["top"] - layout["illustration_to_footer_gap"]
    usable_height = illustration_bottom - layout["margin_top"]
    if usable_height <= 0:
        raise LayoutOverflowError(
            "margins and footer leave no usable content area"
        )

    copy = (
        ("kicker", str(page.get("kicker", ""))),
        ("title", str(page.get("title", ""))),
        ("subtitle", str(page.get("subtitle", ""))),
        ("body", str(page.get("body", ""))),
        ("emphasis", emphasis),
    )
    blocks: list[dict[str, Any]] = []
    cursor_y = layout["margin_top"]
    for kind, text in copy:
        if not text:
            continue
        if blocks:
            cursor_y += layout["block_gap"]
        measured = _measure_block(
            draw,
            text,
            fonts[kind],
            content_width,
            theme["line_spacing"].get(kind, 0),
        )
        blocks.append(
            {
                "kind": kind,
                "text": text,
                "top": cursor_y,
                **measured,
            }
        )
        cursor_y += measured["height"]

    copy_bottom = cursor_y
    divider_y = copy_bottom + layout["copy_to_divider_gap"]
    illustration_top = divider_y + layout["divider_to_illustration_gap"]
    illustration_height = illustration_bottom - illustration_top
    illustration_share = illustration_height / usable_height
    minimum = float(layout["min_illustration_share"])
    if illustration_height <= 0 or illustration_share < minimum:
        actual = max(0.0, illustration_share) * 100
        required = minimum * 100
        raise LayoutOverflowError(
            f"{page.get('id', 'page')}: illustration space is {actual:.1f}% "
            f"of the usable content area, below the required {required:.0f}%; "
            "return to Gate 1 and shorten or split the copy"
        )

    snapshot = {
        "version": LAYOUT_VERSION,
        "fingerprint": layout_fingerprint(page, visual_bible),
        "copy_bottom": copy_bottom,
        "divider_y": divider_y,
        "illustration_box": {
            "x": margin_x,
            "y": illustration_top,
            "width": content_width,
            "height": illustration_height,
        },
        "illustration_share": round(illustration_share, 4),
    }
    runtime = {
        "fonts": fonts,
        "blocks": blocks,
        "footer_top": footer["top"],
        "content_width": content_width,
    }
    return snapshot, runtime

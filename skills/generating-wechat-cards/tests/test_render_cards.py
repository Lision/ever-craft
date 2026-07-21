import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))
from render_cards import (
    LayoutOverflowError,
    assert_glyph_coverage,
    find_font_paths,
    render_all,
    render_card,
    wrap_text,
)


REGULAR_FONT = Path("/Users/lision/Library/Fonts/MapleMono-NF-CN-Regular.ttf")
BOLD_FONT = Path("/Users/lision/Library/Fonts/MapleMono-NF-CN-Bold.ttf")
IMPOSTOR_FONT = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
ILLUSTRATION_COLORS = {"p01": "#012FA7", "p02": "#854953"}


class CardRendererTests(unittest.TestCase):
    def setUp(self):
        missing_fonts = [path for path in (REGULAR_FONT, BOLD_FONT) if not path.is_file()]
        if missing_fonts:
            self.skipTest(
                "Maple Mono NF CN test fonts are unavailable: "
                + ", ".join(str(path) for path in missing_fonts)
            )

        self.temp_dir = tempfile.TemporaryDirectory()
        self.project = Path(self.temp_dir.name)
        fixture = SKILL_DIR / "tests" / "fixtures"
        for name in ("source.md", "manifest.yaml", "visual-bible.yaml"):
            shutil.copy2(fixture / name, self.project / name)

        (self.project / "illustrations").mkdir()
        for page_id, color in ILLUSTRATION_COLORS.items():
            Image.new("RGB", (800, 520), color).save(
                self.project / "illustrations" / f"{page_id}-v01.png"
            )

        self.mutate(
            "visual-bible.yaml",
            lambda data: data["typography"].update(
                regular_path=str(REGULAR_FONT), bold_path=str(BOLD_FONT)
            ),
        )

    def tearDown(self):
        if hasattr(self, "temp_dir"):
            self.temp_dir.cleanup()

    def mutate(self, filename, callback):
        path = self.project / filename
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        callback(data)
        path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def test_render_card_has_fixed_dimensions_and_exact_colors(self):
        card = render_card(self.project, "p01")

        with Image.open(card) as image:
            self.assertEqual(image.size, (1080, 1440))
            self.assertEqual(image.getpixel((20, 20)), (250, 250, 248))
            self.assertEqual(image.getpixel((540, 920)), (1, 47, 167))

    def test_visual_bible_cannot_override_fixed_typography_scale(self):
        card = render_card(self.project, "p01")
        expected_png = card.read_bytes()
        self.mutate(
            "visual-bible.yaml",
            lambda data: data.update(typography_scale={"cover_title": 12}),
        )

        render_card(self.project, "p01")

        self.assertEqual(card.read_bytes(), expected_png)

    def test_render_all_uses_manifest_page_order(self):
        project = self.project
        self.assertEqual(
            [path.name for path in render_all(project)], ["p01.png", "p02.png"]
        )

    def test_render_all_validates_before_reading_pages(self):
        self.mutate("manifest.yaml", lambda data: data.update(pages=[]))

        with self.assertRaises(ValueError) as invalid_project_exception:
            render_all(self.project)

        self.assertIn(
            "pages: expected a non-empty list",
            str(invalid_project_exception.exception),
        )

    def test_missing_explicit_font_reports_required_family(self):
        visual_bible = {
            "typography": {
                "family": "Maple Mono NF CN",
                "regular_path": "/missing/MapleMono-NF-CN-Regular.ttf",
                "bold_path": "/missing/MapleMono-NF-CN-Bold.ttf",
            }
        }

        with self.assertRaises(FileNotFoundError) as missing_font_exception:
            find_font_paths(visual_bible)

        self.assertIn("Maple Mono NF CN", str(missing_font_exception.exception))

    def test_rejects_existing_non_maple_explicit_font(self):
        if not IMPOSTOR_FONT.is_file():
            self.skipTest(f"non-Maple system test font is unavailable: {IMPOSTOR_FONT}")
        visual_bible = {
            "typography": {
                "family": "Maple Mono NF CN",
                "regular_path": str(IMPOSTOR_FONT),
                "bold_path": str(BOLD_FONT),
            }
        }

        with self.assertRaises(ValueError) as impostor_font_exception:
            find_font_paths(visual_bible)

        self.assertIn("Maple Mono NF CN", str(impostor_font_exception.exception))

    def test_rejects_swapped_maple_font_weights(self):
        visual_bible = {
            "typography": {
                "family": "Maple Mono NF CN",
                "regular_path": str(BOLD_FONT),
                "bold_path": str(REGULAR_FONT),
            }
        }

        with self.assertRaises(ValueError) as wrong_weight_exception:
            find_font_paths(visual_bible)

        self.assertIn("regular", str(wrong_weight_exception.exception))

    def test_missing_glyph_fails_preflight(self):
        with self.assertRaises(ValueError) as missing_glyph_exception:
            assert_glyph_coverage(REGULAR_FONT, "\U0010ffff")

        self.assertIn("uncovered glyph", str(missing_glyph_exception.exception))

    def test_wrap_text_preserves_explicit_newlines(self):
        image = Image.new("RGB", (400, 200), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(str(REGULAR_FONT), 34)

        self.assertEqual(wrap_text(draw, "甲乙\n丙丁", font, 400), ["甲乙", "丙丁"])

    def test_crowded_body_raises_layout_overflow(self):
        project = self.project
        self.mutate(
            "manifest.yaml",
            lambda data: data["pages"][1].update(body="过" * 2000),
        )

        self.assertRaises(LayoutOverflowError, render_card, project, "p02")

    def test_layout_fields_require_non_boolean_integers(self):
        for field in (
            "margin_x",
            "margin_top",
            "margin_bottom",
            "illustration_height",
        ):
            with self.subTest(field=field):
                self.mutate(
                    "visual-bible.yaml",
                    lambda data, field=field: data["layout"].update({field: True}),
                )

                with self.assertRaises(LayoutOverflowError) as layout_exception:
                    render_card(self.project, "p01")

                self.assertIn(f"layout.{field}", str(layout_exception.exception))
                self.mutate(
                    "visual-bible.yaml",
                    lambda data, field=field: data["layout"].update(
                        {
                            field: {
                                "margin_x": 80,
                                "margin_top": 72,
                                "margin_bottom": 72,
                                "illustration_height": 520,
                            }[field]
                        }
                    ),
                )

    def test_margin_x_requires_nonnegative_positive_content_width(self):
        for value in (-1, 540):
            with self.subTest(value=value):
                self.mutate(
                    "visual-bible.yaml",
                    lambda data, value=value: data["layout"].update(margin_x=value),
                )

                with self.assertRaises(LayoutOverflowError) as layout_exception:
                    render_card(self.project, "p01")

                self.assertIn("layout.margin_x", str(layout_exception.exception))
                self.mutate(
                    "visual-bible.yaml",
                    lambda data: data["layout"].update(margin_x=80),
                )

    def test_vertical_margins_keep_text_and_footer_inside_canvas(self):
        for field, value, default in (
            ("margin_top", 2000, 72),
            ("margin_bottom", -1000, 72),
        ):
            with self.subTest(field=field, value=value):
                self.mutate(
                    "visual-bible.yaml",
                    lambda data, field=field, value=value: data["layout"].update(
                        {field: value}
                    ),
                )

                with self.assertRaises(LayoutOverflowError) as layout_exception:
                    render_card(self.project, "p01")

                self.assertIn(f"layout.{field}", str(layout_exception.exception))
                self.mutate(
                    "visual-bible.yaml",
                    lambda data, field=field, default=default: data["layout"].update(
                        {field: default}
                    ),
                )

    def test_illustration_region_stays_inside_canvas_without_footer_overlap(self):
        for value in (1000, 700):
            with self.subTest(value=value):
                self.mutate(
                    "visual-bible.yaml",
                    lambda data, value=value: data["layout"].update(
                        illustration_height=value
                    ),
                )

                with self.assertRaises(LayoutOverflowError) as layout_exception:
                    render_card(self.project, "p01")

                self.assertIn(
                    "layout.illustration_height", str(layout_exception.exception)
                )
                self.mutate(
                    "visual-bible.yaml",
                    lambda data: data["layout"].update(illustration_height=520),
                )

    def test_footer_signature_outside_content_width_raises_layout_overflow(self):
        self.mutate(
            "visual-bible.yaml",
            lambda data: data.update(footer={"signature": "S" * 100}),
        )

        self.assertRaises(LayoutOverflowError, render_card, self.project, "p01")

    def test_footer_signature_collision_raises_layout_overflow(self):
        self.mutate(
            "visual-bible.yaml",
            lambda data: data.update(footer={"signature": "S" * 65}),
        )

        self.assertRaises(LayoutOverflowError, render_card, self.project, "p01")

    def test_footer_signature_requires_string(self):
        self.mutate(
            "visual-bible.yaml",
            lambda data: data.update(footer={"signature": 42}),
        )

        with self.assertRaises(ValueError) as signature_exception:
            render_card(self.project, "p01")

        self.assertIn("footer.signature", str(signature_exception.exception))


if __name__ == "__main__":
    unittest.main()

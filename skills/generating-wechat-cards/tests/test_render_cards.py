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

    def test_render_all_uses_manifest_page_order(self):
        project = self.project
        self.assertEqual(
            [path.name for path in render_all(project)], ["p01.png", "p02.png"]
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


if __name__ == "__main__":
    unittest.main()

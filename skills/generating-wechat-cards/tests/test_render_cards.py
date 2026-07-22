import shutil
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
        Image.new("RGB", (64, 64), "white").save(self.project / "style-anchor.png")
        Image.new("RGB", (64, 64), "white").save(
            self.project / "character-sheet.png"
        )
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

    def test_transparent_illustration_blends_with_exact_background(self):
        illustration = Image.new("RGBA", (800, 520), (0, 0, 0, 0))
        illustration.putpixel((400, 260), (1, 47, 167, 255))
        illustration.save(self.project / "illustrations" / "p01-v01.png")

        card = render_card(self.project, "p01")

        with Image.open(card) as image:
            self.assertEqual(image.getpixel((140, 700)), (250, 250, 248))
            self.assertEqual(image.getpixel((540, 960)), (1, 47, 167))

    def test_subtitle_and_emphasis_each_change_rendered_pixels(self):
        card = render_card(self.project, "p01")
        baseline = card.read_bytes()

        self.mutate(
            "manifest.yaml",
            lambda data: data["pages"][0].update(subtitle="完全不同的副标题"),
        )
        render_card(self.project, "p01")
        subtitle_output = card.read_bytes()
        self.assertNotEqual(subtitle_output, baseline)

        self.mutate(
            "manifest.yaml",
            lambda data: data["pages"][0].update(emphasis=["全新强调"]),
        )
        render_card(self.project, "p01")
        self.assertNotEqual(card.read_bytes(), subtitle_output)

    def test_subtitle_and_emphasis_are_in_glyph_preflight(self):
        for field, value in (
            ("subtitle", "\U0010ffff"),
            ("emphasis", ["\U0010ffff"]),
        ):
            with self.subTest(field=field):
                self.mutate(
                    "manifest.yaml",
                    lambda data, field=field, value=value: data["pages"][0].update(
                        {field: value}
                    ),
                )
                with self.assertRaisesRegex(ValueError, "uncovered glyph"):
                    render_card(self.project, "p01")
                self.mutate(
                    "manifest.yaml",
                    lambda data, field=field: data["pages"][0].update(
                        {field: "有效副标题" if field == "subtitle" else []}
                    ),
                )

    def test_unsupported_glyph_in_nondisplayed_metadata_is_not_preflighted(self):
        self.mutate(
            "manifest.yaml",
            lambda data: data["pages"][0].update(compressible=["\U0010ffff"]),
        )

        output = render_card(self.project, "p01")

        self.assertTrue(output.is_file())

    def test_subtitle_and_emphasis_overflow_fixed_regions(self):
        for field, value in (
            ("subtitle", "过" * 1000),
            ("emphasis", ["过" * 1000]),
        ):
            with self.subTest(field=field):
                self.mutate(
                    "manifest.yaml",
                    lambda data, field=field, value=value: data["pages"][0].update(
                        {field: value}
                    ),
                )
                with self.assertRaises(LayoutOverflowError):
                    render_card(self.project, "p01")
                self.mutate(
                    "manifest.yaml",
                    lambda data, field=field: data["pages"][0].update(
                        {field: "有效副标题" if field == "subtitle" else []}
                    ),
                )

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

    def _write_card_sentinels(self):
        cards = self.project / "cards"
        cards.mkdir(exist_ok=True)
        sentinels = {
            cards / "p01.png": b"old-p01",
            cards / "p02.png": b"old-p02",
        }
        for path, content in sentinels.items():
            path.write_bytes(content)
        return sentinels

    def _assert_sentinels_and_no_temps(self, sentinels):
        for path, content in sentinels.items():
            self.assertEqual(path.read_bytes(), content)
        self.assertEqual(list((self.project / "cards").glob(".*.tmp")), [])

    def test_render_all_later_overflow_preserves_entire_existing_set(self):
        sentinels = self._write_card_sentinels()
        self.mutate(
            "manifest.yaml",
            lambda data: data["pages"][1].update(body="过" * 2000),
        )

        with self.assertRaises(LayoutOverflowError):
            render_all(self.project)

        self._assert_sentinels_and_no_temps(sentinels)

    def test_render_all_later_save_failure_preserves_entire_existing_set(self):
        sentinels = self._write_card_sentinels()
        original_save = Image.Image.save
        call_count = 0

        def fail_second_save(image, path, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                original_save(image, path, *args, **kwargs)
                raise OSError("injected stage save failure")
            return original_save(image, path, *args, **kwargs)

        with mock.patch.object(Image.Image, "save", new=fail_second_save):
            with self.assertRaisesRegex(OSError, "injected stage save failure"):
                render_all(self.project)

        self._assert_sentinels_and_no_temps(sentinels)

    def test_render_all_replace_failure_rolls_back_every_published_card(self):
        sentinels = self._write_card_sentinels()
        original_replace = os.replace
        publication_count = 0

        def fail_second_publication(source, destination):
            nonlocal publication_count
            if Path(destination).name in {"p01.png", "p02.png"}:
                publication_count += 1
                if publication_count == 2:
                    raise OSError("injected publish replace failure")
            return original_replace(source, destination)

        with mock.patch("render_cards.os.replace", side_effect=fail_second_publication):
            with self.assertRaisesRegex(OSError, "injected publish replace failure"):
                render_all(self.project)

        self._assert_sentinels_and_no_temps(sentinels)

    def test_render_all_rollback_replace_failure_retains_recovery_backup(self):
        sentinels = self._write_card_sentinels()
        original_replace = os.replace

        def fail_publication_then_rollback(source, destination):
            source = Path(source)
            destination = Path(destination)
            if destination.name == "p02.png" and ".stage.tmp" in source.name:
                raise OSError("injected p02 publication failure")
            if destination.name == "p01.png" and ".backup.tmp" in source.name:
                raise OSError("injected p01 rollback failure")
            return original_replace(source, destination)

        with mock.patch(
            "render_cards.os.replace", side_effect=fail_publication_then_rollback
        ):
            with self.assertRaises(OSError) as rollback_exception:
                render_all(self.project)

        recovery_backups = list(
            (self.project / "cards").glob(".p01.png.*.backup.tmp")
        )
        self.assertEqual(len(recovery_backups), 1)
        self.assertEqual(
            recovery_backups[0].read_bytes(),
            sentinels[self.project / "cards" / "p01.png"],
        )
        message = str(rollback_exception.exception)
        self.assertIn("injected p02 publication failure", message)
        self.assertIn("injected p01 rollback failure", message)
        self.assertIn(str(self.project / "cards" / "p01.png"), message)
        self.assertIn(str(recovery_backups[0]), message)
        self.assertEqual(
            list((self.project / "cards").glob(".*.tmp")), recovery_backups
        )

    def test_render_all_reports_failed_removal_of_new_output_without_backup(self):
        original_replace = os.replace
        original_unlink = Path.unlink
        p01 = self.project / "cards" / "p01.png"

        def fail_second_publication(source, destination):
            if Path(destination).name == "p02.png":
                raise OSError("injected p02 publication failure")
            return original_replace(source, destination)

        def fail_published_output_removal(path, *args, **kwargs):
            if path == p01:
                raise OSError("injected p01 removal failure")
            return original_unlink(path, *args, **kwargs)

        with mock.patch(
            "render_cards.os.replace", side_effect=fail_second_publication
        ), mock.patch.object(Path, "unlink", new=fail_published_output_removal):
            with self.assertRaises(OSError) as rollback_exception:
                render_all(self.project)

        message = str(rollback_exception.exception)
        self.assertIn("injected p02 publication failure", message)
        self.assertIn("injected p01 removal failure", message)
        self.assertIn(str(p01), message)
        self.assertIn("original output did not exist", message)
        self.assertIn("no recovery backup", message)
        self.assertTrue(p01.is_file())
        self.assertEqual(list((self.project / "cards").glob(".*.tmp")), [])

    def test_single_card_save_failure_preserves_output_and_cleans_temp(self):
        sentinels = self._write_card_sentinels()
        original_save = Image.Image.save

        def save_then_fail(image, path, *args, **kwargs):
            original_save(image, path, *args, **kwargs)
            raise OSError("injected save failure")

        with mock.patch.object(Image.Image, "save", new=save_then_fail):
            with self.assertRaisesRegex(OSError, "injected save failure"):
                render_card(self.project, "p01")
        self._assert_sentinels_and_no_temps(sentinels)

    def test_single_card_replace_failure_preserves_output_and_cleans_temp(self):
        sentinels = self._write_card_sentinels()
        with mock.patch(
            "render_cards.os.replace", side_effect=OSError("injected replace failure")
        ):
            with self.assertRaisesRegex(OSError, "injected replace failure"):
                render_card(self.project, "p01")
        self._assert_sentinels_and_no_temps(sentinels)

    def test_renderer_refuses_noncanonical_card_before_touching_source(self):
        source_before = (self.project / "source.md").read_bytes()
        self.mutate(
            "manifest.yaml",
            lambda data: data["pages"][0].update(card="source.md"),
        )
        with self.assertRaisesRegex(ValueError, "cards/p01.png"):
            render_card(self.project, "p01")
        self.assertEqual((self.project / "source.md").read_bytes(), source_before)

    def test_cli_reports_oserror_without_traceback(self):
        cards = self.project / "cards"
        cards.mkdir()
        (cards / "p01.png").mkdir()
        result = subprocess.run(
            [
                sys.executable,
                str(SKILL_DIR / "scripts" / "render_cards.py"),
                str(self.project),
                "p01",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(result.stdout, "")

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

    def test_page_number_must_fit_without_signature(self):
        self.mutate(
            "manifest.yaml",
            lambda data: data["pages"][0].update(
                title="I", kicker="I", body="I", must_keep=[]
            ),
        )
        self.mutate(
            "visual-bible.yaml",
            lambda data: data["layout"].update(margin_x=500),
        )

        with self.assertRaises(LayoutOverflowError) as page_number_exception:
            render_card(self.project, "p01")

        self.assertIn("page number", str(page_number_exception.exception))

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

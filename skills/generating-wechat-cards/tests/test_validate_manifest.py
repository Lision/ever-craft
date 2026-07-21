import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from PIL import Image

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))
from validate_manifest import validate_project


EXPECTED_PALETTE = {
    "background": "#FAFAF8",
    "surface": "#F0F0EE",
    "ink": "#0A0A08",
    "solid": "#000000",
    "accent": "#012FA7",
    "annotation": "#854953",
    "muted": "#747472",
    "divider": "#D1D1CF",
}


class ManifestValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project = Path(self.temp_dir.name)
        fixture = SKILL_DIR / "tests" / "fixtures"
        for name in ("source.md", "manifest.yaml", "visual-bible.yaml"):
            shutil.copy2(fixture / name, self.project / name)
        (self.project / "illustrations").mkdir()
        for page_id in ("p01", "p02"):
            Image.new("RGB", (800, 520), "white").save(
                self.project / "illustrations" / f"{page_id}-v01.png"
            )

    def tearDown(self):
        self.temp_dir.cleanup()

    def mutate(self, filename, callback):
        path = self.project / filename
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        callback(data)
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def assert_error_contains(self, text):
        self.assertTrue(any(text in error for error in validate_project(self.project)))

    def test_valid_project_has_no_errors(self):
        self.assertEqual(validate_project(self.project), [])

    def test_rejects_canvas_other_than_1080_by_1440(self):
        self.mutate("visual-bible.yaml", lambda data: data["canvas"].update(width=1200))
        self.assert_error_contains("canvas must be exactly 1080x1440")

    def test_requires_maple_mono_nf_cn(self):
        self.mutate("visual-bible.yaml", lambda data: data["typography"].update(family="Arial"))
        self.assert_error_contains("typography.family must be Maple Mono NF CN")

    def test_rejects_wrong_value_for_every_palette_token(self):
        for token, expected in EXPECTED_PALETTE.items():
            with self.subTest(token=token):
                self.mutate(
                    "visual-bible.yaml",
                    lambda data, token=token: data["palette"].update({token: "wrong"}),
                )
                self.assert_error_contains(f"palette.{token} must be {expected}")
                self.mutate(
                    "visual-bible.yaml",
                    lambda data, token=token, expected=expected: data["palette"].update(
                        {token: expected}
                    ),
                )

    def test_requires_every_palette_token(self):
        for token, expected in EXPECTED_PALETTE.items():
            with self.subTest(token=token):
                self.mutate(
                    "visual-bible.yaml",
                    lambda data, token=token: data["palette"].pop(token),
                )
                self.assert_error_contains(f"palette.{token} must be {expected}")
                self.mutate(
                    "visual-bible.yaml",
                    lambda data, token=token, expected=expected: data["palette"].update(
                        {token: expected}
                    ),
                )

    def test_rejects_duplicate_page_ids(self):
        self.mutate("manifest.yaml", lambda data: data["pages"][1].update(id="p01"))
        self.assert_error_contains("duplicate page id: p01")

    def test_empty_page_mapping_reports_every_required_field(self):
        self.mutate("manifest.yaml", lambda data: data.update(pages=[{}]))
        errors = validate_project(self.project)
        for field in (
            "id",
            "type",
            "title",
            "kicker",
            "body",
            "visual_metaphor",
            "illustration_prompt",
            "image_generation_count",
            "max_image_generations",
            "illustration",
            "card",
            "status",
        ):
            with self.subTest(field=field):
                self.assertTrue(any(f"pages[0].{field}" in error for error in errors))

    def test_rejects_unknown_page_type(self):
        self.mutate("manifest.yaml", lambda data: data["pages"][0].update(type="poster"))
        self.assert_error_contains("pages[0].type")

    def test_rejects_generation_round_above_three(self):
        self.mutate("manifest.yaml", lambda data: data["post"].update(generation_round=4))
        self.assert_error_contains("post.generation_round must be between 0 and 3")

    def test_requires_post_max_generation_rounds_to_equal_three(self):
        self.mutate("manifest.yaml", lambda data: data["post"].update(max_generation_rounds=2))
        self.assert_error_contains("post.max_generation_rounds must be exactly 3")

    def test_rejects_post_round_above_configured_maximum(self):
        self.mutate(
            "manifest.yaml",
            lambda data: data["post"].update(generation_round=3, max_generation_rounds=2),
        )
        self.assert_error_contains(
            "post.generation_round must not exceed post.max_generation_rounds"
        )

    def test_rejects_page_generation_count_above_three(self):
        self.mutate("manifest.yaml", lambda data: data["pages"][0].update(image_generation_count=4))
        self.assert_error_contains("pages[0].image_generation_count must be between 0 and 3")

    def test_requires_page_max_image_generations_to_equal_three(self):
        self.mutate(
            "manifest.yaml", lambda data: data["pages"][0].update(max_image_generations=2)
        )
        self.assert_error_contains("pages[0].max_image_generations must be exactly 3")

    def test_rejects_page_count_above_configured_maximum(self):
        self.mutate(
            "manifest.yaml",
            lambda data: data["pages"][0].update(
                image_generation_count=3, max_image_generations=2
            ),
        )
        self.assert_error_contains(
            "pages[0].image_generation_count must not exceed pages[0].max_image_generations"
        )

    def test_rejects_absolute_and_parent_paths(self):
        self.mutate("manifest.yaml", lambda data: data.update(source="../source.md"))
        self.assert_error_contains("source: path must stay inside the post directory")

    def test_rejects_source_symlink_resolving_outside_project(self):
        with tempfile.TemporaryDirectory() as external_dir:
            external_source = Path(external_dir) / "source.md"
            shutil.copy2(self.project / "source.md", external_source)
            (self.project / "source-link.md").symlink_to(external_source)
            self.mutate("manifest.yaml", lambda data: data.update(source="source-link.md"))
            self.assert_error_contains("source: path must stay inside the post directory")

    def test_rejects_visual_bible_symlink_resolving_outside_project(self):
        with tempfile.TemporaryDirectory() as external_dir:
            external_bible = Path(external_dir) / "visual-bible.yaml"
            shutil.copy2(self.project / "visual-bible.yaml", external_bible)
            (self.project / "visual-bible-link.yaml").symlink_to(external_bible)
            self.mutate(
                "manifest.yaml",
                lambda data: data.update(visual_bible="visual-bible-link.yaml"),
            )
            self.assert_error_contains(
                "visual_bible: path must stay inside the post directory"
            )

    def test_rejects_illustration_symlink_resolving_outside_project(self):
        with tempfile.TemporaryDirectory() as external_dir:
            external_image = Path(external_dir) / "p01-v01.png"
            shutil.copy2(self.project / "illustrations" / "p01-v01.png", external_image)
            (self.project / "illustrations" / "p01-link.png").symlink_to(external_image)
            self.mutate(
                "manifest.yaml",
                lambda data: data["pages"][0].update(
                    illustration="illustrations/p01-link.png"
                ),
            )
            self.assert_error_contains(
                "pages[0].illustration: path must stay inside the post directory"
            )

    def test_accepts_symlinks_resolving_inside_project(self):
        (self.project / "source-link.md").symlink_to(self.project / "source.md")
        (self.project / "visual-bible-link.yaml").symlink_to(
            self.project / "visual-bible.yaml"
        )
        (self.project / "illustrations" / "p01-link.png").symlink_to(
            self.project / "illustrations" / "p01-v01.png"
        )
        self.mutate(
            "manifest.yaml",
            lambda data: data.update(
                source="source-link.md", visual_bible="visual-bible-link.yaml"
            ),
        )
        self.mutate(
            "manifest.yaml",
            lambda data: data["pages"][0].update(
                illustration="illustrations/p01-link.png"
            ),
        )
        self.assertEqual(validate_project(self.project), [])

    def test_requires_existing_source_visual_bible_and_illustration(self):
        (self.project / "source.md").unlink()
        (self.project / "illustrations" / "p01-v01.png").unlink()
        errors = validate_project(self.project)
        self.assertTrue(any("source.md does not exist" in error for error in errors))
        self.assertTrue(any("p01-v01.png does not exist" in error for error in errors))

    def test_cli_reports_valid_project(self):
        result = subprocess.run(
            [sys.executable, str(SKILL_DIR / "scripts" / "validate_manifest.py"), str(self.project)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), f"OK: {self.project}")
        self.assertEqual(result.stderr, "")

    def test_cli_reports_errors_to_stderr(self):
        (self.project / "source.md").unlink()
        result = subprocess.run(
            [sys.executable, str(SKILL_DIR / "scripts" / "validate_manifest.py"), str(self.project)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR: source: source.md does not exist", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()

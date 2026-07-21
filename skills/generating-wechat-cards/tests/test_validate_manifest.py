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

    def test_rejects_duplicate_page_ids(self):
        self.mutate("manifest.yaml", lambda data: data["pages"][1].update(id="p01"))
        self.assert_error_contains("duplicate page id: p01")

    def test_rejects_unknown_page_type(self):
        self.mutate("manifest.yaml", lambda data: data["pages"][0].update(type="poster"))
        self.assert_error_contains("pages[0].type")

    def test_rejects_generation_round_above_three(self):
        self.mutate("manifest.yaml", lambda data: data["post"].update(generation_round=4))
        self.assert_error_contains("post.generation_round must be between 0 and 3")

    def test_rejects_page_generation_count_above_three(self):
        self.mutate("manifest.yaml", lambda data: data["pages"][0].update(image_generation_count=4))
        self.assert_error_contains("pages[0].image_generation_count must be between 0 and 3")

    def test_rejects_absolute_and_parent_paths(self):
        self.mutate("manifest.yaml", lambda data: data.update(source="../source.md"))
        self.assert_error_contains("source: path must stay inside the post directory")

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

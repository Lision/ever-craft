"""Run on macOS: python3 -m unittest discover -s skills/frontend-pr/tests -v."""

from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib


def write_png(path, width=320, height=600, rectangles=()):
    """Write deterministic RGB fixtures using only the Python standard library."""
    pixels = bytearray([240] * width * height * 3)
    for x, y, w, h, color in rectangles:
        for row in range(y, y + h):
            for column in range(x, x + w):
                offset = (row * width + column) * 3
                pixels[offset:offset + 3] = bytes(color)

    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data)))

    rows = b"".join(b"\0" + pixels[y * width * 3:(y + 1) * width * 3]
                    for y in range(height))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")
    )


@unittest.skipUnless(sys.platform == "darwin" and shutil.which("swiftc"),
                     "Requires macOS and Swift")
class ComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix="frontend-pr-build-")
        cls.addClassCleanup(cls.build.cleanup)
        cls.binary = Path(cls.build.name) / "before-after"
        script = Path(__file__).resolve().parents[1] / "scripts" / "before_after.swift"
        subprocess.run(["swiftc", str(script), "-o", str(cls.binary)],
                       check=True, capture_output=True, text=True)

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="frontend-pr-images-")
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.before = self.directory / "before.png"
        self.after = self.directory / "after.png"
        self.output = self.directory / "comparison.png"
        write_png(self.before)
        write_png(self.after, rectangles=[(100, 100, 40, 20, (200, 40, 60))])

    def run_comparison(self, *options):
        return subprocess.run(
            [str(self.binary), "--before", str(self.before), "--after", str(self.after),
             "--out", str(self.output), *options], capture_output=True, text=True,
        )

    def test_auto_crop_uses_top_left_coordinates(self):
        result = self.run_comparison()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("crop=0,40,320,140", result.stdout)
        self.assertEqual(struct.unpack(">II", self.output.read_bytes()[16:24]), (648, 140))

    def test_separate_changes_produce_separate_images(self):
        write_png(self.after, rectangles=[(100, 100, 40, 20, (200, 40, 60)),
                                          (180, 450, 40, 20, (40, 80, 200))])
        result = self.run_comparison()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("crop=0,40,320,140", result.stdout)
        self.assertIn("crop=0,390,320,140", result.stdout)
        self.assertTrue((self.directory / "comparison-1.png").exists())
        self.assertTrue((self.directory / "comparison-2.png").exists())
        self.assertFalse(self.output.exists())

    def test_identical_images_rejected_in_every_mode(self):
        shutil.copyfile(self.before, self.after)
        for options in [(), ("--full",), ("--crop", "0,0,320,600")]:
            with self.subTest(options=options):
                self.assertEqual(self.run_comparison(*options).returncode, 2)
                self.assertFalse(self.output.exists())

    def test_crop_checks_only_selected_pixels(self):
        for crop in ["0,300,320,100", "0,100,50,20"]:
            with self.subTest(crop=crop):
                self.assertEqual(self.run_comparison("--crop", crop).returncode, 2)
        result = self.run_comparison("--crop", "90,90,60,40")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("crop=90,90,60,40", result.stdout)

    def test_subtle_color_change_and_explicit_tolerance(self):
        write_png(self.after, rectangles=[(100, 100, 40, 20, (239, 240, 240))])
        self.assertEqual(self.run_comparison().returncode, 0)
        self.assertEqual(self.run_comparison("--tolerance", "1").returncode, 2)

    def test_full_screen(self):
        result = self.run_comparison("--full")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("crop=0,0,320,600", result.stdout)
        self.assertEqual(struct.unpack(">II", self.output.read_bytes()[16:24]), (648, 600))

    def test_invalid_inputs(self):
        for options in [("--crop", "0,0,320,600", "--full"),
                        ("--crop", "0,,0,320,600"), ("--crop", "900,900,5,5"),
                        ("--padding", "-1"), ("--gap", "bad"),
                        ("--tolerance", "256"), ("--unknown", "10")]:
            with self.subTest(options=options):
                self.assertEqual(self.run_comparison(*options).returncode, 1)
                self.assertFalse(self.output.exists())

    def test_mismatched_dimensions(self):
        write_png(self.after, width=321)
        result = self.run_comparison()
        self.assertEqual(result.returncode, 1)
        self.assertIn("differ in size", result.stderr)


if __name__ == "__main__":
    unittest.main()

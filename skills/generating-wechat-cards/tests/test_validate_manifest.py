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
        Image.new("RGB", (64, 64), "white").save(self.project / "style-anchor.png")
        Image.new("RGB", (64, 64), "white").save(
            self.project / "character-sheet.png"
        )
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

    def test_canvas_dimensions_require_actual_integers(self):
        for dimension, expected in (("width", 1080), ("height", 1440)):
            for invalid in (float(expected), True, False):
                with self.subTest(dimension=dimension, invalid=invalid):
                    self.mutate(
                        "visual-bible.yaml",
                        lambda data, dimension=dimension, invalid=invalid: data[
                            "canvas"
                        ].update({dimension: invalid}),
                    )
                    errors = validate_project(self.project)
                    self.mutate(
                        "visual-bible.yaml",
                        lambda data, dimension=dimension, expected=expected: data[
                            "canvas"
                        ].update({dimension: expected}),
                    )
                    self.assertTrue(
                        any("canvas must be exactly 1080x1440" in error for error in errors)
                    )

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
            "subtitle",
            "body",
            "emphasis",
            "must_keep",
            "compressible",
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

    def test_requires_subtitle_as_a_nonempty_string(self):
        for invalid in (None, "", [], 42):
            with self.subTest(invalid=invalid):
                self.mutate(
                    "manifest.yaml",
                    lambda data, invalid=invalid: data["pages"][0].update(
                        subtitle=invalid
                    ),
                )
                self.assert_error_contains(
                    "pages[0].subtitle: expected a non-empty string"
                )
                self.mutate(
                    "manifest.yaml",
                    lambda data: data["pages"][0].update(subtitle="有效副标题"),
                )

    def test_requires_copy_metadata_as_lists_of_strings(self):
        for field in ("emphasis", "must_keep", "compressible"):
            for invalid in (None, "text", ["ok", 42]):
                with self.subTest(field=field, invalid=invalid):
                    self.mutate(
                        "manifest.yaml",
                        lambda data, field=field, invalid=invalid: data["pages"][0].update(
                            {field: invalid}
                        ),
                    )
                    self.assert_error_contains(
                        f"pages[0].{field}: expected a list of strings"
                    )
                    self.mutate(
                        "manifest.yaml",
                        lambda data, field=field: data["pages"][0].update({field: []}),
                    )

    def test_validation_does_not_modify_manifest(self):
        before = (self.project / "manifest.yaml").read_bytes()
        validate_project(self.project, phase="pre-generation", page_ids=["p01"])
        self.assertEqual((self.project / "manifest.yaml").read_bytes(), before)

    def test_rejects_unknown_page_type(self):
        self.mutate("manifest.yaml", lambda data: data["pages"][0].update(type="poster"))
        self.assert_error_contains("pages[0].type")

    def test_rejects_non_string_page_type_without_crashing(self):
        self.mutate("manifest.yaml", lambda data: data["pages"][0].update(type=[]))
        errors = validate_project(self.project)
        self.assertTrue(
            any("pages[0].type: expected a string" in error for error in errors)
        )

    def test_cli_reports_non_string_page_type_without_traceback(self):
        self.mutate("manifest.yaml", lambda data: data["pages"][0].update(type=[]))
        result = subprocess.run(
            [sys.executable, str(SKILL_DIR / "scripts" / "validate_manifest.py"), str(self.project)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR: pages[0].type: expected a string", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_rejects_generation_round_above_three(self):
        self.mutate("manifest.yaml", lambda data: data["post"].update(generation_round=4))
        self.assert_error_contains("post.generation_round must be between 0 and 3")

    def test_requires_post_max_generation_rounds_to_equal_three(self):
        self.mutate("manifest.yaml", lambda data: data["post"].update(max_generation_rounds=2))
        self.assert_error_contains("post.max_generation_rounds must be exactly 3")

    def test_post_max_generation_rounds_requires_an_actual_integer(self):
        for invalid in (3.0, True, False):
            with self.subTest(invalid=invalid):
                self.mutate(
                    "manifest.yaml",
                    lambda data, invalid=invalid: data["post"].update(
                        max_generation_rounds=invalid
                    ),
                )
                errors = validate_project(self.project)
                self.mutate(
                    "manifest.yaml",
                    lambda data: data["post"].update(max_generation_rounds=3),
                )
                self.assertTrue(
                    any(
                        "post.max_generation_rounds must be exactly 3" in error
                        for error in errors
                    )
                )

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

    def test_page_max_image_generations_requires_an_actual_integer(self):
        for invalid in (3.0, True, False):
            with self.subTest(invalid=invalid):
                self.mutate(
                    "manifest.yaml",
                    lambda data, invalid=invalid: data["pages"][0].update(
                        max_image_generations=invalid
                    ),
                )
                errors = validate_project(self.project)
                self.mutate(
                    "manifest.yaml",
                    lambda data: data["pages"][0].update(max_image_generations=3),
                )
                self.assertTrue(
                    any(
                        "pages[0].max_image_generations must be exactly 3" in error
                        for error in errors
                    )
                )

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

    def test_rejects_noncanonical_source_and_visual_bible_roles(self):
        for field, value, expected in (
            ("source", "article.md", "source must be exactly source.md"),
            (
                "visual_bible",
                "theme.yaml",
                "visual_bible must be exactly visual-bible.yaml",
            ),
        ):
            with self.subTest(field=field):
                self.mutate("manifest.yaml", lambda data: data.update({field: value}))
                self.assert_error_contains(expected)
                self.mutate(
                    "manifest.yaml",
                    lambda data: data.update(
                        {field: {"source": "source.md", "visual_bible": "visual-bible.yaml"}[field]}
                    ),
                )

    def test_rejects_card_paths_that_alias_canonical_inputs(self):
        for value in ("source.md", "manifest.yaml"):
            with self.subTest(value=value):
                self.mutate(
                    "manifest.yaml",
                    lambda data, value=value: data["pages"][0].update(card=value),
                )
                self.assert_error_contains("pages[0].card must be exactly cards/p01.png")
                self.mutate(
                    "manifest.yaml",
                    lambda data: data["pages"][0].update(card="cards/p01.png"),
                )

    def test_rejects_card_and_illustration_alias(self):
        self.mutate(
            "manifest.yaml",
            lambda data: data["pages"][0].update(card="illustrations/p01-v01.png"),
        )
        errors = validate_project(self.project)
        self.assertTrue(any("pages[0].card must be exactly cards/p01.png" in e for e in errors))
        self.assertTrue(any("artifact paths must be unique" in e for e in errors))

    def test_rejects_duplicate_card_paths(self):
        self.mutate(
            "manifest.yaml",
            lambda data: data["pages"][1].update(card="cards/p01.png"),
        )
        errors = validate_project(self.project)
        self.assertTrue(any("pages[1].card must be exactly cards/p02.png" in e for e in errors))
        self.assertTrue(any("artifact paths must be unique" in e for e in errors))

    def test_rejects_noncanonical_png_output_names(self):
        for field, value, expected in (
            ("card", "cards/p01.PNG", "pages[0].card must be exactly cards/p01.png"),
            (
                "illustration",
                "illustrations/p01.png",
                "pages[0].illustration must match illustrations/p01-vNN.png",
            ),
        ):
            with self.subTest(field=field):
                self.mutate(
                    "manifest.yaml",
                    lambda data, field=field, value=value: data["pages"][0].update(
                        {field: value}
                    ),
                )
                self.assert_error_contains(expected)
                self.mutate(
                    "manifest.yaml",
                    lambda data, field=field: data["pages"][0].update(
                        {
                            field: {
                                "card": "cards/p01.png",
                                "illustration": "illustrations/p01-v01.png",
                            }[field]
                        }
                    ),
                )

    def test_rejects_symlinked_output_parent_even_when_it_resolves_inside(self):
        (self.project / "real-cards").mkdir()
        (self.project / "cards").symlink_to(self.project / "real-cards", target_is_directory=True)
        self.assert_error_contains("pages[0].card: output path must not use symlinks")

    def test_rejects_symlinked_output_file_even_when_it_resolves_inside(self):
        (self.project / "cards").mkdir()
        (self.project / "cards" / "target.png").write_bytes(b"sentinel")
        (self.project / "cards" / "p01.png").symlink_to(
            self.project / "cards" / "target.png"
        )
        self.assert_error_contains("pages[0].card: output path must not use symlinks")

    def test_requires_existing_source_visual_bible_and_illustration(self):
        (self.project / "source.md").unlink()
        (self.project / "illustrations" / "p01-v01.png").unlink()
        errors = validate_project(self.project)
        self.assertTrue(any("source.md does not exist" in error for error in errors))
        self.assertTrue(any("p01-v01.png does not exist" in error for error in errors))

    def test_pre_generation_accepts_only_missing_illustration_files(self):
        for illustration in (self.project / "illustrations").iterdir():
            illustration.unlink()

        self.assertEqual(
            validate_project(self.project, phase="pre-generation"),
            [],
        )

    def test_both_phases_require_approved_gates_with_timestamps(self):
        for phase in ("pre-generation", "complete"):
            for gate in ("script", "anchor"):
                with self.subTest(phase=phase, gate=gate, missing="status"):
                    self.mutate(
                        "manifest.yaml",
                        lambda data, gate=gate: data["approvals"][gate].update(
                            status="pending"
                        ),
                    )
                    errors = validate_project(self.project, phase=phase)
                    self.assertTrue(
                        any(f"approvals.{gate}.status must be approved" in e for e in errors),
                        errors,
                    )
                    self.mutate(
                        "manifest.yaml",
                        lambda data, gate=gate: data["approvals"][gate].update(
                            status="approved"
                        ),
                    )
                with self.subTest(phase=phase, gate=gate, missing="timestamp"):
                    self.mutate(
                        "manifest.yaml",
                        lambda data, gate=gate: data["approvals"][gate].update(
                            approved_at=""
                        ),
                    )
                    errors = validate_project(self.project, phase=phase)
                    self.assertTrue(
                        any(
                            f"approvals.{gate}.approved_at: expected a non-empty string"
                            in e
                            for e in errors
                        ),
                        errors,
                    )
                    self.mutate(
                        "manifest.yaml",
                        lambda data, gate=gate: data["approvals"][gate].update(
                            approved_at="2026-07-21T10:10:00+08:00"
                        ),
                    )

    def test_both_phases_reject_draft_and_script_pending_states(self):
        for phase in ("pre-generation", "complete"):
            for status in ("draft", "script_pending"):
                with self.subTest(phase=phase, status=status):
                    self.mutate(
                        "manifest.yaml",
                        lambda data, status=status: data["post"].update(status=status),
                    )
                    errors = validate_project(self.project, phase=phase)
                    self.assertTrue(
                        any(f"post.status is not valid for {phase}" in e for e in errors),
                        errors,
                    )
                    self.mutate(
                        "manifest.yaml",
                        lambda data: data["post"].update(status="generating"),
                    )

    def test_pre_generation_requires_every_page_to_be_generating_or_revising(self):
        self.mutate(
            "manifest.yaml",
            lambda data: data["pages"][1].update(status="reviewing"),
        )
        errors = validate_project(
            self.project, phase="pre-generation", page_ids=["p01"]
        )
        self.assertTrue(
            any("pages[1].status is not valid for pre-generation" in e for e in errors),
            errors,
        )

    def test_both_phases_require_style_anchor_file(self):
        (self.project / "style-anchor.png").unlink()
        for phase in ("pre-generation", "complete"):
            with self.subTest(phase=phase):
                errors = validate_project(self.project, phase=phase)
                self.assertTrue(
                    any("anchors.style: style-anchor.png does not exist" in e for e in errors),
                    errors,
                )

    def test_character_anchor_is_required_only_when_characters_are_enabled(self):
        (self.project / "character-sheet.png").unlink()
        errors = validate_project(self.project, phase="complete")
        self.assertTrue(
            any("anchors.character: character-sheet.png does not exist" in e for e in errors),
            errors,
        )

        self.mutate(
            "visual-bible.yaml",
            lambda data: data["illustration"].update(character_enabled=False),
        )
        self.mutate(
            "manifest.yaml",
            lambda data: data["anchors"].update(character=None),
        )
        self.assertEqual(validate_project(self.project, phase="complete"), [])

    def test_character_enabled_requires_a_boolean(self):
        for invalid in (None, 1, "false"):
            with self.subTest(invalid=invalid):
                self.mutate(
                    "visual-bible.yaml",
                    lambda data, invalid=invalid: data["illustration"].update(
                        character_enabled=invalid
                    ),
                )
                self.assert_error_contains(
                    "illustration.character_enabled must be true or false"
                )
                self.mutate(
                    "visual-bible.yaml",
                    lambda data: data["illustration"].update(character_enabled=True),
                )

    def test_pre_generation_rejects_exhausted_set_but_complete_allows_it(self):
        self.mutate(
            "manifest.yaml",
            lambda data: data["post"].update(generation_round=3),
        )
        self.assertTrue(
            any(
                "post.generation_round has reached the generation limit" in e
                for e in validate_project(self.project, phase="pre-generation")
            )
        )
        self.assertEqual(validate_project(self.project, phase="complete"), [])

    def test_pre_generation_rejects_only_exhausted_target_pages(self):
        self.mutate(
            "manifest.yaml",
            lambda data: data["pages"][0].update(image_generation_count=3),
        )
        errors = validate_project(
            self.project, phase="pre-generation", page_ids=["p01"]
        )
        self.assertTrue(
            any("pages[0].image_generation_count has reached the generation limit" in e for e in errors),
            errors,
        )
        self.assertEqual(
            validate_project(self.project, phase="pre-generation", page_ids=["p02"]),
            [],
        )

    def test_complete_allows_page_generation_count_at_limit(self):
        self.mutate(
            "manifest.yaml",
            lambda data: data["pages"][0].update(image_generation_count=3),
        )
        self.assertEqual(validate_project(self.project, phase="complete"), [])

    def test_pre_generation_rejects_issue_unresolved_in_two_consecutive_rounds(self):
        reviews = self.project / "reviews"
        reviews.mkdir()
        for round_number in (1, 2):
            (reviews / f"round-{round_number:02d}.yaml").write_text(
                yaml.safe_dump(
                    {
                        "round": round_number,
                        "pages": [
                            {
                                "page": "p01",
                                "issues": [
                                    {
                                        "id": "p1-image-01",
                                        "resolution": "unresolved",
                                    }
                                ],
                            }
                        ],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

        errors = validate_project(
            self.project, phase="pre-generation", page_ids=["p01"]
        )
        self.assertTrue(
            any("p1-image-01 is unresolved in two consecutive review rounds" in e for e in errors),
            errors,
        )

    def test_targeted_pre_generation_only_permits_missing_target_illustrations(self):
        (self.project / "illustrations" / "p01-v01.png").unlink()
        self.assertEqual(
            validate_project(
                self.project, phase="pre-generation", page_ids=["p01"]
            ),
            [],
        )

        (self.project / "illustrations" / "p02-v01.png").unlink()
        errors = validate_project(
            self.project, phase="pre-generation", page_ids=["p01"]
        )
        self.assertTrue(
            any("pages[1].illustration: p02-v01.png does not exist" in e for e in errors),
            errors,
        )

    def test_pre_generation_rejects_unknown_target_page(self):
        errors = validate_project(
            self.project, phase="pre-generation", page_ids=["p99"]
        )
        self.assertIn("unknown target page id: p99", errors)

    def test_pre_generation_still_reports_all_other_validation_errors(self):
        for illustration in (self.project / "illustrations").iterdir():
            illustration.unlink()
        (self.project / "source.md").unlink()
        self.mutate(
            "manifest.yaml",
            lambda data: (
                data["post"].update(
                    status="not-a-workflow-state",
                    generation_round=4,
                    max_generation_rounds=2,
                ),
                data["pages"][0].update(
                    image_generation_count=4,
                    max_image_generations=2,
                ),
                data["pages"][0].pop("illustration"),
                data["pages"][1].pop("card"),
            ),
        )
        self.mutate(
            "visual-bible.yaml",
            lambda data: (
                data["canvas"].update(width=1200),
                data["typography"].update(family="Arial"),
                data["palette"].update(accent="#FFFFFF"),
            ),
        )

        errors = validate_project(self.project, phase="pre-generation")

        for expected in (
            "post.status must be one of:",
            "post.generation_round must be between 0 and 3",
            "post.max_generation_rounds must be exactly 3",
            "source: source.md does not exist",
            "canvas must be exactly 1080x1440",
            "typography.family must be Maple Mono NF CN",
            "palette.accent must be #012FA7",
            "pages[0].image_generation_count must be between 0 and 3",
            "pages[0].max_image_generations must be exactly 3",
            "pages[0].illustration: expected a non-empty relative path",
            "pages[1].card: expected a non-empty relative path",
        ):
            with self.subTest(expected=expected):
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_accepts_generating_and_rejects_legacy_approved_for_render_state(self):
        def set_all_statuses(data, status):
            data["post"]["status"] = status
            for page in data["pages"]:
                page["status"] = status

        self.mutate(
            "manifest.yaml",
            lambda data: set_all_statuses(data, "generating"),
        )
        self.assertEqual(validate_project(self.project), [])

        self.mutate(
            "manifest.yaml",
            lambda data: set_all_statuses(data, "approved_for_render"),
        )
        errors = validate_project(self.project)
        for field in ("post.status", "pages[0].status", "pages[1].status"):
            with self.subTest(field=field):
                self.assertTrue(
                    any(f"{field} must be one of:" in error for error in errors),
                    errors,
                )

    def test_pre_generation_rejects_unsafe_illustration_paths(self):
        self.mutate(
            "manifest.yaml",
            lambda data: data["pages"][0].update(illustration="../p01.png"),
        )
        errors = validate_project(self.project, phase="pre-generation")
        self.assertTrue(
            any(
                "pages[0].illustration: path must stay inside the post directory"
                in error
                for error in errors
            )
        )

    def test_pre_generation_rejects_existing_illustration_symlink_escape(self):
        with tempfile.TemporaryDirectory() as external_dir:
            external_image = Path(external_dir) / "p01-v01.png"
            Image.new("RGB", (800, 520), "white").save(external_image)
            link = self.project / "illustrations" / "p01-external.png"
            link.symlink_to(external_image)
            self.mutate(
                "manifest.yaml",
                lambda data: data["pages"][0].update(
                    illustration="illustrations/p01-external.png"
                ),
            )

            errors = validate_project(self.project, phase="pre-generation")

            self.assertTrue(
                any(
                    "pages[0].illustration: path must stay inside the post directory"
                    in error
                    for error in errors
                )
            )

    def test_pre_generation_rejects_existing_non_file_illustration(self):
        illustration = self.project / "illustrations" / "p01-v01.png"
        illustration.unlink()
        illustration.mkdir()

        errors = validate_project(self.project, phase="pre-generation")

        self.assertTrue(any("p01-v01.png does not exist" in error for error in errors))

    def test_complete_phase_rejects_missing_illustration(self):
        (self.project / "illustrations" / "p01-v01.png").unlink()
        errors = validate_project(self.project, phase="complete")
        self.assertTrue(any("p01-v01.png does not exist" in error for error in errors))

    def test_default_phase_remains_complete(self):
        (self.project / "illustrations" / "p01-v01.png").unlink()
        self.assertEqual(
            validate_project(self.project),
            validate_project(self.project, phase="complete"),
        )

    def test_api_rejects_unknown_phase(self):
        with self.assertRaisesRegex(
            ValueError,
            "phase must be one of: complete, pre-generation",
        ):
            validate_project(self.project, phase="draft")

    def test_cli_pre_generation_accepts_missing_illustrations(self):
        for illustration in (self.project / "illustrations").iterdir():
            illustration.unlink()
        result = subprocess.run(
            [
                sys.executable,
                str(SKILL_DIR / "scripts" / "validate_manifest.py"),
                "--phase",
                "pre-generation",
                str(self.project),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), f"OK: {self.project}")
        self.assertEqual(result.stderr, "")

    def test_cli_pre_generation_accepts_repeated_page_id_targets(self):
        (self.project / "illustrations" / "p01-v01.png").unlink()
        result = subprocess.run(
            [
                sys.executable,
                str(SKILL_DIR / "scripts" / "validate_manifest.py"),
                "--phase",
                "pre-generation",
                "--page-id",
                "p01",
                "--page-id",
                "p01",
                str(self.project),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"OK: {self.project}")
        self.assertEqual(result.stderr, "")

    def test_cli_rejects_unknown_phase_deterministically(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SKILL_DIR / "scripts" / "validate_manifest.py"),
                "--phase",
                "draft",
                str(self.project),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid choice: 'draft'", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(result.stdout, "")

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

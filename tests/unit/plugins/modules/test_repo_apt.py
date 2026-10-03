# Copyright: (c) 2026, Jonas Mauer
# GNU General Public License v3.0+ (see LICENSE)

"""APT source preservation and module lifecycle tests."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.jomrr.general.plugins.module_utils._repo_deb822 import (
    AptOptions,
    converge_deb822,
)
from ansible_collections.jomrr.general.plugins.module_utils._repo_deb822_parser import (
    SourceError,
)
from ansible_collections.jomrr.general.plugins.modules import repo_apt as apt
from ansible_collections.jomrr.general.tests.unit.repo_helpers import run_module


def replace_deb822(text: str, suites: list[str], uris: list[str]) -> str:
    """Converge the selected suites with an explicit mirror."""
    return converge_deb822(text, {"suites": suites, "uris": uris})


def replace_one_line(text: str, suites: list[str], uris: list[str]) -> str:
    """Converge existing legacy entries."""
    return apt.converge_one_line(text, {"suites": suites, "uris": uris})


class AptRepositoryTest(unittest.TestCase):
    """Retain source content and report real module results."""

    def test_split_preserves_inline_key_and_repeated_updates(self) -> None:
        """Retain multiline fields and avoid growing stanzas on subsequent edits."""
        original = (
            "# keep\nTypes: deb deb-src\nURIs: https://old.invalid\n"
            "Suites: stable\n stable-backports\nComponents: main\n"
            "Signed-By:\n -----BEGIN PGP PUBLIC KEY BLOCK-----\n .\n"
            " abcdef\n -----END PGP PUBLIC KEY BLOCK-----\nEnabled: no\n"
        )
        first = replace_deb822(original, ["stable-backports"], ["https://new.invalid"])
        self.assertEqual(first.count("Signed-By:"), 2)
        self.assertEqual(first.count(" abcdef\n"), 2)
        self.assertIn("URIs: https://old.invalid\nSuites: stable\n", first)
        self.assertEqual(
            first, replace_deb822(first, ["stable-backports"], ["https://new.invalid"])
        )
        second = replace_deb822(first, ["stable-backports"], ["https://next.invalid"])
        self.assertEqual(second.count("Types:"), 2)
        self.assertNotIn("https://new.invalid", second)

    def test_all_matching_stanzas_and_multiple_uris(self) -> None:
        """Update every matching entry while retaining unselected archive fields."""
        original = (
            "Types: deb\nSuites: stable\nURIs: https://old.invalid\nComponents: main\n"
        )
        original += (
            "\nTypes: deb-src\nSuites: stable\n"
            "URIs: https://old.invalid\nComponents: main\n"
        )
        result = replace_deb822(
            original, ["stable"], ["https://one.invalid", "https://two.invalid"]
        )
        self.assertEqual(
            result.count("URIs: https://one.invalid https://two.invalid"), 2
        )

    def test_missing_suite_fails_without_a_partial_write(self) -> None:
        """Return a useful selection error and leave the complete source intact."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.sources"
            original = (
                "Types: deb\nURIs: https://old.invalid\n"
                "Suites: stable\nComponents: main\n"
            )
            path.write_text(original, encoding="utf-8")
            result = self.run_module(path, ["stable", "missing"])
            self.assertTrue(result["failed"])
            self.assertIn("New non-path suites require components", str(result["msg"]))
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_invalid_file_does_not_expose_contents(self) -> None:
        """Keep parser diagnostics from revealing credentials in supplied files."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.sources"
            original = "not-a-field: secret-fixture\ninvalid-secret-fixture\n"
            path.write_text(original, encoding="utf-8")
            result = self.run_module(path, ["stable"])
            self.assertTrue(result["failed"])
            self.assertNotIn("secret-fixture", json.dumps(result))
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_legacy_disabled_entries_and_options(self) -> None:
        """Preserve option blocks, inline comments and unrelated suite lines."""
        original = (
            "# source comment\n"
            "deb [arch=amd64 signed-by=/keys/archive.gpg] "
            "https://old.invalid stable main # keep\n"
            "# deb-src https://old.invalid stable main\n"
            "deb https://old.invalid testing main\n"
        )
        expected = original.replace(
            "https://old.invalid stable", "https://new.invalid stable"
        )
        self.assertEqual(
            replace_one_line(original, ["stable"], ["https://new.invalid"]), expected
        )
        disabled = apt.converge_one_line(
            original, {"suites": ["stable"], "enabled": False}
        )
        self.assertIn("# deb [arch=amd64", disabled)
        self.assertIn("# deb-src https://old.invalid stable", disabled)
        remaining = apt.converge_one_line(
            disabled, {"suites": ["stable"], "state": "absent"}
        )
        self.assertEqual(
            remaining, "# source comment\ndeb https://old.invalid testing main\n"
        )
        with self.assertRaises(SourceError):
            replace_one_line(
                original, ["stable"], ["https://one.invalid", "https://two.invalid"]
            )

    def test_deb822_desired_presence_and_unspecified_fields(self) -> None:
        """Create sources, retain omitted settings and remove selected suites."""
        settings: AptOptions = {
            "suites": ["stable", "stable-backports"],
            "uris": ["https://public.invalid"],
            "components": ["main"],
        }
        initial = converge_deb822("", settings)
        self.assertIn("Enabled: yes", initial)
        self.assertEqual(initial, converge_deb822(initial, settings))
        changed = converge_deb822(
            initial, {"suites": ["stable-backports"], "enabled": False}
        )
        self.assertEqual(changed.count("Types: deb"), 2)
        self.assertIn("Enabled: no", changed)
        changed = converge_deb822(
            changed, {"suites": ["stable-backports"], "state": "absent"}
        )
        self.assertNotIn("stable-backports", changed)
        self.assertIn("Suites: stable", changed)

    def test_downloaded_keys_keep_check_mode_read_only(self) -> None:
        """Resolve public keys inline or to scoped paths without writes."""
        with tempfile.TemporaryDirectory() as directory:
            module = Mock(spec=AnsibleModule)
            module.check_mode = True
            module.tmpdir = directory
            armor = (
                b"-----BEGIN PGP PUBLIC KEY BLOCK-----\n"
                b"fixture\n-----END PGP PUBLIC KEY BLOCK-----\n"
            )
            for content in (armor, b"binary-public-key-fixture"):
                module.params = {
                    "state": "present",
                    "signed_by": "https://keys.example.org/test",
                }
                with patch.object(
                    apt,
                    "fetch_url",
                    return_value=(io.BytesIO(content), {"status": 200}),
                ):
                    changed = apt.signing_key(module)
                if content == armor:
                    self.assertFalse(changed)
                    self.assertEqual(module.params["signed_by"], armor.decode("ascii"))
                else:
                    self.assertTrue(changed)
                    self.assertTrue(
                        module.params["signed_by"].startswith("/etc/apt/keyrings/")
                    )
                    self.assertTrue(module.params["signed_by"].endswith(".gpg"))
                module.atomic_move.assert_not_called()
                self.assertEqual(list(Path(directory).iterdir()), [])

    @staticmethod
    def run_module(path: Path, suites: list[str]) -> dict[str, object]:
        """Invoke the actual module boundary, including JSON error serialization."""
        args = {"path": str(path), "suites": suites, "uris": ["https://mirror.invalid"]}
        return run_module(apt.main, args)

# Copyright: (c) 2026, Jonas Mauer
# GNU General Public License v3.0+ (see LICENSE)

"""Verify lossless RPM declarations and atomic module behavior."""

import json
import tempfile
import unittest
from pathlib import Path

from ansible_collections.jomrr.general.plugins.modules import repo_rpm as rpm
from ansible_collections.jomrr.general.tests.unit.repo_helpers import run_module


class RpmRepositoryTest(unittest.TestCase):
    """Exercise RPM-specific preservation and lifecycle behavior."""

    def test_multiline_sources_comments_and_sibling_sections(self) -> None:
        """Replace a mirror source without touching other options or comments."""
        original = (
            "# package-supplied\r\n[release]\r\nname=Release\r\n"
            "# baseurl=https://comment.invalid\r\n"
            "metalink = https://old.invalid/one\r\n"
            "  https://old.invalid/two\r\n"
            "# keep between continuation lines\r\n"
            "  https://old.invalid/three\r\n"
            "enabled=0\r\ngpgkey=https://key.invalid\r\n\r\n"
            "# updates comment\r\n[updates]\r\nname=Updates\r\nenabled=0\r\n"
        )
        desired: rpm.RpmOptions = {
            "backend": "dnf",
            "name": "release",
            "baseurl": ["https://mirror.invalid"],
        }
        changed = rpm.converge_repository(original, desired)
        self.assertIsNotNone(changed)
        assert changed is not None
        self.assertNotIn("metalink =", changed)
        self.assertNotIn("https://old.invalid", changed)
        self.assertIn("# baseurl=https://comment.invalid\r\n", changed)
        self.assertIn("# keep between continuation lines\r\n", changed)
        self.assertIn("enabled=0\r\ngpgkey=https://key.invalid\r\n", changed)
        self.assertIn("# updates comment\r\n", changed)
        self.assertEqual(changed.split("[updates]")[1], original.split("[updates]")[1])
        self.assertEqual(rpm.converge_repository(changed, desired), changed)

    def test_creation_policies_preservation_and_removal(self) -> None:
        """Use defaults only for creation and preserve a supplied sibling on removal."""
        desired: rpm.RpmOptions = {
            "backend": "zypper",
            "name": "release",
            "repo": "file:///tmp/repo",
            "default_enabled": False,
        }
        created = rpm.converge_repository("", desired)
        assert created is not None
        self.assertIn("enabled=0\n", created)
        self.assertIn("gpgcheck=1\n", created)
        self.assertIn("autorefresh=1\n", created)
        self.assertIn("baseurl=file:/tmp/repo\n", created)
        self.assertEqual(
            rpm.converge_repository(created, {**desired, "default_enabled": True}),
            created,
        )
        supplied = created + "# sibling comment\n[sibling]\nenabled=0\n"
        removed = rpm.converge_repository(
            supplied, {"backend": "zypper", "name": "release", "state": "absent"}
        )
        self.assertEqual(removed, "# sibling comment\n[sibling]\nenabled=0\n")
        self.assertIsNone(
            rpm.converge_repository(
                created, {"backend": "zypper", "name": "release", "state": "absent"}
            )
        )
        with self.assertRaises(rpm.RepositoryError):
            rpm.converge_repository(
                "", {"backend": "dnf", "name": "release", "enabled": False}
            )

    def test_check_mode_failure_and_atomic_update(self) -> None:
        """Retain bytes in check mode and on failure, and metadata on success."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "supplied.repo"
            original = (
                "# keep\n[supplied]\nname=Supplied\n"
                "baseurl=https://public.invalid\nenabled=0\n"
            )
            path.write_text(original, encoding="utf-8")
            path.chmod(0o640)
            arguments = {
                "backend": "dnf",
                "name": "supplied",
                "path": str(path),
                "enabled": True,
            }
            result = run_module(rpm.main, {**arguments, "_ansible_check_mode": True})
            self.assertTrue(result["changed"])
            self.assertEqual(path.read_text(encoding="utf-8"), original)
            result = run_module(rpm.main, arguments)
            self.assertTrue(result["changed"])
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                original.replace("enabled=0", "enabled=1"),
            )
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)
            self.assertFalse(run_module(rpm.main, arguments)["changed"])
            invalid = "secret-fixture\n[supplied]\nenabled=0\n"
            path.write_text(invalid, encoding="utf-8")
            result = run_module(rpm.main, arguments)
            self.assertTrue(result["failed"])
            self.assertNotIn("secret-fixture", json.dumps(result))
            self.assertEqual(path.read_text(encoding="utf-8"), invalid)


if __name__ == "__main__":
    unittest.main()

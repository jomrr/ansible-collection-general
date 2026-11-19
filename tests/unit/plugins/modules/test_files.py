# Copyright: (c) 2026, Jonas Mauer <jomrr@online.de>
# GNU General Public License v3.0+ (see LICENSE)

"""Batch file contracts through real Ansible argument validation and results."""

import base64
import errno
import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.jomrr.general.plugins.modules import slurp_files, write_files
from ansible_collections.jomrr.general.tests.unit.repo_helpers import run_module


class BatchFileTests(unittest.TestCase):
    """Check byte preservation, optional attributes, predictions and safe failures."""

    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory)
        self.path = self.directory / "certificate.der"
        self.data = b"\x30\x82\x00\xff\x80\x00batch-file-secret\r\n"
        self.encoded = base64.b64encode(self.data).decode("ascii")

    def write(self, **options: object) -> dict[str, object]:
        """Invoke one item with optional attributes through the module boundary."""
        check = options.pop("check", False)
        return run_module(
            write_files.main,
            {
                "files": [{"path": str(self.path), "content": self.encoded, **options}],
                "_ansible_check_mode": check,
            },
        )

    def assert_redacted(self, result: dict[str, object], value: str = "") -> None:
        """Check public results, excluding Ansible's private transport metadata."""
        output = json.dumps(
            {
                key: result.get(key)
                for key in (
                    "msg",
                    "exception",
                    "invocation",
                    "diff",
                    "content",
                    "paths",
                )
            }
        )
        for secret in (self.encoded, "batch-file-secret", value):
            if secret:
                self.assertNotIn(secret, output)

    def test_slurp_binary_empty_and_check_mode(self) -> None:
        """Reading and check mode return the same complete mapping without changes."""
        self.path.write_bytes(self.data)
        empty = self.directory / "empty"
        empty.touch()
        for check in (False, True):
            result = run_module(
                slurp_files.main,
                {
                    "paths": [os.path.relpath(self.path), str(empty)],
                    "_ansible_check_mode": check,
                },
            )
            self.assertFalse(result["changed"])
            self.assertEqual(
                result["content"], {str(self.path): self.encoded, str(empty): ""}
            )

    def test_slurp_failure_omits_partial_contents(self) -> None:
        """A later missing file fails with strerror and no earlier file contents."""
        self.path.write_bytes(self.data)
        missing = self.directory / "missing"
        result = run_module(slurp_files.main, {"paths": [str(self.path), str(missing)]})
        self.assertTrue(result["failed"])
        self.assertEqual(result["msg"], f"{missing}: {os.strerror(errno.ENOENT)}")
        self.assertNotIn("content", result)
        self.assert_redacted(result)

    def test_slurp_denied_read(self) -> None:
        """Permission errors retain their meaning without returning file contents."""
        with patch(
            "ansible_collections.jomrr.general.plugins.modules.slurp_files.open",
            side_effect=PermissionError(errno.EACCES, os.strerror(errno.EACCES)),
            create=True,
        ):
            result = run_module(slurp_files.main, {"paths": [str(self.path)]})
        self.assertTrue(result["failed"])
        self.assertEqual(result["msg"], f"{self.path}: {os.strerror(errno.EACCES)}")
        self.assertNotIn("content", result)

    def test_empty_batches(self) -> None:
        """An empty batch is a successful no-op."""
        read = run_module(slurp_files.main, {"paths": []})
        written = run_module(write_files.main, {"files": []})
        self.assertEqual(read["content"], {})
        self.assertFalse(read["changed"])
        self.assertEqual(written["paths"], [])
        self.assertFalse(written["changed"])

    def test_binary_round_trip_and_idempotence(self) -> None:
        """Write binary and empty files and preserve inodes on a repeated batch."""
        empty = self.directory / "empty"
        files = [
            {"path": str(self.path), "content": self.encoded},
            {"path": str(empty), "content": ""},
        ]
        result = run_module(write_files.main, {"files": files})
        self.assertTrue(result["changed"])
        self.assertEqual(result["paths"], [str(self.path), str(empty)])
        self.assertEqual(self.path.read_bytes(), self.data)
        self.assertEqual(empty.read_bytes(), b"")
        self.assert_redacted(result)
        before = self.path.stat()
        repeated = run_module(write_files.main, {"files": files})
        self.assertFalse(repeated["changed"])
        self.assertEqual(repeated["paths"], [])
        self.assertEqual(self.path.stat().st_ino, before.st_ino)
        self.assertEqual(self.path.stat().st_mtime_ns, before.st_mtime_ns)
        self.assert_redacted(repeated)

    def test_new_file_umask_and_omitted_attributes(self) -> None:
        """New files follow umask; later omitted permissions are never reset."""
        previous = os.umask(0o027)
        try:
            self.write()
        finally:
            os.umask(previous)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o640)
        self.path.chmod(0o604)
        self.assertFalse(self.write()["changed"])
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o604)
        self.path.write_bytes(b"old contents")
        self.assertTrue(self.write()["changed"])
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o604)

    def test_attribute_only_changes(self) -> None:
        """Explicit attributes converge without replacing unchanged contents."""
        self.path.write_bytes(self.data)
        self.path.chmod(0o600)
        inode = self.path.stat().st_ino
        owner = 65534 if os.getuid() == 0 else os.getuid()
        group = 65534 if os.getuid() == 0 else os.getgid()
        result = self.write(mode="0640", owner=str(owner), group=str(group))
        self.assertEqual(result["paths"], [str(self.path)])
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o640)
        self.assertEqual(self.path.stat().st_ino, inode)
        self.assertEqual(self.path.stat().st_uid, owner)
        self.assertEqual(self.path.stat().st_gid, group)
        self.assertFalse(self.write(mode="u=rw,g=r,o=")["changed"])

    def test_check_mode_before_and_after_convergence(self) -> None:
        """Predict creation, content and attribute changes without writing files."""
        predicted = self.write(check=True, mode="0640")
        self.assertEqual(predicted["paths"], [str(self.path)])
        self.assertEqual(list(self.directory.iterdir()), [])
        self.path.write_bytes(b"old contents")
        self.path.chmod(0o600)
        before = self.path.stat()
        self.assertTrue(self.write(check=True, mode="0640")["changed"])
        self.assertEqual(self.path.read_bytes(), b"old contents")
        self.assertEqual(self.path.stat().st_mode, before.st_mode)
        self.assertTrue(self.write(mode="0640")["changed"])
        self.assertFalse(self.write(check=True, mode="0640")["changed"])

    def test_missing_parent_and_partial_batch(self) -> None:
        """A failed later item reports completed paths without leaking input."""
        missing = self.directory / "missing" / "certificate.der"
        for check in (True, False):
            result = run_module(
                write_files.main,
                {
                    "files": [
                        {"path": str(self.path), "content": self.encoded},
                        {"path": str(missing), "content": self.encoded},
                    ],
                    "_ansible_check_mode": check,
                },
            )
            self.assertTrue(result["failed"])
            self.assertEqual(result["msg"], f"{missing}: {os.strerror(errno.ENOENT)}")
            self.assertEqual(result["paths"], [str(self.path)])
            self.assert_redacted(result)

    def test_invalid_content_and_argument_errors_are_redacted(self) -> None:
        """Real argument validation and malformed base64 never echo secret content."""
        for content in ("batch-file-secret!", "non-ascii-ü", "YWJjZA"):
            result = self.write(content=content)
            self.assertTrue(result["failed"])
            self.assert_redacted(result, content)
            self.assertFalse(self.path.exists())
        for item in (
            {"content": self.encoded},
            {"path": str(self.path), "content": self.encoded, "unknown": True},
        ):
            result = run_module(write_files.main, {"files": [item]})
            self.assertTrue(result["failed"])
            self.assert_redacted(result)

    def test_symlinks_are_rejected_even_when_contents_match(self) -> None:
        """Both normal and dangling destination links remain untouched."""
        target = self.directory / "target"
        target.write_bytes(self.data)
        self.path.symlink_to(target)
        for check in (False, True):
            result = self.write(check=check)
            self.assertTrue(result["failed"])
            self.assertEqual(result["msg"], f"{self.path}: is a symbolic link")
            self.assertTrue(self.path.is_symlink())
            self.assertEqual(target.read_bytes(), self.data)
        target.unlink()
        self.assertTrue(self.write()["failed"])
        self.assertTrue(self.path.is_symlink())
        self.assertFalse(target.exists())

    def test_parent_symlinks_and_slurp_links(self) -> None:
        """Allow linked parent directories for writing and linked files for reading."""
        parent = self.directory / "linked-directory"
        parent.symlink_to(self.directory, target_is_directory=True)
        result = self.write(path=str(parent / self.path.name))
        self.assertTrue(result["changed"])
        self.assertEqual(self.path.read_bytes(), self.data)
        link = self.directory / "current.der"
        link.symlink_to(self.path)
        read = run_module(slurp_files.main, {"paths": [str(link)]})
        self.assertEqual(read["content"], {str(link): self.encoded})

    def test_failed_atomic_move_removes_temporary_file(self) -> None:
        """An I/O failure leaves the original file and no temporary content behind."""
        self.path.write_bytes(b"original")
        with patch.object(
            AnsibleModule, "atomic_move", side_effect=OSError(errno.EIO, "I/O error")
        ):
            result = self.write()
        self.assertTrue(result["failed"])
        self.assertEqual(self.path.read_bytes(), b"original")
        self.assertEqual(list(self.directory.iterdir()), [self.path])
        self.assert_redacted(result)

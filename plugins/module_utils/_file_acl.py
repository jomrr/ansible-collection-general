# Copyright: (c) 2026, Jonas Mauer <jomrr@online.de>
# GNU General Public License v3.0+ (see LICENSE)

"""Compare and replace complete POSIX access ACLs using the system ACL tools."""

from __future__ import annotations

import errno
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from ansible.module_utils.basic import AnsibleModule


def _run(module: AnsibleModule, command: list[str], data: str | None = None) -> str:
    """Run an ACL tool without a shell and retain its diagnostic on failure."""
    status, stdout, stderr = cast(
        Callable[..., tuple[int, str, str]], module.run_command
    )(command, data=data)
    if status:
        raise OSError(errno.EINVAL, stderr.strip() or "ACL command failed")
    return stdout


def _tool_path(module: AnsibleModule, name: str) -> str:
    """Resolve required ACL tools at the Ansible API boundary."""
    executable = cast(Callable[..., str | None], module.get_bin_path)(name)
    if executable is None:
        raise OSError(errno.ENOENT, f"{name} is required to manage POSIX ACLs")
    return executable


@dataclass(frozen=True)
class AccessACL:
    """Validated ACL input and its comparison with the current access ACL."""

    text: str
    executable: str
    changed: bool

    def apply(self, module: AnsibleModule, path: str) -> None:
        """Replace all access entries, including removal of unspecified entries."""
        _run(module, [self.executable, "--set-file=-", "--", path], self.text)


def prepare_access_acl(
    module: AnsibleModule, path: str, entries: list[str], exists: bool
) -> AccessACL:
    """Validate and compare through setfacl's dry run, without writing files."""
    for entry in entries:
        fields = entry.split(":")
        if (
            len(fields) != 3
            or fields[0].strip()
            not in {"user", "u", "group", "g", "mask", "m", "other", "o"}
            or any(character in entry for character in "\n\r,")
        ):
            raise OSError(
                errno.EINVAL, "acl requires one access ACL entry per list item"
            )
    getfacl = _tool_path(module, "getfacl")
    setfacl = _tool_path(module, "setfacl")
    text = "\n".join(entries) + "\n"
    # A missing file has no ACL to compare. Validate against its existing parent;
    # --test changes neither the parent nor its default ACL.
    target = path if exists else os.path.dirname(path)
    command = [setfacl, "--test", "--set-file=-", "--", target]
    desired = _run(module, command, text)
    changed = True
    if exists:
        current = _run(
            module,
            [
                getfacl,
                "--access",
                "--numeric",
                "--omit-header",
                "--absolute-names",
                "--",
                path,
            ],
        )
        # Comparing native previews handles entry ordering, user names versus
        # IDs, and explicit masks without parsing setfacl's output format.
        changed = desired != _run(module, command, current)
    return AccessACL(text, setfacl, changed)

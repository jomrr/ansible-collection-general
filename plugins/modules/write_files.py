# Copyright: (c) 2026, Jonas Mauer <jomrr@online.de>
# GNU General Public License v3.0+ (see LICENSE)

"""Write multiple base64-encoded files with optional filesystem attributes."""

from __future__ import annotations

DOCUMENTATION = r"""
module: write_files
short_description: Write multiple base64-encoded files in one call
version_added: 1.2.0
description:
  - Compare decoded bytes and atomically replace only files with different contents.
  - Temporary files are created in the destination directory, which must exist.
  - New files use the current umask and the default SELinux context.
  - Existing files retain attributes through Ansible's atomic file replacement.
  - Only explicitly supplied mode, owner and group values are enforced.
  - Unchanged content without explicit attributes leaves the file and its ACL intact.
  - Destination symbolic links are rejected; links in parent directories are allowed.
  - Relative paths are made absolute.
  - Files are processed in order; earlier changes are not rolled back on failure.
  - Contents are excluded from results, errors and diffs.
options:
  files:
    description: Files to write on the managed host.
    type: list
    elements: dict
    required: true
    suboptions:
      path:
        description: Destination file path.
        type: path
        required: true
      content:
        description: Base64-encoded bytes. This value is masked in module diagnostics.
        type: str
        required: true
      mode:
        description:
          - Optional permissions, as a quoted octal value such as C('0640') or
            a symbolic mode such as C(u=rw,g=r,o=).
          - Omitted permissions are not enforced.
        type: raw
      owner:
        description: Optional owner name or numeric user ID.
        type: str
      group:
        description: Optional group name or numeric group ID.
        type: str
attributes:
  check_mode:
    description: Predict content and attribute changes without writing files.
    support: full
  diff_mode:
    description: Diffs are omitted to protect file contents.
    support: none
author:
  - Jonas Mauer (@jomrr)
"""

EXAMPLES = r"""
- name: Write certificates in one call
  jomrr.general.write_files:
    files:
      - path: /etc/pki/host.pem
        content: "{{ certificates.content['/var/lib/ca/host.pem'] }}"
        mode: '0644'
        owner: root
        group: root
      - path: /srv/share/host.der
        content: "{{ certificates.content['/var/lib/ca/host.der'] }}"
"""

RETURN = r"""
paths:
  description: Absolute requested paths whose contents or attributes changed.
  type: list
  elements: str
  returned: success
  sample:
    - /etc/pki/host.pem
"""

# Ansible requires DOCUMENTATION, EXAMPLES and RETURN before normal imports.
# pylint: disable=wrong-import-position
import base64
import binascii
import errno
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict, cast

from ansible.module_utils.basic import AnsibleModule

# pylint: enable=wrong-import-position


class FileItem(TypedDict):
    """Ansible-validated input; absent optional attributes are normalized to None."""

    path: str
    content: str
    mode: object
    owner: str | None
    group: str | None


def _current(path: str) -> bytes | None:
    """Read an existing file; only absence is treated as new content."""
    if os.path.islink(path):
        raise OSError(errno.ELOOP, "is a symbolic link")
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except FileNotFoundError:
        return None


def _write(module: AnsibleModule, path: str, data: bytes) -> None:
    """Replace a file atomically and remove the temporary file on failure."""
    descriptor, temporary = tempfile.mkstemp(dir=os.path.dirname(path))
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        cast(Callable[..., None], module.atomic_move)(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _converge(module: AnsibleModule, item: FileItem, path: str, data: bytes) -> bool:
    """Compare contents and apply only explicitly supplied filesystem attributes."""
    before = _current(path)
    changed = before != data
    if changed:
        if before is None:
            os.stat(os.path.dirname(path))
        if not module.check_mode:
            _write(module, path, data)
    attributes = {
        key: value
        for key, value in {
            "mode": item["mode"],
            "owner": item["owner"],
            "group": item["group"],
        }.items()
        if value is not None
    }
    if attributes:
        file_args = cast(
            Callable[..., dict[str, object]], module.load_file_common_arguments
        )({"path": path, **attributes})
        changed = cast(Callable[..., bool], module.set_fs_attributes_if_different)(
            file_args, changed
        )
    return changed


def main() -> None:
    """Apply a batch using Ansible's argument validation and secret redaction."""
    module = cast(Callable[..., AnsibleModule], AnsibleModule)(
        argument_spec={
            "files": {
                "type": "list",
                "elements": "dict",
                "required": True,
                "options": {
                    "path": {"type": "path", "required": True},
                    "content": {"type": "str", "required": True, "no_log": True},
                    "mode": {"type": "raw"},
                    "owner": {"type": "str"},
                    "group": {"type": "str"},
                },
            },
        },
        supports_check_mode=True,
    )
    changed: list[str] = []
    for item in cast(list[FileItem], module.params["files"]):
        path = os.path.abspath(item["path"])
        try:
            data = base64.b64decode(item["content"], validate=True)
        except (binascii.Error, ValueError):
            module.fail_json(
                msg=f"{path}: invalid base64 content",
                paths=changed,
                changed=bool(changed),
            )
        try:
            if _converge(module, item, path, data):
                changed.append(path)
        except OSError as error:
            module.fail_json(
                msg=f"{path}: {error.strerror}", paths=changed, changed=bool(changed)
            )
    module.exit_json(changed=bool(changed), paths=changed)


if __name__ == "__main__":
    main()

# Copyright: (c) 2026, Jonas Mauer <jomrr@online.de>
# GNU General Public License v3.0+ (see LICENSE)

"""Read several files in a single module invocation."""

from __future__ import annotations

DOCUMENTATION = r"""
module: slurp_files
short_description: Read multiple files as base64 in one call
version_added: 1.2.0
description:
  - Read files on the managed host and return their contents keyed by absolute path.
  - Relative paths are resolved against the module's working directory.
  - Symbolic links are followed. File contents are held in memory.
  - Use task-level C(no_log=true) when reading confidential files.
options:
  paths:
    description: Files to read on the managed host.
    type: list
    elements: path
    required: true
attributes:
  check_mode:
    description: Read the same files without modifying them.
    support: full
  diff_mode:
    description: File contents are returned as data, never as a diff.
    support: none
author:
  - Jonas Mauer (@jomrr)
"""

EXAMPLES = r"""
- name: Read certificates from the CA host in one call
  jomrr.general.slurp_files:
    paths:
      - /var/lib/ca/host.pem
      - /var/lib/ca/host.der
  delegate_to: ca.example.org
  register: certificates
  no_log: true
"""

RETURN = r"""
content:
  description: Base64-encoded file contents keyed by absolute path.
  type: dict
  returned: success
  sample:
    /tmp/example.txt: aGVsbG8K
"""

# Ansible requires DOCUMENTATION, EXAMPLES and RETURN before normal imports.
# pylint: disable=wrong-import-position
import base64
import os
from collections.abc import Callable
from typing import cast

from ansible.module_utils.basic import AnsibleModule

# pylint: enable=wrong-import-position


def main() -> None:
    """Read all requested files or fail without returning partial contents."""
    module = cast(Callable[..., AnsibleModule], AnsibleModule)(
        argument_spec={
            "paths": {"type": "list", "elements": "path", "required": True},
        },
        supports_check_mode=True,
    )
    content = {}
    for requested in cast(list[str], module.params["paths"]):
        path = os.path.abspath(requested)
        try:
            with open(path, "rb") as handle:
                content[path] = base64.b64encode(handle.read()).decode("ascii")
        except OSError as error:
            module.fail_json(msg=f"{path}: {error.strerror}")
    module.exit_json(changed=False, content=content)


if __name__ == "__main__":
    main()

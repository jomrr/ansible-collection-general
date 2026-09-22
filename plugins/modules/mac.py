# Copyright: (c) 2020, Jonas Mauer <jomrr@online.de>
# GNU General Public License v3.0+ (see LICENSE)

"""Generate MAC addresses from a name using SHA-256."""

from __future__ import annotations

DOCUMENTATION = r"""
module: mac
short_description: Generate deterministic MAC addresses from a name
version_added: 0.0.1
description: Generate MAC addresses with the C(52:54:) prefix using SHA-256.
attributes:
  check_mode:
    description: Calculate the same addresses without modifying host state.
    support: full
  diff_mode:
    description: The module calculates addresses and does not modify host state.
    support: none
options:
  name:
    description: This is the FQDN/name of a guest to generate MAC(s) for.
    required: true
    type: str
  count:
    description: A positive count generates indexed addresses by hashing <name>-<index>,
      starting at zero. Null or a nonpositive count generates one address by hashing
      the name directly.
    required: false
    type: int
    default: null
author:
- Jonas Mauer (@jomrr)
"""

EXAMPLES = r"""
- name: Test MAC generation
  jomrr.general.mac:
    name: test.mauer.in
    count: 1
"""

RETURN = r"""
original_message:
  description: The original name and count param that was passed in.
  type: list
  elements: raw
  returned: always
  sample:
  - test.mauer.in
  - 2
message:
  description: The output message that the module generates.
  type: str
  returned: always
  sample: ok
macs:
  description: The list with the MAC address(es).
  type: list
  elements: str
  returned: always
  sample:
  - 52:54:89:4e:c3:ed
  - 52:54:3c:b6:a8:45
"""

# Ansible requires DOCUMENTATION, EXAMPLES and RETURN before normal imports.
# pylint: disable=wrong-import-position
from typing import TYPE_CHECKING, cast

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.jomrr.general.plugins.module_utils._mac import generate_mac

# pylint: enable=wrong-import-position

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import NoReturn


def gen_mac(name: str, count: int | None = None) -> list[str]:
    """Hash the name directly, adding interface indices only for positive counts."""
    if count is None or count <= 0:
        return [generate_mac(name)]
    return [generate_mac(f"{name}-{index}") for index in range(count)]


def main() -> None:
    """Calculate addresses without changing state, including in check mode."""
    module = cast("Callable[..., AnsibleModule]", AnsibleModule)(
        argument_spec={
            "name": {"type": "str", "required": True},
            "count": {"type": "int", "default": None},
        },
        supports_check_mode=True,
    )
    name = cast(str, module.params["name"])
    count = cast("int | None", module.params["count"])
    exit_json = cast("Callable[..., NoReturn]", module.exit_json)
    exit_json(
        changed=False,
        original_message=[name, count],
        message="ok",
        macs=gen_mac(name, count),
    )


if __name__ == "__main__":
    main()

# Copyright: (c) 2020, Jonas Mauer <jomrr@online.de>
# GNU General Public License v3.0+ (see LICENSE)

"""Generate MAC addresses from a name using SHA-256."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.jomrr.general.plugins.module_utils._mac import generate_mac

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

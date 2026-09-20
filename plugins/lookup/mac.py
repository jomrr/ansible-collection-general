# Copyright: (c) 2024, Jonas Mauer <jomrr@online.de>
# GNU General Public License v3.0+ (see LICENSE)

"""Generate a MAC address from a string on the controller."""

from __future__ import annotations

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase
from ansible_collections.jomrr.general.plugins.module_utils._mac import generate_mac


class LookupModule(LookupBase):
    """Return a deterministic MAC address for exactly one input string."""

    def run(
        self,
        terms: list[object],
        variables: dict[str, object] | None = None,
        **kwargs: object,
    ) -> list[str]:
        """Validate the lookup arguments and calculate the address."""
        if len(terms) != 1 or not isinstance(terms[0], str):
            raise AnsibleError("mac lookup expects exactly one string argument.")
        return [generate_mac(terms[0])]

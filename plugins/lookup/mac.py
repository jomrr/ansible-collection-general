# Copyright: (c) 2024, Jonas Mauer <jomrr@online.de>
# GNU General Public License v3.0+ (see LICENSE)

"""Generate a MAC address from a string on the controller."""

from __future__ import annotations

DOCUMENTATION = r"""
name: mac
author: Jonas Mauer (@jomrr)
version_added: 0.2.0
short_description: Generate MAC address from string
description:
- This lookup returns a MAC address starting with C(52:54:) generated from a SHA-256
  hash of the given string.
options:
  _terms:
    description: String to hash into a MAC address.
    required: true
    type: list
    elements: str
"""

EXAMPLES = r"""
- name: Generate MAC address from string
  ansible.builtin.debug:
    msg: "{{ lookup('jomrr.general.mac', 'host.example.com-1') }}"
"""

RETURN = r"""
_raw:
  description:
  - MAC address starting with C(52:54:) generated from the given string.
  type: list
  elements: str
"""

# Ansible requires DOCUMENTATION, EXAMPLES and RETURN before normal imports.
# pylint: disable=wrong-import-position
from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase
from ansible_collections.jomrr.general.plugins.module_utils._mac import generate_mac

# pylint: enable=wrong-import-position


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

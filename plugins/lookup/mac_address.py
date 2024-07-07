# -*- coding: utf-8 -*-

"""Lookup plugin to generate a mac address from a string using sha256."""

from hashlib import sha256

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase

DOCUMENTATION = """
    name: mac_address
    author: Jonas Mauer <jam@kabelmail.net>
    version_added: "1.0"
    short_description: Generate MAC address from string
    description:
        - This lookup returns a MAC address starting with 02: generated from a hash of the given string.
    options:
      _terms:
        description: String to hash into a MAC address.
        required: True
"""

EXAMPLES = """
- name: Generate MAC address from string
  debug: msg="{{ lookup('mac_address', 'host.example.com-1') }}"
"""

RETURN = """
  _raw:
    description:
      - MAC address starting with 02: generated from the given string.
"""

class LookupModule(LookupBase):
    """Lookup plugin to generate a mac address from a string using sha256."""
    def run(self, terms, variables=None, **kwargs):
        if not terms or len(terms) != 1:
            raise AnsibleError("mac_address_generator lookup expects a single FQDN as an argument.")

        string = terms[0]

        # Generate SHA256 hash of the string
        hash_object = sha256(string.encode())
        hex_dig = hash_object.hexdigest()

        # Construct the MAC address
        mac_address = "02:" + ":".join([hex_dig[i:i+2] for i in range(0, 10, 2)])

        return [mac_address]

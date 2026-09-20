# Copyright: (c) 2026, Jonas Mauer
# GNU General Public License v3.0+ (see LICENSE)

"""Public MAC generation contracts and fixed SHA-256 reference values."""

from __future__ import annotations

import unittest
from typing import TYPE_CHECKING, cast

from ansible.errors import AnsibleError
from ansible_collections.jomrr.general.plugins.lookup.mac import LookupModule
from ansible_collections.jomrr.general.plugins.module_utils._mac import generate_mac
from ansible_collections.jomrr.general.plugins.modules.mac import gen_mac

if TYPE_CHECKING:
    from collections.abc import Callable


class MacTests(unittest.TestCase):
    """Check module and controller lookup output and input validation."""

    def setUp(self) -> None:
        self.lookup = cast("Callable[..., LookupModule]", LookupModule)()

    def test_reference_addresses(self) -> None:
        """The module and lookup produce identical, known SHA-256 addresses."""
        for name, expected in (
            ("host.example.com-1", "52:54:d7:ec:44:89"),
            ("", "52:54:e3:b0:c4:42"),
            ("münchen.example", "52:54:0e:4b:5d:e1"),
        ):
            with self.subTest(name=name):
                self.assertEqual(generate_mac(name), expected)
                self.assertEqual(gen_mac(name), [expected])
                self.assertEqual(self.lookup.run([name]), [expected])

    def test_module_indices(self) -> None:
        """Positive counts add an interface index starting at zero."""
        expected = ["52:54:89:4e:c3:ed", "52:54:3c:b6:a8:45"]
        self.assertEqual(gen_mac("test_guest", 2), expected)
        self.assertEqual(gen_mac("test_guest", 1), expected[:1])
        self.assertEqual(self.lookup.run(["test_guest-0"]), expected[:1])

    def test_nonpositive_counts(self) -> None:
        """Null and nonpositive counts hash the name without a suffix."""
        for count in (None, 0, -1):
            with self.subTest(count=count):
                self.assertEqual(
                    gen_mac("host.example.com-1", count), ["52:54:d7:ec:44:89"]
                )

    def test_invalid_lookup_terms(self) -> None:
        """Lookup arity and type errors are reported as Ansible errors."""
        cases: list[list[object]] = [[], ["one", "two"], [None], [42], [{}]]
        for terms in cases:
            with self.subTest(terms=terms), self.assertRaises(AnsibleError):
                self.lookup.run(terms)

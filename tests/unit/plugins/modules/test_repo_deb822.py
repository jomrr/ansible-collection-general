# Copyright: (c) 2026, Jonas Mauer
# GNU General Public License v3.0+ (see LICENSE)

"""DEB822 grammar and lossless editing cases beyond the migrated module tests."""

import unittest

from ansible_collections.jomrr.general.plugins.module_utils._repo_deb822 import (
    AptOptions,
    converge_deb822,
)
from ansible_collections.jomrr.general.plugins.module_utils._repo_deb822_parser import (
    SourceError,
    parse_sources,
)


class Deb822Test(unittest.TestCase):
    """Exercise case-insensitive fields, comments and paragraph boundaries."""

    def test_comments_continuations_separators_and_copy(self) -> None:
        """A split preserves multiline keys and whitespace-only paragraph separators."""
        first = (
            "# leading\r\ntYpEs: deb deb-src\r\nuRiS: https://old.invalid\r\n"
            "sUiTeS: stable\r\n# between continuations\r\n stable-backports\r\n"
            "Components: main\r\nsigned-by:\r\n"
            " -----BEGIN PGP PUBLIC KEY BLOCK-----\r\n"
            " .\r\n# within key\r\n abcdef\r\n"
            " -----END PGP PUBLIC KEY BLOCK-----\r\n"
            "Enabled: no\r\n"
        )
        sibling = "Types: deb\r\nSuites: other\r\nURIs: https://unrelated.invalid\r\n"
        original = first + " \t\r\n" + sibling
        self.assertEqual(parse_sources(original).to_text(), original)
        options: AptOptions = {
            "suites": ["stable-backports"],
            "uris": ["https://mirror.invalid"],
        }
        changed = converge_deb822(original, options)
        self.assertIn(sibling, changed)
        self.assertIn(" \t\r\n", changed)
        self.assertEqual(changed.count("# within key"), 2)
        self.assertEqual(changed.count("# between continuations"), 2)
        self.assertEqual(changed, converge_deb822(changed, options))

    def test_replace_position_append_and_remove(self) -> None:
        """Editing an existing field retains casing and unrelated lines."""
        document = parse_sources(
            "# keep\nTyPeS: deb\nUris: old\n# middle\n more\nSuites: stable"
        )
        paragraph = document.paragraphs()[0]
        self.assertEqual(paragraph.get("URIS"), "old\n more")
        paragraph.set("URIs", "new")
        self.assertEqual(
            document.to_text(),
            "# keep\nTyPeS: deb\nUris: new\n# middle\nSuites: stable",
        )
        paragraph.set("Enabled", "no")
        self.assertTrue(document.to_text().endswith("Suites: stable\nEnabled: no\n"))
        document.remove(paragraph)
        self.assertEqual(document.to_text(), "")

    def test_unsupported_and_duplicate_fields(self) -> None:
        """Malformed content fails safely, including case variants of a duplicate."""
        for invalid in (
            "Suites: stable\nsUiTeS: other\n",
            "# comment\n orphaned continuation\n",
            "Types: deb\nnot a field\n",
            "Types: deb\n \t\n orphaned continuation\n",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(SourceError):
                parse_sources(invalid)

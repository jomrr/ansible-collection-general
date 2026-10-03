# Copyright: (c) 2026, Jonas Mauer
# GNU General Public License v3.0+ (see LICENSE)

"""Repository filter selection and override contracts."""

import unittest

from ansible.errors import AnsibleFilterError
from ansible_collections.jomrr.general.plugins.filter.repo import (
    FilterModule,
    merge_options,
)


class RepoFilterTest(unittest.TestCase):
    """Resolve declarations without mutating caller data."""

    def test_overrides_clear_alternative_sources_without_mutating_presets(self) -> None:
        """Merge each repository independently and keep untouched fields intact."""
        presets: list[dict[str, object]] = [
            {"name": "a", "metalink": "old", "gpgkey": ["key"]},
            {"name": "b", "baseurl": ["original"]},
        ]
        overrides: list[dict[str, object]] = [
            {"name": "a", "baseurl": ["mirror-a"]},
            {"name": "b", "mirrorlist": "mirror-b"},
        ]
        result = [
            merge_options(preset, override)
            for preset, override in zip(presets, overrides)
        ]
        self.assertEqual(
            result,
            [
                {"name": "a", "baseurl": ["mirror-a"], "gpgkey": ["key"]},
                {"name": "b", "mirrorlist": "mirror-b"},
            ],
        )
        self.assertEqual(presets[0]["metalink"], "old")

    def test_presets_and_supplied_repositories_share_one_list(self) -> None:
        """Resolve nested mirrors and a supplied entry without operation modes."""
        catalog = {
            "example": [
                {"name": "release", "metalink": "public-release"},
                {"name": "updates", "metalink": "public-updates"},
            ]
        }
        result = FilterModule.resolve_repositories(
            [
                {
                    "preset": "example",
                    "enabled": False,
                    "repositories": [
                        {"name": "release", "baseurl": ["mirror-release"]},
                        {"name": "updates", "baseurl": ["mirror-updates"]},
                    ],
                },
                {"name": "fedora", "enabled": False},
            ],
            catalog,
            "dnf",
            {"enabled": True, "state": "present"},
            "/etc/yum.repos.d",
        )
        self.assertEqual(
            [item["baseurl"] for item in result[:2]],
            [["mirror-release"], ["mirror-updates"]],
        )
        self.assertTrue(all("metalink" not in item for item in result))
        self.assertEqual(
            result[2],
            {
                "name": "fedora",
                "file": "fedora",
                "enabled": False,
                "state": "present",
                "path": "/etc/yum.repos.d/fedora.repo",
            },
        )
        self.assertEqual(catalog["example"][0]["metalink"], "public-release")
        with self.assertRaises(AnsibleFilterError):
            FilterModule.resolve_repositories(
                [{"preset": "example"}, {"name": "release", "enabled": False}],
                catalog,
                "dnf",
                {"enabled": True, "state": "present"},
                "/etc/yum.repos.d",
            )

    def test_apt_ownership_rejects_overlapping_selections(self) -> None:
        """Prevent declarations for the same suite from fighting each other."""
        for second in (
            {"name": "example"},
            {"path": "/etc/apt/sources.list.d/example.sources", "suites": ["stable"]},
        ):
            with self.subTest(second=second), self.assertRaises(AnsibleFilterError):
                FilterModule.resolve_repositories(
                    [{"name": "example", "suites": ["stable"]}, second],
                    {},
                    "apt",
                    {"enabled": True, "state": "present"},
                    "/etc/apt/sources.list.d",
                )

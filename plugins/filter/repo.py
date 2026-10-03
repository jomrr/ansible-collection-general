# Copyright: (c) 2026, Jonas Mauer
# GNU General Public License v3.0+ (see LICENSE)

"""Resolve desired repositories and preserve unspecified RPM settings."""

import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import PurePosixPath

from ansible.errors import AnsibleFilterError

DOCUMENTATION = r"""
name: repo
short_description: Resolve desired repositories and caller-supplied presets
version_added: 1.1.0
description:
  - Expands selected presets, applies common and named overrides, and resolves file paths.
  - Returns new mappings without changing the input or preset catalogue.
  - Rejects duplicate RPM IDs and overlapping APT suite selections before modules write files.
  - Contains no distribution presets and performs no file or network operations.
positional: [catalog, backend, policies, directory]
options:
  _input:
    description: Repository declarations with a name, an APT path, or a preset.
    type: list
    elements: dict
    required: true
  catalog:
    description: Mapping[str, object] of preset names to lists of repository declarations.
    type: dict
    required: true
  backend:
    description: Repository format. Both DNF versions use V(dnf).
    type: str
    choices: [apt, dnf, zypper]
    required: true
  policies:
    description: Mapping[str, object] containing state (present or absent) and enabled (boolean).
    type: dict
    required: true
  directory:
    description: Absolute repository directory used for entries identified by name.
    type: path
    required: true
notes:
  - RPM C(name) identifies a section; C(file) is the filename stem and defaults to C(name).
  - APT C(name) identifies a C(.sources) file; C(path) selects a file explicitly.
  - Presets accept common overrides and a C(repositories) list of overrides keyed by name.
  - An explicit RPM mirror source replaces alternative sources inherited from a preset.
author: Jonas Mauer (@jomrr)
"""

EXAMPLES = r"""
- name: Resolve supplied repositories before calling repo_rpm
  ansible.builtin.debug:
    msg: "{{ repositories | jomrr.general.repo({}, 'dnf', policies, '/etc/yum.repos.d') }}"
  vars:
    policies: {state: present, enabled: true}
    repositories:
      - name: fedora
        enabled: true
        baseurl: ['https://mirror.example.org/fedora/$releasever/$basearch']
      - name: extras
        file: almalinux-extras
        enabled: false
"""

RETURN = r"""
_value:
  description: Expanded declarations with resolved path and state and supplied options.
  type: list
  elements: dict
"""


def declarations(value: object) -> list[dict[str, object]]:
    """Validate a declaration list, preserving arbitrary backend module options."""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise AnsibleFilterError("Repository declarations must be a list of mappings")
    result = []
    for entry in value:
        if not isinstance(entry, Mapping) or any(
            not isinstance(key, str) for key in entry
        ):
            raise AnsibleFilterError(
                "Repository declarations require mappings with string keys"
            )
        result.append(dict(entry))
    return result


def string_value(entry: Mapping[str, object], key: str) -> str:
    """Read an identifier without echoing arbitrary user-supplied values."""
    value = entry.get(key)
    if not isinstance(value, str) or not value:
        raise AnsibleFilterError(f"Repository {key} must be a nonempty string")
    return value


def suite_names(entry: Mapping[str, object]) -> set[str] | None:
    """Validate the optional selection; omission selects the entire APT file."""
    value = entry.get("suites")
    if value is None:
        return None
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise AnsibleFilterError("APT suites must be a list of strings")
    return set(value) if value else None


def merge_options(
    base: Mapping[str, object], options: Mapping[str, object]
) -> dict[str, object]:
    """Replace RPM source alternatives together without mutating preset data."""
    result = dict(base)
    sources = ("baseurl", "metalink", "mirrorlist")
    selected = [key for key in sources if key in options]
    if len(selected) > 1:
        raise AnsibleFilterError(
            "Select only one of baseurl, metalink and mirrorlist per entry"
        )
    if selected:
        for key in sources:
            result.pop(key, None)
    result.update(options)
    for key in ("baseurl", "metalink", "mirrorlist", "repo"):
        if key in result:
            value = result[key]
            values = value if isinstance(value, list) else [value]
            if not values or any(
                not isinstance(value, str) or not value or re.search(r"\s", value)
                for value in values
            ):
                raise AnsibleFilterError(
                    "Repository URLs must be nonempty and contain no whitespace"
                )
    return result


def expand_preset(
    entry: Mapping[str, object], catalog: Mapping[str, object], enabled: bool
) -> list[dict[str, object]]:
    """Apply common and named options before resolving each desired repository."""
    preset = entry["preset"]
    if not isinstance(preset, str) or preset not in catalog:
        raise AnsibleFilterError("Select a preset supported by this distribution")
    if any(key in entry for key in ("name", "file", "path")):
        raise AnsibleFilterError(
            "A preset supplies name and file; override its settings directly"
        )
    nested = declarations(entry.get("repositories", []))
    definitions = declarations(catalog[preset])
    names = [string_value(definition, "name") for definition in definitions]
    requested = [string_value(item, "name") for item in nested]
    if any(name not in names for name in requested) or len(requested) != len(
        set(requested)
    ):
        raise AnsibleFilterError(
            "Nested overrides must name distinct repositories from their preset"
        )
    options = {
        key: value
        for key, value in entry.items()
        if key not in ("preset", "repositories")
    }
    result = []
    for definition in definitions:
        merged = merge_options(definition, {"enabled": enabled, **options})
        for override in nested:
            if override["name"] == definition["name"]:
                merged = merge_options(merged, override)
        result.append(merged)
    return result


def target_entry(
    entry: Mapping[str, object], backend: str, directory: str, state: str
) -> dict[str, object]:
    """Derive a stable target without exposing creation or update operations."""
    result = {"state": state, **entry}
    name = result.get("name")
    if backend == "apt" and "path" in result:
        path = string_value(result, "path")
        if (
            not path.startswith("/")
            or str(PurePosixPath(path)) != path
            or ".." in PurePosixPath(path).parts
        ):
            raise AnsibleFilterError("APT path must be normalized and absolute")
        if name is not None:
            raise AnsibleFilterError(
                "APT entries identify their file by name or path, not both"
            )
    else:
        if not isinstance(name, str) or not name:
            raise AnsibleFilterError(
                "Repository entries require name, or an explicit APT path"
            )
        if backend == "apt":
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
                raise AnsibleFilterError(
                    "APT names must use lowercase letters, digits and hyphens"
                )
            result["path"] = directory + "/" + name + ".sources"
        else:
            if re.search(r"[\[\]\s]", name):
                raise AnsibleFilterError(
                    "RPM names must be section identifiers "
                    "without whitespace or brackets"
                )
            result.setdefault("file", name)
            if not re.fullmatch(
                r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", string_value(result, "file")
            ):
                raise AnsibleFilterError(
                    "RPM file must be a filename stem "
                    "without whitespace or path separators"
                )
            result["path"] = directory + "/" + string_value(result, "file") + ".repo"
    return result


def validate_ownership(entries: Sequence[Mapping[str, object]], backend: str) -> None:
    """Reject duplicate identities and overlapping APT selections before writes."""
    if backend != "apt":
        names = [string_value(entry, "name") for entry in entries]
        if len(names) != len(set(names)):
            raise AnsibleFilterError(
                "Each repository name may appear only once, "
                "including preset repositories"
            )
        return
    selections: dict[str, set[str] | None] = {}
    for entry in entries:
        path = string_value(entry, "path")
        suites = suite_names(entry)
        if path in selections:
            previous = selections[path]
            if previous is None or suites is None or previous & suites:
                raise AnsibleFilterError(
                    "APT entries for one file must select disjoint suites"
                )
            suites |= previous
        selections[path] = suites


class FilterModule:
    """Expose repository resolution and RPM option mapping."""

    @staticmethod
    def resolve_repositories(
        entries: object,
        catalog: Mapping[str, object],
        backend: str,
        policies: Mapping[str, object],
        directory: str,
    ) -> list[dict[str, object]]:
        """Expand requested presets once and enforce unique ownership."""
        if backend not in ("apt", "dnf", "zypper"):
            raise AnsibleFilterError("backend must be apt, dnf or zypper")
        if not isinstance(catalog, Mapping) or not isinstance(policies, Mapping):
            raise AnsibleFilterError("catalog and policies must be mappings")
        enabled = policies.get("enabled")
        state = string_value(policies, "state")
        if not isinstance(enabled, bool) or state not in ("present", "absent"):
            raise AnsibleFilterError(
                "policies require enabled (boolean) and state (present/absent)"
            )
        if not isinstance(directory, str) or not PurePosixPath(directory).is_absolute():
            raise AnsibleFilterError("directory must be an absolute path")
        result: list[dict[str, object]] = []
        for entry in declarations(entries):
            if "preset" in entry:
                expanded = expand_preset(entry, catalog, enabled)
            else:
                if "repositories" in entry:
                    raise AnsibleFilterError("Nested repositories require a preset")
                expanded = [merge_options({}, entry)]
            result.extend(
                target_entry(item, backend, directory, state) for item in expanded
            )
        validate_ownership(result, backend)
        return result

    def filters(self) -> dict[str, Callable[..., list[dict[str, object]]]]:
        """Return filter entry points."""
        return {
            "repo": self.resolve_repositories,
        }

# Copyright: (c) 2026, Jonas Mauer
# GNU General Public License v3.0+ (see LICENSE)

"""Converge RPM repository sections without replacing supplied configuration."""

from __future__ import annotations

DOCUMENTATION = r"""
module: repo_rpm
version_added: 1.1.0
short_description: Manage desired DNF and Zypper repository settings
description:
  - Creates, updates or removes a named section in an RPM repository file.
  - Preserves unspecified options, other sections, comments and existing file metadata.
  - Replaces alternative mirror sources when a URL is explicitly supplied.
  - Applies creation defaults only to missing sections.
  - Writes changed content atomically after validating INI syntax.
  - Removes the file after removing its last repository section.
  - Rejects symlinks and malformed or duplicate INI sections and options.
  - Omits file diffs because supplied repository files can contain credentials.
options:
  path:
    description: Absolute repository file path.
    type: path
    required: true
  name:
    description: Repository ID or alias, identifying the INI section.
    type: str
    required: true
  backend:
    description: Package manager backend.
    type: str
    choices: [dnf, zypper]
    required: true
  state:
    description: Desired repository presence.
    type: str
    choices: [present, absent]
    default: present
  default_enabled:
    description: Enabled flag for new sections.
    type: bool
    default: true
  default_gpgcheck:
    description: Signature verification for new sections.
    type: bool
    default: true
  description:
    description: Repository display name.
    type: str
  enabled:
    description: Desired enabled flag.
    type: bool
  baseurl:
    description: Desired DNF base URLs.
    type: list
    elements: str
  repo:
    description: Desired Zypper base URL.
    type: str
  metalink:
    description: Desired metalink URL.
    type: str
  mirrorlist:
    description: Desired mirror-list URL.
    type: str
  gpgkey:
    description: Public signing key URLs.
    type: list
    elements: str
  gpgcheck:
    description: Desired package signature verification.
    type: bool
  repo_gpgcheck:
    description: Desired metadata signature verification.
    type: bool
  priority:
    description: Repository priority.
    type: int
  exclude:
    description: Excluded package patterns.
    type: list
    elements: str
  includepkgs:
    description: Included package patterns.
    type: list
    elements: str
  autorefresh:
    description: Desired Zypper automatic refresh flag; defaults to true for new sections.
    type: bool
  auto_import_keys:
    description: Refresh the selected Zypper repository and import its key after a change.
    type: bool
    default: false
attributes:
  check_mode:
    description: Predict changes without writing files or refreshing repositories.
    support: full
  diff_mode:
    description: Supplied repository contents are never returned.
    support: none
author: Jonas Mauer (@jomrr)
"""

EXAMPLES = r"""
- name: Disable AlmaLinux Extras without replacing its other settings
  jomrr.general.repo_rpm:
    backend: dnf
    path: /etc/yum.repos.d/almalinux-extras.repo
    name: extras
    enabled: false
"""

RETURN = r"""
path:
  description: Selected repository file.
  type: str
  returned: always
"""

# Ansible requires documentation before normal imports.
# pylint: disable=wrong-import-position
import configparser
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TypedDict, cast

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.jomrr.general.plugins.module_utils._repo_files import (
    RepositoryFileError,
    atomic_write,
    read_regular,
)

# pylint: enable=wrong-import-position

SECTION = re.compile(r"(?m)^[ \t]*\[([^\]\r\n]+)\][^\r\n]*(?:\r?\n|$)")
OPTION = re.compile(
    r"^(?P<prefix>[ \t]*(?P<key>[^=#;\s][^=]*?)[ \t]*=[ \t]*)"
    r"(?P<value>[^\r\n]*)(?P<end>\r?\n)?$"
)
FIELDS = {
    "description": {"type": "str"},
    "enabled": {"type": "bool"},
    "baseurl": {"type": "list", "elements": "str"},
    "repo": {"type": "str"},
    "metalink": {"type": "str"},
    "mirrorlist": {"type": "str"},
    "gpgkey": {"type": "list", "elements": "str", "no_log": True},
    "gpgcheck": {"type": "bool"},
    "repo_gpgcheck": {"type": "bool"},
    "priority": {"type": "int"},
    "exclude": {"type": "list", "elements": "str"},
    "includepkgs": {"type": "list", "elements": "str"},
    "autorefresh": {"type": "bool"},
}


class RpmOptions(TypedDict, total=False):
    """Validated repository options, separate from Ansible execution controls."""

    name: str
    backend: str
    state: str
    description: str | None
    enabled: bool | None
    baseurl: list[str] | None
    repo: str | None
    metalink: str | None
    mirrorlist: str | None
    gpgkey: list[str] | None
    gpgcheck: bool | None
    repo_gpgcheck: bool | None
    priority: int | None
    exclude: list[str] | None
    includepkgs: list[str] | None
    autorefresh: bool | None
    default_enabled: bool
    default_gpgcheck: bool


class RepositoryError(ValueError):
    """A configuration error safe to report without file contents."""


def parse_repository(text: str) -> configparser.ConfigParser:
    """Validate INI syntax while retaining RPM URL macros as literal data."""
    parser = configparser.ConfigParser(
        interpolation=None, delimiters=("=",), default_section=""
    )
    try:
        parser.read_string(text)
    except configparser.Error as error:
        raise RepositoryError(
            "Invalid repository INI syntax or duplicate section/option"
        ) from error
    if [match[1] for match in SECTION.finditer(text)] != parser.sections():
        raise RepositoryError("Section-like continuation lines are not supported")
    return parser


def encode_option(key: str, value: object) -> str:
    """Encode explicit values without permitting newlines in repository options."""
    if isinstance(value, bool):
        encoded = "1" if value else "0"
    elif isinstance(value, list):
        encoded = " ".join(value)
    else:
        encoded = str(value)
    if key == "repo":
        encoded = re.sub(r"^file:///", "file:/", encoded)
    if "\n" in encoded or "\r" in encoded:
        raise RepositoryError("Repository option values must not contain line breaks")
    if key in {"baseurl", "repo", "metalink", "mirrorlist"} and not encoded.strip():
        raise RepositoryError("Repository URLs must not be empty")
    return encoded


def explicit_options(params: Mapping[str, object]) -> dict[str, str | None]:
    """Encode the supported option keys at the INI serialization boundary."""
    aliases = {"description": "name", "repo": "baseurl"}
    return {
        aliases.get(key, key): encode_option(key, params[key])
        for key in FIELDS
        if params.get(key) is not None
    }


def desired_options(params: RpmOptions, existing: bool) -> dict[str, str | None]:
    """Apply explicit settings and policy defaults only for new sections."""
    desired = explicit_options(params)
    if not existing:
        if not any(desired.get(key) for key in ("baseurl", "metalink", "mirrorlist")):
            raise RepositoryError("New RPM repositories require a repository URL")
        desired.setdefault("name", params["name"])
        desired.setdefault(
            "enabled", encode_option("enabled", params.get("default_enabled", True))
        )
        desired.setdefault(
            "gpgcheck", encode_option("gpgcheck", params.get("default_gpgcheck", True))
        )
        desired.setdefault(
            "autorefresh" if params["backend"] == "zypper" else "sslverify", "1"
        )
    if any(key in desired for key in ("baseurl", "metalink", "mirrorlist")):
        for key in ("baseurl", "metalink", "mirrorlist"):
            desired.setdefault(key, None)
    return desired


def option_rows(lines: list[str]) -> dict[str, list[int]]:
    """Locate option and continuation lines without claiming adjacent comments."""
    rows: dict[str, list[int]] = {}
    current = ""
    indentation = 0
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if index == 0 or not stripped.strip() or stripped.startswith(("#", ";")):
            continue
        indent = len(line) - len(stripped)
        if current and indent > indentation:
            rows[current].append(index)
        else:
            match = OPTION.match(line)
            if match is None:
                raise RepositoryError("Unsupported repository option layout")
            current = match["key"].strip().lower()
            indentation = indent
            rows[current] = [index]
    return rows


def update_section(
    text: str, desired: Mapping[str, str | None], current: Mapping[str, str]
) -> str:
    """Replace only requested option lines, preserving everything else verbatim."""
    lines = text.splitlines(keepends=True)
    rows = option_rows(lines)
    ending = "\r\n" if "\r\n" in text else "\n"
    additions = []
    for key, value in desired.items():
        if key not in rows:
            if value is not None:
                additions.append(key + "=" + value + ending)
            continue
        indices = rows[key]
        if value is not None and " ".join(current[key].split()) == value:
            continue
        match = OPTION.fullmatch(lines[indices[0]])
        if match is None:
            raise RepositoryError("Cannot locate the selected option")
        lines[indices[0]] = (
            "" if value is None else match["prefix"] + value + (match["end"] or "")
        )
        for index in indices[1:]:
            lines[index] = ""
    if additions and lines and not lines[-1].endswith("\n"):
        lines[-1] += ending
    return "".join(lines + additions)


def converge_repository(text: str, params: RpmOptions) -> str | None:
    """Resolve desired state and return None only when the last section is removed."""
    current = parse_repository(text)
    name = params["name"]
    matches = list(SECTION.finditer(text))
    bounds = {
        match[1]: (
            match.start(),
            matches[index + 1].start() if index + 1 < len(matches) else len(text),
        )
        for index, match in enumerate(matches)
    }
    if params.get("state", "present") == "absent":
        if name not in current:
            return text
        start, end = bounds[name]
        lines = text[start:end].splitlines(keepends=True)
        removed = {0} | {
            index for indices in option_rows(lines).values() for index in indices
        }
        comments = "".join(
            line for index, line in enumerate(lines) if index not in removed
        )
        remaining = text[:start] + comments + text[end:]
        return remaining if parse_repository(remaining).sections() else None
    desired = desired_options(params, name in current)
    if name not in current:
        prefix = text + ("\n" if text and not text.endswith("\n") else "")
        result = prefix + update_section("[" + name + "]\n", desired, {})
    else:
        start, end = bounds[name]
        result = (
            text[:start]
            + update_section(text[start:end], desired, current[name])
            + text[end:]
        )
    parse_repository(result)
    return result


def main() -> None:
    """Converge a section and optionally refresh that Zypper repository."""
    module = cast(Callable[..., AnsibleModule], AnsibleModule)(
        argument_spec={
            "path": {"type": "path", "required": True},
            "name": {"type": "str", "required": True},
            "backend": {"type": "str", "choices": ["dnf", "zypper"], "required": True},
            "state": {
                "type": "str",
                "choices": ["present", "absent"],
                "default": "present",
            },
            "default_enabled": {"type": "bool", "default": True},
            "default_gpgcheck": {"type": "bool", "default": True},
            "auto_import_keys": {"type": "bool", "default": False},
            **FIELDS,
        },
        mutually_exclusive=[["baseurl", "repo", "metalink", "mirrorlist"]],
        supports_check_mode=True,
    )
    path = Path(module.params["path"])
    try:
        if not path.is_absolute() or path.suffix != ".repo":
            raise RepositoryError("path must be an absolute .repo filename")
        if not module.params["name"] or re.search(r"[\[\]\s]", module.params["name"]):
            raise RepositoryError(
                "name must be a repository ID without whitespace or brackets"
            )
        if module.params["auto_import_keys"] and module.params["backend"] != "zypper":
            raise RepositoryError("auto_import_keys requires Zypper")
        before = read_regular(path)
        after = converge_repository(before, cast(RpmOptions, module.params))
        changed = before != after
        if changed and not module.check_mode:
            if after is None:
                path.unlink()
            else:
                atomic_write(module, path, after.encode("utf-8"))
    except (RepositoryError, RepositoryFileError) as error:
        module.fail_json(msg=str(error), path=str(path))
    except (OSError, UnicodeError) as error:
        module.fail_json(
            msg=f"Cannot manage selected RPM source ({type(error).__name__})",
            path=str(path),
        )
    if (
        changed
        and not module.check_mode
        and after is not None
        and module.params["auto_import_keys"]
    ):
        status = cast(Callable[..., tuple[int, str, str]], module.run_command)(
            [
                cast(Callable[..., str], module.get_bin_path)("zypper", required=True),
                "--non-interactive",
                "--gpg-auto-import-keys",
                "refresh",
                "--force",
                "--repo",
                module.params["name"],
            ]
        )[0]
        if status:
            module.fail_json(
                msg="Zypper repository refresh failed",
                rc=status,
                changed=True,
                path=str(path),
            )
    module.exit_json(changed=changed, path=str(path))


if __name__ == "__main__":
    main()

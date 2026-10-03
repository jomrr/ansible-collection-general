# Copyright: (c) 2026, Jonas Mauer
# GNU General Public License v3.0+ (see LICENSE)

"""Converge APT sources without replacing unspecified fields."""

from __future__ import annotations

DOCUMENTATION = r"""
module: repo_apt
version_added: 1.1.0
short_description: Manage desired APT sources while preserving unspecified settings
description:
  - Converges selected suites in DEB822 sources, including disabled entries and source packages.
  - Splits multi-suite stanzas when a subset needs different settings.
  - Creates missing sources when their required fields are supplied.
  - Legacy C(.list) files support URIs, enabled state and removal of selected suites.
  - Preserves comments and unspecified fields. Rejects symlinks.
  - Validates changed files with C(apt-get update --print-uris) without downloads.
  - Omits file diffs because source files can contain credentials.
options:
  path:
    description: Absolute source file path.
    type: path
    required: true
  state:
    description: Desired presence; absent without suites removes the file.
    type: str
    choices: [present, absent]
    default: present
  suites:
    description: Exact suite names; omitted selects all sources in the file.
    type: list
    elements: str
  uris:
    description: Archive URIs; one URI for legacy files.
    type: list
    elements: str
  enabled:
    description: Desired enabled flag; omitted preserves supplied settings.
    type: bool
  default_enabled:
    description: Enabled flag for new sources.
    type: bool
    default: true
  types:
    description: APT package types.
    type: list
    elements: str
    choices: [deb, deb-src]
  components:
    description: Archive components; required for new non-path suites.
    type: list
    elements: str
  architectures:
    description: Desired architectures.
    type: list
    elements: str
  signed_by:
    description:
      - Keyring path, HTTPS key URL, fingerprint or armored public key.
      - Downloaded armored keys are embedded; binary keys use C(/etc/apt/keyrings/<hash>.gpg).
      - The hash is the first 24 hexadecimal characters of the SHA-256 of the URL.
      - Existing key files are not automatically removed.
    type: str
requirements:
  - apt-get on the managed host.
attributes:
  check_mode:
    description: Predicts source file and scoped signing-key changes.
    support: full
  diff_mode:
    description: Source contents may contain credentials and are never returned.
    support: none
author: Jonas Mauer (@jomrr)
"""

EXAMPLES = r"""
- name: Use a mirror for Ubuntu Backports
  jomrr.general.repo_apt:
    path: /etc/apt/sources.list.d/ubuntu.sources
    suites: [resolute-backports]
    uris: [https://mirror.example.org/ubuntu]
"""

RETURN = r"""
path:
  description: Selected source file.
  type: str
  returned: always
"""

# Ansible requires documentation before normal imports.
# pylint: disable=wrong-import-position
import hashlib
import re
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, cast

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url
from ansible_collections.jomrr.general.plugins.module_utils._repo_deb822 import (
    AptOptions,
    converge_deb822,
    validate_tokens,
)
from ansible_collections.jomrr.general.plugins.module_utils._repo_deb822_parser import (
    SourceError,
)
from ansible_collections.jomrr.general.plugins.module_utils._repo_files import (
    RepositoryFileError,
    atomic_write,
    read_regular,
)

# pylint: enable=wrong-import-position

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import BinaryIO


def converge_one_line(text: str, options: AptOptions) -> str:
    """Preserve legacy lines while converging URLs, enabled state and presence."""
    unsupported = any(
        value is not None
        for value in (
            options.get("types"),
            options.get("components"),
            options.get("architectures"),
            options.get("signed_by"),
        )
    )
    if unsupported:
        raise SourceError(
            "Legacy .list files support suites, uris, enabled and state; "
            "use .sources for other settings"
        )
    uris = options.get("uris")
    if uris is not None:
        validate_tokens(uris, "uris")
        if len(uris) != 1:
            raise SourceError("One-line .list sources require exactly one mirror URI")
    suites = options.get("suites")
    if suites is not None:
        validate_tokens(suites, "suites")
    entry = re.compile(
        r"^(?P<indent>[ \t]*)(?P<disabled>#[ \t]*)?"
        r"(?P<kind>deb(?:-src)?)[ \t]+(?:\[[^\]\r\n]*\][ \t]+)?"
        r"(?P<uri>[^\s#]+)[ \t]+(?P<suite>[^\s#]+)[^\r\n]*(?:\r?\n)?$"
    )
    found: set[str] = set()
    output = []
    for line in text.splitlines(keepends=True):
        match = entry.match(line)
        if match and (suites is None or match["suite"] in suites):
            found.add(match["suite"])
            if options.get("state") == "absent":
                continue
            if uris is not None:
                line = line[: match.start("uri")] + uris[0] + line[match.end("uri") :]
            if options.get("enabled") is True and match["disabled"]:
                line = line[: match.start("disabled")] + line[match.end("disabled") :]
            elif options.get("enabled") is False and not match["disabled"]:
                line = line[: match.start("kind")] + "# " + line[match.start("kind") :]
        output.append(line)
    if options.get("state") != "absent" and (not found or set(suites or []) - found):
        raise SourceError(
            "New APT sources require a .sources file; selected legacy suites must exist"
        )
    return "".join(output)


def validate_apt(module: AnsibleModule, candidate: str) -> None:
    """Parse a candidate without locks, downloads or cache changes."""
    status = cast(Callable[..., tuple[int, str, str]], module.run_command)(
        [
            cast(Callable[..., str], module.get_bin_path)("apt-get", required=True),
            "update",
            "--print-uris",
            "-o",
            "Dir::Etc::sourcelist=" + candidate,
            "-o",
            "Dir::Etc::sourceparts=-",
            "-o",
            "Debug::NoLocking=1",
        ]
    )[0]
    if status:
        module.fail_json(
            msg="APT rejected the candidate source file",
            rc=status,
            path=module.params["path"],
        )


def signing_key(module: AnsibleModule) -> bool:
    """Resolve HTTPS signing keys to public inline armor or a scoped binary keyring."""
    value = module.params["signed_by"]
    if (
        not value
        or not value.startswith("https://")
        or module.params["state"] == "absent"
    ):
        return False
    response, info = cast(
        "Callable[..., tuple[BinaryIO | None, Mapping[str, object]]]", fetch_url
    )(module, value, timeout=30)
    if response is None or info["status"] != 200:
        raise SourceError("Could not fetch signed_by public key")
    with response:
        content = response.read()
    if b"-----BEGIN PGP PUBLIC KEY BLOCK-----" in content:
        module.params["signed_by"] = content.decode("ascii")
        return False
    path = Path("/etc/apt/keyrings") / (
        hashlib.sha256(value.encode()).hexdigest()[:24] + ".gpg"
    )
    module.params["signed_by"] = str(path)
    if path.exists() and path.read_bytes() == content:
        return False
    if not module.check_mode:
        path.parent.mkdir(mode=0o755, exist_ok=True)
    atomic_write(module, path, content)
    return True


def main() -> None:
    """Compare declared state with source content and commit validated changes."""
    module = cast(Callable[..., AnsibleModule], AnsibleModule)(
        argument_spec={
            "path": {"type": "path", "required": True},
            "state": {
                "type": "str",
                "choices": ["present", "absent"],
                "default": "present",
            },
            "suites": {"type": "list", "elements": "str"},
            "uris": {"type": "list", "elements": "str"},
            "enabled": {"type": "bool"},
            "default_enabled": {"type": "bool", "default": True},
            "types": {"type": "list", "elements": "str", "choices": ["deb", "deb-src"]},
            "components": {"type": "list", "elements": "str"},
            "architectures": {"type": "list", "elements": "str"},
            "signed_by": {"type": "str"},
        },
        supports_check_mode=True,
    )
    path = Path(module.params["path"])
    try:
        if not path.is_absolute() or path.suffix not in {".list", ".sources"}:
            raise SourceError("path must be an absolute .list or .sources filename")
        before = read_regular(path)
        if module.params["state"] == "absent" and module.params["suites"] is None:
            changed = path.exists()
            if changed and not module.check_mode:
                path.unlink()
            module.exit_json(changed=changed, path=str(path))
        key_changed = signing_key(module)
        after = (
            converge_deb822(
                before,
                cast(AptOptions, module.params),
                module.params["default_enabled"],
            )
            if path.suffix == ".sources"
            else converge_one_line(before, cast(AptOptions, module.params))
        )
        changed = before != after
        if changed:
            atomic_write(
                module,
                path,
                after.encode("utf-8"),
                lambda candidate: validate_apt(module, candidate),
            )
    except (SourceError, RepositoryFileError) as error:
        module.fail_json(msg=str(error), path=str(path))
    except (OSError, UnicodeError) as error:
        module.fail_json(
            msg=f"Cannot manage selected APT source ({type(error).__name__})",
            path=str(path),
        )
    module.exit_json(changed=changed or key_changed, path=str(path))


if __name__ == "__main__":
    main()

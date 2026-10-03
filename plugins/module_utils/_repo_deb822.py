# Copyright: (c) 2026, Jonas Mauer
# GNU General Public License v3.0+ (see LICENSE)

"""Converge DEB822 sources through the collection-owned line parser."""

from __future__ import annotations

import re
from typing import TypedDict

from ansible_collections.jomrr.general.plugins.module_utils._repo_deb822_parser import (
    Document,
    Paragraph,
    SourceError,
    parse_sources,
)


class AptOptions(TypedDict, total=False):
    """Validated module arguments consumed by source convergence."""

    suites: list[str] | None
    uris: list[str] | None
    types: list[str] | None
    components: list[str] | None
    architectures: list[str] | None
    signed_by: str | None
    enabled: bool | None
    state: str


def validate_tokens(values: list[str], name: str) -> None:
    """Reject list elements that could introduce configuration syntax."""
    if not values or any(not value or re.search(r"[\s#]", value) for value in values):
        raise SourceError(
            f"{name} must contain nonempty tokens without whitespace or comments"
        )


def desired_fields(options: AptOptions) -> dict[str, str]:
    """Translate explicitly supplied options into DEB822 fields."""
    fields: dict[str, str] = {}
    for key, value in (
        ("uris", options.get("uris")),
        ("types", options.get("types")),
        ("components", options.get("components")),
        ("architectures", options.get("architectures")),
        ("signed_by", options.get("signed_by")),
        ("enabled", options.get("enabled")),
    ):
        if value is None:
            continue
        if isinstance(value, list):
            validate_tokens(value, key)
            value = " ".join(value)
        elif isinstance(value, bool):
            value = "yes" if value else "no"
        elif isinstance(value, str) and "\n" in value:
            value = "\n" + "\n".join(
                " " + (line.strip() or ".") for line in value.strip().splitlines()
            )
        field = "URIs" if key == "uris" else key.replace("_", "-").title()
        if not isinstance(value, str):
            raise SourceError("Invalid APT source field type")
        fields[field] = value
    return fields


def ensure_new_source(
    fields: dict[str, str], suites: list[str], enabled: bool
) -> dict[str, str]:
    """Require a usable declaration before adding a missing suite or source."""
    if not suites or not fields.get("URIs"):
        raise SourceError("New APT sources require suites and uris")
    if not fields.get("Components") and any(
        not suite.endswith("/") for suite in suites
    ):
        raise SourceError("New non-path suites require components")
    return {
        "Types": "deb",
        "Enabled": "yes" if enabled else "no",
        **fields,
        "Suites": " ".join(suites),
    }


def update_stanza(
    source: Document,
    stanza: Paragraph,
    selected: list[str],
    fields: dict[str, str],
    removing: bool,
) -> None:
    """Retain unselected suites while applying fields to the selected paragraph."""
    remaining = [
        suite for suite in stanza.get("Suites").split() if suite not in selected
    ]
    target = stanza
    if remaining:
        target = stanza.copy()
        stanza.set("Suites", " ".join(remaining))
        target.set("Suites", " ".join(selected))
        if not removing:
            source.append(target)
    elif removing:
        source.remove(stanza)
    if not removing:
        for key, value in fields.items():
            target.set(key, value)


def converge_deb822(text: str, options: AptOptions, enabled: bool = True) -> str:
    """Converge selected suites, splitting only when their desired fields differ."""
    source = parse_sources(text)
    suites = options.get("suites")
    if suites is not None:
        validate_tokens(suites, "suites")
    fields = desired_fields(options)
    found: set[str] = set()
    for stanza in source.paragraphs():
        present = stanza.get("Suites", "").split()
        selected = [suite for suite in present if suites is None or suite in suites]
        if not selected:
            continue
        found.update(selected)
        removing = options.get("state") == "absent"
        if not removing and all(
            stanza.get(key, "").strip() == value.strip()
            for key, value in fields.items()
        ):
            continue
        update_stanza(source, stanza, selected, fields, removing)
    missing = [suite for suite in (suites or []) if suite not in found]
    if options.get("state") != "absent" and (missing or not found):
        new_fields = ensure_new_source(fields, missing, enabled)
        source.append(
            parse_sources(
                "".join(key + ": " + value + "\n" for key, value in new_fields.items())
            ).paragraphs()[0]
        )
    return source.to_text()

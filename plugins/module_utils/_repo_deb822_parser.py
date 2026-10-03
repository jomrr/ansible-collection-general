# Copyright: (c) 2026, Jonas Mauer
# GNU General Public License v3.0+ (see LICENSE)

"""Strict, line-preserving DEB822 parsing internal to this collection."""

from __future__ import annotations

import re
from dataclasses import dataclass

FIELD = re.compile(
    r"(?P<name>[!-9;-~]+):(?P<space>[ \t]*)(?P<value>[^\r\n]*)(?P<end>\r?\n)?"
)


class SourceError(ValueError):
    """A source error safe to report without supplied file contents."""


def field_rows(lines: list[str]) -> dict[str, list[int]]:
    """Index fields and continuations; column-zero comments never end a field."""
    result: dict[str, list[int]] = {}
    current: list[int] | None = None
    for index, line in enumerate(lines):
        if line.startswith("#"):
            continue
        if line.startswith((" ", "\t")) and line.strip():
            if current is None:
                raise SourceError("Unsupported DEB822 continuation without a field")
            current.append(index)
            continue
        match = FIELD.fullmatch(line)
        if match is None:
            raise SourceError("Unsupported DEB822 source field layout")
        name = match["name"].lower()
        if name in result:
            raise SourceError("Duplicate DEB822 field in source paragraph")
        current = [index]
        result[name] = current
    return result


@dataclass(eq=False)
class Paragraph:
    """Own paragraph lines while retaining comments between continuation lines."""

    lines: list[str]

    def get(self, name: str, default: str = "") -> str:
        """Read first and continued lines, ignoring interspersed comments."""
        rows = field_rows(self.lines).get(name.lower())
        if rows is None:
            return default
        first = self.lines[rows[0]].split(":", 1)[1].strip(" \t\r\n")
        return "\n".join([first, *(self.lines[row].rstrip("\r\n") for row in rows[1:])])

    def set(self, name: str, value: str) -> None:
        """Replace active field lines at their position or append a missing field."""
        rows = field_rows(self.lines).get(name.lower())
        ending = "\r\n" if any(line.endswith("\r\n") for line in self.lines) else "\n"
        values = value.split("\n")
        prefix = name + ": "
        final_ending = ending
        if rows is not None:
            match = FIELD.fullmatch(self.lines[rows[0]])
            if match is None:
                raise SourceError("Unsupported DEB822 source field layout")
            prefix = match["name"] + ":" + match["space"]
            if len(values) >= len(rows) and not self.lines[rows[-1]].endswith("\n"):
                final_ending = ""
        replacement = [prefix + values[0]] + values[1:]
        replacement = [line + ending for line in replacement[:-1]] + [
            replacement[-1] + final_ending
        ]
        if rows is None:
            if self.lines and not self.lines[-1].endswith("\n"):
                self.lines[-1] += ending
            self.lines.extend(replacement)
        else:
            # Keep comments at their original position between continued values.
            for position, row in enumerate(rows):
                self.lines[row] = (
                    replacement[position] if position < len(replacement) else ""
                )
            if len(replacement) > len(rows):
                self.lines[rows[-1] + 1 : rows[-1] + 1] = replacement[len(rows) :]
            self.lines = [line for line in self.lines if line]

    def copy(self) -> Paragraph:
        """Copy exact lines without reparsing or sharing mutable state."""
        return Paragraph(self.lines.copy())


@dataclass
class Document:
    """Keep paragraphs and untouched separator/comment-only blocks in order."""

    blocks: list[Paragraph | str]

    def paragraphs(self) -> list[Paragraph]:
        """Return the original paragraph identities for safe iteration during edits."""
        return [block for block in self.blocks if isinstance(block, Paragraph)]

    def append(self, paragraph: Paragraph) -> None:
        """Separate a new paragraph without normalizing existing content."""
        text = self.to_text()
        if text and not text.endswith("\n"):
            self.blocks.append("\n")
        if text and text.splitlines()[-1].strip():
            self.blocks.append("\n")
        self.blocks.append(paragraph)

    def remove(self, paragraph: Paragraph) -> None:
        """Remove exactly the selected paragraph, retaining neighboring blocks."""
        self.blocks.remove(paragraph)

    def to_text(self) -> str:
        """Serialize original lines and separators without formatting changes."""
        return "".join(
            "".join(block.lines) if isinstance(block, Paragraph) else block
            for block in self.blocks
        )


def parse_sources(text: str) -> Document:
    """Split only on blank lines and reject unsupported or duplicate field layouts."""
    blocks: list[Paragraph | str] = []
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        if not line.strip():
            if lines:
                fields = field_rows(lines)
                blocks.append(Paragraph(lines) if fields else "".join(lines))
                lines = []
            blocks.append(line)
        else:
            lines.append(line)
    if lines:
        fields = field_rows(lines)
        blocks.append(Paragraph(lines) if fields else "".join(lines))
    return Document(blocks)

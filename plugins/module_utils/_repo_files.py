# Copyright: (c) 2026, Jonas Mauer
# GNU General Public License v3.0+ (see LICENSE)

"""Shared lossless file I/O for repository modules."""

from __future__ import annotations

import os
import stat
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import cast

from ansible.module_utils.basic import AnsibleModule


class RepositoryFileError(ValueError):
    """A file constraint error that contains no repository contents."""


def read_regular(path: Path) -> str:
    """Read a regular UTF-8 file without following symlinks; absence is empty."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return ""
    with os.fdopen(descriptor, "rb") as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise RepositoryFileError("Repository path must refer to a regular file")
        return source.read().decode("utf-8")


def atomic_write(
    module: AnsibleModule,
    path: Path,
    content: bytes,
    validator: Callable[[str], None] | None = None,
) -> None:
    """Validate a temporary candidate and atomically replace it, retaining metadata."""
    descriptor, temporary = tempfile.mkstemp(dir=module.tmpdir, suffix=path.suffix)
    with os.fdopen(descriptor, "wb") as destination:
        destination.write(content)
    try:
        if validator is not None:
            validator(temporary)
        if not module.check_mode:
            cast(Callable[..., bool], module.atomic_move)(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

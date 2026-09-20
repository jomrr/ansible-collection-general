# Copyright: (c) 2026, Jonas Mauer
# GNU General Public License v3.0+ (see LICENSE)

"""Internal MAC address derivation shared by the module and lookup plugin."""

from hashlib import sha256


def generate_mac(name: str) -> str:
    """Return a deterministic address with the 52:54 prefix and four hash bytes."""
    digest = sha256(name.encode("utf-8")).hexdigest()
    return "52:54:" + ":".join(digest[index : index + 2] for index in range(0, 8, 2))

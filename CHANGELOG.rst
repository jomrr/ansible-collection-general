===============================
jomrr.general 1.1 Release Notes
===============================

.. contents:: Topics

v1.1.0
======

Minor Changes
-------------

- repo - resolve desired repository declarations and caller-supplied presets.
- repo_apt - manage selected APT sources with a strict, dependency-free DEB822 parser.
- repo_rpm - manage DNF, DNF5 and Zypper sections while preserving unrelated configuration.

New Plugins
-----------

Filter
~~~~~~

- repo - Resolve desired repositories and caller\-supplied presets

New Modules
-----------

- repo_apt - Manage desired APT sources while preserving unspecified settings
- repo_rpm - Manage desired DNF and Zypper repository settings

v1.0.0
======

Minor Changes
-------------

- Add the mac module and lookup plugin with shared SHA-256 address generation and the 52:54 prefix.
- Hash names directly by default; positive module counts generate indexed addresses.
- Install development dependencies directly from pyproject.toml without a uv.lock file.
- License the collection under GPL-3.0-or-later.
- Manage collection metadata, documentation, tooling and workflows through Ansible Factory.
- Return calculated MAC addresses in module check mode without reporting changes.

Bugfixes
--------

- mac - embed module and lookup documentation in Python to prevent duplicate Galaxy entries.

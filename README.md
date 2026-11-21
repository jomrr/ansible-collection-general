# Ansible Collection: jomrr.general

![GitHub](https://img.shields.io/github/license/jomrr/ansible-collection-general)
![GitHub last commit](https://img.shields.io/github/last-commit/jomrr/ansible-collection-general)
![GitHub issues](https://img.shields.io/github/issues-raw/jomrr/ansible-collection-general)
[![dev](https://img.shields.io/github/actions/workflow/status/jomrr/ansible-collection-general/dev.yml?branch=dev&label=dev)](https://github.com/jomrr/ansible-collection-general/actions/workflows/dev.yml?query=branch%3Adev)
[![main](https://img.shields.io/github/actions/workflow/status/jomrr/ansible-collection-general/main.yml?branch=main&label=main)](https://github.com/jomrr/ansible-collection-general/actions/workflows/main.yml?query=branch%3Amain)

Ansible collection with general modules and plugins.

## Purpose

Manage selected APT and RPM package repositories while retaining unspecified
settings, transfer batches of files between hosts, and generate reproducible MAC
addresses for virtual machines from stable host names.

## Requirements

- ansible-core >=2.20.0
- repo_apt requires apt-get on the managed host and uses Python's standard
  library.
- repo_rpm requires zypper only when auto_import_keys is enabled. DNF and DNF5
  use the same file format.
- The repo filter runs on the controller; it and the MAC plugins need no
  additional Python packages.
- slurp_files and write_files use Python's standard library and Ansible on the
  managed host.
- write_files additionally requires getfacl and setfacl when managing POSIX
  ACLs.

## Installation

```console
ansible-galaxy collection install jomrr.general
```

## Contents

### Modules

| Name | idempotent | check_mode | Description |
| ---- | ---------- | ---------- | ----------- |
| [`jomrr.general.mac`](plugins/modules/mac.py) | n/a (read) | yes | Generate deterministic MAC addresses from a name |
| [`jomrr.general.repo_apt`](plugins/modules/repo_apt.py) | True | yes | Manage desired APT sources while preserving unspecified settings |
| [`jomrr.general.repo_rpm`](plugins/modules/repo_rpm.py) | True | yes | Manage desired DNF and Zypper repository settings |
| [`jomrr.general.slurp_files`](plugins/modules/slurp_files.py) | n/a (read) | yes | Read multiple files as base64 in one call |
| [`jomrr.general.write_files`](plugins/modules/write_files.py) | True | yes | Write multiple base64-encoded files in one call |

### Filter Plugins

| Name | idempotent | check_mode | Description |
| ---- | ---------- | ---------- | ----------- |
| [`jomrr.general.repo`](plugins/filter/repo.py) | n/a | n/a | Resolve desired repositories and caller-supplied presets |

### Lookup Plugins

| Name | idempotent | check_mode | Description |
| ---- | ---------- | ---------- | ----------- |
| [`jomrr.general.mac`](plugins/lookup/mac.py) | n/a | n/a | Generate MAC address from string |

## Batch File Transfer

`jomrr.general.slurp_files` reads a list of paths in one module call and returns
a `content` mapping from absolute paths to base64-encoded bytes.
`jomrr.general.write_files` writes a list of `path` and base64 `content` pairs
in one call, returning the changed `paths`. Both handle binary files.

Writes compare bytes before atomically replacing a file. Destination directories
must already exist. New files use the default SELinux context and, when both
`mode` and `acl` are omitted, the current umask. Explicit modes protect new content from the start.
Optional `mode`, `acl`, `owner` and `group` values are enforced only when supplied.
Each file accepts either `mode` or `acl`. Omit both to retain an existing POSIX ACL,
including its mask, across content updates.
With an extended ACL, the group bits of `mode` control the mask, as with `chmod`.

`acl` defines the complete access ACL and removes unspecified entries. Explicit
masks are retained; without one, `setfacl` calculates the mask. For example:

```yaml
jomrr.general.write_files:
  files:
    - path: /srv/share/host.der
      content: "{{ certificates.content['/var/lib/ca/host.der'] }}"
      acl:
        - user::rw-
        - user:service:r--
        - group::---
        - mask::r--
        - other::---
```

This ACL reports mode `0640` because its mask allows reading; the owning group
has no access. A repeated run reports no change. New ACL-managed files start
with `0600` before the ACL is applied. Content replacement is atomic; ownership
and ACL changes are separate filesystem operations. Check mode predicts both
content and ACL changes without writing.

Writing rejects a symlink in the final path component; linked parent directories
are allowed. Reading follows symlinks. Batches stop at the first error without
rolling back earlier writes. File contents are held in memory.

Write inputs are masked and content diffs are omitted. Use task-level `no_log: true`
when reading confidential files, because the read result intentionally contains their contents.

## Package Repositories

`jomrr.general.repo_apt` manages selected suites in a DEB822 `.sources` file.
Omitted suites select the whole file. Existing `.list` files support mirror URLs,
enabled state and removal; new sources use DEB822. Omitted options are preserved.

`jomrr.general.repo_rpm` selects a repository ID with `name` and its file with
`path`. For example, the ID `extras` can be in `almalinux-extras.repo`.
Creation defaults apply only to new sections. Explicit mirror URLs replace
alternative `metalink` or `mirrorlist` settings while retaining other options,
comments and sibling sections. `backend: dnf` covers DNF and DNF5;
`backend: zypper` manages openSUSE repository files.

`jomrr.general.repo` resolves declarations and caller-supplied presets before
module execution. It accepts a list followed by `catalog`, `backend`, `policies`
and `directory`. The collection includes no distro presets or default-repo catalogue.

APT downloaded armored keys are embedded. Binary keys use
`/etc/apt/keyrings/<hash>.gpg`, with the first 24 hexadecimal SHA-256 characters
of the URL. Existing key files are not automatically deleted.

DEB822 files are parsed without external Python dependencies. The parser
preserves comments and multiline fields and rejects duplicate fields or
unsupported layouts. Integration tests cover Debian 13 and Ubuntu 24.04
and 26.04 with each distribution's system Python and native APT validator.

## Address Generation

The `jomrr.general.mac` module runs on the managed host and returns a list
of addresses in `macs`. The `jomrr.general.mac` lookup runs on the controller
and returns a single address with `lookup()` or a one-element list with `query()`.

Both hash the input name with SHA-256 and use `52:54:` followed by the first
four hash bytes. The module's optional `count` defaults to `null`: omitted,
null or nonpositive counts hash the name directly, producing the same
address as the lookup for that name.

A positive `count` generates that many addresses from `<name>-<index>`,
with indices starting at zero. For example, the first address for
`name: guest` and `count: 2` equals the lookup result for `guest-0`.

## Check Mode

Repository modules predict changes without writing managed files or refreshing
repositories. MAC generation always returns unchanged. Repository file diffs are
omitted because files may contain credentials. slurp_files reads without
changes; write_files predicts content and attribute changes without writing.

## Example Playbook

### Transfer certificates in two module calls

```yaml
---
- name: Distribute certificates
  hosts: consumers
  gather_facts: false
  tasks:
    - name: Read certificates from the CA host
      jomrr.general.slurp_files:
        paths:
          - /var/lib/ca/host.pem
          - /var/lib/ca/host.der
      delegate_to: ca.example.org
      register: certificates
      no_log: true

    - name: Write certificates on the consumer
      jomrr.general.write_files:
        files:
          - path: /etc/pki/host.pem
            content: "{{ certificates.content['/var/lib/ca/host.pem'] }}"
            mode: '0644'
          - path: /srv/share/host.der
            content: "{{ certificates.content['/var/lib/ca/host.der'] }}"
```

### Manage repositories installed by distribution or release packages

```yaml
---
- name: Select private Fedora mirrors
  hosts: fedora
  tasks:
    - name: Use a private Fedora mirror
      jomrr.general.repo_rpm:
        backend: dnf
        path: /etc/yum.repos.d/fedora.repo
        name: fedora
        enabled: true
        baseurl: ['https://mirror.example.org/fedora/$releasever/$basearch']

    - name: Change RPM Fusion installed by its release package
      jomrr.general.repo_rpm:
        backend: dnf
        path: /etc/yum.repos.d/rpmfusion-free.repo
        name: rpmfusion-free
        baseurl: ['https://mirror.example.org/rpmfusion/free/fedora/$releasever/$basearch']

- name: Select a private APT mirror
  hosts: debian
  tasks:
    - name: Change the Backports mirror
      jomrr.general.repo_apt:
        path: /etc/apt/sources.list.d/backports.sources
        suites: [trixie-backports]
        uris: ['https://mirror.example.org/debian']
        components: [main]
        signed_by: /usr/share/keyrings/debian-archive-keyring.gpg

```

### Generate addresses for a virtual machine

```yaml
---
- name: Generate virtual machine MAC addresses
  hosts: localhost
  gather_facts: false
  tasks:
    - name: Generate one address from the name
      jomrr.general.mac:
        name: test_guest
      register: guest_mac

    - name: Generate the same address on the controller
      ansible.builtin.debug:
        msg: "{{ lookup('jomrr.general.mac', 'test_guest') }}"

    - name: Generate two indexed addresses
      jomrr.general.mac:
        name: test_guest
        count: 2
      register: guest_macs

    - name: Display the indexed addresses
      ansible.builtin.debug:
        var: guest_macs.macs
```

## References

- [Collection documentation](https://github.com/jomrr/ansible-collection-general)

## Author

- Jonas Mauer

## License

License: GPL-3.0-or-later.
See [LICENSE](LICENSE) for the full license text.

Copyright (c) 2022-2026 Jonas Mauer.

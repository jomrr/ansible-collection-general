# Ansible Collection: jomrr.general

![GitHub](https://img.shields.io/github/license/jomrr/ansible-collection-general)
![GitHub last commit](https://img.shields.io/github/last-commit/jomrr/ansible-collection-general)
![GitHub issues](https://img.shields.io/github/issues-raw/jomrr/ansible-collection-general)
[![dev](https://img.shields.io/github/actions/workflow/status/jomrr/ansible-collection-general/dev.yml?branch=dev&label=dev)](https://github.com/jomrr/ansible-collection-general/actions/workflows/dev.yml?query=branch%3Adev)
[![main](https://img.shields.io/github/actions/workflow/status/jomrr/ansible-collection-general/main.yml?branch=main&label=main)](https://github.com/jomrr/ansible-collection-general/actions/workflows/main.yml?query=branch%3Amain)

Ansible collection with general modules and plugins.

## Purpose

Generate reproducible MAC addresses for virtual machines from stable host names.
The module and lookup plugin share SHA-256 address generation with the 52:54
prefix.

## Requirements

- ansible-core >=2.20.0
- Both plugins use Python's standard library and Ansible; no additional Python
  packages or system programs are required.

## Installation

```console
ansible-galaxy collection install jomrr.general
```

## Contents

### Modules

| Name | Description | idempotent | check_mode |
| ---- | ----------- | ---------- | ---------- |
| [`jomrr.general.mac`](plugins/modules/mac.py) | Generate deterministic MAC addresses from a name | n/a (read) | yes |

### Lookup Plugins

| Name | Description | idempotent | check_mode |
| ---- | ----------- | ---------- | ---------- |
| [`jomrr.general.mac`](plugins/lookup/mac.py) | Generate MAC address from string | n/a | n/a |

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

The module calculates the same addresses in normal and check mode and always
returns unchanged.

## Example Playbook

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

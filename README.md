# Ansible collection: jam82.general

Documentation for the collection jam82.general.

## Modules

### jam82.general.gen_mac_from_name

Used with roles kickstart and virtinstall to generate reproducable MACs for VMs.

## Installation

### molecule.yml

Specify the requirements file in molecule.yml:

```yaml
---
# file: molecule/default/molecule.yml
dependency:
  name: galaxy
  options:
    requirements-file: requirements.yml
```

### requirements.yml

```yaml
---

collections:
  - name: git+https://github.com/jam82/ansible-collection-general.git
    version: main
```

This automatically installs into the namespace jam82 defined in `galaxy.yml`.

## Usage

### Example for gen_mac_from_name

Usage in role task to generate 2 MACs for host `test_guest`:

```yaml
    - name: "Generate reproducable MAC Address(es) from name/fqdn"
      jam82.general.gen_mac_from_name:
        name: "test_guest"
        count: 2
```

## License and Author

- Author:: [jam82](https://github.com/jam82/)
- Copyright:: 2022, [jam82](https://github.com/jam82/)

Licensed under [MIT License](https://opensource.org/licenses/MIT).
See [LICENSE](https://github.com/jam82/ansible-role-virtinstall/blob/master/LICENSE) file in repository.

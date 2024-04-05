# Ansible collection: jomrr.general

Documentation for the collection jomrr.general.

## Modules

### jomrr.general.gen_mac_from_name

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
  - name: git+https://github.com/jomrr/ansible-collection-general.git
    version: main
```

This automatically installs into the namespace jomrr defined in `galaxy.yml`.

## Usage

### Example for gen_mac_from_name

Usage in role task to generate 2 MACs for host `test_guest`:

```yaml
    - name: "Generate reproducable MAC Address(es) from name/fqdn"
      jomrr.general.gen_mac_from_name:
        name: "test_guest"
        count: 2
```

## License and Author

- Author:: [jomrr](https://github.com/jomrr/)
- Copyright:: 2022, [jomrr](https://github.com/jomrr/)

Licensed under [MIT License](https://opensource.org/licenses/MIT).
See [LICENSE](https://github.com/jomrr/ansible-role-virtinstall/blob/master/LICENSE) file in repository.

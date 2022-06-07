# Ansible collection: jam82.general

Documentation for the collection jam82.general.

## Modules

### jam82.general.gen_mac_from_name

Used with roles kickstart and virtinstall to generate reproducable MACs for VMs.

## dependency part of molecule.yml

```yaml
dependency:
  name: galaxy
  options:
    requirements-file: collections.yml
    role-file: requirements.yml
```

## requirements.yml

```yaml
---

collections:
  - name: git+https://github.com/jam82/ansible-collection-general.git
    version: main
```

This automatically installs into the namespace defined in `galaxy.yml`.

## usage in role tasks/main.yml

```yaml
    - name: "Generate reproducable MAC Address(es) from name/fqdn"
      jam82.general.gen_mac_from_name:
        name: "test_guest"
        count: 2
```

cool :)

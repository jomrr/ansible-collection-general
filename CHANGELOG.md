# CHANGELOG



## v0.2.0 (2024-03-20)

### Feature

* feat: generate MAC addresses from strings using sha256

- Create a new file `mac_address.py` for generating MAC addresses from strings using sha256
- Defined a lookup plugin to generate a MAC address from a given string
- Added example and return documentation for the lookup plugin
- Implemented the `run` function to generate the MAC address from the input string
- Modify the `pyproject.toml` file by adding a build command using sed for updating version numbers

Signed-off-by: Jonas Mauer &lt;jam@kabelmail.net&gt; ([`8639de3`](https://github.com/jam82/ansible-collection-general/commit/8639de389840c2da36eb7c7f105be2ed4e5019d1))


## v0.1.0 (2024-03-19)

### Build

* build(release): version 0.1.0 ([`d60fcff`](https://github.com/jam82/ansible-collection-general/commit/d60fcff9ea67dd8e609312879f58ea5d5092da86))

### Chore

* chore: standardize project configuration and update licensing information

- Add a `.pre-commit-config.yaml` file with hooks for commitizen
- Update the version in `galaxy.yml` from `0.0.1` to `1.0.0`
- Update the description in `galaxy.yml` to `&#34;Ansible collection with general modules and plugins.&#34;`
- Change the license in `gen_mac_from_name.py` from GNU General Public License v3.0 to MIT License
- Update the version in `pyproject.toml` from `0.0.0` to the final version for the release

Signed-off-by: Jonas Mauer &lt;jam@kabelmail.net&gt; ([`10a984f`](https://github.com/jam82/ansible-collection-general/commit/10a984f5f0a599701fed3bd3ba83f34d999c1f85))

### Feature

* feat: module for mac generation ([`91d1bd1`](https://github.com/jam82/ansible-collection-general/commit/91d1bd1c4b4949c0d7a3c8da6213ec52fd9fa051))

### Unknown

* doc: fix typo ([`bbe13bc`](https://github.com/jam82/ansible-collection-general/commit/bbe13bca4cf1ff9e4c67843ddaae5667f80b3f44))

* doc: add license and author info and add examples ([`43aa9e1`](https://github.com/jam82/ansible-collection-general/commit/43aa9e1d1d4ddb9f4de406648fb4b63ebb03952b))

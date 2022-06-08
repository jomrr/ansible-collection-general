#!/usr/bin/python

# Copyright: (c) 2020, Jonas Mauer <jam@kabelmail.net>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
This ansible module generates a mac address from a name and network card index.
"""

from __future__ import absolute_import, division, print_function

from hashlib import md5

from ansible.module_utils.basic import AnsibleModule

__metaclass__ = type

DOCUMENTATION = r'''
---
module: gen_mac_from_name

short_description: Generate MAC(s) from name/fqdn and networks

version_added: "0.0.1"

description: Generate reproducable MAC address(es) from a name/fqdn.

options:
    name:
        description: This is the FQDN/name of a guest to generate MAC(s) for.
        required: true
        type: str
    count:
        description: This is the numbers of MACs to generate.
        required: false
        type: int

author:
    - Jonas Mauer (@jam82)
'''

EXAMPLES = r'''
- name: Test MAC generation
  gen_mac_from_fqdn:
    name: test.mauer.in
    count: 1
'''

RETURN = r'''
original_message:
    description: The original name and count param that was passed in.
    type: str
    returned: always
    sample:
        test.mauer.in,
        2
message:
    description: The output message that the module generates.
    type: str
    returned: always
    sample: 'ok'
macs:
    description: The list with the MAC address(es).
    type: list
    returned: always
    sample: [
        '02:09:07:10:12:02',
        '02:06:13:00:22:09'
    ]
'''


def get_md5_hex(name: str):
    """return md5 hash in hexadecimal format"""
    return md5(name.encode('utf-8')).hexdigest()

def split_n(split: list, by_n: int):
    """split string to list by number of characters in n"""
    return [split[index : index + by_n] for index in range(0, len(split), by_n)]

def gen_mac(name: str, count: int):
    """generate mac address based on name and network card index"""
    macs = []
    # loop over count
    for idx in range(0, count):
        # get hash from fqdn + network index, e.g. get_md5('test.mauer.in-1')
        md5hex  = get_md5_hex(name + '-' + str(idx))
        # md5 = 6abba68431...
        # we split it by 2 so parts = [6a, bb, a6, 84, 31, ..]
        parts = split_n(md5hex, 2)
        # x2:xx.. is a private mac prefix, so we use 02
        # and add the first 5 elements of parts
        elements = ["02",parts[0],parts[1],parts[2],parts[3],parts[4]]
        # then we join elements by ':' to get the mac address
        # which in this case is "02:6a:bb:a6:84:31"
        mac = ':'.join(elements)
        # and append it to the list of macs that we return
        macs.append(mac)
    return macs

def run_module():
    """the wrapper function for the ansible module"""
    module_args = dict(
        name=dict(type='str', required=True),
        count=dict(type='int', required=False,default=1),
    )

    result = dict(
        changed=False,
        original_message='',
        message='',
        macs='',
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    if module.check_mode:
        module.exit_json(**result)

    result['original_message'] = [
        module.params['name'],
        module.params['count']
    ]
    result['message'] = 'ok'
    result['macs'] = gen_mac(module.params['name'], module.params['count'])

    module.exit_json(**result)


def main():
    """the main function of the module"""
    run_module()


if __name__ == '__main__':
    main()

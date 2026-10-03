# Copyright: (c) 2026, Jonas Mauer
# GNU General Public License v3.0+ (see LICENSE)

"""Exercise real Ansible argument validation and JSON results in unit tests."""

import io
import json
from collections.abc import Callable, Mapping
from contextlib import redirect_stdout

from ansible.module_utils.testing import patch_module_args


def run_module(
    main: Callable[[], None], arguments: Mapping[str, object]
) -> dict[str, object]:
    """Capture the module protocol without replacing AnsibleModule or its imports."""
    output = io.StringIO()
    with patch_module_args(dict(arguments)), redirect_stdout(output):
        try:
            main()
        except SystemExit as error:
            if error.code not in (0, 1):
                raise
    result: dict[str, object] = json.loads(output.getvalue())
    return result

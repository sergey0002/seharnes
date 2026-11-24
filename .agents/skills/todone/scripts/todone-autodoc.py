#!/usr/bin/env python3
"""Compatibility entry point for ``tcheck autodoc``.

It deliberately uses the same CheckCli parser and handlers; there is no second
bundle or output contract.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tdcore.check_cli import CheckCli  # noqa: E402
from tdcore.cli import main            # noqa: E402


if __name__ == "__main__":
    argv = list(sys.argv[1:])
    if not argv:
        argv = ["autodoc"]
    elif argv[0] in ("-h", "--help"):
        argv = ["autodoc"] + argv
    else:
        argv = ["autodoc"] + argv
    main(CheckCli, argv)

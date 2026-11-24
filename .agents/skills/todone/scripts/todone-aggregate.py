#!/usr/bin/env python3
"""Thin standalone alias for ``tcheck aggregate``."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tdcore.check_cli import CheckCli
from tdcore.cli import main


if __name__ == "__main__":
    main(CheckCli, ["aggregate"] + sys.argv[1:])

#!/usr/bin/env python3
"""Точка входа `tcheck`: контроль, типы, потоки, роли, привязки возможностей.

Тонкий файл: состав команд объявлен в `tdcore/check_cli.py`, общий контракт
вывода — в `tdcore/cli.py`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tdcore.check_cli import CheckCli  # noqa: E402
from tdcore.cli import main            # noqa: E402

if __name__ == "__main__":
    main(CheckCli)

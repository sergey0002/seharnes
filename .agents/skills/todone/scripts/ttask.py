#!/usr/bin/env python3
"""Точка входа `ttask`: запись как работа.

Тонкий файл: состав команд объявлен в `tdcore/task_cli.py`, общий контракт
вывода — в `tdcore/cli.py`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tdcore.cli import main          # noqa: E402
from tdcore.task_cli import TaskCli  # noqa: E402

if __name__ == "__main__":
    main(TaskCli)

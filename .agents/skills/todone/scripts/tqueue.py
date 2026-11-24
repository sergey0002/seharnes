#!/usr/bin/env python3
"""Точка входа `tqueue`: очередь как порядок.

Тонкий файл: состав команд объявлен в `tdcore/queue_cli.py`, общий контракт
вывода — в `tdcore/cli.py`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tdcore.cli import main          # noqa: E402
from tdcore.queue_cli import QueueCli  # noqa: E402

if __name__ == "__main__":
    main(QueueCli)

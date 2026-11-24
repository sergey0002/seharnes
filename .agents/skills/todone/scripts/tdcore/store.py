"""Хранилище записей: папка `data/`, одна папка на запись, атомарная запись.

Источник правды — файл записи. Хранилище умеет читать, писать с резервной
копией, создавать запись с выдачей идентификатора и перечислять записи.
"""

import datetime
import json
import os
import re
import shutil

from . import schema
from .errors import Issue, SkillError
from .record import Record, new_task


def modified_at(path):
    """Метка изменения файла записи: время для строки индекса."""
    try:
        stamp = datetime.datetime.fromtimestamp(os.path.getmtime(path),
                                                datetime.timezone.utc)
    except OSError:
        return None
    # Микросекунды нужны для DIGEST_STALE: несколько CLI-правок могут
    # произойти в одну секунду.
    return stamp.isoformat().replace("+00:00", "Z")


def folder_name(task_id, kind):
    """Имя папки записи: номер первым, тип вторым."""
    return "%s-%s" % (task_id, kind)


class RecordStore:
    """Записи одной очереди: папка `data/` внутри `.todone/` очереди."""

    def __init__(self, data_dir):
        self.data_dir = data_dir

    # --- пути ---
    def folder_of(self, task_id, kind=None):
        if kind:
            return os.path.join(self.data_dir, folder_name(task_id, kind))
        for name in self.names():
            if name.startswith(task_id + "-"):
                return os.path.join(self.data_dir, name)
        return None

    def path_of(self, task_id, kind=None):
        folder = self.folder_of(task_id, kind)
        return os.path.join(folder, "task.json") if folder else None

    def names(self):
        if not os.path.isdir(self.data_dir):
            return []
        return sorted(n for n in os.listdir(self.data_dir)
                      if os.path.isdir(os.path.join(self.data_dir, n)))

    # --- чтение ---
    def read(self, task_id):
        """Запись по идентификатору: путь разрешается через имя папки."""
        path = self.path_of(task_id)
        if not path or not os.path.isfile(path):
            raise SkillError("RECORD_NOT_FOUND",
                             "записи %s в папке data нет" % task_id, task_id)
        return self.read_path(path)

    def read_path(self, path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except ValueError as exc:
            raise SkillError("JSON_MALFORMED",
                             "файл не разбирается как JSON: %s" % exc, path)
        except OSError as exc:
            raise SkillError("JSON_MALFORMED", "файл не читается: %s" % exc, path)
        if not isinstance(data, dict):
            raise SkillError("JSON_MALFORMED",
                             "запись должна быть объектом, а не %s" % type(data).__name__,
                             path)
        return Record(data, path=path)

    def read_all(self):
        """Все записи папки: порядок по имени, то есть по идентификатору."""
        records = []
        for name in self.names():
            path = os.path.join(self.data_dir, name, "task.json")
            if os.path.isfile(path):
                records.append(self.read_path(path))
        return records

    # --- запись ---
    def write(self, record):
        """Атомарная запись с резервной копией прежнего файла."""
        if not record.path:
            raise SkillError("RECORD_NOT_FOUND",
                             "у записи нет пути: её не создали", str(record.id))
        folder = os.path.dirname(record.path)
        os.makedirs(folder, exist_ok=True)
        if os.path.isfile(record.path):
            shutil.copy2(record.path, record.path + ".bak")
        tmp = record.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(record.data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, record.path)
        return record

    # --- создание ---
    FOLDER_ID_RE = re.compile(r"^(?P<prefix>[A-Z])-(?P<digits>\d{3})-")

    def next_id(self, prefix="T"):
        """Следующий идентификатор: сквозная нумерация по именам папок записей."""
        highest = 0
        for name in self.names():
            match = self.FOLDER_ID_RE.match(name)
            if match and match.group("prefix") == prefix:
                highest = max(highest, int(match.group("digits")))
        return "%s-%03d" % (prefix, highest + 1)

    def create(self, title, kind, **fields):
        """Создать запись: папка, файл, идентификатор. Тип и id неизменны."""
        if not isinstance(title, str) or not title.strip():
            raise SkillError("EMPTY", "заголовок записи обязателен", "ttask new")
        if not schema.TYPE_ID_RE.match(kind or ""):
            raise SkillError("TYPE_UNKNOWN",
                             "имя типа «%s» не объявлено или не в форме" % kind,
                             "ttask new")
        task_id = self.next_id("T")
        data = new_task(task_id, title.strip(), kind, **fields)
        folder = os.path.join(self.data_dir, folder_name(task_id, kind))
        if os.path.isdir(folder):
            raise SkillError("RECORD_NOT_FOUND",
                             "папка %s уже существует" % folder, folder)
        record = Record(data, path=os.path.join(folder, "task.json"),
                        folder=folder)
        return self.write(record)

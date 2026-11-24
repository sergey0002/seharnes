"""Очередь и реестр очередей: пути, разрешение записи, настройка проекта.

Очередь — это порядок и ссылки. Записи живёт в папке `data/`, индекс —
производный кэш, пороги чтения — настройка проекта, а не константа ядра.
"""

import json
import os

from . import schema
from .errors import Issue, SkillError
from .index import Index, row_of
from .record import Record, now_stamp
from .store import RecordStore, modified_at

QUEUE_DIRNAME = ".todone"
TASKS_DIRNAME = "tasks"
REGISTRY_FILENAME = "queues.json"
INDEX_FILENAME = "index.json"
DATA_DIRNAME = "data"
SETTINGS_FILENAME = "settings.json"
ROLES_FILENAME = "roles.json"
TOOLS_FILENAME = "tools.json"


def load_json(path, what, keys=None):
    """Прочитать JSON-конфиг: одна точка отказа и один код на всю раскладку."""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except ValueError as exc:
        raise SkillError("JSON_MALFORMED", "%s не разбирается как JSON: %s" % (what, exc),
                         path)
    if not isinstance(data, dict):
        raise SkillError("JSON_MALFORMED", "%s должен быть объектом" % what, path)
    if keys:
        for key in data:
            if key not in keys:
                raise SkillError("KEY_UNKNOWN",
                                 "ключ «%s» не из схемы %s" % (key, what), path)
    return data


def save_json(path, data):
    """Атомарная запись конфига с резервной копией."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as src, \
                open(path + ".bak", "w", encoding="utf-8") as dst:
            dst.write(src.read())
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    return path


class Registry:
    """Реестр очередей `<корень>/.todone/queues.json`."""

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.path = os.path.join(self.root, QUEUE_DIRNAME, REGISTRY_FILENAME)

    def read(self):
        data = load_json(self.path, "реестр очередей", schema.QUEUES_KEYS)
        if data is None:
            return {"schema": "QUEUES-1", "updated_at": now_stamp(), "queues": []}
        data.setdefault("queues", [])
        return data

    def write(self, data):
        data["schema"] = "QUEUES-1"
        data["updated_at"] = now_stamp()
        return save_json(self.path, data)

    def entries(self):
        return [e for e in self.read().get("queues", []) if isinstance(e, dict)]

    def default_alias(self):
        """Очередь по умолчанию: одна запись в реестре — она и есть очередь."""
        entries = self.entries()
        if len(entries) == 1:
            return entries[0].get("alias")
        return None

    def find(self, alias):
        for entry in self.entries():
            if entry.get("alias") == alias:
                return entry
        return None

    def register(self, alias, path):
        """Зарегистрировать очередь: алиас, путь, метка времени."""
        if not alias or not alias.strip():
            raise SkillError("EMPTY", "алиас очереди обязателен", "tqueue init")
        data = self.read()
        entry = self.find(alias)
        absolute = os.path.abspath(path)
        if entry:
            entry["path"] = absolute
            entry["updated_at"] = now_stamp()
        else:
            data["queues"].append({"alias": alias, "path": absolute,
                                   "updated_at": now_stamp()})
        self.write(data)
        return entry or data["queues"][-1]

    def resolve(self, alias=None, cwd=None):
        """Разрешить очередь: по алиасу, по текущей папке либо единственную."""
        entries = self.entries()
        if alias:
            entry = self.find(alias)
            if not entry:
                raise SkillError("QUEUE_UNKNOWN",
                                 "очереди «%s» в реестре нет" % alias, self.path)
            return entry
        cwd = os.path.abspath(cwd or os.getcwd())
        for entry in entries:
            path = entry.get("path") or ""
            if cwd == path or cwd.startswith(path + os.sep):
                return entry
        if len(entries) == 1:
            return entries[0]
        if not entries:
            raise SkillError("QUEUE_UNKNOWN",
                             "реестр очередей пуст: очередь не создана", self.path)
        raise SkillError("QUEUE_NOT_RESOLVED",
                         "очередей %d, а какая нужна, не названо" % len(entries),
                         "реестр очередей",
                         hint="назови очередь явно",
                         command="tqueue list --queue <алиас>")


class Queue:
    """Очередь: пути, хранилище записей, индекс, настройка проекта."""

    def __init__(self, root, alias, base_dir=None):
        self.root = os.path.abspath(root)
        self.alias = alias
        self.dir = os.path.abspath(base_dir or os.path.join(
            self.root, TASKS_DIRNAME, alias))
        self.todone_dir = os.path.join(self.dir, QUEUE_DIRNAME)
        self.data_dir = os.path.join(self.todone_dir, DATA_DIRNAME)
        self.index_path = os.path.join(self.todone_dir, INDEX_FILENAME)
        self.settings_path = os.path.join(self.todone_dir, SETTINGS_FILENAME)
        self._store = None
        self._index = None
        self._settings = None

    # --- составные части ---
    @property
    def store(self):
        if self._store is None:
            self._store = RecordStore(self.data_dir)
        return self._store

    @property
    def index(self):
        if self._index is None:
            self._index = Index.load(self.index_path, self.alias)
        return self._index

    @property
    def settings(self):
        """Пороги чтения — настройка проекта, а не константа ядра."""
        if self._settings is None:
            data = load_json(self.settings_path, "настройка очереди") or {}
            merged = dict(schema.DEFAULT_SETTINGS)
            for key, value in data.items():
                if key not in schema.SETTINGS_KEYS:
                    raise SkillError("KEY_UNKNOWN",
                                     "ключа «%s» в настройке очереди нет" % key,
                                     self.settings_path)
                merged[key] = value
            self._settings = merged
        return self._settings

    def set_setting(self, key, value):
        if key not in schema.SETTINGS_KEYS:
            raise SkillError("KEY_UNKNOWN",
                             "ключа «%s» в настройке очереди нет" % key, key)
        data = load_json(self.settings_path, "настройка очереди") or {}
        data[key] = value
        save_json(self.settings_path, data)
        self._settings = None
        return self.settings

    @property
    def records(self):
        """Записи очереди: источник правды — файлы, не индекс."""
        return self.store.read_all()

    def rows(self):
        """Строки индекса в порядке очереди."""
        return self.index.ordered()

    # --- разрешение записи ---
    def resolve(self, task_id):
        """Запись по идентификатору: путь разрешается через индекс или папку."""
        row = self.index.find(task_id)
        if row and row.get("path"):
            path = os.path.join(self.todone_dir, row["path"])
            if os.path.isfile(path):
                return self.store.read_path(path)
        return self.store.read(task_id)

    def path_of(self, task_id):
        record = self.resolve(task_id)
        return record.path

    # --- правка с обновлением индекса ---
    def save(self, record):
        """Записать запись и обновить её строку индекса: один вызов, два файла."""
        self.store.write(record)
        self._index_row(record)
        self.index.save()
        return record

    def create(self, title, kind, **fields):
        record = self.store.create(title, kind, **fields)
        self._index_row(record)
        self.index.save()
        return record

    def _index_row(self, record):
        """Строка индекса записи: состояние потока переносится из прежней строки."""
        rel = os.path.relpath(record.path, self.todone_dir)
        old = self.index.find(record.id)
        flow = old.get("flow") if old else None
        step = old.get("flow_step") if old else None
        run = old.get("flow_run") if old else None
        item = old.get("flow_item") if old else None
        revision = old.get("flow_revision") if old else None
        return self.index.upsert(row_of(record, rel, modified_at(record.path),
                                        flow, step, run, item, revision))

    def init(self):
        """Создать очередь: индекс с пустым списком, папки записей ещё нет."""
        os.makedirs(self.todone_dir, exist_ok=True)
        if not os.path.isfile(self.index_path):
            self.index.save()
        return self.index_path

    def rebuild_index(self):
        """Пересборка индекса из папки записей одной командой."""
        return self.index.rebuild(self.store, self.data_dir)

    # --- положение дел ---
    def counts(self):
        rows = self.rows()
        total = {"all": len(rows)}
        for status in schema.STATUSES:
            total[status] = len([r for r in rows if r.get("status") == status])
        return total

    def next_candidates(self):
        """Что брать в работу: ready, in_progress и blocked; зеркало исключено."""
        return [r for r in self.index.queue_rows()
                if r.get("status") in ("ready", "in_progress", "blocked")]

    def overdue(self, today_iso):
        rows = [r for r in self.index.queue_rows()
                if isinstance(r.get("due"), str) and r["due"] < today_iso
                and r.get("status") not in ("closed", "cancelled")]
        return rows

    def sync_issues(self):
        return self.index.sync_issues(self.store,
                                      where=os.path.relpath(self.index_path,
                                                            self.todone_dir))

    def children_of(self, task_id):
        return [r for r in self.rows() if r.get("parent") == task_id]

    def __repr__(self):
        return "Queue(%s @ %s)" % (self.alias, self.dir)

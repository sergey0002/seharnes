"""Индекс очереди: производный кэш, порядок, ссылки и мета.

Очередь не описывает задачи: в индексе идентификатор, путь, тип, заголовок,
статус, приоритет, фаза, релиз, владелец, срок, оценка, родитель, состояние
потока и метка времени. Содержательные тексты записи сюда не копируются.
"""

import json
import os

from . import schema
from .errors import Issue, SkillError
from .record import now_stamp
from .store import modified_at


def row_of(record, rel_path, updated_at=None, flow=None, flow_step=None,
           flow_run=None, flow_item=None, flow_revision=None,
           flow_run_status=None, flow_transition=None, flow_control=None):
    """Строка индекса из записи: ничего из текстов записи не копируется.

    Состояние потока — поля строки индекса, а не поля записи: отдельного файла
    состояния нет, и в записи его дубля нет тоже. `flow_run` различает два
    запуска одного preset, `flow_item` — экземпляры dynamic fan-out, а
    `flow_revision` — повторный проход через revision route.
    """
    data = record.data
    return {
        "id": data.get("id"),
        "path": rel_path,
        "type": data.get("kind"),
        "title": data.get("title"),
        "status": data.get("status"),
        "priority": data.get("priority"),
        "phase": data.get("phase"),
        "release": data.get("release"),
        "owner": data.get("owner"),
        "due": data.get("due"),
        "estimate_h": data.get("estimate_h"),
        "parent": data.get("parent"),
        "flow": flow,
        "flow_step": flow_step,
        "flow_run": flow_run,
        "flow_item": flow_item,
        "flow_revision": flow_revision,
        "flow_run_status": flow_run_status,
        "flow_transition": flow_transition,
        "flow_control": flow_control,
        "updated_at": updated_at or data.get("created_at"),
    }


def sort_key(row):
    """Порядок очереди: приоритет, фаза, идентификатор.

    Зеркало в порядке не участвует: такие строки уходят в конец и помечаются.
    """
    priority = row.get("priority")
    phase = row.get("phase") or ""
    return (1 if row.get("status") == "mirror" else 0,
            priority if isinstance(priority, int) else 99,
            str(phase), str(row.get("id") or ""))


class Index:
    """Индекс одной очереди."""

    def __init__(self, path, alias, items=None, updated_at=None):
        self.path = path
        self.alias = alias
        self.items = items if items is not None else []
        self.updated_at = updated_at or now_stamp()

    # --- чтение и запись ---
    @classmethod
    def load(cls, path, alias):
        if not os.path.isfile(path):
            return cls(path, alias, [])
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except ValueError as exc:
            raise SkillError("JSON_MALFORMED",
                             "индекс не разбирается как JSON: %s" % exc, path)
        if not isinstance(data, dict):
            raise SkillError("JSON_MALFORMED", "индекс должен быть объектом", path)
        for key in data:
            if key not in schema.INDEX_KEYS:
                raise SkillError("KEY_UNKNOWN",
                                 "ключ «%s» не из схемы INDEX-1" % key, path)
        items = data.get("items") or []
        if not isinstance(items, list):
            raise SkillError("KEY_UNKNOWN", "items индекса — массив строк", path)
        return cls(path, data.get("alias") or alias, items,
                   data.get("updated_at"))

    def save(self):
        """Атомарная запись индекса с резервной копией."""
        self.updated_at = now_stamp()
        data = {"schema": "INDEX-1", "alias": self.alias,
                "updated_at": self.updated_at, "order": schema.INDEX_ORDER,
                "items": self.items}
        folder = os.path.dirname(self.path)
        os.makedirs(folder, exist_ok=True)
        if os.path.isfile(self.path):
            with open(self.path, "r", encoding="utf-8") as src, \
                    open(self.path + ".bak", "w", encoding="utf-8") as dst:
                dst.write(src.read())
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, self.path)
        return self

    # --- строки ---
    def find(self, task_id):
        for row in self.items:
            if isinstance(row, dict) and row.get("id") == task_id:
                return row
        return None

    def ordered(self):
        rows = [r for r in self.items if isinstance(r, dict)]
        return sorted(rows, key=sort_key)

    def queue_rows(self):
        """Строки, которые участвуют в порядке очереди: зеркало исключено."""
        return [r for r in self.ordered() if r.get("status") != "mirror"]

    def upsert(self, row):
        for pos, item in enumerate(self.items):
            if isinstance(item, dict) and item.get("id") == row.get("id"):
                self.items[pos] = row
                return row
        self.items.append(row)
        return row

    # --- состояние потока ---
    def set_flow(self, record_id, flow, flow_step, flow_run=None,
                 flow_item=None, flow_revision=None, flow_run_status=None,
                 flow_transition=None, flow_control=None):
        """Записать flow coordinates/control in the derived index domain."""
        for row in self.items:
            if isinstance(row, dict) and row.get("id") == record_id:
                row["flow"] = flow
                row["flow_step"] = flow_step
                row["flow_run"] = flow_run
                row["flow_item"] = flow_item
                row["flow_revision"] = flow_revision
                if flow_run_status is not None:
                    row["flow_run_status"] = flow_run_status
                if flow_transition is not None:
                    row["flow_transition"] = flow_transition
                if flow_control is not None:
                    row["flow_control"] = flow_control
                self.updated_at = now_stamp()
                self.save()
                return row
        raise SkillError("RECORD_NOT_FOUND",
                         "строки записи %s в индексе нет" % record_id, self.path,
                         command="tqueue index-rebuild")

    def flow_rows(self, flow, flow_run=None):
        """Строки потока, при необходимости ограниченные одним запуском."""
        return [row for row in self.items
                if isinstance(row, dict) and row.get("flow") == flow
                and (flow_run is None or row.get("flow_run") == flow_run)]

    # --- пересборка ---
    def rebuild(self, store, data_dir):
        """Пересборка из папки записей: индекс восстанавливает очередь целиком.

        Состояние потока принадлежит индексу, поэтому пересборка переносит его
        из прежних строк по идентификатору, а не теряет.
        """
        kept = {row.get("id"): (row.get("flow"), row.get("flow_step"),
                                  row.get("flow_run"), row.get("flow_item"),
                                  row.get("flow_revision"), row.get("flow_run_status"),
                                  row.get("flow_transition"), row.get("flow_control"))
                for row in self.items if isinstance(row, dict)}
        rows = []
        for record in store.read_all():
            rel = os.path.relpath(record.path, os.path.dirname(data_dir))
            flow, step, run, item, revision, run_status, transition, control = kept.get(
                record.id, (None, None, None, None, None, None, None, None))
            rows.append(row_of(record, rel, modified_at(record.path), flow, step,
                               run, item, revision, run_status, transition, control))
        rows.sort(key=sort_key)
        self.items = rows
        return self.save()

    # --- сверка ---
    def sync_issues(self, store, where="index.json"):
        """Рассинхрон индекса и папки записей: три кода и одно действие."""
        issues = []
        listed = {}
        for row in self.items:
            if not isinstance(row, dict):
                issues.append(Issue("error", where, "строка индекса — не объект",
                                    "KEY_UNKNOWN"))
                continue
            for key in row:
                if key not in schema.INDEX_ITEM_KEYS:
                    issues.append(Issue("error", "%s %s" % (where, row.get("id")),
                                        "ключ «%s» не из строки INDEX-1" % key,
                                        "KEY_UNKNOWN"))
            listed[row.get("id")] = row
        on_disk = {}
        for record in store.read_all():
            on_disk[record.id] = record
        for task_id, row in listed.items():
            if task_id not in on_disk:
                issues.append(Issue("error", "%s %s" % (where, task_id),
                                    "строка индекса указывает на запись, которой нет в папке data",
                                    "INDEX_ORPHAN"))
                continue
            record = on_disk[task_id]
            expected_path = os.path.relpath(record.path, os.path.dirname(store.data_dir))
            if row.get("path") != expected_path:
                issues.append(Issue("error", "%s %s.path" % (where, task_id),
                                    "индекс держит путь «%s», а папка записи имеет «%s»"
                                    % (row.get("path"), expected_path),
                                    "INDEX_MISMATCH"))
            actual = row_of(record, expected_path, modified_at(record.path),
                            row.get("flow"), row.get("flow_step"),
                            row.get("flow_run"), row.get("flow_item"),
                            row.get("flow_revision"), row.get("flow_run_status"),
                            row.get("flow_transition"), row.get("flow_control"))
            for key in schema.INDEX_ITEM_KEYS:
                if key in ("path", "updated_at", "flow", "flow_step", "flow_run",
                           "flow_item", "flow_revision", "flow_run_status",
                           "flow_transition", "flow_control"):
                    continue
                if row.get(key) != actual.get(key):
                    issues.append(Issue("error", "%s %s.%s" % (where, task_id, key),
                                        "индекс держит «%s», а файл записи — «%s»"
                                        % (row.get(key), actual.get(key)),
                                        "INDEX_MISMATCH"))
        for task_id in on_disk:
            if task_id not in listed:
                issues.append(Issue("error", "%s %s" % (where, task_id),
                                    "запись лежит в папке data, но её нет в индексе",
                                    "RECORD_UNLISTED"))
        return issues

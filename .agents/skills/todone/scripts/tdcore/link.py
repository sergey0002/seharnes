"""Связь записей указателем: атомарность вместо копирования.

Ни один факт не хранится в двух записях. Связь — указатель `refs` с родом
`queue`; дерево записи печатается по строке на потомка.
"""

from .errors import Issue, SkillError


def link(parent, child_id, note, by=None):
    """Проставить связь указателем: текст ребёнка в родителя не копируется."""
    for ref in parent.refs:
        if isinstance(ref, dict) and ref.get("kind") == "queue" \
                and ref.get("path") == child_id:
            return ref
    return parent.add_ref("queue", child_id,
                          note or "связь с записью %s" % child_id, by=by)


def tree(queue, root_id):
    """Дерево записи: объект записи с потомками по указателям и полю parent."""
    root = queue.resolve(root_id)
    by_parent = {}
    records = {r.id: r for r in queue.records}
    for record in records.values():
        parent = record.parent
        if parent:
            by_parent.setdefault(parent, []).append(record)
    for record in records.values():
        for ref in record.refs:
            if isinstance(ref, dict) and ref.get("kind") == "queue":
                child = records.get(ref.get("path"))
                if child is not None and child.id != record.id:
                    bucket = by_parent.setdefault(record.id, [])
                    if child not in bucket:
                        bucket.append(child)
    for bucket in by_parent.values():
        bucket.sort(key=lambda r: r.id)
    return root, by_parent


def broken_links(queue, issues=None):
    """Указатели на записи, которых нет: код LINK_BROKEN."""
    issues = issues if issues is not None else []
    known = {r.id for r in queue.records}
    for record in queue.records:
        for pos, ref in enumerate(record.refs):
            if isinstance(ref, dict) and ref.get("kind") == "queue":
                target = ref.get("path")
                if target not in known:
                    issues.append(Issue("error", "%s.refs[%d]" % (record.id, pos),
                                        "указатель на запись %s ведёт в никуда" % target,
                                        "LINK_BROKEN"))
    return issues


class Linker:
    """Связь записей указателями и дерево: факты не копируются."""

    def __init__(self, queue):
        self.queue = queue

    def link(self, parent_id, child_id, note, by=None):
        parent = self.queue.resolve(parent_id)
        result = link(parent, child_id, note, by=by)
        self.queue.save(parent)
        return result

    def tree(self, root_id):
        return tree(self.queue, root_id)

    def broken(self):
        return broken_links(self.queue)

"""Профиль типа: поведение типа как класс.

Универсальный профиль собирается из конфига `type.json` без загрузки кода.
Потомок пишется только тогда, когда поведение процедурное: объявленный в
`type.json` ключ `profile` называет модуль и класс, которые ядро загружает по
требованию. Отказ загрузки — `PROFILE_LOAD_FAILED` с путём и готовым действием.
"""

import importlib.util
import os
import sys

from .errors import SkillError


class TypeProfile:
    """Базовый профиль: поведение типа из данных объявления."""

    #: Ключи, которые профиль вправе переопределить своим методом.
    hooks = ("before_close", "after_write", "resolve_field", "stages")

    def __init__(self, typedef):
        self.type = typedef

    # --- данные из объявления ---
    @property
    def gates(self):
        return dict(self.type.gates or {})

    @property
    def fields(self):
        return list(self.type.fields or [])

    @property
    def capabilities(self):
        return list(self.type.capabilities or [])

    @property
    def editor(self):
        return self.type.editor

    def stages(self, record):
        """Этапы записи: внутренний контур — этапы одной записи, не записи."""
        return list(record.data.get("stages") or self.type.stages or [])

    # --- точки расширения ---
    def before_close(self, record, report=None, issues=None):
        """Находки закрытия, которые объявление данными выразить не может."""
        return issues if issues is not None else []

    def after_write(self, record):
        """Действие после записи: по умолчанию ничего."""
        return None

    def resolve_field(self, record, name):
        """Значение дополнительного поля: по умолчанию из `extra`."""
        return record.extra.get(name)


class UniversalProfile(TypeProfile):
    """Универсальный профиль: собран из конфига, кода не загружает."""


def load_profile(typedef, types_root):
    """Загрузить объявленный профиль типа либо собрать универсальный."""
    declared = typedef.profile
    if not declared:
        return UniversalProfile(typedef)
    module_name = declared.get("module") if isinstance(declared, dict) else None
    class_name = declared.get("class") if isinstance(declared, dict) else None
    if not module_name or not class_name:
        raise SkillError("PROFILE_LOAD_FAILED",
                         "профиль типа %s объявлен без модуля или класса"
                         % typedef.id,
                         os.path.join(types_root, typedef.id, "type.json"),
                         command="tcheck types show %s" % typedef.id)
    path = _module_path(module_name, types_root, typedef.id)
    if not path or not os.path.isfile(path):
        raise SkillError("PROFILE_LOAD_FAILED",
                         "модуля профиля «%s» нет" % module_name,
                         path or os.path.join(types_root, typedef.id),
                         command="tcheck types show %s" % typedef.id)
    spec = importlib.util.spec_from_file_location(
        "tdcore_profile_%s" % typedef.id.replace("-", "_"), path)
    if spec is None or spec.loader is None:
        raise SkillError("PROFILE_LOAD_FAILED",
                         "модуль профиля «%s» не загружается" % module_name, path,
                         command="tcheck types show %s" % typedef.id)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - отказ загрузки печатается кодом
        raise SkillError("PROFILE_LOAD_FAILED",
                         "модуль профиля «%s» упал при загрузке: %s"
                         % (module_name, exc), path,
                         command="tcheck types show %s" % typedef.id)
    klass = getattr(module, class_name, None)
    if klass is None:
        raise SkillError("PROFILE_LOAD_FAILED",
                         "класса «%s» в модуле профиля нет" % class_name, path,
                         command="tcheck types show %s" % typedef.id)
    if not (isinstance(klass, type) and issubclass(klass, TypeProfile)):
        raise SkillError("PROFILE_LOAD_FAILED",
                         "класс профиля «%s» не потомок TypeProfile" % class_name,
                         path, command="tcheck types show %s" % typedef.id)
    return klass(typedef)


def _module_path(module_name, types_root, type_id):
    """Путь модуля профиля: `profile.py` папки типа или путь от корня типов."""
    if module_name.endswith(".py"):
        candidate = os.path.join(types_root, type_id, module_name)
        return candidate if os.path.isfile(candidate) else None
    parts = module_name.split(".")
    candidate = os.path.join(types_root, type_id, *parts) + ".py"
    if os.path.isfile(candidate):
        return candidate
    candidate = os.path.join(types_root, *parts) + ".py"
    return candidate if os.path.isfile(candidate) else None

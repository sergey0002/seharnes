"""Находки, коды отказов и готовые действия.

Ошибка печатается одной строкой из четырёх частей: код, что не так, чем лечить,
какую команду выполнить. У каждого кода есть готовое действие в таблице
подсказок; коды, объявленные типами, сливаются с этой таблицей.
"""

#: Успех, находки, вопрос человеку.
EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ASK_USER = 3

#: Таблица готовых действий: код -> (чем лечить, какую команду выполнить).
HINTS = {
    "INDEX_ORPHAN": ("строка индекса указывает на запись, которой нет в папке data",
                     "tqueue index-rebuild"),
    "RECORD_UNLISTED": ("запись лежит в папке data, но её нет в индексе",
                        "tqueue index-rebuild"),
    "INDEX_MISMATCH": ("поле строки индекса расходится с файлом записи",
                       "tqueue index-rebuild"),
    "JSON_MALFORMED": ("файл не разбирается как JSON: данные и конфиги правит только CLI",
                       "tcheck doctor --all --strict"),
    "TYPE_FIELD_UNKNOWN": ("тип не объявляет такого поля в extra",
                           "tcheck types fields <тип>"),
    "TYPE_FIELD_MISSING": ("обязательное поле типа не заполнено",
                           "ttask set <id> --extra <имя>=<значение>"),
    "TYPE_FIELD_INVALID": ("значение поля не проходит правило типа: тип значения, перечень или формат",
                           "tcheck types fields <тип>"),
    "REF_NOTE_MISSING": ("указатель без пояснения: непонятно, что в нём смотреть",
                         "ttask ref add <id> --kind file --path <путь> --note <зачем>"),
    "ARTIFACT_MISSING": ("артефакт объявлен, но файла в папке записи нет",
                         "ttask artifact add <id> --kind <род> --path <путь> --note <что внутри>"),
    "LINK_BROKEN": ("указатель на запись ведёт в никуда",
                    "ttask ref remove <id> --path <адрес> --by <кто>"),
    "MIRROR_READONLY": ("зеркало внешней системы правит только импорт",
                        "ttask new «Формализация стадии» --type intake --parent <зеркало> --by <имя>"),
    "DIGEST_STALE": ("выгрузка устарела: запись правили после неё",
                     "ttask digest <id>"),
    "SOURCE_RAW_MISSING": ("у записи с источником нет содержимого дословно",
                           "tcheck import jira --file <путь> --by <имя>"),
    "SOURCE_KEYS_EXTRA": ("в источнике лишний ключ: схема SOURCE строга",
                          "tcheck schema SOURCE"),
    "JIRA_MIRROR_INVALID": ("Jira-MIRROR-1 projection не проходит validation",
                            "tcheck import jira --file <путь> --by <имя>"),
    "INTAKE_INVALID": ("intake draft не проходит INTAKE-1",
                       "tcheck intake validate <session> --root <root>"),
    "INTAKE_SESSION_INVALID": ("intake session имеет небезопасный идентификатор",
                               "tcheck intake list --root <root>"),
    "INTAKE_SESSION_NOT_FOUND": ("intake session не найдена",
                                 "tcheck intake list --root <root>"),
    "INTAKE_PROVENANCE_MISSING": ("вход постановки задачи не имеет provenance",
                                  "зафиксировать source_kind и source_ref"),
    "INTAKE_SOURCE_INVALID": ("тип источника intake не поддержан",
                              "использовать message, file, screenshot, url или task"),
    "INTAKE_SOURCE_NOT_FOUND": ("входной файл постановки задачи не найден",
                                "проверить путь к файлу или скриншоту"),
    "INTAKE_QUESTION_SEQUENCE": ("следующий вопрос нельзя задать до ответа на текущий",
                                 "ответить на объявленный вопрос"),
    "INTAKE_QUESTION_INVALID": ("вопрос постановки задачи не проходит validation",
                                "проверить choices, default, on_decline и on_disabled"),
    "INTAKE_QUESTION_UNKNOWN": ("открытый вопрос постановки задачи не найден",
                                "tcheck intake show <session> --root <root>"),
    "INTAKE_ANSWER_INVALID": ("ответ не входит в choices вопроса",
                              "выбрать один из объявленных choices"),
    "INTAKE_REQUIRES_CONFIRMATION": ("перед созданием задачи остались вопросы или риски",
                                     "ответить на вопросы или явно подтвердить remaining risks"),
    "INTAKE_FINALIZE_INCOMPLETE": ("для typed task не хватает обязательной части постановки",
                                   "добавить problem, acceptance и verify"),
    "INTAKE_TITLE_MISSING": ("для intake нужен заголовок",
                             "tcheck intake start --title <название> --by <имя>"),
    "INTAKE_TEXT_MISSING": ("текст intake entry пуст",
                            "передать подтверждённый текст"),
    "INTAKE_ENTRY_STATUS_INVALID": ("статус входа intake не поддержан",
                                    "использовать observed, requested, proposed, accepted или unknown"),
    "INTAKE_OPTION_INVALID": ("вариант intake не имеет названия",
                              "добавить label и pros/cons"),
    "INTAKE_OPTION_UNKNOWN": ("вариант intake не найден",
                              "tcheck intake show <session> --root <root>"),
    "AUDIT_INVALID": ("TASK-AUDIT-1 verdict не проходит validation",
                      "tcheck intake audit <session> --task <id> --root <root>"),
    "AUDIT_TARGET_NOT_FOUND": ("целевая задача для аудита не найдена",
                               "проверить queue и task id"),
    "AUDIT_REF_BROKEN": ("аудит нашёл неразрешимый ref",
                         "исправить ref или явно добавить remaining risk"),
    "AUDIT_ACCEPTANCE_MISSING": ("аудит нашёл задачу без acceptance",
                                 "ttask set <id> --acceptance <критерий> --by <имя>"),
    "AUDIT_VERIFY_MISSING": ("аудит нашёл задачу без проверки",
                             "ttask set <id> --verify <команда> --by <имя>"),
    "AUDIT_DUPLICATE_CANDIDATE": ("аудит нашёл похожую задачу",
                                  "сравнить refs и явно решить, duplicate это или нет"),
    "TYPE_IMMUTABLE": ("тип записи не меняется после создания",
                       "ttask new «Новая форма работы» --type <нужный тип> --parent <id> --by <имя>"),
    "ID_IMMUTABLE": ("идентификатор записи не меняется после создания",
                     "ttask new «Новая дочерняя работа» --type <тип> --parent <id> --by <имя>"),
    "READ_MODE_UNKNOWN": ("неизвестный режим чтения",
                          "ttask show <id> --mode full"),
    "PACK_INCOMPLETE": ("пакет субагенту не собран: не хватает объявленного предмета",
                        "ttask pack <id> --mode handoff"),
    "CHECK_LOAD_FAILED": ("объявленную типом проверку не загрузить",
                          "tcheck types show <тип>"),
    "CHECK_CONTRACT": ("проверка типа нарушает контракт: вход, выход или коды возврата",
                       "tcheck types show <тип>"),
    "PROFILE_LOAD_FAILED": ("профиль типа, объявленный в конфиге, не загрузился",
                            "tcheck types show <тип>"),
    "CAPABILITY_UNBOUND": ("возможность среды объявлена типом, а привязки в проекте нет",
                           "tcheck tools bind <возможность> --command <команда>"),
    "FLOW_STEP_MISSING": ("шаг потока ссылается на шаг, которого в определении нет",
                          "tcheck flows show <поток>"),
    "FLOW_STATE_MISMATCH": ("состояние потока в индексе расходится с определением",
                            "ttask flow state <id>"),
    "FLOW_OUTPUT_MISSING": ("шаг закрыт и оставил не всё, что объявил следующему",
                            "ttask flow next <id>"),
    "FLOW_CONDITION_UNMET": ("условие перехода потока не выполнено",
                             "ttask flow state <id>"),
    "FLOW_PREREQUISITE_OPEN": ("предыдущий шаг потока ещё не закрыт",
                               "ttask flow state <id>"),
    "FLOW_FANOUT_INVALID": ("список fan-out не соответствует объявленному контракту",
                            "ttask flow state <id>"),
    "FLOW_JOIN_PENDING": ("fan-in ждёт закрытия всех экземпляров шага",
                         "ttask flow state <id>"),
    "ROLE_UNKNOWN": ("роль не объявлена в файле ролей",
                     "tcheck roles list"),
    "BATCH_FAILED": ("пакет операций не выполнен целиком: транзакция откатилась",
                     "ttask batch <файл> --dry-run"),
    "PROSE_HIDDEN_TEXT": ("в прозе найдена невидимая вставка: скрытый комментарий или символ нулевой ширины",
                          "tcheck doctor --all --strict"),
    "EMPTY": ("значение обязательно и не может быть пустым",
              "ttask set <id> --title <значение> --by <имя>"),
    "KEY_UNKNOWN": ("ключ не из схемы: опечатка или лишнее поле",
                    "tcheck schema TASK"),
    "AC_TOO_FEW": ("критериев приёмки меньше, чем требует тип: задача непроверяема",
                   "ttask set <id> --acceptance <текст критерия>"),
    "RELEASE_FORMAT": ("имя релиза — null либо непустая строка",
                       "ttask set <id> --release <имя>"),
    "NO_HANDOFF": ("тип требует реплику пересменки перед закрытием",
                   "ttask comment add <id> --kind handoff --by <кто> --body <что передать>"),
    "NO_TESTS": ("гейт типа требует свидетельство прогона теста",
                 "ttask evidence <id> --kind tests --path <путь> --note <что> --by <имя>"),
    "NO_REFS": ("тип требует указатели на файлы, символы или документацию",
                "ttask ref add <id> --kind file --path <путь> --note <зачем>"),
    "COMMENT_SOURCE_LOCKED": ("в ленту записи из внешней системы пишет только импорт",
                              "ttask new «Служебное уточнение» --type intake --parent <зеркало> --by <имя>"),
    "ASK_USER": ("нужно решение человека: команда ничего не создала и ничего не правила",
                 "прочитай вывод и повтори вызов с явным решением"),
    "QUEUE_UNKNOWN": ("очередь не найдена в реестре",
                      "tqueue find --root <root>"),
    "QUEUE_NOT_RESOLVED": ("очередей несколько, а какая нужна, не названо",
                           "tqueue list --queue <алиас> --root <root>"),
    "RECORD_NOT_FOUND": ("записи с таким идентификатором в очереди нет",
                         "tqueue list --queue <алиас>"),
    "TYPE_UNKNOWN": ("тип не объявлен: ни в поставке, ни в папке типов проекта",
                     "tcheck types list"),
    "STATUS_UNKNOWN": ("статус не из восьми объявленных",
                       "tcheck schema STATUSES"),
    "PATH_OUTSIDE": ("путь ведёт за пределы папки записи",
                     "ttask artifact add <id> --kind other --path <путь внутри папки>"),
    "NOT_IMPLEMENTED": ("команда объявлена планом, но в этой фазе ещё не реализована",
                        "tcheck selftest"),
    "FLOW_CONTROL_INVALID": ("declarative step control не проходит FLOW-STEP-CONTROL-1",
                              "tcheck flows show <поток>"),
    "FLOW_DOC_INVALID": ("documentation extension не проходит FLOW-DOC-1",
                         "tcheck flows show <поток>"),
    "FLOW_CHOICE_INVALID": ("choice envelope не проходит allowlist/schema validation",
                            "ttask flow choice <id> --request <file> --value <id>"),
    "FLOW_CHOICE_REQUIRED": ("flow step ждёт явный ответ на объявленный вопрос",
                             "ttask flow choice <id> --request <file> --value <id> --by <имя>"),
    "FLOW_CHOICE_USER_REQUIRED": ("рекомендация агента не является выбором пользователя",
                                  "повторить choice с source=user или явной политикой"),
    "FLOW_CONTROL_BLOCKED": ("обязательный flow step нельзя silent-skip или disable",
                             "дать явный ответ по вопросу из flow.json"),
    "FLOW_TRANSITION_UNAUTHORIZED": ("agent не имеет права сам применить flow transition",
                                     "получить human/policy approval и повторить transition"),
    "FLOW_RELEASE_CONFLICT": ("release context старого и target flow несовместим",
                              "выбрать flow того же release или явно создать release transition"),
    "FLOW_SELECTION_INVALID": ("flow/preset не входит в allowlist входного selector",
                               "tcheck flows list"),
    "FLOW_DECISION_TREE_INVALID": ("decision tree не проходит versioned deterministic contract",
                                   "tcheck flows show <поток>"),
    "FLOW_CHOICE_INVALID": ("choice envelope не проходит allowlist/schema validation",
                            "ttask flow choice <id> --request <file> --value <id>"),
    "FLOW_DECISION_INVALID": ("сохранённое решение flow имеет неверную схему",
                              "tcheck doctor --all --strict"),
    "FLOW_DECISION_DUPLICATE": ("эквивалентное решение flow уже сохранено",
                                "ttask flow state <id>"),
    "FLOW_TRANSITION_INVALID": ("переход flow не проходит immutable contract",
                                "ttask flow transition <id> --target-flow <flow>"),
    "FLOW_TRANSITION_DUPLICATE": ("эквивалентный переход уже применён",
                                  "ttask flow transition state <transition>"),
    "FLOW_TRANSITION_UNKNOWN": ("переход flow не найден в immutable ledger",
                                "tcheck flows list"),
    "AGGREGATE_MISSING": ("generated aggregate catalog ещё не построен",
                          "tcheck aggregate scan --root <root>"),
    "AGGREGATE_INVALID": ("AGGREGATE-1 manifest или catalog повреждён",
                          "tcheck aggregate scan --root <root>"),
    "AGGREGATE_REF_UNKNOWN": ("global aggregate reference не найден",
                              "tcheck aggregate list --root <root>"),
    "AGGREGATE_RUN_UNKNOWN": ("aggregate run не найден",
                              "tcheck aggregate status --root <root>"),
    "AGGREGATE_KIND_UNKNOWN": ("вид aggregate catalog неизвестен",
                               "tcheck aggregate list --kind tasks --root <root>"),
    "AGGREGATE_SOURCE_STALE": ("source fingerprint отличается от aggregate catalog",
                               "tcheck aggregate scan --root <root>"),
    "WORKSPACE_MANIFEST_INVALID": ("workspace marker не проходит WORKSPACE-1",
                                   "исправить <root>/.todone/workspace.json"),
    "WORKSPACE_MARKER_MISSING": ("дочерний project root не имеет explicit workspace marker",
                                  "добавить .todone/workspace.json или исключить каталог"),
    "WORKSPACE_ID_DUPLICATE": ("workspace_id объявлен более одного раза",
                               "изменить marker и повторить aggregate scan"),
    "DOC_WORKSPACE_MISSING": ("documentation workspace не настроен явно",
                              "tcheck docs init --root <root>"),
    "DOC_MANIFEST_INVALID": ("docs/manifest.json не проходит WORKSPACE-1",
                             "tcheck docs check --root <root>"),
    "DOC_POLICY_INVALID": ("documentation policy не проходит DOC-POLICY-1",
                           "tcheck docs policy show --root <root>"),
    "DOC_IMPACT_INVALID": ("documentation_impact не проходит planning contract",
                           "ttask set <id> --extra documentation_impact=<json> --by <имя>"),
    "DOC_POLICY_CONFLICT": ("required/critical documentation нельзя отключить без approval",
                            "tcheck docs policy set --automation ask --by <имя>"),
    "DOC_POLICY_DISABLED": ("documentation path отключён в выбранном scope",
                            "tcheck docs policy set --automation manual --by <имя>"),
    "DOC_CAPTURE_INVALID": ("capture envelope не проходит DOC-CAPTURE-1",
                            "ttask document --from-chat <capture.json> --by <имя>"),
    "DOC_CAPTURE_EMPTY": ("в запросе нет явного documentable change",
                          "задокументируй с task/file/doc scope"),
    "NO_DOCUMENTABLE_CHANGE": ("обсуждение не содержит решения или явного capture intent",
                               "ничего не записывать; использовать «задокументируй» явно"),
    "DOC_KEY_INVALID": ("doc_key не является стабильным namespaced адресом",
                        "tcheck docs catalog --root <root>"),
    "DOC_KEY_UNKNOWN": ("документальный модуль не найден в catalog",
                        "tcheck docs catalog --root <root>"),
    "DOC_MODULE_INVALID": ("DOC-1 module envelope не проходит exact validation",
                           "tcheck docs check --root <root>"),
    "DOC_CLAIM_INVALID": ("DOC-CLAIM-1 claim envelope не проходит validation",
                          "tcheck docs check --root <root>"),
    "DOC_CLAIM_NO_EVIDENCE": ("observed/declared claim не имеет evidence refs",
                              "добавить evidence_refs и review_status"),
    "DOC_MACHINE_INVALID": ("DOC-MACHINE-1 machine payload не проходит exact validation",
                            "tcheck docs check --root <root>"),
    "DOC_PACKET_INVALID": ("DOC-PACKET-1 bounded packet не проходит validation",
                           "tcheck docs check --root <root>"),
    "DOC_WRITER_INVALID": ("DOC-WRITER-1 writer return contract не проходит validation",
                           "tcheck docs check --root <root>"),
    "DOC_QUERY_INVALID": ("DOC-QUERY-1 request не проходит validation",
                          "tcheck docs resolve --mode catalog --root <root>"),
    "CONTRACT_INVALID": ("versioned contract payload не проходит validation",
                         "tcheck schema --file <fixture.json>"),
    "CONTRACT_UNKNOWN": ("versioned contract schema не зарегистрирована",
                         "tcheck schema --file <fixture.json>"),
    "DOC_RENDER_FAILED": ("Markdown module не проходит deterministic render check",
                          "tcheck docs render --key <doc_key> --root <root>"),
    "DOC_STALE": ("source fingerprint документального модуля устарел",
                  "tcheck docs stale --root <root>"),
    "DOC_REVISION_CONFLICT": ("запрошенная revision document module отсутствует",
                              "tcheck docs catalog --root <root>"),
    "DOC_REF_BROKEN": ("document module ссылается на отсутствующий файл",
                       "tcheck docs check --root <root>"),
    "AUTODOC_ROOT_MISSING": ("autodoc root должен быть существующим каталогом",
                             "tcheck autodoc discover --root <root>"),
    "AUTODOC_BUNDLE_REQUIRED": ("нужен существующий AUTODOC-BUNDLE-1 bundle",
                                "tcheck autodoc bundle --root <root>"),
    "AUTODOC_BUNDLE_INVALID": ("bundle не проходит AUTODOC-BUNDLE-1 validation",
                               "tcheck schema --file <bundle.json>"),
    "AUTODOC_PATH_UNSAFE": ("path выходит за portable root или содержит traversal",
                            "tcheck autodoc verify --bundle <bundle.json>"),
    "AUTODOC_OUTPUT_NOT_OWNED": ("output не принадлежит todone-autodoc",
                                 "выбрать пустой каталог или AUTODOC-HTML-1 output"),
    "AUTODOC_DIGEST_MISMATCH": ("canonical bundle digest устарел или повреждён",
                                "пересобрать bundle из canonical sources"),
    "AUTODOC_SOURCE_DIGEST_MISMATCH": ("embedded source bytes не совпадают с digest",
                                       "пересобрать bundle без ручного редактирования"),
    "AUTODOC_HTML_REQUIRED": ("для HTML render нужен явно объявленный output directory",
                              "tcheck autodoc render --bundle <bundle> --html <dir>"),
    "AUTODOC_HTML_MANIFEST_MISSING": ("AUTODOC-HTML-1 manifest отсутствует",
                                      "tcheck autodoc render --bundle <bundle> --html <dir>"),
    "AUTODOC_RECONSTRUCTION_TARGET_NOT_EMPTY": ("reconstruction target не пуст без явного force",
                                                 "выбрать fresh target или добавить --force"),
    "AUTODOC_RECONSTRUCTION_DUPLICATE": ("два source records претендуют на один target path",
                                         "исправить bundle source inventory"),
    "AUTODOC_CONTRACT_UNKNOWN": ("autodoc schema не зарегистрирована",
                                 "tcheck schema --file <fixture.json>"),
}



class Issue:
    """Находка: уровень, место, сообщение, код и готовое действие."""

    __slots__ = ("level", "where", "message", "code", "hint", "command")

    def __init__(self, level, where, message, code=None, hint=None,
                 command=None):
        self.level = level
        self.where = where
        self.message = message
        self.code = code or _code_of(message)
        known = HINTS.get(self.code)
        self.hint = hint or (known[0] if known else "")
        self.command = command or (known[1] if known else "")

    @property
    def is_error(self):
        return self.level == "error"

    def as_line(self):
        """Одна строка из четырёх частей: код, что не так, чем лечить, команда."""
        head = "[%s] %s: %s" % (self.code, self.where, self.message)
        parts = [p for p in (self.hint, self.command) if p]
        return " → ".join([head] + parts)

    def as_dict(self):
        return {"level": self.level, "where": self.where,
                "message": self.message, "code": self.code,
                "hint": self.hint, "command": self.command}

    def __repr__(self):
        return "Issue(%s)" % self.as_line()


class SkillError(Exception):
    """Отказ команды: код, сообщение и место. Печатается одной строкой."""

    def __init__(self, code, message, where="", hint=None, command=None,
                 details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.where = where
        self.details = details or {}
        # Choice/transition callers may attach a machine envelope without
        # putting it into the human one-line error contract.
        self.request = self.details.get("request") if isinstance(self.details, dict) else None
        known = HINTS.get(code)
        self.hint = hint or (known[0] if known else "")
        self.command = command or (known[1] if known else "")

    @property
    def exit_code(self):
        return EXIT_ASK_USER if self.code == "ASK_USER" else EXIT_FINDINGS

    def as_line(self):
        return Issue("error", self.where or "-", self.message, self.code,
                     self.hint, self.command).as_line()

    def __str__(self):
        return self.as_line()


def _code_of(message):
    """Код по тексту, если его не назвали: держит вывод однозначным."""
    low = message.lower()
    if "пуст" in low:
        return "EMPTY"
    return "KEY_UNKNOWN"


def merge_hints(extra):
    """Слить коды, объявленные типами, с таблицей диагностики."""
    merged = dict(HINTS)
    for code, hint in (extra or {}).items():
        merged.setdefault(code, hint)
    return merged


def coverage_gaps(codes):
    """Коды без готового действия: находка проверки покрытия."""
    return sorted(c for c in codes if c not in HINTS)


class Finding(Issue):
    """Находка диагностики: именованный публичный тип поверх Issue."""

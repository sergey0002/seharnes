"""Поток работы: шаги как данные, состояние в индексе, цепочка черновиков.

Поток — второй вид плагина: `flows/<имя>/flow.json` объявляет шаги,
`flows/<имя>/instruction.md` — как вести поток. Состояние потока живёт в
индексе очереди: два поля строки записи, отдельного файла состояния нет.
Поток создаёт черновики, в работу их переводит человек.
"""

import copy
import json
import os

from . import schema
from .errors import Issue, SkillError
from .link import link
from .queue import load_json
from .record import now_stamp
from .choice import (branch_decision_tree, make_choice_request,
                     validate_choice_definition, validate_decision_tree)
from .flow_control import (DecisionStore, control_request, doc_request,
                           persist_control_decision, route_for_decision,
                           validate_doc_extension, validate_step_control)
from .documentation import (DocumentationWorkspace, PolicyDecisionStore,
                            default_policy, effective_policy)
from .choice import validate_choice_response
from .transition import (TransitionStore, make_transition, validate_transition)

FLOW_FILENAME = "flow.json"
INSTRUCTION_FILENAME = "instruction.md"
#: Сколько черновиков поток создаёт за один вызов, если объявление молчит.
DEFAULT_MAX_BATCH = 5
EXECUTOR_KEYS = ("role", "tier", "mode")


class Step:
    """Шаг потока по STEP-1."""

    def __init__(self, data, position=0):
        self.data = data if isinstance(data, dict) else {}
        self.position = position
        self.id = self.data.get("id")
        self.type = self.data.get("type")
        self.input_from = list(self.data.get("input_from") or [])
        # `output` is the spelling used by the v0.7 presets. FLOW-2 also
        # accepts the plural `outputs`; both describe logical facts, not paths.
        raw_output = (self.data.get("outputs") if "outputs" in self.data
                      else self.data.get("output"))
        self.output = list(raw_output or []) if isinstance(raw_output, list) else []
        self.executor = self.data.get("executor")
        self.parallel = bool(self.data.get("parallel"))
        self.optional = bool(self.data.get("optional"))
        self.gate_out = self.data.get("gate_out")
        self.brief = self.data.get("brief")
        # FLOW-2: declarative facts required from a prerequisite before this
        # step may be created. It never changes a record status automatically.
        raw_requires = self.data.get("requires")
        self.requires = raw_requires if isinstance(raw_requires, list) else raw_requires or []
        self.routes = self.data.get("routes") or {}
        self.route_field = self.data.get("route_field") or "verdict"
        self.fan_out = self.data.get("fan_out")
        # Explicit runtime extensions.  ``None`` means the step is ordinary;
        # it must never inherit a hidden confirmation/disable policy.
        self.step_control = self.data.get("step_control")
        self.documentation = self.data.get("documentation")
        self.choice = self.data.get("choice")
        self.decision_tree = self.data.get("decision_tree")
        self.version = self.data.get("version") or 1

    def as_line(self):
        marks = []
        if self.parallel:
            marks.append("параллельно")
        if self.optional:
            marks.append("пропускаемый")
        return "%d. %-12s %-13s вход: %-18s выход: %-28s %s" % (
            self.position + 1, self.id or "-", self.type or "-",
            ",".join(self.input_from) or "-", ",".join(self.output) or "-",
            " ".join(marks) or "-")

    def validate(self, flow_id, known_steps=None, known_types=None, issues=None):
        issues = issues if issues is not None else []
        where = "flows/%s/flow.json steps[%d]" % (flow_id, self.position)
        for key in self.data:
            if key not in schema.STEP_KEYS:
                issues.append(Issue("error", "%s.%s" % (where, key),
                                    "ключа нет в объявлении шага", "KEY_UNKNOWN"))
        for key in ("id", "type"):
            if not self.data.get(key):
                issues.append(Issue("error", where,
                                    "обязательного поля «%s» нет" % key,
                                    "TYPE_FIELD_MISSING"))
        if known_types is not None and self.type and self.type not in known_types:
            issues.append(Issue("error", "%s.type" % where,
                                "тип «%s» не объявлен" % self.type, "TYPE_UNKNOWN"))
        if "output" in self.data and "outputs" in self.data:
            issues.append(Issue("error", "%s.output" % where,
                                "нельзя одновременно объявить output и outputs",
                                "KEY_UNKNOWN"))
        raw_output = self.data.get("outputs") if "outputs" in self.data \
            else self.data.get("output")
        if raw_output is not None and not isinstance(raw_output, list):
            issues.append(Issue("error", "%s.output" % where,
                                "выходы шага — массив логических имён",
                                "KEY_UNKNOWN"))
        for source in self.input_from:
            if known_steps is not None and source not in known_steps:
                issues.append(Issue("error", "%s.input_from" % where,
                                    "шаг «%s» объявил вход от несуществующего шага"
                                    % source, "FLOW_STEP_MISSING"))
        if not isinstance(self.requires, list):
            issues.append(Issue("error", "%s.requires" % where,
                                "условия шага — массив объектов", "KEY_UNKNOWN"))
        else:
            for pos, requirement in enumerate(self.requires):
                spot = "%s.requires[%d]" % (where, pos)
                if not isinstance(requirement, dict):
                    issues.append(Issue("error", spot,
                                        "условие — объект from/field/equals",
                                        "KEY_UNKNOWN"))
                    continue
                for key in requirement:
                    if key not in ("from", "field", "equals"):
                        issues.append(Issue("error", "%s.%s" % (spot, key),
                                            "ключа нет в условии шага",
                                            "KEY_UNKNOWN"))
                if not requirement.get("from") or not requirement.get("field") \
                        or "equals" not in requirement:
                    issues.append(Issue("error", spot,
                                        "нужны from, field и equals",
                                        "TYPE_FIELD_MISSING"))
                elif known_steps is not None \
                        and requirement.get("from") not in known_steps:
                    issues.append(Issue("error", "%s.from" % spot,
                                        "условие ссылается на несуществующий шаг",
                                        "FLOW_STEP_MISSING"))
        if self.routes:
            if not isinstance(self.routes, dict):
                issues.append(Issue("error", "%s.routes" % where,
                                    "routes — объект значение → цель шага",
                                    "KEY_UNKNOWN"))
            else:
                for value, target in self.routes.items():
                    spot = "%s.routes.%s" % (where, value)
                    if not isinstance(target, str) or not target:
                        issues.append(Issue("error", spot,
                                            "цель маршрута должна быть строкой",
                                            "TYPE_FIELD_MISSING"))
                        continue
                    base = target[:-9] if target.endswith(".revision") else target
                    if (known_steps is not None and base not in known_steps
                            and target != "human-decision"):
                        issues.append(Issue("error", spot,
                                            "маршрут ведёт к несуществующему шагу «%s»"
                                            % target, "FLOW_STEP_MISSING"))
        if self.fan_out is not None:
            if not isinstance(self.fan_out, dict):
                issues.append(Issue("error", "%s.fan_out" % where,
                                    "fan_out — объект источника элементов и join",
                                    "KEY_UNKNOWN"))
            else:
                for key in self.fan_out:
                    if key not in schema.FAN_OUT_KEYS:
                        issues.append(Issue("error", "%s.fan_out.%s" % (where, key),
                                            "ключа нет в объявлении fan_out",
                                            "KEY_UNKNOWN"))
                source = self.fan_out.get("items_from")
                if (not isinstance(source, list) or len(source) != 2
                        or not all(isinstance(item, str) and item for item in source)):
                    issues.append(Issue("error", "%s.fan_out.items_from" % where,
                                        "items_from — [шаг, поле]",
                                        "TYPE_FIELD_MISSING"))
                elif known_steps is not None and source[0] not in known_steps:
                    issues.append(Issue("error", "%s.fan_out.items_from" % where,
                                        "источник элементов «%s» не объявлен" % source[0],
                                        "FLOW_STEP_MISSING"))
                if not self.fan_out.get("item_id"):
                    issues.append(Issue("error", "%s.fan_out.item_id" % where,
                                        "fan_out требует имя идентификатора элемента",
                                        "TYPE_FIELD_MISSING"))
                join = self.fan_out.get("join")
                if join not in schema.JOIN_MODES:
                    issues.append(Issue("error", "%s.fan_out.join" % where,
                                        "join должен быть одним из %s"
                                        % list(schema.JOIN_MODES), "KEY_UNKNOWN"))
        if self.executor is not None:
            if not isinstance(self.executor, dict):
                issues.append(Issue("error", "%s.executor" % where,
                                    "исполнитель — объект или null", "KEY_UNKNOWN"))
            else:
                for key in self.executor:
                    if key not in EXECUTOR_KEYS:
                        issues.append(Issue("error", "%s.executor.%s" % (where, key),
                                            "ключа нет в объявлении исполнителя",
                                            "KEY_UNKNOWN"))
                if self.executor.get("tier") \
                        and self.executor["tier"] not in schema.TIERS:
                    issues.append(Issue("error", "%s.executor.tier" % where,
                                        "уровень — cheap, balanced или strong",
                                        "KEY_UNKNOWN"))
                if self.executor.get("mode") \
                        and self.executor["mode"] not in schema.MODES:
                    issues.append(Issue("error", "%s.executor.mode" % where,
                                        "режим — inline, subagent или either",
                                        "KEY_UNKNOWN"))
        if self.gate_out and known_types is not None:
            issues.extend(self._gate_issue(where))
        if self.step_control is not None:
            issues.extend(validate_step_control(self.step_control,
                                                "%s.step_control" % where))
        if self.documentation is not None:
            issues.extend(validate_doc_extension(self.documentation,
                                                 "%s.documentation" % where))
        if self.choice is not None:
            # A step choice uses the same exact envelope as every other adapter.
            choice = dict(self.choice) if isinstance(self.choice, dict) else self.choice
            if isinstance(choice, dict) and "request_id" not in choice:
                # Definition fragments are completed by the orchestrator, but
                # their declared question/options are still checked here.
                for key in ("question", "selection", "options", "default",
                            "allow_custom_response", "policy_scope"):
                    if key not in choice:
                        issues.append(Issue("error", "%s.choice" % where,
                                            "choice fragment без %s" % key,
                                            "FLOW_CHOICE_INVALID"))
            elif choice is not None:
                issues.extend(validate_choice_definition(choice,
                                                        "%s.choice" % where))
        if self.decision_tree is not None:
            tree_where = "%s.decision_tree" % where
            issues.extend(validate_decision_tree(self.decision_tree, tree_where))
            nodes = self.decision_tree.get("nodes") if isinstance(self.decision_tree, dict) else None
            if isinstance(nodes, list):
                nodes = {item.get("id"): item for item in nodes
                         if isinstance(item, dict) and item.get("id")}
            if isinstance(nodes, dict):
                node_ids = set(nodes)
                for node_id, node in nodes.items():
                    for choice, raw_target in (node.get("routes") or {}).items():
                        target = raw_target.get("target") if isinstance(raw_target, dict) else raw_target
                        base = target[:-9] if isinstance(target, str) and target.endswith(".revision") else target
                        if (isinstance(target, str) and target not in node_ids
                                and base not in (known_steps or set())
                                and target not in ("human-decision", "block")):
                            issues.append(Issue("error", "%s.nodes.%s.routes.%s" %
                                                (tree_where, node_id, choice),
                                                "маршрут ведёт к несуществующему шагу «%s»" % target,
                                                "FLOW_STEP_MISSING"))
        return issues

    def _gate_issue(self, where):
        from .typedefs import GATE_KEYS
        if self.gate_out not in GATE_KEYS:
            return [Issue("error", "%s.gate_out" % where,
                          "гейта «%s» нет среди объявленных" % self.gate_out,
                          "KEY_UNKNOWN")]
        return []


class Flow:
    """Поток по FLOW-1: определение шагов и точка входа."""

    def __init__(self, data, folder=None):
        self.data = data if isinstance(data, dict) else {}
        self.folder = folder
        self.id = self.data.get("id")
        self.name = self.data.get("name")
        self.entry = self.data.get("entry")
        self.schema = self.data.get("schema") or "FLOW-1"
        self.version = self.data.get("version") or 1
        self.max_batch = self.data.get("max_batch") or DEFAULT_MAX_BATCH
        self.instruction = self.data.get("instruction") or INSTRUCTION_FILENAME
        self.allowlist = self.data.get("allowlist")
        if self.allowlist is None:
            self.allowlist = self.data.get("allowlisted")
        self.presets = self.data.get("presets") or {}
        self.entry_selection = self.data.get("entry_selection")
        self.choice = self.data.get("choice")
        self.decision_tree = self.data.get("decision_tree")
        self.transitions = self.data.get("transitions")
        self.policy = self.data.get("policy")
        self.release = self.data.get("release")
        self.capabilities = self.data.get("capabilities") or []
        self.steps = [Step(item, pos) for pos, item
                      in enumerate(self.data.get("steps") or [])]

    # --- доступ к шагам ---
    def step(self, step_id):
        for item in self.steps:
            if item.id == step_id:
                return item
        return None

    def step_ids(self):
        return [item.id for item in self.steps]

    def order(self):
        """Порядок шагов: топологический по `input_from`, устойчивый к объявлению."""
        placed = []
        pending = list(self.steps)
        guard = 0
        while pending and guard < 1000:
            guard += 1
            for item in list(pending):
                needs = [s for s in item.input_from if s in self.step_ids()]
                if all(n in placed for n in needs):
                    placed.append(item.id)
                    pending.remove(item)
        placed.extend(item.id for item in pending)
        return placed

    def next_steps(self, done_ids, existing_ids=None):
        """Шаги, готовые к созданию после закрытия prerequisite-записей.

        `done_ids` — закрытые шаги, `existing_ids` — уже созданные шаги. Старый
        runtime передавал только наличие записей и тем самым мог открыть
        planning до research. FLOW-2 различает эти множества явно.
        """
        done = set(done_ids or [])
        existing = set(existing_ids or [])
        ready = []
        for step_id in self.order():
            if step_id in existing:
                continue
            step = self.step(step_id)
            needs = [s for s in step.input_from if s in self.step_ids()]
            if all(n in done for n in needs):
                ready.append(step)
        return ready

    def instruction_path(self, flows_root=None):
        root = self.folder or flows_root or ""
        return os.path.join(root, self.instruction)

    def as_line(self):
        return "%-16s %-28s вход: %-7s шагов: %d, за раз: %d" % (
            self.id or "-", self.name or "-", self.entry or "-",
            len(self.steps), self.max_batch)

    def choice_request(self, step_id=None, revision=1, policy_scope="flow_run"):
        """Build a declared choice request for a flow or one controlled step."""
        if step_id is not None:
            step = self.step(step_id)
            if step is None:
                raise SkillError("FLOW_STEP_MISSING", "шага «%s» нет в потоке" % step_id,
                                 self.id)
            if step.choice is not None:
                definition = step.choice
                if not isinstance(definition, dict):
                    raise SkillError("FLOW_CHOICE_INVALID",
                                     "choice должен быть объектом", self.id)
                if definition.get("schema") == "FLOW-CHOICE-1":
                    return definition
                question = definition.get("question") or definition
                from .flow_control import _choice_fragment
                return _choice_fragment(question, self.id, step.id, revision,
                                        policy_scope=policy_scope)
            if step.step_control is not None:
                return control_request(self, step, revision, policy_scope)
            if step.documentation is not None:
                return doc_request(self, step, revision)
            return None
        definition = self.entry_selection or self.choice
        if definition is None:
            return None
        if not isinstance(definition, dict):
            raise SkillError("FLOW_CHOICE_INVALID",
                             "entry choice должен быть объектом", self.id)
        if definition.get("schema") == "FLOW-CHOICE-1":
            return definition
        if isinstance(definition.get("options"), list):
            return make_choice_request(
                request_id="choice:%s:entry:%s:%s" % (self.id, revision,
                                                        definition.get("decision_id", "select_flow")),
                decision_id=definition.get("decision_id", "select_flow"),
                question=definition.get("question") or definition.get("text") or "Выберите flow",
                selection=definition.get("selection", "single"), options=definition.get("options"),
                default=definition.get("default"),
                allow_custom_response=bool(definition.get("allow_custom_response", False)),
                policy_scope=policy_scope, flow_id=self.id, flow_revision=revision,
                step_id="entry", source="flow.json")
        from .flow_control import _choice_fragment
        return _choice_fragment(definition, self.id, "entry", revision,
                                policy_scope=policy_scope)

    # --- сверка объявления ---
    def validate(self, known_types=None, issues=None):
        issues = issues if issues is not None else []
        where = "flows/%s/flow.json" % (self.id or "?")
        for key in self.data:
            if key not in schema.FLOW_KEYS:
                issues.append(Issue("error", "%s.%s" % (where, key),
                                    "ключа нет в объявлении потока", "KEY_UNKNOWN"))
        for key in ("id", "name", "entry", "steps"):
            if not self.data.get(key):
                issues.append(Issue("error", where,
                                    "обязательного поля «%s» нет" % key,
                                    "TYPE_FIELD_MISSING"))
        if self.entry and self.entry not in schema.FLOW_ENTRIES:
            issues.append(Issue("error", "%s.entry" % where,
                                "точка входа — source, file или text", "KEY_UNKNOWN"))
        if not isinstance(self.capabilities, list) or any(
                capability not in schema.CAPABILITIES for capability in self.capabilities):
            issues.append(Issue("error", "%s.capabilities" % where,
                                "capabilities должны быть из %s" % list(schema.CAPABILITIES),
                                "CAPABILITY_UNBOUND"))
        if self.release is not None and (not isinstance(self.release, str)
                                         or not self.release.strip()):
            issues.append(Issue("error", "%s.release" % where,
                                "release должен быть непустой строкой",
                                "FLOW_RELEASE_CONFLICT"))
        batch = self.data.get("max_batch")
        if batch is not None and (not isinstance(batch, int) or isinstance(batch, bool)
                                  or batch < 1 or batch > DEFAULT_MAX_BATCH):
            issues.append(Issue("error", "%s.max_batch" % where,
                                "черновиков за раз — целое от 1 до %d"
                                % DEFAULT_MAX_BATCH, "BATCH_FAILED"))
        if self.allowlist is not None:
            if not isinstance(self.allowlist, list) or not all(
                    isinstance(item, str) and item for item in self.allowlist):
                issues.append(Issue("error", "%s.allowlist" % where,
                                    "allowlist flow должен быть массивом строк",
                                    "FLOW_SELECTION_INVALID"))
            elif self.id not in self.allowlist and self.data.get("allowlisted") is not False:
                # A flow-local allowlist may name presets/flows; self exclusion
                # is only an error when it is explicitly an allowlist of flows.
                pass
        if self.entry_selection is not None:
            if not isinstance(self.entry_selection, dict):
                issues.append(Issue("error", "%s.entry_selection" % where,
                                    "entry_selection должен быть объектом",
                                    "FLOW_SELECTION_INVALID"))
            else:
                for key in self.entry_selection:
                    if key not in ("schema", "decision_id", "question", "text", "selection",
                                   "options", "default", "allow_custom_response",
                                   "policy_scope", "allowlist", "version"): 
                        issues.append(Issue("error", "%s.entry_selection.%s" % (where, key),
                                            "ключ не из entry choice", "KEY_UNKNOWN"))
                if self.entry_selection.get("schema") not in (None, "FLOW-CHOICE-1"):
                    issues.append(Issue("error", "%s.entry_selection.schema" % where,
                                        "schema должен быть FLOW-CHOICE-1",
                                        "FLOW_SELECTION_INVALID"))
                if self.entry_selection.get("allowlist") is not None and (
                        not isinstance(self.entry_selection.get("allowlist"), list)
                        or not all(isinstance(item, str) and item
                                   for item in self.entry_selection.get("allowlist"))):
                    issues.append(Issue("error", "%s.entry_selection.allowlist" % where,
                                        "allowlist должен быть массивом непустых строк",
                                        "FLOW_SELECTION_INVALID"))
                declared_options = self.entry_selection.get("options")
                if declared_options is not None:
                    if not isinstance(declared_options, list):
                        issues.append(Issue("error", "%s.entry_selection.options" % where,
                                            "options должен быть массивом",
                                            "FLOW_SELECTION_INVALID"))
                    else:
                        for pos, raw in enumerate(declared_options):
                            spot = "%s.entry_selection.options[%d]" % (where, pos)
                            if not isinstance(raw, dict):
                                issues.append(Issue("error", spot, "option должен быть объектом",
                                                    "FLOW_SELECTION_INVALID"))
                                continue
                            allowed_option = set(("id", "label", "description", "value",
                                                  "route", "flow", "target_flow", "preset",
                                                  "effects", "policy", "documentation"))
                            for key in raw:
                                if key not in allowed_option:
                                    issues.append(Issue("error", "%s.%s" % (spot, key),
                                                        "ключ не из entry option",
                                                        "FLOW_SELECTION_INVALID"))
                            if not (raw.get("flow") or raw.get("target_flow") or raw.get("id")):
                                issues.append(Issue("error", spot,
                                                    "entry option требует flow/target_flow/id",
                                                    "FLOW_SELECTION_INVALID"))
        if self.choice is not None:
            if isinstance(self.choice, dict) and self.choice.get("schema") == "FLOW-CHOICE-1":
                issues.extend(validate_choice_definition(self.choice, "%s.choice" % where))
            elif not isinstance(self.choice, dict):
                issues.append(Issue("error", "%s.choice" % where,
                                    "choice должен быть объектом", "FLOW_CHOICE_INVALID"))
        if self.decision_tree is not None:
            issues.extend(validate_decision_tree(self.decision_tree,
                                                 "%s.decision_tree" % where))
        seen = set()
        known = set(self.step_ids())
        for step in self.steps:
            if step.id in seen:
                issues.append(Issue("error", "%s.steps" % where,
                                    "шаг «%s» объявлен дважды" % step.id,
                                    "FLOW_STEP_MISSING"))
            seen.add(step.id)
            issues.extend(step.validate(self.id, known, known_types, issues=[]))
        return issues

    def coverage_issues(self, steps_done):
        """Выход предыдущего шага покрывает вход следующего: без копирования."""
        issues = []
        for step in self.steps:
            for source_id in step.input_from:
                source = self.step(source_id)
                if source is None:
                    continue
                left = set(steps_done.get(source_id) or [])
                missing = sorted(set(source.output) - left)
                if missing and source_id in steps_done:
                    issues.append(Issue(
                        "error", "flows/%s шаг %s" % (self.id, source_id),
                        "шаг закрыт и оставил не всё, что объявил: нет %s"
                        % ", ".join(missing), "FLOW_OUTPUT_MISSING"))
        return issues


class FlowIndex:
    """Индекс определений потоков: поставка плюс project overlay.

    Встроенный каталог остаётся fallback. Если в `<root>/.todone/flows` есть
    поток с тем же id, project definition целиком перекрывает встроенный; это
    не смешивает два JSON и делает источник выбранного определения ясным.
    """

    def __init__(self, flows_root, overlay_root=None):
        self.root = flows_root
        self.overlay_root = overlay_root
        self.flows = {}

    def _read_root(self, root):
        if not os.path.isdir(root):
            return
        for name in sorted(os.listdir(root)):
            folder = os.path.join(root, name)
            path = os.path.join(folder, FLOW_FILENAME)
            if not os.path.isfile(path):
                continue
            data = load_json(path, "объявление потока %s" % name) or {}
            flow = Flow(data, folder)
            self.flows[flow.id or name] = flow

    def read(self):
        self.flows = {}
        self._read_root(self.root)
        if self.overlay_root and os.path.abspath(self.overlay_root) != os.path.abspath(self.root):
            self._read_root(self.overlay_root)
        return self.flows

    def all(self):
        if not self.flows:
            self.read()
        return sorted(self.flows.values(), key=lambda f: f.id or "")

    def names(self):
        return [f.id for f in self.all()]

    def allowlisted(self, allowlist=None):
        """Return only flows explicitly admitted by the selector profile.

        Without a project selector, the installed flow catalog is the
        allowlist.  A supplied/declared list is never expanded from user text.
        """
        requested = allowlist
        for flow in self.all():
            if requested is None and isinstance(flow.allowlist, list):
                requested = flow.allowlist
                break
        if requested is None:
            return self.all()
        allowed = set(str(item) for item in requested)
        return [flow for flow in self.all() if flow.id in allowed]

    def entry_choice(self, allowlist=None, request_id="choice:entry:flow",
                     decision_id="select_flow", question="Какой маршрут применить к этому изменению?",
                     default=None, policy_scope="flow_run"):
        """Build one allowlisted entry selector from versioned flow metadata."""
        declared = next((flow.entry_selection for flow in self.all()
                         if isinstance(flow.entry_selection, dict)
                         and isinstance(flow.entry_selection.get("options"), list)), None)
        if allowlist is None and isinstance(declared, dict):
            declared_allowlist = declared.get("allowlist")
            if isinstance(declared_allowlist, list):
                allowlist = declared_allowlist
        candidates = self.allowlisted(allowlist)
        allowed_ids = {flow.id for flow in candidates}
        if declared is not None:
            options = []
            for raw in declared.get("options") or []:
                if not isinstance(raw, dict):
                    raise SkillError("FLOW_SELECTION_INVALID", "entry option должен быть объектом", self.root)
                option = dict(raw)
                target = option.get("flow") or option.get("target_flow") or option.get("id")
                if target not in allowed_ids:
                    raise SkillError("FLOW_SELECTION_INVALID",
                                     "entry option target «%s» не входит в allowlist" % target, self.root)
                option.pop("target_flow", None)
                documentation = option.pop("documentation", None)
                option["flow"] = target
                if documentation is not None and option.get("policy") is None:
                    option["policy"] = ({"automation": documentation}
                                         if isinstance(documentation, str)
                                         else documentation)
                option.setdefault("preset", target)
                option.setdefault("label", target)
                option.setdefault("description", option["label"])
                options.append(option)
            question = declared.get("question") or declared.get("text") or question
            decision_id = declared.get("decision_id") or decision_id
            default = declared.get("default") or default
            selection = declared.get("selection") or "single"
            allow_custom = bool(declared.get("allow_custom_response", False))
        else:
            options = []
            for flow in candidates:
                selection = flow.entry_selection or {}
                option_id = selection.get("option_id") or flow.id
                option = {"id": option_id, "label": selection.get("label") or flow.name or flow.id,
                          "description": selection.get("description") or flow.name or flow.id,
                          "flow": flow.id, "preset": selection.get("preset") or flow.id}
                if selection.get("documentation") is not None:
                    option["policy"] = selection.get("documentation")
                options.append(option)
            selection, allow_custom = "single", False
        if not options:
            raise SkillError("FLOW_SELECTION_INVALID", "allowlist не содержит доступных flow",
                             self.root, command="tcheck flows list")
        default = default or options[0]["id"]
        return make_choice_request(request_id=request_id, decision_id=decision_id,
                                   question=question, selection=selection, options=options,
                                   default=default, allow_custom_response=allow_custom,
                                   policy_scope=policy_scope, source="flow.json",
                                   metadata={"allowlisted": [item["flow"] for item in options]})

    def has(self, flow_id):
        return flow_id in (self.flows or self.read())

    def get(self, flow_id):
        flows = self.flows or self.read()
        if flow_id not in flows:
            raise SkillError("QUEUE_UNKNOWN",
                             "потока «%s» в поставке нет" % flow_id, self.root,
                             command="tcheck flows list")
        return flows[flow_id]

    def validate_all(self, known_types=None, issues=None):
        issues = issues if issues is not None else []
        for flow in self.all():
            issues.extend(flow.validate(known_types, issues))
        return issues


class FlowState:
    """Положение flow в очереди: один run, повторяемые шаги и fan-out.

    Индекс хранит координаты конкретной записи: preset, логический шаг,
    запуск, элемент fan-out и номер revision. Никакого второго state-файла
    движку не нужно. `task.json` по-прежнему содержит только факты самой
    записи, а переходы проверяют их явно и не меняют status автоматически.
    """

    def __init__(self, queue, flows, types=None):
        self.queue = queue
        self.flows = flows
        self.types = types

    # --- координаты запуска и группировка записей ---
    @staticmethod
    def _revision(item):
        row = item.get("row") if isinstance(item, dict) else None
        value = row.get("flow_revision") if isinstance(row, dict) else None
        try:
            return int(value or 1)
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def _item_id(item):
        row = item.get("row") if isinstance(item, dict) else None
        return row.get("flow_item") if isinstance(row, dict) else None

    def _run_id(self, flow, source):
        row = self.queue.index.find(source.id)
        if row and row.get("flow") == flow.id and row.get("flow_run"):
            return row.get("flow_run")
        return source.id

    def _step_records(self, chain, step_id, revision=None):
        result = []
        for item in chain:
            if item.get("step") != step_id or item.get("record") is None:
                continue
            if revision is not None and self._revision(item) != revision:
                continue
            result.append(item)
        return result

    def _latest(self, items):
        if not items:
            return None
        return sorted(items, key=lambda item: (self._revision(item),
                                               str(item.get("record").id))) [-1]

    def _latest_revision(self, items):
        return max((self._revision(item) for item in items), default=1)

    def _records_at_or_latest(self, chain, step_id, revision=None):
        records = self._step_records(chain, step_id, revision)
        if records or revision is None:
            return records
        latest_revision = self._latest_revision(self._step_records(chain, step_id))
        return self._step_records(chain, step_id, latest_revision)

    def _field_value(self, record, field):
        """Прочитать logical output из extra или обычного поля записи."""
        if field.startswith("extra."):
            return record.extra.get(field.split(".", 1)[1])
        if field in record.extra:
            return record.extra.get(field)
        if field in record.data:
            return record.data.get(field)
        return _condition_value(record, field)

    def _fanout_items(self, flow, step, chain, revision=None):
        """Получить список элементов из закрытого output prerequisite.

        Источник и имя поля объявлены в flow.json. Элемент обязан иметь
        стабильный `item_id`; это позволяет повторному вызову отличать уже
        созданные T-* от ещё не созданных, не добавляя скрытый state store.
        """
        config = step.fan_out or {}
        source = config.get("items_from") or []
        if len(source) != 2:
            return []
        source_records = self._step_records(chain, source[0], revision)
        if not source_records:
            source_records = self._step_records(chain, source[0])
        closed = [item for item in source_records
                  if item.get("record") is not None
                  and item["record"].status == "closed"]
        holder = self._latest(closed)
        if holder is None:
            return []
        raw = self._field_value(holder["record"], source[1])
        if isinstance(raw, dict):
            raw = raw.get("items") or raw.get("slices")
        if not isinstance(raw, list) or not raw:
            raise SkillError(
                "FLOW_FANOUT_INVALID",
                "закрытый шаг «%s» не оставил непустой список «%s»"
                % (source[0], source[1]),
                "flows/%s/%s" % (flow.id, source[0]))
        item_key = config.get("item_id")
        result = []
        seen = set()
        for pos, item in enumerate(raw):
            if not isinstance(item, dict):
                raise SkillError("FLOW_FANOUT_INVALID",
                                 "элемент fan-out [%d] не является объектом" % pos,
                                 "flows/%s/%s" % (flow.id, source[0]))
            value = item.get(item_key)
            if value is None or not str(value).strip():
                raise SkillError("FLOW_FANOUT_INVALID",
                                 "элемент fan-out [%d] не имеет «%s»" % (pos, item_key),
                                 "flows/%s/%s" % (flow.id, source[0]))
            value = str(value)
            if value in seen:
                raise SkillError("FLOW_FANOUT_INVALID",
                                 "идентификатор fan-out «%s» повторяется" % value,
                                 "flows/%s/%s" % (flow.id, source[0]))
            seen.add(value)
            result.append((value, item))
        for value, item in result:
            dependencies = item.get("depends_on") or []
            if isinstance(dependencies, str):
                dependencies = [dependencies]
            unknown = [str(dep) for dep in dependencies if str(dep) not in seen]
            if unknown:
                raise SkillError("FLOW_FANOUT_INVALID",
                                 "элемент «%s» зависит от неизвестных slices: %s"
                                 % (value, ", ".join(unknown)),
                                 "flows/%s/%s" % (flow.id, source[0]))
        return result

    def _step_complete(self, flow, step, chain, revision=None, flow_run=None):
        records = self._step_records(chain, step.id, revision)
        if flow_run is None:
            run_ids = {((item.get("row") or {}).get("flow_run")) for item in chain
                       if (item.get("row") or {}).get("flow_run")}
            if len(run_ids) == 1:
                flow_run = next(iter(run_ids))
        if not records and (step.step_control is not None or step.documentation is not None):
            # A declared skip/manual outcome is an explicit state, not a silent
            # absence of a task.  It is persisted in the append-only decision
            # ledger and may satisfy optional/control routing diagnostics.
            try:
                request = flow.choice_request(step.id, revision=revision or 1,
                                              policy_scope="flow_run")
                if request is not None:
                    decisions = self._decision_store().read().get("decisions", [])
                    for item in decisions:
                        if item.get("request_id") == request.get("request_id") \
                                and (flow_run is None or item.get("run_id") == flow_run) \
                                and item.get("outcome", {}).get("action") in (
                                    "skip", "manual"):
                            return True
            except SkillError:
                pass
            return False
        if not records:
            return False
        if step.fan_out:
            expected = {item_id for item_id, _ in
                        self._fanout_items(flow, step, chain, revision)}
            actual = {self._item_id(item): item for item in records
                      if self._item_id(item) is not None}
            if not expected or not expected.issubset(actual):
                return False
            return all(actual[item_id]["record"].status == "closed"
                       for item_id in expected)
        latest = self._latest(records)
        return latest is not None and latest["record"].status == "closed"

    def _input_revision(self, flow, step, chain):
        revisions = []
        for source_id in step.input_from:
            source_records = self._step_records(chain, source_id)
            revisions.append(self._latest_revision(source_records))
        return max(revisions or [1])

    def _prerequisites_ready(self, flow, step, chain, respect_routes=True):
        """Все input_from имеют закрытый результат нужной revision."""
        revision = self._input_revision(flow, step, chain)
        for source_id in step.input_from:
            source = flow.step(source_id)
            if source is None:
                return False, revision
            if not self._step_complete(flow, source, chain, revision):
                # До появления новой revision допустима последняя закрытая.
                if revision != 1 and self._step_complete(flow, source, chain):
                    continue
                return False, revision
            if respect_routes:
                # A route is an explicit branch, not a hint. A downstream
                # step is ready only when the latest prerequisite selected it.
                source_records = self._records_at_or_latest(chain, source_id, revision)
                latest = self._latest(source_records)
                target = self._route_target(source, latest["record"] if latest else None)
                if target and target not in (step.id, "%s.revision" % step.id):
                    return False, revision
        return True, revision

    def _ready_steps(self, flow, chain):
        """Вернуть `(step, revision, item)` для обычных и dynamic шагов."""
        ready = []
        for step_id in flow.order():
            step = flow.step(step_id)
            if step is None:
                continue
            ok, revision = self._prerequisites_ready(flow, step, chain)
            if not ok:
                continue
            if step.fan_out:
                expected = self._fanout_items(flow, step, chain, revision)
                if not expected:
                    continue
                existing_entries = self._step_records(chain, step.id, revision)
                existing = {self._item_id(item) for item in existing_entries}
                pending = []
                for item_id, data in expected:
                    if item_id in existing:
                        continue
                    dependencies = data.get("depends_on") or []
                    if isinstance(dependencies, str):
                        dependencies = [dependencies]
                    # A slice may depend on another slice. Do not create a
                    # dangling depends_on reference to a T-* that does not
                    # exist yet; the next batch will materialize it.
                    if all(str(dep) in existing for dep in dependencies):
                        pending.append((item_id, data))
                if pending:
                    ready.append((step, revision, pending))
                continue
            existing = self._step_records(chain, step.id, revision)
            if not existing:
                ready.append((step, revision, None))
        return ready

    # --- revision routes ---
    @staticmethod
    def _tree_nodes(tree):
        nodes = tree.get("nodes") if isinstance(tree, dict) else None
        if isinstance(nodes, list):
            return {item.get("id"): item for item in nodes
                    if isinstance(item, dict) and item.get("id")}
        return nodes if isinstance(nodes, dict) else {}

    def _tree_choices(self, tree, step, record):
        """Read only declared decision-tree fields from a closed record."""
        choices = {}
        for node_id, node in self._tree_nodes(tree).items():
            field = node.get("field") or (
                step.route_field if node_id == tree.get("root") else node_id)
            value = self._field_value(record, field)
            if value is not None:
                choices[node_id] = value
        return choices

    def _route_target(self, step, record):
        if record is None:
            return None
        # DECISION-TREE-1 is the primary branch mechanism when declared on a
        # step.  The legacy routes map remains a compatibility adapter for old
        # FLOW-2 definitions, but is never consulted before the tree.
        if step.decision_tree is not None:
            branch = branch_decision_tree(
                step.decision_tree,
                self._tree_choices(step.decision_tree, step, record),
                where="decision_tree.%s" % step.id)
            return branch.get("target")
        if not step.routes:
            return None
        value = _condition_value(record, step.route_field)
        target = step.routes.get(value)
        if target is None:
            target = step.routes.get(str(value))
        return target

    def _revision_candidate(self, flow, chain):
        """Найти ещё не материализованный `target.revision` route."""
        for step in flow.steps:
            records = sorted(self._step_records(chain, step.id),
                             key=lambda item: (self._revision(item),
                                                str(item["record"].id)))
            for item in records:
                record = item["record"]
                if record.status != "closed":
                    continue
                target = self._route_target(step, record)
                if not isinstance(target, str) or not target.endswith(".revision"):
                    continue
                target_id = target[:-9]
                next_revision = self._revision(item) + 1
                previous = self._step_records(chain, target_id, next_revision)
                if not previous:
                    return flow.step(target_id), next_revision, item
        return None

    # --- declarative control, choices and policy ---
    def _decision_store(self):
        return DecisionStore(self.queue.root)

    def _documentation_policy(self, flow=None, step=None, impact=None,
                              explicit=False, override=None, run_id=None,
                              task_ref=None):
        """Resolve workspace < flow/preset < task impact < explicit command."""
        workspace = DocumentationWorkspace(self.queue.root)
        if workspace.manifest is not None:
            base = workspace.policy()
        else:
            base = default_policy()
        flow_policy = (flow.policy if flow is not None and isinstance(flow.policy, dict)
                       else {})
        extension = (step.documentation if step is not None
                     and isinstance(step.documentation, dict) else {})
        impact = impact if isinstance(impact, dict) else {}
        result = effective_policy(base, flow_policy)
        result = effective_policy(result, extension)
        for source in (impact, override if isinstance(override, dict) else {}):
            values = {}
            for key in ("automation", "enforcement", "cadence", "update_after", "verify"):
                value = source.get("%s_override" % key, source.get(key))
                if value is not None:
                    if (key == "enforcement" and result.get("enforcement") in ("required", "critical")
                            and value == "advisory" and not source.get("approved_by")):
                        continue
                    values[key] = value
            result = effective_policy(result, values)
        scoped = PolicyDecisionStore(self.queue.root)
        for scope, ref in (("flow", getattr(flow, "id", None)),
                           ("run", run_id), ("task", task_ref)):
            if ref:
                decision = scoped.current(scope, scope_ref=ref)
                result = effective_policy(result, decision)
        if explicit:
            result["explicit_intent"] = True
            # Explicit intent starts the manual path but must not downgrade a
            # disabled policy.  Manual/ask/always are allowed to proceed.
            if result.get("automation") == "manual":
                result["automation"] = "always"
        return result

    def choice_request(self, flow_id, step_id=None, source_id=None, revision=1):
        flow = self.flows.get(flow_id)
        run_id = None
        if source_id:
            row = self.queue.index.find(source_id)
            run_id = (row or {}).get("flow_run")
        request = flow.choice_request(step_id=step_id, revision=revision,
                                      policy_scope="flow_run" if run_id else "step")
        if request is None:
            raise SkillError("FLOW_CHOICE_INVALID",
                             "для шага/потока не объявлен choice или step_control",
                             "flows/%s" % flow_id,
                             command="tcheck flows show %s" % flow_id)
        if run_id:
            request = dict(request)
            request["flow_run"] = run_id
            request["task_ref"] = source_id
        return request

    def answer_choice(self, flow_id, source_id, step_id, response, by=None,
                      revision=1, disabled=False):
        """Validate and persist one explicit response; never changes policy."""
        flow = self.flows.get(flow_id)
        source = self.queue.resolve(source_id)
        row = self.queue.index.find(source.id)
        run_id = (row or {}).get("flow_run") or source.id
        step = flow.step(step_id)
        if step is None:
            raise SkillError("FLOW_STEP_MISSING", "шага «%s» в потоке нет" % step_id,
                             flow_id)
        request = flow.choice_request(step_id, revision=revision,
                                      policy_scope="flow_run")
        request = dict(request) if request is not None else None
        if request is not None:
            request["flow_run"] = run_id
            request["task_ref"] = source_id
        if request is None:
            raise SkillError("FLOW_CHOICE_INVALID",
                             "шаг «%s» не объявляет choice" % step_id,
                             "%s/%s" % (flow_id, step_id))
        final = validate_choice_response(request, response, actor=by)
        control = step.step_control or step.documentation or {}
        outcome = route_for_decision(control, final, disabled=disabled)
        if outcome.get("action") == "route":
            value = final.get("value") or (final.get("values") or [None])[0]
            target = step.routes.get(value) if isinstance(step.routes, dict) else None
            target = target or (step.routes.get("decline") if isinstance(step.routes, dict) else None)
            if not target:
                raise SkillError("FLOW_CONTROL_INVALID",
                                 "step «%s» объявил route без target в flow.json" % step.id,
                                 "%s/%s" % (flow.id, step.id))
            outcome["route"] = target
        return persist_control_decision(self._decision_store(), request, final, outcome,
                                        run_id, flow_id, step_id, revision)

    def _stored_control(self, flow, step, run_id, revision, task_ref=None):
        request = flow.choice_request(step.id, revision=revision,
                                      policy_scope="flow_run")
        if request is None:
            return None, None
        request = dict(request)
        request["flow_run"] = run_id
        request["task_ref"] = task_ref or run_id
        return request, self._decision_store().find(request["request_id"],
                                                     run_id=run_id,
                                                     step_id=step.id)

    def _control_gate(self, flow, step, run_id, revision, response=None,
                      disabled=False, by=None, explicit_document=False,
                      impact=None, policy_override=None, task_ref=None):
        """Return run/skip/manual or raise a machine-choice question."""
        if step.step_control is None and step.documentation is None:
            return {"action": "run", "route": None, "reason": "not controlled"}
        # FLOW-DOC policy is evaluated before a task is materialized.
        if step.documentation is not None:
            policy = self._documentation_policy(flow, step, impact=impact,
                                                explicit=explicit_document,
                                                override=policy_override,
                                                run_id=run_id, task_ref=task_ref or run_id)
            automation = policy.get("automation")
            required = bool(step.documentation.get("required", not step.optional))
            enforcement = policy.get("enforcement", "advisory")
            if automation == "disabled":
                if required or enforcement in ("required", "critical"):
                    raise SkillError("DOC_POLICY_CONFLICT",
                                     "documentation step «%s» required, but policy disabled"
                                     % step.id,
                                     "%s/%s" % (flow.id, step.id))
                request = doc_request(flow, step, revision)
                if request is not None:
                    request = dict(request)
                    request["flow_run"] = run_id
                    request["task_ref"] = task_ref or run_id
                    synthetic = {"schema": "FLOW-CHOICE-RESPONSE-1",
                                 "request_id": request["request_id"],
                                 "decision_id": request["decision_id"],
                                 "selection": request["selection"], "value": "disable",
                                 "source": "policy", "actor": by,
                                 "reason": "documentation policy disabled"}
                    disabled_control = dict(step.documentation)
                    disabled_control.setdefault("on_disabled", "skip_with_reason")
                    outcome = route_for_decision(disabled_control, synthetic,
                                                 disabled=True)
                    if outcome.get("action") == "block":
                        raise SkillError("DOC_POLICY_CONFLICT",
                                         "documentation step «%s» has no disabled route"
                                         % step.id, "%s/%s" % (flow.id, step.id))
                    persist_control_decision(self._decision_store(), request, synthetic,
                                             outcome, run_id, flow.id, step.id, revision)
                    return outcome
                return {"action": "skip", "route": None,
                        "reason": "documentation policy disabled"}
            if automation == "manual" and not explicit_document:
                return {"action": "manual", "route": None,
                        "reason": "manual documentation waits for explicit intent"}
            if automation == "always":
                return {"action": "run", "route": None,
                        "reason": "documentation policy always"}
            # ask continues through the declared FLOW-DOC question below.
            if step.step_control is None and step.documentation.get("question"):
                request = doc_request(flow, step, revision)
                request = dict(request)
                request["flow_run"] = run_id
                request["task_ref"] = task_ref or run_id
                stored = self._decision_store().find(request["request_id"],
                                                     run_id=run_id, step_id=step.id)
                if stored is not None:
                    outcome = stored.get("outcome") or {"action": "block"}
                    if outcome.get("action") != "run" and (required or
                                                             enforcement in ("required", "critical")):
                        raise SkillError("DOC_POLICY_CONFLICT",
                                         "documentation step «%s» нельзя пропустить при %s policy"
                                         % (step.id, enforcement), "%s/%s" % (flow.id, step.id))
                    return outcome
                if response is None:
                    raise SkillError("FLOW_CHOICE_REQUIRED",
                                     "documentation step «%s» ждёт явный ответ"
                                     % step.id,
                                     "%s/%s" % (flow.id, step.id),
                                     details={"request": request, "run_id": run_id,
                                              "flow_id": flow.id, "step_id": step.id})
                final = validate_choice_response(request, response, actor=by)
                outcome = route_for_decision(step.documentation, final)
                persist_control_decision(self._decision_store(), request, final, outcome,
                                         run_id, flow.id, step.id, revision)
                if outcome.get("action") != "run" and (required or
                                                         enforcement in ("required", "critical")):
                    raise SkillError("DOC_POLICY_CONFLICT",
                                     "documentation step «%s» нельзя пропустить при %s policy"
                                     % (step.id, enforcement), "%s/%s" % (flow.id, step.id),
                                     details={"request": request, "response": final})
                return outcome
        if step.step_control is None:
            return {"action": "run", "route": None, "reason": "documentation explicit path"}
        control = step.step_control
        if control.get("confirmation") == "never" or not control.get("enabled_by_default"):
            return {"action": "run", "route": None, "reason": "control disabled by definition"}
        request, stored = self._stored_control(flow, step, run_id, revision,
                                               task_ref=task_ref)
        if stored is not None:
            return stored.get("outcome") or {"action": "block", "reason": "empty decision"}
        if disabled:
            synthetic = {"schema": "FLOW-CHOICE-RESPONSE-1", "request_id": request["request_id"],
                         "decision_id": request["decision_id"], "selection": request["selection"],
                         "value": "disable", "source": "user", "actor": by,
                         "reason": "explicit disabled flag"}
            outcome = route_for_decision(control, synthetic, disabled=True)
            persist_control_decision(self._decision_store(), request, synthetic, outcome,
                                     run_id, flow.id, step.id, revision)
            if outcome.get("action") == "block":
                raise SkillError("FLOW_CONTROL_BLOCKED",
                                 "step «%s» объявил block для disabled outcome" % step.id,
                                 "%s/%s" % (flow.id, step.id), details={"request": request})
            return outcome
        if response is None:
            raise SkillError("FLOW_CHOICE_REQUIRED",
                             "шаг «%s» ждёт явный ответ на вопрос «%s»"
                             % (step.id, request.get("question")),
                             "%s/%s" % (flow.id, step.id),
                             details={"request": request, "run_id": run_id,
                                      "flow_id": flow.id, "step_id": step.id})
        final = validate_choice_response(request, response, actor=by)
        outcome = route_for_decision(control, final, disabled=disabled)
        if outcome.get("action") == "route":
            value = final.get("value") or (final.get("values") or [None])[0]
            target = step.routes.get(value) if isinstance(step.routes, dict) else None
            target = target or (step.routes.get("decline") if isinstance(step.routes, dict) else None)
            if not target:
                raise SkillError("FLOW_CONTROL_INVALID",
                                 "step «%s» объявил route без target в flow.json" % step.id,
                                 "%s/%s" % (flow.id, step.id))
            outcome["route"] = target
        persist_control_decision(self._decision_store(), request, final, outcome,
                                 run_id, flow.id, step.id, revision)
        if outcome.get("action") == "block" and not step.optional:
            raise SkillError("FLOW_CONTROL_BLOCKED",
                             "обязательный шаг «%s» отклонён и объявил block" % step.id,
                             "%s/%s" % (flow.id, step.id),
                             details={"request": request, "response": final})
        return outcome

    # --- запуск ---
    def start(self, flow_id, source_id, batch=None, by=None, title=None,
              choice=None, choices=None, disabled=False, explicit_document=False,
              policy_override=None):
        """Создать обычные или dynamic черновики для одного run.

        `batch` ограничивает число физических T-* за вызов. При повторном
        вызове недостающие fan-out элементы находятся по flow_item в index.json.
        """
        flow = self.flows.get(flow_id)
        if flow_id not in {item.id for item in self.flows.allowlisted()}:
            raise SkillError("FLOW_SELECTION_INVALID",
                             "flow «%s» не входит в allowlist входного selector" % flow_id,
                             flow_id, command="tcheck flows list")
        source = self.queue.resolve(source_id)
        try:
            limit = int(batch or flow.max_batch or DEFAULT_MAX_BATCH)
        except (TypeError, ValueError):
            raise SkillError("BATCH_FAILED", "batch должен быть целым числом",
                             "ttask flow start")
        if limit < 1 or limit > int(flow.max_batch or DEFAULT_MAX_BATCH):
            raise SkillError("BATCH_FAILED",
                             "поток «%s» объявил не больше %d черновиков за раз, "
                             "просят %d" % (flow_id, flow.max_batch, limit),
                             "flows/%s/flow.json" % flow_id,
                             hint="поток создаёт черновики порциями: оставшиеся "
                                  "создаёт следующий вызов той же команды",
                             command="ttask flow start %s --from %s --batch %d"
                                     % (flow_id, source_id, flow.max_batch))
        run_id = self._run_id(flow, source)
        chain = self.chain(flow, run_id)
        created = []
        gated = set()
        supplied_choices = dict(choices or {}) if isinstance(choices, dict) else {}
        if choice is not None:
            supplied_choices["*"] = choice

        def gate(step, revision):
            response = supplied_choices.get(step.id, supplied_choices.get("*"))
            outcome = self._control_gate(flow, step, run_id, revision,
                                         response=response, disabled=disabled,
                                         by=by, explicit_document=explicit_document,
                                         impact=(source.extra.get("documentation_impact")
                                                or source.data.get("documentation_impact")),
                                         policy_override=policy_override,
                                         task_ref=source.id)
            if outcome.get("action") != "run":
                gated.add((step.id, revision))
            return outcome

        # Route `changes_required -> planning.revision` имеет приоритет над
        # обычной DAG-готовностью: существующая logical step не блокирует
        # повторное прохождение, но новая запись всё равно обычный task.
        candidate = self._revision_candidate(flow, chain)
        if candidate is not None and len(created) < limit:
            step, revision, route_item = candidate
            if step is not None:
                outcome = gate(step, revision)
                if outcome.get("action") != "run":
                    candidate = None
                ready, _ = self._prerequisites_ready(flow, step, chain)
                if candidate is not None and not ready:
                    raise SkillError("FLOW_PREREQUISITE_OPEN",
                                     "revision шага «%s» ещё не имеет закрытых входов"
                                     % step.id,
                                     "flows/%s/%s" % (flow.id, step.id),
                                     command="ttask flow state %s" % route_item["record"].id)
                if candidate is not None:
                    self._check_outputs(flow, chain, step, revision)
                    self._check_requires(flow, chain, step, revision)
                    record = self._draft(flow, step, source, chain, by, title,
                                         run_id=run_id, revision=revision,
                                         route_source=route_item["record"])
                    created.append(record)
                    chain.append({"step": step.id, "record": record,
                                  "row": self.queue.index.find(record.id)})

        if not created:
            ready = self._ready_steps(flow, chain)
            for step, revision, pending in ready:
                if len(created) >= limit:
                    break
                outcome = gate(step, revision)
                if outcome.get("action") != "run":
                    continue
                self._check_outputs(flow, chain, step, revision)
                self._check_requires(flow, chain, step, revision)
                if step.fan_out:
                    for item_id, item in pending:
                        if len(created) >= limit:
                            break
                        record = self._draft(flow, step, source, chain, by, title,
                                             run_id=run_id, flow_item=item_id,
                                             revision=revision, item=item)
                        created.append(record)
                        chain.append({"step": step.id, "record": record,
                                      "row": self.queue.index.find(record.id)})
                else:
                    record = self._draft(flow, step, source, chain, by, title,
                                         run_id=run_id, revision=revision)
                    created.append(record)
                    chain.append({"step": step.id, "record": record,
                                  "row": self.queue.index.find(record.id)})

        remaining = [step.id for step in flow.steps
                     if not self._step_complete(flow, step, chain, flow_run=run_id)]
        return created, remaining

    def select_entry(self, request, response, by="user", allowlist=None):
        """Resolve one FLOW-CHOICE-1 entry response to an allowlisted flow."""
        from .choice import validate_choice_response
        final = validate_choice_response(request, response, actor=by)
        value = final.get("value")
        options = {item.get("id"): item for item in request.get("options", [])}
        option = options.get(value)
        if option is None:
            raise SkillError("FLOW_SELECTION_INVALID",
                             "выбранный flow не входит в allowlist", request.get("request_id"))
        target = option.get("flow") or value
        declared = ((request.get("metadata") or {}).get("allowlisted")
                    if isinstance(request.get("metadata"), dict) else None)
        if isinstance(declared, list) and target not in set(declared):
            raise SkillError("FLOW_SELECTION_INVALID",
                             "flow «%s» отсутствует в allowlisted request" % target,
                             request.get("request_id"))
        allowed_flows = self.flows.allowlisted(allowlist if allowlist is not None else declared)
        if target not in {flow.id for flow in allowed_flows}:
            raise SkillError("FLOW_SELECTION_INVALID",
                             "flow «%s» не входит в allowlist" % target,
                             request.get("request_id"))
        policy = option.get("policy") or option.get("documentation")
        result = {"flow": target, "preset": option.get("preset") or target,
                  "policy": copy.deepcopy(policy), "choice": final,
                  "request_id": request.get("request_id")}
        # Entry selection is a durable decision/provenance event, not a hidden
        # mutation of the workspace policy or a model recommendation.
        self._decision_store().append({
            "schema": "FLOW-ENTRY-DECISION-1",
            "decision_id": "entry:%s:%s" % (request.get("request_id"), target),
            "request_id": request.get("request_id"), "flow_id": target,
            "step_id": "entry", "run_id": None, "revision": 1,
            "scope": request.get("policy_scope"), "question_id": request.get("decision_id"),
            "choice": final, "outcome": {"action": "select", "flow": target,
                                           "preset": result["preset"],
                                           "policy": copy.deepcopy(result["policy"])},
            "actor": by, "reason": "entry flow selection", "at": now_stamp(),
            "policy_fingerprint": None,
        })
        return result

    def transition(self, source_id, target_flow, target_step=None, choice_ref=None,
                   carry_refs=None, requested_by="user", by=None, title=None,
                   scope=None, release_context=None, policy=None):
        """Apply a validated flow switch without rewriting the old run."""
        source = self.queue.resolve(source_id)
        old_row = self.queue.index.find(source.id)
        if old_row is None or not old_row.get("flow"):
            raise SkillError("FLOW_TRANSITION_INVALID",
                             "источник не принадлежит flow run", source_id)
        from_flow = old_row.get("flow")
        from_run = old_row.get("flow_run") or source.id
        from_step = old_row.get("flow_step") or "entry"
        allowed = {flow.id for flow in self.flows.allowlisted()}
        if target_flow not in allowed:
            raise SkillError("FLOW_SELECTION_INVALID",
                             "target flow «%s» не входит в allowlist" % target_flow,
                             target_flow)
        target = self.flows.get(target_flow)
        if target.capabilities:
            from .tools import ToolsIndex
            tools = ToolsIndex(self.queue.root)
            missing = [cap for cap in target.capabilities if tools.get(cap) is None
                       or not tools.get(cap).command]
            if missing:
                raise SkillError("CAPABILITY_UNBOUND",
                                 "target flow требует непривязанные capabilities: %s"
                                 % ", ".join(missing), target_flow)
        source_release = old_row.get("release")
        if not source_release:
            source_flow = self.flows.get(from_flow)
            source_release = source_flow.release
        if target.release and source_release and target.release != source_release:
            raise SkillError("FLOW_RELEASE_CONFLICT",
                             "release source=%s несовместим с target=%s"
                             % (source_release, target.release), target_flow)
        target_step = target_step or target.entry or (target.step_ids() or [None])[0]
        target_node = target.step(target_step)
        if target_node is None:
            raise SkillError("FLOW_STEP_MISSING",
                             "target step «%s» не объявлен в «%s»"
                             % (target_step, target_flow), target_flow)
        refs = list(carry_refs or [])
        if len(refs) > 32:
            raise SkillError("FLOW_TRANSITION_INVALID", "carry_refs превышает limit 32",
                             source_id)
        for ref in refs:
            if isinstance(ref, str) and (ref.startswith("T-") or ":T-" in ref):
                task_id = ref.rsplit(":", 1)[-1]
                try:
                    self.queue.resolve(task_id)
                except SkillError:
                    raise SkillError("FLOW_TRANSITION_INVALID",
                                     "carry task ref «%s» не найден" % ref, source_id)
            elif isinstance(ref, str) and not (ref.startswith("artifact:")
                                               or ref.startswith("ref:")
                                               or ref.startswith("file:")):
                raise SkillError("FLOW_TRANSITION_INVALID",
                                 "carry ref «%s» не имеет разрешённого вида" % ref,
                                 source_id)
            elif isinstance(ref, dict):
                if any(key not in ("kind", "path", "ref", "id", "note") for key in ref):
                    raise SkillError("FLOW_TRANSITION_INVALID",
                                     "carry object содержит лишний key", source_id)
                if not any(ref.get(key) for key in ("path", "ref", "id")):
                    raise SkillError("FLOW_TRANSITION_INVALID",
                                     "carry object не содержит bounded ref", source_id)
            else:
                raise SkillError("FLOW_TRANSITION_INVALID", "carry ref должен быть bounded",
                                 source_id)
        if requested_by == "agent" and not by:
            raise SkillError("FLOW_TRANSITION_UNAUTHORIZED",
                             "agent может запросить switch, но не применить его без approval",
                             source_id)
        payload = make_transition(from_flow, from_run, from_step, target_flow,
                                  target_step, choice_ref=choice_ref,
                                  carry_refs=refs, requested_by=requested_by,
                                  status="applied", scope=scope,
                                  release_context=release_context, policy=policy,
                                  reason="approved by %s" % (by or requested_by))
        transition_id = payload["transition_id"]
        store = TransitionStore(self.queue.root)
        existing = store.get(transition_id) or store.find_duplicate(payload)
        if existing is not None:
            raise SkillError("FLOW_TRANSITION_DUPLICATE",
                             "эквивалентный переход уже применён: %s"
                             % existing.get("transition_id"), self.queue.root)
        new_run = "%s:%s" % (target_flow, transition_id.split(":")[-1])
        target_chain = self.chain(target, new_run)
        if target_node.input_from:
            # A switch may carry references, but it may not fabricate closed
            # prerequisites. Start at an input-free target step or block.
            raise SkillError("FLOW_TRANSITION_INVALID",
                             "target step «%s» имеет prerequisites; carry refs не заменяют их"
                             % target_step, target_flow)
        record = self._draft(target, target_node, source, target_chain, by or requested_by,
                             title, run_id=new_run)
        payload["new_run"] = new_run
        payload["new_record"] = record.id
        payload["approved_at"] = now_stamp()
        payload["applied_at"] = now_stamp()
        payload["validation"] = {"allowlist": True, "target_step": True,
                                  "carry_refs": True, "duplicate": False,
                                  "permission": requested_by != "agent" or bool(by)}
        store.append(payload)
        # Flow run state lives in the index; task facts/status are not rewritten.
        for row in self.queue.index.flow_rows(from_flow, from_run):
            row["flow_run_status"] = "switched"
            row["flow_transition"] = transition_id
        self.queue.index.save()
        return {"transition": payload, "record": record,
                "old_run": {"flow": from_flow, "run": from_run,
                             "status": "switched"},
                "new_run": {"flow": target_flow, "run": new_run,
                             "record": record.id}}

    def _draft(self, flow, step, source, chain, by, title, run_id=None,
               flow_item=None, revision=1, item=None, route_source=None):
        """Черновик шага: тип/родители из flow, состояние — в index."""
        parents = []
        for source_id in step.input_from:
            candidates = self._records_at_or_latest(chain, source_id, revision)
            for entry in candidates:
                record = entry.get("record")
                if record is not None and record.id not in {p.id for p in parents}:
                    parents.append(record)
        if route_source is not None and route_source.id not in {p.id for p in parents}:
            parents.append(route_source)
        parent = parents[0].id if parents else source.id
        depends_on = [record.id for record in parents]
        if isinstance(item, dict) and step.fan_out:
            item_dependencies = item.get("depends_on") or []
            if isinstance(item_dependencies, str):
                item_dependencies = [item_dependencies]
            for dependency in item_dependencies:
                for entry in self._step_records(chain, step.id, revision):
                    if self._item_id(entry) == str(dependency):
                        dependency_record = entry.get("record")
                        if (dependency_record is not None
                                and dependency_record.id not in depends_on):
                            depends_on.append(dependency_record.id)

        kind = step.type
        item_title = None
        if isinstance(item, dict):
            title_key = (step.fan_out or {}).get("title_from")
            if title_key:
                item_title = item.get(title_key)
            item_title = item_title or item.get("title") or item.get("name")
            type_key = (step.fan_out or {}).get("task_type_from")
            if type_key and item.get(type_key):
                kind = str(item.get(type_key))
        actual_title = title or item_title
        if not actual_title:
            actual_title = "%s: %s" % (flow.name or flow.id, step.id)
            if flow_item is not None:
                actual_title += " [%s]" % flow_item
        fields = {"status": "draft", "parent": parent,
                  "depends_on": depends_on,
                  "parallelizable": bool(step.parallel)}
        release = source.data.get("release") or flow.release
        if release is not None:
            fields["release"] = release
        record = self.queue.create(actual_title, kind, **fields)
        if by:
            record.add_comment("поток «%s» создал черновик шага «%s»; в работу "
                               "переводит человек" % (flow.id, step.id), by,
                               kind="agent")
        self.queue.save(record)
        self.queue.index.set_flow(record.id, flow.id, step.id,
                                  flow_run=run_id or source.id,
                                  flow_item=flow_item,
                                  flow_revision=revision)
        holders = [source] + parents
        if route_source is not None:
            holders.append(route_source)
        seen = set()
        for holder in holders:
            if holder is None or holder.id in seen:
                continue
            seen.add(holder.id)
            # Внешнее зеркало — import_only: запуск потока не редактирует его.
            if holder.is_mirror:
                continue
            link(holder, record.id,
                 "поток «%s», шаг «%s»" % (flow.id, step.id), by=by)
            self.queue.save(holder)
        return record

    def _check_outputs(self, flow, chain, step, revision=None):
        """Не создавать шаг, пока prerequisites не оставили outputs."""
        for source_id in step.input_from:
            source = flow.step(source_id)
            if source is None:
                continue
            entries = self._records_at_or_latest(chain, source_id, revision)
            if source.fan_out:
                expected = {item_id for item_id, _ in
                            self._fanout_items(flow, source, chain, revision)}
                entries = [entry for entry in entries
                           if self._item_id(entry) in expected]
            if not entries:
                continue
            for entry in entries:
                holder = entry.get("record")
                if holder is None or holder.status != "closed":
                    continue
                missing = sorted(set(source.output) - set(_left(holder)))
                if missing:
                    raise SkillError(
                        "FLOW_OUTPUT_MISSING",
                        "шаг «%s» оставил не всё для «%s»: нет %s"
                        % (source_id, step.id, ", ".join(missing)),
                        "flows/%s/%s" % (flow.id, source_id),
                        command="ttask flow next %s" % holder.id)

    def _check_requires(self, flow, chain, step, revision=None):
        """Проверить FLOW-2 условия без автоматической смены статуса."""
        if not isinstance(step.requires, list):
            return
        for requirement in step.requires:
            if not isinstance(requirement, dict):
                continue
            source_id = requirement.get("from")
            records = self._records_at_or_latest(chain, source_id, revision)
            holder_item = self._latest(records)
            holder = holder_item.get("record") if holder_item else None
            source_step = flow.step(source_id)
            complete = (source_step is not None
                        and self._step_complete(flow, source_step, chain, revision))
            if holder is None or holder.status != "closed" or not complete:
                code = ("FLOW_JOIN_PENDING" if source_step is not None
                        and source_step.fan_out else "FLOW_PREREQUISITE_OPEN")
                raise SkillError(
                    code,
                    "условие шага «%s» ждёт закрытый prerequisite «%s»"
                    % (step.id, source_id),
                    "flows/%s/%s" % (flow.id, step.id),
                    command="ttask flow state %s" % holder.id
                    if holder is not None else "ttask flow start --flow %s --from <id>"
                                          % flow.id)
            field = str(requirement.get("field"))
            if field == "fan_out":
                actual = "all_closed" if complete else "pending"
            else:
                actual = _condition_value(holder, field)
            expected = requirement.get("equals")
            if actual != expected:
                raise SkillError(
                    "FLOW_CONDITION_UNMET",
                    "для шага «%s» нужно %s.%s=%r, получено %r"
                    % (step.id, source_id, field, expected, actual),
                    "flows/%s/%s" % (flow.id, step.id),
                    hint="исправить prerequisite или явно пройти ветку revision",
                    command="ttask reopen %s --reason «исправить условие потока» --by <имя>"
                            % holder.id)

    def chain(self, flow, flow_run=None):
        """Цепочка flow в индексе: placeholder или все экземпляры шага."""
        rows = self.queue.index.flow_rows(flow.id, flow_run)
        by_step = {}
        for row in rows:
            by_step.setdefault(row.get("flow_step"), []).append(row)
        chain = []
        for step_id in flow.order():
            step_rows = sorted(by_step.get(step_id, []),
                               key=lambda row: (int(row.get("flow_revision") or 1),
                                                str(row.get("flow_item") or ""),
                                                str(row.get("id") or "")))
            if not step_rows:
                chain.append({"step": step_id, "row": None, "record": None})
                continue
            for row in step_rows:
                record = None
                try:
                    record = self.queue.resolve(row.get("id"))
                except SkillError:
                    pass
                chain.append({"step": step_id, "row": row, "record": record})
        return chain

    # --- положение ---
    def state(self, flow_id, source_id=None):
        """Положение flow: все экземпляры dynamic шага и их outputs."""
        flow = self.flows.get(flow_id)
        source = self.queue.resolve(source_id) if source_id is not None else None
        run_id = self._run_id(flow, source) if source is not None else None
        chain = self.chain(flow, run_id)
        if source is not None:
            row = self.queue.index.find(source.id)
            if not row or not row.get("flow_step"):
                chain.insert(0, {"step": None, "row": row, "record": source})
        lines = []
        for item in chain:
            record = item["record"]
            step = flow.step(item["step"]) if item["step"] else None
            if record is None:
                lines.append("%-12s %-13s %s" % (item["step"] or "вход",
                                                 step.type if step else "-",
                                                 "черновик не создан"))
                continue
            marker = []
            if (item.get("row") or {}).get("flow_item"):
                marker.append("item=%s" % item["row"]["flow_item"])
            if self._revision(item) != 1:
                marker.append("revision=%d" % self._revision(item))
            suffix = (" [" + ", ".join(marker) + "]") if marker else ""
            left = _left(record)
            lines.append("%-12s %-13s %s %-11s %s%s" % (
                item["step"] or "вход", record.kind, record.id, record.status,
                "оставил: " + ", ".join(left) if left else "ничего не оставил",
                suffix))
        return lines

    def _structural_candidates(self, flow, chain):
        """Кандидаты до route/condition фильтра, только для диагностики.

        `start` использует `_ready_steps` и не создаёт заблокированную работу.
        `next` дополнительно показывает такую работу, чтобы человек видел,
        какое условие ветки не выполнено.
        """
        candidates = []
        for step_id in flow.order():
            step = flow.step(step_id)
            if step is None:
                continue
            ready, revision = self._prerequisites_ready(
                flow, step, chain, respect_routes=False)
            if not ready:
                continue
            if step.fan_out:
                expected = self._fanout_items(flow, step, chain, revision)
                existing = {self._item_id(item) for item in
                            self._step_records(chain, step.id, revision)}
                if any(item_id not in existing for item_id, _ in expected):
                    candidates.append((step, revision))
            elif not self._step_records(chain, step.id, revision):
                candidates.append((step, revision))
        return candidates

    def _coverage_issues(self, flow, chain):
        issues = []
        for step in flow.steps:
            for source_id in step.input_from:
                source = flow.step(source_id)
                if source is None or not source.output:
                    continue
                for item in self._step_records(chain, source_id):
                    record = item.get("record")
                    if record is None or record.status != "closed":
                        continue
                    missing = sorted(set(source.output) - set(_left(record)))
                    if missing:
                        issues.append(Issue(
                            "error", "flows/%s шаг %s" % (flow.id, source_id),
                            "шаг закрыт и оставил не всё, что объявил: нет %s"
                            % ", ".join(missing), "FLOW_OUTPUT_MISSING"))
        return issues

    def next(self, record_id):
        """Следующий шаг и declared/left для его prerequisites."""
        row = self.queue.index.find(record_id)
        if row is None:
            raise SkillError("RECORD_NOT_FOUND",
                             "строки записи %s в индексе нет" % record_id,
                             self.queue.index.path, command="tqueue index-rebuild")
        flow_id = row.get("flow")
        if not flow_id:
            raise SkillError("FLOW_STATE_MISMATCH",
                             "запись %s не участвует в потоке" % record_id,
                             self.queue.index.path,
                             command="ttask flow start <поток> --from %s" % record_id)
        flow = self.flows.get(flow_id)
        step_id = row.get("flow_step")
        current = flow.step(step_id)
        if current is None:
            raise SkillError("FLOW_STATE_MISMATCH",
                             "шага «%s» в определении потока «%s» нет"
                             % (step_id, flow_id),
                             os.path.join(self.flows.root, flow_id, FLOW_FILENAME),
                             command="tcheck flows show %s" % flow_id)
        chain = self.chain(flow, row.get("flow_run"))
        infos = [(step, revision) for step, revision, _ in
                 self._ready_steps(flow, chain)]
        known = {(step.id, revision) for step, revision in infos}
        # Keep diagnostics useful when a route or a requires condition blocks
        # creation: structurally eligible work is shown, but start() still
        # refuses to materialize it.
        for step, revision in self._structural_candidates(flow, chain):
            if (step.id, revision) not in known:
                infos.append((step, revision))
                known.add((step.id, revision))
        # A fan-in prerequisite may be incomplete even though its first
        # slice is closed. Keep the downstream logical step visible in `next`
        # as a blocked diagnostic; `start` never uses this list to create it.
        for step in flow.steps:
            if (step.id, self._input_revision(flow, step, chain)) in known:
                continue
            for source_id in step.input_from:
                source = flow.step(source_id)
                source_records = self._step_records(chain, source_id)
                if (source is not None and source.fan_out and source_records
                        and not self._step_complete(flow, source, chain)):
                    revision = self._latest_revision(source_records)
                    if (step.id, revision) not in known:
                        infos.append((step, revision))
                        known.add((step.id, revision))
                    break
        candidate = self._revision_candidate(flow, chain)
        if candidate is not None and candidate[0] is not None:
            step, revision, _ = candidate
            if (step.id, revision) not in known:
                infos.insert(0, (step, revision))
        upcoming = infos
        requires = []
        for step, revision in upcoming:
            try:
                self._check_requires(flow, chain, step, revision)
            except SkillError as exc:
                condition = step.requires[0] if isinstance(step.requires, list) \
                    and step.requires else {}
                requires.append({
                    "step": step.id,
                    "from": condition.get("from", "condition"),
                    "declared": ["%s=%r" % (condition.get("field"),
                                               condition.get("equals"))],
                    "left": ["%s: %s" % (exc.code, exc.message)],
                    "record": None,
                })
        for step, revision in upcoming:
            for source_id in step.input_from:
                source = flow.step(source_id)
                if source is None:
                    continue
                entries = self._records_at_or_latest(chain, source_id, revision)
                if source.fan_out and entries and not self._step_complete(
                        flow, source, chain, revision):
                    requires.append({
                        "step": step.id, "from": source_id,
                        "declared": list(source.output) + ["join=all_closed"],
                        "left": ["FLOW_JOIN_PENDING: закрыты не все элементы"],
                        "record": None, "revision": revision,
                        "item": None,
                    })
                holders = entries if source.fan_out else ([self._latest(entries)]
                                                            if entries else [])
                for holder_item in holders:
                    holder = holder_item.get("record") if holder_item else None
                    requires.append({
                        "step": step.id, "from": source_id,
                        "declared": list(source.output),
                        "left": _left(holder) if holder is not None else [],
                        "record": holder.id if holder is not None else None,
                        "revision": revision,
                        "item": self._item_id(holder_item) if holder_item else None,
                    })
        issues = self._coverage_issues(flow, chain)
        return current, [step for step, _ in upcoming], requires, issues

def _condition_value(record, field):
    """Значение условия: extra, обычное поле или наличие результата."""
    if field.startswith("extra."):
        return record.extra.get(field.split(".", 1)[1])
    if field in record.extra:
        return record.extra.get(field)
    if field in record.data:
        return record.data.get(field)
    if field == "handoff":
        return bool(record.handoffs())
    if field == "refs":
        return bool(record.refs)
    if field == "artifacts":
        return bool(record.artifacts)
    return None


def _left(record):
    """Что запись оставила: имена полей, указателей, артефактов и реплик."""
    if record is None:
        return []
    names = []
    names.extend(sorted(k for k, v in record.extra.items() if v))
    if record.refs:
        names.append("refs")
    if record.artifacts:
        names.append("artifacts")
        if any(isinstance(item, dict) and item.get("kind") in ("log", "report", "tests")
               for item in record.artifacts):
            names.append("evidence")
        if any(isinstance(item, dict) and (
                str(item.get("path") or "").startswith("docs/")
                or "/docs/" in str(item.get("path") or "")
                or str(item.get("path") or "").endswith((".md", ".rst"))
                or "docs" in os.path.basename(str(item.get("path") or "")).lower())
               for item in record.artifacts):
            names.append("docs")
    if record.data.get("source"):
        names.append("source")
    for ref in record.refs:
        if isinstance(ref, dict) and ref.get("path"):
            names.append(os.path.basename(str(ref["path"])))
    for art in record.artifacts:
        if isinstance(art, dict) and art.get("path"):
            names.append(os.path.basename(str(art["path"])))
    for field in ("goals", "acceptance", "verify", "steps"):
        if record.data.get(field):
            names.append(field)
    if record.handoffs():
        names.extend(["handoff", "comments:handoff"])
    return names


def read_flow(path, flows_root=None):
    """Прочитать объявление потока из файла: одна точка отказа."""
    data = load_json(path, "объявление потока")
    if data is None:
        raise SkillError("QUEUE_UNKNOWN", "объявления потока нет", path,
                         command="tcheck flows list")
    return Flow(data, os.path.dirname(path))


def dump(flow):
    """Объявление потока как объект: для --json."""
    return {"id": flow.id, "name": flow.name, "entry": flow.entry,
            "schema": flow.schema, "max_batch": flow.max_batch,
            "instruction": flow.instruction,
            "steps": [s.data for s in flow.steps]}


def write(flow, flows_root):
    """Записать объявление потока: данные правит CLI, атомарно."""
    folder = os.path.join(flows_root, flow.id)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, FLOW_FILENAME)
    payload = json.dumps(dump(flow), ensure_ascii=False, indent=2) + "\n"
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as src, \
                open(path + ".bak", "w", encoding="utf-8") as dst:
            dst.write(src.read())
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    return path


def state_issues(queue, flow_index, issues=None):
    """Проверить два поля состояния потока в индексе без второго хранилища."""
    issues = issues if issues is not None else []
    seen = set()
    for row in queue.index.items:
        if not isinstance(row, dict):
            continue
        flow_id, step_id = row.get("flow"), row.get("flow_step")
        if not flow_id and step_id:
            issues.append(Issue("error", "%s.flow_step" % row.get("id"),
                                "номер шага есть без имени потока",
                                "FLOW_STATE_MISMATCH"))
            continue
        if not flow_id:
            continue
        try:
            flow = flow_index.get(flow_id)
        except SkillError:
            issues.append(Issue("error", "%s.flow" % row.get("id"),
                                "поток «%s» из индекса не объявлен" % flow_id,
                                "FLOW_STATE_MISMATCH",
                                command="tcheck flows list"))
            continue
        if not step_id or flow.step(step_id) is None:
            issues.append(Issue("error", "%s.flow_step" % row.get("id"),
                                "шаг «%s» не входит в поток «%s»"
                                % (step_id, flow_id), "FLOW_STATE_MISMATCH",
                                command="tcheck flows show %s" % flow_id))
            continue
        step = flow.step(step_id)
        run = row.get("flow_run") or row.get("parent") or row.get("id")
        revision = row.get("flow_revision") or 1
        item = row.get("flow_item") if step and step.fan_out else None
        if step and step.fan_out and not item:
            issues.append(Issue("error", "%s.flow_item" % row.get("id"),
                                "fan-out запись не имеет идентификатора элемента",
                                "FLOW_STATE_MISMATCH",
                                command="ttask flow state --flow %s %s"
                                        % (flow_id, row.get("id"))))
        key = (flow_id, run, step_id, revision, item)
        if key in seen:
            issues.append(Issue("error", "%s.flow_step" % row.get("id"),
                                "экземпляр шага «%s» потока «%s» повторяется"
                                % (step_id, flow_id), "FLOW_STATE_MISMATCH",
                                command="ttask flow state --flow %s %s"
                                        % (flow_id, row.get("id"))))
        seen.add(key)
    return issues

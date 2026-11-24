"""Точка входа `tcheck`: контроль, типы, потоки, роли, привязки возможностей.

Состав команд: диагностика скилла и очередей, проверка формата, контракт схемы,
самопроверка поставки, типы и их поля, потоки и их шаги, роли и модели,
привязки возможностей среды. Порядок очереди — в `tqueue`, запись как работа —
в `ttask`.
"""

import os

from . import schema
from .cli import Cli, Command
from .doctor import Doctor, hints_count, settings_issues
from .errors import EXIT_FINDINGS, EXIT_OK, Issue, SkillError
from .contracts import validate_contract_file
from .documentation import (DocumentationWorkspace, DOC_PATH_KEYS, AUTOMATION, CADENCE,
                            ENFORCEMENT, UPDATE_AFTER, VERIFY, default_policy,
                            validate_policy)
from .aggregate import Aggregate
from .autodoc import (AUTODOC_AUDIT_SCHEMA, AUTODOC_BUNDLE_SCHEMA, audit_bundle,
                      audit_payload, augment_markdown, build_bundle, canonical_digest,
                      discover_workspace, reconstruct_bundle, render_bundle,
                      schema_contract_payload, validate_autodoc_contract, verify_bundle)
from .flow import FlowIndex, state_issues
from .importer import import_payload, read_payload
from .intake import DraftStore, validate_intake_draft
from .queue import Registry
from .roles import RolesIndex
from .tools import ToolsIndex
from .typedefs import TypeIndex
from .validate import Validator


class CheckCli(Cli):
    """Контроль поставки и данных: находки с готовым действием на каждую."""

    entry = "tcheck"
    area = "контроль, типы, потоки, роли и привязки"
    commands = (
        Command("doctor", "диагностика скилла и очередей",
                flags=[("--all", bool, "все очереди реестра, а не одна"),
                       ("--strict", bool, "строгая проверка: предупреждения как ошибки"),
                       ("--prose", bool, "проверить прозу поставки на невидимые вставки")]),
        Command("validate", "проверить записи: схема, факты, поля типа, гейты",
                flags=[("ids", None, "идентификаторы записей"),
                       ("--all", bool, "все записи очереди"),
                       ("--strict", bool, "строгая проверка")]),
        Command("schema", "контракт схемы: ключи и перечисления данными",
                flags=[("name", None,
                        "имя схемы: TASK, INDEX, TYPE, FIELD, REF, ARTEFACT, "
                        "SOURCE, COMMENT, REPORT, CHECK, FLOW, STEP, TOOL, ROLE, "
                        "AGENT, SETTINGS, AGGREGATE, JIRA_MIRROR, INTAKE, "
                        "TASK_AUDIT, DOC_PATH, PREZA_PARITY; без имени — все"),
                       ("--file", None,
                        "JSON fixture/envelope для общего contract dispatch")]),
        Command("selftest", "самопроверка поставки: команды, флаги, коды, объявления"),
        Command("types", "типы записей и их объявления",
                nested=("list", "show", "fields")),
        Command("flows", "потоки и их шаги", nested=("list", "show")),
        Command("docs", "documentation workspace, catalog, resolver and policy",
                nested=("init", "catalog", "show", "resolve", "check", "stale",
                        "render", "policy_show", "policy_set"), mutating=True),
        Command("aggregate", "recursive read-only catalog of declared workspaces",
                nested=("scan", "status", "list", "show", "diff", "rebuild",
                        "verify", "export"), mutating=True),
        Command("autodoc", "deterministic bundle, offline HTML, diagrams and audit",
                nested=("discover", "bundle", "render", "diagram", "audit",
                        "verify", "reconstruct", "generate"), mutating=True),
        Command("roles", "роли и модели проекта",
                nested=("list", "show", "set", "unset"), mutating=True),
        Command("tools", "привязки возможностей среды",
                nested=("list", "bind", "unbind"), mutating=True),
        Command("import", "импорт внешнего входа в зеркало",
                nested=("jira", "openspec", "speckit"), mutating=True),
        Command("intake", "persistent conversational task-intake and read-only audit",
                nested=("start", "list", "show", "capture", "ask", "answer", "fix",
                        "validate", "finalize", "audit", "cancel"), mutating=True),
    )

    def nested_flags(self, command, action):
        return NESTED_FLAGS.get((command, action), [])

    def normalize_argv(self, argv):
        argv = list(argv)
        # Public contract uses ``tcheck docs policy show|set`` while the
        # dependency-free generic parser stores one nested action token.
        if len(argv) >= 3 and argv[0] == "docs" and argv[1] == "policy":
            if argv[2] in ("show", "set"):
                argv = ["docs", "policy_" + argv[2]] + argv[3:]
        return argv

    # --- documentation ---
    def cmd_docs(self, args):
        action = getattr(args, "action", None)
        if not action:
            raise SkillError("ASK_USER", "docs action не названа", "tcheck docs",
                             hint="init, catalog, show, resolve, check, stale, render, policy show|set",
                             command="tcheck docs catalog --root <root>")
        return getattr(self, "_docs_%s" % action)(args)

    def _docs_workspace(self, args=None):
        return DocumentationWorkspace(self.root,
                                      docs_path=getattr(args, "docs_path", None)
                                      if args is not None else None)

    def _docs_init(self, args):
        workspace = self._docs_workspace(args)
        manifest = workspace.init(workspace_id=getattr(args, "workspace_id", None),
                                  product_id=getattr(args, "product_id", None))
        return self.print_lines(["documentation workspace инициализирован: %s"
                                 % workspace.manifest_path],
                                manifest,
                                next_action="tcheck docs check --root %s" % self.root)

    def _docs_catalog(self, args):
        workspace = self._docs_workspace(args)
        workspace.require_manifest()
        payload = workspace.build_catalog()
        release = getattr(args, "release", None)
        if release:
            payload = workspace.resolve(mode="catalog", release=release,
                                        limits={"modules": getattr(args, "limit", None) or 12})
        lines = ["модулей: %d" % len(payload.get("modules") or []),
                 "catalog: %s" % workspace.catalog_path]
        lines.extend("%s r%s %s" % (item.get("doc_key"), item.get("revision"),
                                    item.get("status"))
                     for item in (payload.get("modules") or []))
        return self.print_lines(lines, payload,
                                next_action="tcheck docs resolve --mode for-task --root %s"
                                            % self.root)

    def _docs_show(self, args):
        workspace = self._docs_workspace(args)
        item = workspace.read_module(getattr(args, "key", None),
                                     revision=getattr(args, "revision", None))
        payload = dict(item["module"])
        payload["content"] = item["content"]
        payload["machine"] = item["machine"]
        payload["claims"] = item["claims"]
        return self.print_lines(["%s r%s %s" % (payload["doc_key"], payload["revision"],
                                                payload["status"]),
                                payload.get("summary") or ""],
                                payload,
                                next_action="tcheck docs check --root %s" % self.root)

    def _docs_resolve(self, args):
        workspace = self._docs_workspace(args)
        workspace.require_manifest()
        task_refs = []
        raw = getattr(args, "task_ref", None)
        if raw:
            task_refs = list(raw)
        raw_files = getattr(args, "file", None)
        files = ([raw_files] if isinstance(raw_files, str)
                 else list(raw_files or []))
        payload = workspace.resolve(mode=getattr(args, "mode", None) or "catalog",
                                    doc_key=getattr(args, "key", None),
                                    task_refs=task_refs, files=files,
                                    release=getattr(args, "release", None),
                                    limits={"modules": getattr(args, "limit", None) or 12,
                                            "chars": getattr(args, "chars", None) or 24000})
        return self.print_lines(["resolver mode=%s modules=%d unknowns=%d stale=%d"
                                % (payload["mode"], len(payload.get("summaries") or []),
                                   len(payload.get("unknowns") or []),
                                   len(payload.get("stale") or []))],
                               payload,
                               next_action="tcheck docs check --root %s" % self.root)

    def _docs_check(self, args):
        workspace = self._docs_workspace(args)
        issues = workspace.check()
        if getattr(args, "strict", False):
            issues = [Issue("error", item.where, item.message, item.code,
                            item.hint, item.command) for item in issues]
        lines = [item.as_line() for item in issues]
        lines.append("docs findings: %d" % len(issues))
        payload = {"findings": [item.as_dict() for item in issues],
                   "errors": len([item for item in issues if item.is_error])}
        code = self.print_lines(lines, payload,
                                next_action="tcheck docs init --root %s" % self.root)
        return EXIT_FINDINGS if any(item.is_error for item in issues) else code

    def _docs_stale(self, args):
        workspace = self._docs_workspace(args)
        payload = workspace.resolve(mode="catalog")
        stale = payload.get("stale") or []
        return self.print_lines(["stale modules: %d" % len(stale)] + list(stale),
                                {"stale": stale},
                                next_action="tcheck docs check --root %s" % self.root)

    def _docs_render(self, args):
        workspace = self._docs_workspace(args)
        item = workspace.read_module(getattr(args, "key", None))
        # Markdown rendering is deliberately deterministic and dependency-free;
        # syntax validation is a check, not a second canonical document.
        content = item.get("content") or ""
        balanced = content.count("```") % 2 == 0
        if not balanced:
            raise SkillError("DOC_RENDER_FAILED", "Markdown fence не сбалансирован",
                             getattr(args, "key", None))
        return self.print_lines(["render check passed: %s" % args.key],
                                {"doc_key": args.key, "render_check": "passed"},
                                next_action="tcheck docs show --key %s --root %s"
                                            % (args.key, self.root))

    def _docs_policy_show(self, args):
        workspace = self._docs_workspace(args)
        if workspace.manifest is None:
            policy = default_policy()
            configured = False
        else:
            policy = workspace.policy()
            configured = True
        payload = {"configured": configured, "scope": getattr(args, "scope", None) or "workspace",
                   "policy": policy}
        return self.print_lines(["documentation policy: %s" % policy.get("automation"),
                                "enforcement: %s; cadence: %s; update_after: %s; verify: %s"
                                % (policy.get("enforcement"), policy.get("cadence"),
                                   policy.get("update_after"), policy.get("verify"))],
                                payload,
                                next_action="tcheck docs policy set --automation ask --by <имя>")

    def _docs_policy_set(self, args):
        workspace = self._docs_workspace(args)
        who = self.require_by(args, "изменение documentation policy")
        if workspace.manifest is None:
            workspace.init()
        values = {"automation": getattr(args, "automation", None),
                  "enforcement": getattr(args, "enforcement", None),
                  "cadence": getattr(args, "cadence", None),
                  "update_after": getattr(args, "update_after", None),
                  "verify": getattr(args, "verify", None)}
        if (getattr(args, "scope", None) in (None, "workspace")
                and values.get("automation") == "disabled"
                and not getattr(args, "confirm", False)):
            raise SkillError("ASK_USER",
                             "workspace disable требует --confirm и owner/policy approval",
                             "documentation policy",
                             details={"question": "Отключить автоматическое документирование?",
                                      "scope": ["этот run", "этот change/task", "этот flow/preset", "workspace", "нет"]})
        if getattr(args, "scope", None) not in (None, "workspace"):
            # Non-workspace decisions are stored as an explicit override ledger,
            # never silently merged into workspace defaults.
            from .documentation import PolicyDecisionStore
            result = PolicyDecisionStore(self.root).set(getattr(args, "scope"), values,
                                                       by=who, reason=getattr(args, "reason", None),
                                                       scope_ref=getattr(args, "scope_ref", None),
                                                       approved_by=who if getattr(args, "confirm", False) else None)
        else:
            result = workspace.set_policy(values, by=who,
                                          reason=getattr(args, "reason", None),
                                          approved_by=who if getattr(args, "confirm", False) else None)
        return self.print_lines(["documentation policy set: %s" %
                                 (values.get("automation") or workspace.policy().get("automation"))],
                                result,
                                next_action="tcheck docs policy show --root %s" % self.root)

    # --- recursive aggregate ---
    def cmd_aggregate(self, args):
        action = getattr(args, "action", None)
        if not action:
            raise SkillError("ASK_USER", "aggregate action не названа", "tcheck aggregate",
                             hint="scan, status, list, show, diff, rebuild, verify, export",
                             command="tcheck aggregate scan --root <root>")
        return getattr(self, "_aggregate_%s" % action)(args)

    def _aggregate(self):
        return Aggregate(self.root)

    def _aggregate_scan(self, args):
        result = self._aggregate().scan(archive=bool(getattr(args, "archive", False)))
        manifest = result["manifest"]
        lines = ["aggregate run: %s" % manifest["aggregate_run_id"],
                 "workspaces: %d; queues: %d; tasks: %d; documents: %d"
                 % (manifest["counts"]["workspaces"], manifest["counts"]["queues"],
                    manifest["counts"]["tasks"], manifest["counts"]["documents"]),
                 "warnings: %d; completeness: %s"
                 % (manifest["counts"]["warnings"], manifest["completeness"]["status"])]
        code = self.print_lines(lines, manifest,
                                next_action="tcheck aggregate status --root %s" % self.root)
        return EXIT_FINDINGS if any(item.get("severity") == "error"
                                    for item in manifest.get("warnings", [])) else code

    def _aggregate_status(self, args):
        manifest = self._aggregate().status()
        return self.print_lines(["aggregate run: %s" % manifest["aggregate_run_id"],
                                "completeness: %s; workspaces: %d; tasks: %d; documents: %d"
                                % (manifest["completeness"]["status"],
                                   manifest["counts"]["workspaces"],
                                   manifest["counts"]["tasks"],
                                   manifest["counts"]["documents"])],
                                manifest,
                                next_action="tcheck aggregate verify --root %s" % self.root)

    def _aggregate_list(self, args):
        kind = getattr(args, "kind", None) or "tasks"
        values = self._aggregate().listing(kind=kind,
                                           workspace=getattr(args, "workspace", None),
                                           limit=getattr(args, "limit", None))
        lines = ["%s: %d" % (kind, len(values))]
        for item in values:
            lines.append("%s %s" % (item.get("global_ref") or item.get("workspace_id"),
                                     item.get("source_status") or item.get("status") or ""))
        return self.print_lines(lines, {"kind": kind, "items": values},
                                next_action="tcheck aggregate show <global-ref> --root %s" % self.root)

    def _aggregate_show(self, args):
        result = self._aggregate().show(getattr(args, "ref", None))
        item = result["item"]
        return self.print_lines(["%s: %s" % (result["kind"],
                                             item.get("global_ref") or item.get("workspace_id")),
                                "source: %s" % item.get("source_path")],
                                result,
                                next_action="tcheck aggregate verify --root %s" % self.root)

    def _aggregate_diff(self, args):
        result = self._aggregate().diff(getattr(args, "from_run", None),
                                        getattr(args, "to_run", None))
        return self.print_lines(["from: %s; to: %s; added: %d; changed: %d; removed: %d"
                                 % (result.get("from_run"), result.get("to_run"),
                                    len(result.get("added", [])), len(result.get("changed", [])),
                                    len(result.get("removed", [])))],
                                result,
                                next_action="tcheck aggregate status --root %s" % self.root)

    def _aggregate_rebuild(self, args):
        manifest = self._aggregate().rebuild(getattr(args, "run_id", None))
        return self.print_lines(["aggregate catalog rebuilt from %s" % manifest["aggregate_run_id"]],
                                manifest,
                                next_action="tcheck aggregate verify --root %s" % self.root)

    def _aggregate_verify(self, args):
        result = self._aggregate().verify()
        lines = ["checked: %d; stale: %d; valid: %s"
                 % (result["checked"], len(result["stale"]), result["valid"])]
        code = self.print_lines(lines, result,
                                next_action="tcheck aggregate scan --root %s" % self.root)
        return EXIT_FINDINGS if not result["valid"] else code

    def _aggregate_export(self, args):
        result = self._aggregate().export(getattr(args, "output", None))
        return self.print_lines(["aggregate export: %s" % result["path"]], result,
                                next_action="tcheck aggregate verify --root %s" % self.root)

    # --- deterministic autodoc ----------------------------------------
    def cmd_autodoc(self, args):
        action = getattr(args, "action", None)
        if not action:
            raise SkillError("ASK_USER", "autodoc action не названа", "tcheck autodoc",
                             hint="discover, bundle, render, diagram, audit, verify, reconstruct, generate",
                             command="tcheck autodoc generate --root <root>")
        return getattr(self, "_autodoc_%s" % action)(args)

    def _autodoc_bundle_path(self, args, required=False):
        value = getattr(args, "bundle", None)
        if value:
            return os.path.abspath(value)
        default = os.path.join(self.root, ".todone", "autodoc", "bundle.json")
        if required and not os.path.isfile(default):
            raise SkillError("AUTODOC_BUNDLE_REQUIRED", "нужен --bundle с существующим bundle",
                             default, command="tcheck autodoc bundle --root <root>")
        return default

    @staticmethod
    def _autodoc_list(value):
        if not value:
            return []
        values = value if isinstance(value, (list, tuple)) else [value]
        result = []
        for raw in values:
            result.extend(item.strip() for item in str(raw).split(",") if item.strip())
        return result

    def _autodoc_discover(self, args):
        report = discover_workspace(self.root, legacy_root=getattr(args, "legacy_root", None))
        payload = report.as_dict()
        lines = ["discovered: %d; skipped: %d; invalid: %d; unknown: %d" %
                 (len(payload["found"]), len(payload["skipped"]), len(payload["invalid"]),
                  len(payload["unknowns"]))]
        code = self.print_lines(lines, payload,
                                next_action="tcheck autodoc bundle --root %s" % self.root)
        return EXIT_FINDINGS if (payload["invalid"] or payload["unknowns"] or
                                 any(item.get("severity") == "error" for item in payload["warnings"])) else code

    def _autodoc_build(self, args, path=None):
        return build_bundle(self.root, path=path,
                            archive=bool(getattr(args, "archive", False)),
                            redact=bool(getattr(args, "redact", False)),
                            include=self._autodoc_list(getattr(args, "include", None)),
                            exclude=self._autodoc_list(getattr(args, "exclude", None)),
                            legacy_root=getattr(args, "legacy_root", None))

    def _autodoc_bundle(self, args):
        path = self._autodoc_bundle_path(args)
        bundle = self._autodoc_build(args, path=path)
        errors = validate_autodoc_contract(bundle, "bundle")
        payload = {"schema": AUTODOC_BUNDLE_SCHEMA, "path": path,
                   "bundle_id": bundle["bundle_id"], "canonical_digest": bundle["canonical_digest"],
                   "counts": {"entities": len(bundle.get("entities") or []),
                              "relations": len(bundle.get("relations") or []),
                              "sources": len(bundle.get("sources") or []),
                              "documents": len(bundle.get("documents") or [])},
                   "completeness": bundle.get("completeness"),
                   "errors": [item.as_dict() for item in errors]}
        lines = ["bundle: %s" % path,
                 "digest: %s; entities: %d; relations: %d; sources: %d" %
                 (bundle["canonical_digest"], len(bundle.get("entities") or []),
                  len(bundle.get("relations") or []), len(bundle.get("sources") or []))]
        code = self.print_lines(lines, payload,
                                next_action="tcheck autodoc render --bundle %s --html <dir>" % path)
        if errors or bundle.get("completeness", {}).get("status") == "blocked":
            return EXIT_FINDINGS
        return code

    def _autodoc_render(self, args):
        path = self._autodoc_bundle_path(args, required=True)
        html_path = getattr(args, "html", None) or os.path.join(self.root, "docs_html")
        manifest = render_bundle(path, html=html_path)
        payload = {"schema": manifest["schema"], "bundle_digest": manifest["bundle_digest"],
                   "html": os.path.abspath(html_path), "pages": len(manifest.get("pages") or []),
                   "assets": len(manifest.get("assets") or [])}
        return self.print_lines(["HTML: %s; pages: %d; assets: %d" %
                                (html_path, payload["pages"], payload["assets"])], payload,
                               next_action="tcheck autodoc audit --bundle %s" % path)

    def _autodoc_diagram(self, args):
        path = self._autodoc_bundle_path(args, required=True)
        html_path = getattr(args, "html", None) or os.path.join(self.root, "docs_html")
        manifest = render_bundle(path, html=html_path)
        payload = {"bundle_digest": manifest["bundle_digest"], "diagrams": manifest.get("diagrams") or [],
                   "html": os.path.abspath(html_path)}
        return self.print_lines(["diagrams: %d" % len(payload["diagrams"])], payload,
                               next_action="tcheck autodoc verify --bundle %s --html %s" % (path, html_path))

    def _autodoc_audit(self, args):
        path = self._autodoc_bundle_path(args, required=True)
        audit_path = getattr(args, "output", None) or os.path.join(os.path.dirname(path), "audit.json")
        result = audit_bundle(path, output=audit_path)
        if getattr(args, "agent", False):
            from .autodoc import _make_packet, _read_json, _write_json
            packet = _make_packet(_read_json(path), result,
                                  limit=getattr(args, "limit", None) or 12,
                                  chars=24000)
            packet_path = os.path.join(os.path.dirname(audit_path), "audit-packet.json")
            _write_json(packet_path, packet)
            result["packet_path"] = packet_path
        payload = {"schema": AUTODOC_AUDIT_SCHEMA, "path": audit_path,
                   "audit_id": result["audit_id"], "verdict": result["verdict"],
                   "findings": len(result.get("findings") or []),
                   "unknowns": len(result.get("unknowns") or [])}
        code = self.print_lines(["audit: %s; verdict: %s; findings: %d" %
                                (audit_path, result["verdict"], payload["findings"])], payload,
                               next_action="tcheck autodoc verify --bundle %s" % path)
        return EXIT_FINDINGS if result["verdict"] != "approved" else code

    def _autodoc_verify(self, args):
        path = self._autodoc_bundle_path(args, required=True)
        result = verify_bundle(path, html=getattr(args, "html", None))
        payload = result
        code = self.print_lines(["verified: %s; findings: %d" %
                                (result["valid"], len(result.get("findings") or []))], payload,
                               next_action="tcheck autodoc generate --root %s" % self.root)
        return EXIT_OK if result["valid"] else EXIT_FINDINGS

    def _autodoc_reconstruct(self, args):
        path = self._autodoc_bundle_path(args, required=True)
        target = getattr(args, "target", None) or self.root
        report = reconstruct_bundle(path, target, force=bool(getattr(args, "force", False)))
        return self.print_lines(["reconstructed: %s; restored: %d; skipped: %d" %
                                (target, len(report.get("restored") or []), len(report.get("skipped") or []))],
                               report,
                               next_action="tcheck autodoc generate --root %s" % target)

    def _autodoc_generate(self, args):
        bundle_path = self._autodoc_bundle_path(args)
        html_path = getattr(args, "html", None) or os.path.join(self.root, "docs_html")
        # Mermaid source blocks are now the canonical Markdown projection for
        # flow instructions. A caller can explicitly opt out when only the
        # derived HTML is wanted.
        augment_enabled = not bool(getattr(args, "no_augment_md", False))
        bundle = self._autodoc_build(args, path=bundle_path)
        augmentation = {"changed": [], "conflicts": []}
        if augment_enabled:
            augmentation = augment_markdown(self.root, bundle, backup=True)
            # The Markdown bytes are source data. Rebuild after augmentation so
            # bundle provenance, source digests, audit, and HTML all describe
            # exactly the files that will be left on disk.
            if augmentation.get("changed"):
                bundle = self._autodoc_build(args, path=bundle_path)
        # The pre-audit input is part of the portable bundle, making the audit
        # page useful even when the live root is unavailable.  It contains no
        # volatile timestamps, so the final digest remains reproducible.
        result = audit_payload(bundle)
        bundle["audit_input"] = {"algorithm_version": result["algorithm_version"],
                                 "verdict": result["verdict"], "findings": result.get("findings") or []}
        bundle["canonical_digest"] = canonical_digest(bundle)
        bundle["bundle_id"] = "autodoc:" + bundle["canonical_digest"].split(":", 1)[1]
        from .autodoc import write_bundle_atomic
        write_bundle_atomic(bundle_path, bundle)
        manifest = render_bundle(bundle_path, html=html_path)
        audit_path = getattr(args, "output", None) or os.path.join(os.path.dirname(bundle_path), "audit.json")
        result = audit_bundle(bundle_path, output=audit_path)
        packet_path = None
        if getattr(args, "agent", False):
            from .autodoc import _make_packet, _read_json, _write_json
            packet_path = os.path.join(os.path.dirname(audit_path), "audit-packet.json")
            _write_json(packet_path, _make_packet(_read_json(bundle_path), result, limit=12, chars=24000))
        verification = verify_bundle(bundle_path, html=html_path, audit=result)
        payload = {"schema": AUTODOC_BUNDLE_SCHEMA, "bundle": bundle_path,
                   "html": html_path, "audit": audit_path,
                   "bundle_id": bundle["bundle_id"], "canonical_digest": bundle["canonical_digest"],
                   "audit_verdict": result["verdict"],
                   "pages": len(manifest.get("pages") or []),
                   "findings": len(result.get("findings") or []),
                   "augmentation": augmentation, "verification": verification,
                   "packet": packet_path}
        lines = ["bundle: %s" % bundle_path,
                 "HTML: %s; audit: %s (%s); pages: %d" %
                 (html_path, audit_path, result["verdict"], payload["pages"])]
        code = self.print_lines(lines, payload,
                               next_action="tcheck autodoc verify --bundle %s --html %s" % (bundle_path, html_path))
        return EXIT_OK if result["verdict"] == "approved" and verification["valid"] else EXIT_FINDINGS

    # --- импорт ---
    def cmd_import(self, args):
        action = getattr(args, "action", None)
        if not action:
            raise SkillError("ASK_USER", "система импорта не названа",
                             "tcheck import",
                             hint="система — jira, openspec или speckit",
                             command="tcheck import jira --file <путь> --by <имя>")
        return getattr(self, "_import_%s" % action)(args)

    def _import_jira(self, args):
        return self._import_external(args, "jira")

    def _import_openspec(self, args):
        return self._import_external(args, "openspec")

    def _import_speckit(self, args):
        return self._import_external(args, "speckit")

    def _import_external(self, args, system):
        queue = self.resolve_queue(args)
        who = self.require_by(args, "импорт %s" % system)
        if not getattr(args, "file", None):
            raise SkillError("ASK_USER", "файл внешнего входа не назван",
                             "tcheck import %s" % system,
                             hint="назвать файл с дословным входом",
                             command="tcheck import %s --file <путь> --by %s"
                                     % (system, who))
        payload = read_payload(system, args.file,
                               external_id=getattr(args, "id", None),
                               title=getattr(args, "title", None))
        result = import_payload(queue, payload, who)
        record = result["record"]
        source = record.source or {}
        lines = ["%s: %s %s" % (system, result["reason"], record.id),
                 "revision %s; raw %d зн. / %d Б; комментариев добавлено %d, обновлено %d"
                 % (source.get("revision"), len(source.get("raw") or ""),
                    len(str(source.get("raw") or "").encode("utf-8")),
                    len(result["new_comments"]), len(result.get("updated_comments", []))),
                 "зеркало не редактируется системой: %s" % record.path]
        if result.get("profile_files"):
            lines.append("profile artifacts: %s" % ", ".join(result["profile_files"]))
        if result.get("completeness"):
            lines.append("snapshot completeness: %s; custom fields: %d"
                         % (result["completeness"].get("status"),
                            result["completeness"].get("custom_field_count", 0)))
        if result["draft_commands"]:
            lines.append("черновики дочерних записей печатаются, но не создаются:")
            lines.extend("  " + command for command in result["draft_commands"])
        else:
            lines.append("новых комментариев нет: дочерний черновик не нужен")
        payload_out = {"id": record.id, "system": system,
                       "revision": source.get("revision"),
                       "raw_chars": len(source.get("raw") or ""),
                       "new_comments": result["new_comments"],
                       "updated_comments": result.get("updated_comments", []),
                       "draft_commands": result["draft_commands"],
                       "profile_files": result.get("profile_files", []),
                       "completeness": result.get("completeness")}
        return self.print_lines(lines, payload_out, counts=queue.counts(),
                                next_action=(result["draft_commands"][0]
                                             if result["draft_commands"]
                                             else "ttask show %s" % record.id))

    # --- conversational task intake ------------------------------------
    def cmd_intake(self, args):
        action = getattr(args, "action", None)
        if not action:
            raise SkillError("ASK_USER", "intake action не названа", "tcheck intake",
                             hint="start, capture, ask, answer, fix, finalize, audit",
                             command="tcheck intake start --title <название> --by <имя>")
        return getattr(self, "_intake_%s" % action)(args)

    def _intake_store(self):
        return DraftStore(self.root)

    def _intake_draft(self, args):
        return self._intake_store().load(args.session)

    def _intake_start(self, args):
        who = self.require_by(args, "постановка задачи")
        store = self._intake_store()
        draft = store.start(getattr(args, "title", None), who,
                            queue=getattr(args, "queue", None),
                            session_id=getattr(args, "session", None))
        draft_task = None
        if getattr(args, "persist", False):
            queue = self.resolve_queue(args)
            draft_task = draft.create_draft_task(queue, title=getattr(args, "title", None),
                                                 actor=who)
        return self.print_lines(["intake session: %s" % draft.session_id,
                                "режим: collecting; следующий вопрос задаётся явно",
                                ("draft task: %s" % draft_task.id) if draft_task else
                                "draft task ещё не создан: нужен явный --persist"],
                                {"session": draft.data, "draft_task": draft_task.id if draft_task else None},
                                next_action="tcheck intake ask %s --question <текст> --by %s"
                                            % (draft.session_id, who))

    def _intake_list(self, args):
        values = self._intake_store().list()
        return self.print_lines(["intake sessions: %d" % len(values)] +
                                ["%s %s %s" % (item.get("session_id"), item.get("state"),
                                                item.get("verdict") or "-") for item in values],
                                {"sessions": values},
                                next_action="tcheck intake show <session> --root <root>")

    def _intake_show(self, args):
        draft = self._intake_draft(args)
        return self.print_lines(["intake %s: %s; verdict=%s; open=%d"
                                % (draft.session_id, draft.data.get("state"),
                                   draft.data.get("verdict") or "-",
                                   len(draft.data.get("remaining_questions") or []))],
                                draft.data,
                                next_action="tcheck intake validate %s --root %s"
                                            % (draft.session_id, self.root))

    def _intake_capture(self, args):
        who = self.require_by(args, "приём входа постановки задачи")
        draft = self._intake_draft(args)
        path = getattr(args, "file", None)
        if path:
            entry = draft.store.capture_file(draft, path, actor=who,
                                             source_kind=getattr(args, "source_kind", None),
                                             text=getattr(args, "text", None))
        else:
            text = getattr(args, "text", None)
            if not text:
                raise SkillError("INTAKE_TEXT_MISSING", "для capture нужен --text или --file",
                                 "tcheck intake capture")
            entry = draft.add_entry(getattr(args, "status", None) or "observed", text,
                                    getattr(args, "source_kind", None) or "message",
                                    getattr(args, "source", None) or "conversation:message",
                                    actor=who)
        return self.print_lines(["entry %s сохранён с provenance %s"
                                % (entry["id"], entry["provenance"]["source_ref"])],
                                {"session": draft.data, "entry": entry},
                                next_action="tcheck intake ask %s --question <текст> --by %s"
                                            % (draft.session_id, who))

    def _intake_ask(self, args):
        who = self.require_by(args, "уточнение требований")
        draft = self._intake_draft(args)
        choices = getattr(args, "choices", None)
        if isinstance(choices, str):
            choices = [item.strip() for item in choices.split(",") if item.strip()]
        question = draft.ask(getattr(args, "question", None) or getattr(args, "text", None),
                             choices=choices, default=getattr(args, "default", None),
                             on_decline=getattr(args, "on_decline", None) or "ask_again",
                             on_disabled=getattr(args, "on_disabled", None) or "ask_again",
                             actor=who)
        return self.print_lines(["question %s: %s" % (question["id"], question["text"])],
                                {"session": draft.data, "question": question},
                                next_action="tcheck intake answer %s --question-id %s --value <ответ> --by %s"
                                            % (draft.session_id, question["id"], who))

    def _intake_answer(self, args):
        who = self.require_by(args, "ответ на уточняющий вопрос")
        draft = self._intake_draft(args)
        answer = draft.answer(getattr(args, "question_id", None), getattr(args, "value", None),
                              actor=who, source="user", disabled=bool(getattr(args, "disabled", False)))
        return self.print_lines(["answer %s: %s; outcome=%s"
                                % (answer["question_id"], answer["value"], answer["outcome"])],
                                {"session": draft.data, "answer": answer},
                                next_action="tcheck intake show %s --root %s"
                                            % (draft.session_id, self.root))

    def _intake_fix(self, args):
        who = self.require_by(args, "явная фиксация требования")
        draft = self._intake_draft(args)
        entry = draft.fix(getattr(args, "text", None),
                          source_kind=getattr(args, "source_kind", None) or "message",
                          source_ref=getattr(args, "source", None) or "conversation:explicit-fix",
                          actor=who)
        return self.print_lines(["явно зафиксировано в intake %s: %s"
                                % (draft.session_id, entry["id"])],
                                {"session": draft.data, "entry": entry},
                                next_action="tcheck intake show %s --root %s"
                                            % (draft.session_id, self.root))

    def _intake_validate(self, args):
        draft = self._intake_draft(args)
        issues = validate_intake_draft(draft.data, self._intake_store().path(draft.session_id))
        lines = [item.as_line() for item in issues] or ["INTAKE-1 valid"]
        code = self.print_lines(lines, {"session": draft.data,
                                        "findings": [item.as_dict() for item in issues],
                                        "valid": not any(item.is_error for item in issues)},
                                next_action="tcheck intake show %s --root %s" %
                                            (draft.session_id, self.root))
        return EXIT_FINDINGS if any(item.is_error for item in issues) else code

    def _intake_finalize(self, args):
        who = self.require_by(args, "сформулировать задачу")
        draft = self._intake_draft(args)
        queue = self.resolve_queue(args)
        spec = {"problem": getattr(args, "problem", None),
                "goals": getattr(args, "goals", None),
                "acceptance": getattr(args, "acceptance", None),
                "in_scope": getattr(args, "in_scope", None),
                "out_of_scope": getattr(args, "out_of_scope", None),
                "context": getattr(args, "context", None),
                "files_hint": getattr(args, "files_hint", None),
                "steps": getattr(args, "steps", None),
                "verify": getattr(args, "verify", None),
                "open_questions": getattr(args, "open_questions", None),
                "change_kind": getattr(args, "change_kind", None)}
        record = draft.finalize(queue, getattr(args, "type", None) or "default",
                                getattr(args, "title", None), spec, actor=who,
                                allow_open=bool(getattr(args, "allow_open", False)))
        return self.print_lines(["typed task создана: %s (%s)" % (record.id, record.kind),
                                "verdict: %s; remaining questions: %d; risks: %d"
                                % (draft.data.get("verdict"),
                                   len(draft.data.get("remaining_questions") or []),
                                   len(draft.data.get("risks") or []))],
                                {"session": draft.data, "task": record.data},
                                counts=queue.counts(), next_action="ttask show %s" % record.id)

    def _intake_audit(self, args):
        who = self.require_by(args, "аудит задачи")
        draft = self._intake_draft(args)
        queue = self.resolve_queue(args)
        audit = draft.audit(queue, getattr(args, "task", None), actor=who)
        lines = ["audit %s: verdict=%s; findings=%d; remaining questions=%d; risks=%d"
                 % (audit["audit_id"], audit["verdict"], len(audit["findings"]),
                    len(audit["remaining_questions"]), len(audit["remaining_risks"]))]
        return self.print_lines(lines, audit, counts=queue.counts(),
                                next_action="ttask show %s" % (audit.get("audit_task_ref") or
                                                               getattr(args, "task", None)))

    def _intake_cancel(self, args):
        who = self.require_by(args, "отмена постановки задачи")
        draft = self._intake_draft(args)
        draft.data["state"] = "cancelled"
        draft.data["verdict"] = "blocked"
        draft.store.save(draft, event={"kind": "cancelled"}, actor=who, action="cancel")
        return self.print_lines(["intake %s отменён; typed task не создан" % draft.session_id],
                                draft.data,
                                next_action="tcheck intake list --root %s" % self.root)

    # --- диагностика ---
    def cmd_doctor(self, args):
        doctor = self._doctor(args)
        issues = doctor.run(strict=bool(getattr(args, "strict", False)),
                            prose=True)
        if getattr(args, "strict", False):
            issues = [Issue("error", i.where, i.message, i.code, i.hint, i.command)
                      for i in issues]
        lines = [i.as_line() for i in issues]
        summary = doctor.summary(issues)
        lines.append("находок %d: ошибок %d, предупреждений %d; кодов с готовым "
                     "действием %d" % (len(issues), summary["errors"],
                                       summary["warnings"], hints_count()))
        payload = {"findings": [i.as_dict() for i in issues], "summary": summary,
                   "next_actions": doctor.next_actions(issues)}
        code = self.print_lines(lines, payload,
                                next_action=(doctor.next_actions(issues) or
                                             ["tcheck selftest"])[0])
        return EXIT_FINDINGS if summary["errors"] else code

    def cmd_validate(self, args):
        queue = self.resolve_queue(args)
        types = TypeIndex(self.paths()["types"])
        validator = Validator(types)
        ids = self.ids_of(args)
        if getattr(args, "all", False) or not ids:
            ids = [r.id for r in queue.records]
        lines = []
        issues = []
        for task_id in ids:
            record = queue.resolve(task_id)
            found = validator.record(record,
                                     strict=bool(getattr(args, "strict", False)))
            issues.extend(found)
            lines.append("%s %s: находок %d" % (record.id, record.kind, len(found)))
        lines.extend(i.as_line() for i in issues)
        lines.append("проверено записей %d, находок %d" % (len(ids), len(issues)))
        payload = {"ids": ids, "findings": [i.as_dict() for i in issues],
                   "errors": len([i for i in issues if i.is_error])}
        code = self.print_lines(lines, payload, counts=queue.counts(),
                                next_action="tcheck doctor --all")
        return EXIT_FINDINGS if any(i.is_error for i in issues) else code

    def cmd_schema(self, args):
        fixture = getattr(args, "file", None)
        if fixture:
            payload, issues = validate_contract_file(fixture)
            lines = ["contract %s: %s" % (fixture,
                                           "passed" if not issues else "findings %d" % len(issues))]
            lines.extend(item.as_line() for item in issues)
            result = {"file": fixture, "schema": payload.get("schema") or payload.get("policy"),
                      "valid": not any(item.is_error for item in issues),
                      "findings": [item.as_dict() for item in issues]}
            code = self.print_lines(lines, result,
                                    next_action="tcheck schema --file <fixture.json>")
            return EXIT_FINDINGS if any(item.is_error for item in issues) else code
        name = (getattr(args, "name", None) or "").upper()
        table = SCHEMAS
        if name and name not in table:
            raise SkillError("KEY_UNKNOWN", "схемы «%s» нет" % name,
                             "tcheck schema",
                             hint="имя схемы — %s" % ", ".join(sorted(table)),
                             command="tcheck schema %s" % "|".join(sorted(table)))
        names = [name] if name else sorted(table)
        lines = []
        payload = {}
        for item in names:
            keys = table[item]
            lines.append("%s (%d): %s" % (item, len(keys), ", ".join(str(k) for k in keys)))
            payload[item] = list(keys)
        return self.print_lines(lines, payload,
                                next_action="tcheck schema %s" % names[0])

    def cmd_selftest(self, args):
        """Самопроверка: команды, флаги, коды, объявления типов и потоков."""
        issues = []
        issues.extend(_cli_selftest())
        types = TypeIndex(self.paths()["types"])
        issues.extend(types.validate_all())
        paths = self.paths()
        flows = FlowIndex(paths["flows"], paths["project_flows"])
        issues.extend(flows.validate_all([t.id for t in types.all()]))
        issues.extend(Doctor(type_index=types, prose_roots=[]).coverage_issues())
        issues.extend(_prose_selftest(self.paths()["skill"]))
        lines = ["проверено: команд %d, типов %d, потоков %d, кодов с готовым "
                 "действием %d" % (_command_count(), len(types.names()),
                                   len(flows.names()), hints_count())]
        lines.extend(i.as_line() for i in issues)
        lines.append("находок %d" % len(issues))
        payload = {"commands": _command_count(), "types": types.names(),
                   "flows": flows.names(), "hints": hints_count(),
                   "findings": [i.as_dict() for i in issues]}
        code = self.print_lines(lines, payload,
                                next_action="tcheck doctor --all")
        return EXIT_FINDINGS if any(i.is_error for i in issues) else code

    # --- типы ---
    def cmd_types(self, args):
        action = getattr(args, "action", None)
        if not action:
            raise SkillError("ASK_USER", "вложенная команда не названа",
                             "tcheck types", hint="вложенные команды: list, show, fields",
                             command="tcheck types list")
        return getattr(self, "_types_%s" % action)(args)

    def _types_list(self, args):
        types = TypeIndex(self.paths()["types"])
        lines = [t.as_line() for t in types.all()]
        return self.print_lines(lines, {"types": [t.id for t in types.all()]},
                                next_action="tcheck types show <тип>")

    def _types_show(self, args):
        types = TypeIndex(self.paths()["types"])
        typedef = types.get(args.name)
        lines = [typedef.as_line(),
                 "гейты: %s" % (", ".join("%s=%s" % (k, v)
                                          for k, v in sorted((typedef.gates or {}).items()))
                                or "не объявлены"),
                 "возможности: %s" % (", ".join(typedef.capabilities) or "не объявлены"),
                 "редактор: %s" % typedef.editor,
                 "профиль: %s" % (typedef.profile or "универсальный из конфига"),
                 "проверки: %s" % (", ".join(c.get("id", "-")
                                             for c in typedef.checks) or "нет"),
                 "инструкция: %s" % os.path.join(self.paths()["types"], typedef.id,
                                                 "instruction.md"),
                 "дополнительные поля: %s"
                 % (", ".join(f.get("name", "-") for f in typedef.fields) or "нет")]
        payload = {"type": typedef.data, "fields": typedef.fields,
                   "gates": typedef.gates, "capabilities": typedef.capabilities,
                   "editor": typedef.editor, "profile": typedef.profile,
                   "checks": typedef.checks}
        return self.print_lines(lines, payload,
                                next_action="tcheck types fields %s" % typedef.id)

    def _types_fields(self, args):
        types = TypeIndex(self.paths()["types"])
        typedef = types.get(args.name)
        lines = []
        for field in typedef.fields:
            lines.append("%-16s %-8s %-9s %s" % (
                field.get("name"), field.get("type"),
                "обязательно" if field.get("required") else "-",
                field.get("message") or ""))
            if field.get("example"):
                lines.append("    образец: %s" % field["example"])
            if field.get("enum"):
                lines.append("    перечисление: %s" % ", ".join(field["enum"]))
            if field.get("pattern"):
                lines.append("    формат: %s" % field["pattern"])
        if not lines:
            lines = ["дополнительных полей тип не объявляет"]
        return self.print_lines(lines, {"type": typedef.id, "fields": typedef.fields},
                                next_action="ttask set <id> --extra <имя>=<значение>")

    # --- потоки ---
    def cmd_flows(self, args):
        action = getattr(args, "action", None)
        if not action:
            raise SkillError("ASK_USER", "вложенная команда не названа",
                             "tcheck flows", hint="вложенные команды: list, show",
                             command="tcheck flows list")
        return getattr(self, "_flows_%s" % action)(args)

    def _flows_list(self, args):
        paths = self.paths()
        flows = FlowIndex(paths["flows"], paths["project_flows"])
        lines = [f.as_line() for f in flows.all()] or ["потоков в поставке нет"]
        return self.print_lines(lines, {"flows": flows.names()},
                                next_action="tcheck flows show <поток>")

    def _flows_show(self, args):
        paths = self.paths()
        flows = FlowIndex(paths["flows"], paths["project_flows"])
        flow = flows.get(args.name)
        lines = [flow.as_line(), "порядок шагов: %s" % " → ".join(flow.order()),
                 "точка входа: %s" % flow.entry,
                 "промпт потока: %s" % flow.instruction_path(self.paths()["flows"])]
        lines += [step.as_line() for step in flow.steps]
        payload = {"id": flow.id, "name": flow.name, "entry": flow.entry,
                   "schema": flow.schema, "max_batch": flow.max_batch,
                   "order": flow.order(), "steps": [s.data for s in flow.steps]}
        return self.print_lines(lines, payload,
                                next_action="ttask flow start --flow %s --from <id>"
                                            % flow.id)

    # --- роли ---
    def cmd_roles(self, args):
        action = getattr(args, "action", None)
        if not action:
            raise SkillError("ASK_USER", "вложенная команда не названа",
                             "tcheck roles",
                             hint="вложенные команды: list, show, set, unset",
                             command="tcheck roles list")
        return getattr(self, "_roles_%s" % action)(args)

    def _roles_index(self, args):
        return RolesIndex(self.root, who=getattr(args, "by", None))

    def _roles_list(self, args):
        roles = self._roles_index(args)
        roles.read()
        lines = [r.as_line() for r in roles.all()] or ["ролей не объявлено"]
        role, model = roles.weakest()
        if role is not None:
            lines.append("слабейшая модель: %s (роль %s, уровень %s) — на ней "
                         "прогоняют маршруты фазы" % (model, role.role, role.tier))
        payload = {"roles": [r.data for r in roles.all()],
                   "weakest": model,
                   "weakest_role": role.role if role else None}
        return self.print_lines(lines, payload,
                                next_action="tcheck roles set <роль> --tier cheap "
                                            "--mode subagent --models <модель> "
                                            "--by <имя>")

    def _roles_show(self, args):
        roles = self._roles_index(args)
        role = roles.get(args.name)
        if role is None:
            raise SkillError("ROLE_UNKNOWN", "роли «%s» в файле ролей нет" % args.name,
                             roles.path, command="tcheck roles list")
        return self.print_lines([role.as_line()], {"role": role.data},
                                next_action="tcheck roles list")

    def _roles_set(self, args):
        who = self.require_by(args, "правка ролей")
        roles = self._roles_index(args)
        roles.read()
        fields = {}
        for key, flag in (("tier", "tier"), ("mode", "mode"), ("tools", "tools"),
                          ("models", "models")):
            value = getattr(args, flag, None)
            if value is not None:
                fields[key] = [x.strip() for x in str(value).split(",")] \
                    if key == "models" else value
        if not fields:
            raise SkillError("ASK_USER", "ни одно поле роли не названо",
                             "tcheck roles set",
                             hint="назвать уровень, режим, инструменты или модели",
                             command="tcheck roles set %s --tier cheap --by %s"
                                     % (args.name, who))
        role = roles.set(args.name, who, **fields)
        issues = role.validate()
        lines = [role.as_line()]
        lines.extend(i.as_line() for i in issues)
        payload = {"role": role.data, "findings": [i.as_dict() for i in issues]}
        code = self.print_lines(lines, payload, next_action="tcheck roles list")
        return EXIT_FINDINGS if any(i.is_error for i in issues) else code

    def _roles_unset(self, args):
        who = self.require_by(args, "снятие роли")
        roles = self._roles_index(args)
        roles.read()
        if roles.get(args.name) is None:
            raise SkillError("ROLE_UNKNOWN", "роли «%s» в файле ролей нет" % args.name,
                             roles.path, command="tcheck roles list")
        roles.who = who
        roles.roles.pop(args.name)
        roles.write()
        return self.print_lines(["роль %s снята: %s" % (args.name, roles.path)],
                                {"role": args.name, "removed": True},
                                next_action="tcheck roles list")

    # --- привязки возможностей ---
    def cmd_tools(self, args):
        action = getattr(args, "action", None)
        if not action:
            raise SkillError("ASK_USER", "вложенная команда не названа",
                             "tcheck tools",
                             hint="вложенные команды: list, bind, unbind",
                             command="tcheck tools list")
        return getattr(self, "_tools_%s" % action)(args)

    def _tools_index(self, args):
        return ToolsIndex(self.root, who=getattr(args, "by", None))

    def _tools_list(self, args):
        tools = self._tools_index(args)
        tools.read()
        types = TypeIndex(self.paths()["types"])
        lines = [b.as_line() for b in tools.all()] or ["привязок нет"]
        issues = tools.bound_issues(types)
        lines.extend(i.as_line() for i in issues)
        lines.append("возможностей объявлено типами %d, привязано %d"
                     % (len({c for t in types.all() for c in t.capabilities}),
                        len([b for b in tools.all() if b.command])))
        payload = {"tools": [b.data for b in tools.all()],
                   "unbound": [i.as_dict() for i in issues]}
        code = self.print_lines(lines, payload,
                                next_action="tcheck tools bind <возможность> "
                                            "--command <команда> --by <имя>")
        return EXIT_FINDINGS if any(i.is_error for i in issues) else code

    def _tools_bind(self, args):
        who = self.require_by(args, "привязка возможности")
        tools = self._tools_index(args)
        capability = args.capability
        if not getattr(args, "tool_command", None):
            raise SkillError("ASK_USER", "команда привязки не названа",
                             "tcheck tools bind %s" % capability,
                             hint="назвать команду или сервер среды",
                             command="tcheck tools bind %s --command <команда> --by %s"
                                     % (capability, who))
        if capability not in schema.CAPABILITIES:
            raise SkillError("CAPABILITY_UNBOUND",
                             "возможности «%s» нет среди объявленных" % capability,
                             "tcheck tools bind",
                             hint="возможность — %s" % ", ".join(schema.CAPABILITIES),
                             command="tcheck tools bind %s --command <команда> "
                                     "--by %s" % ("|".join(schema.CAPABILITIES), who))
        binding = tools.bind(capability, args.tool_command, who,
                             note=getattr(args, "note", None))
        return self.print_lines([binding.as_line()], {"tool": binding.data},
                                next_action="tcheck tools list")

    def _tools_unbind(self, args):
        who = self.require_by(args, "отвязка возможности")
        tools = self._tools_index(args)
        removed = tools.unbind(args.capability, who)
        if removed is None:
            raise SkillError("CAPABILITY_UNBOUND",
                             "привязки «%s» нет" % args.capability, tools.path,
                             command="tcheck tools list")
        return self.print_lines(["привязка %s снята" % args.capability],
                                {"capability": args.capability, "removed": True},
                                next_action="tcheck tools list")

    # --- сборка диагностики ---
    def _doctor(self, args):
        types = TypeIndex(self.paths()["types"])
        queues = []
        registry = Registry(self.root)
        if getattr(args, "all", False):
            for entry in registry.entries():
                alias = entry.get("alias")
                if alias:
                    queues.append(_queue_of(self.root, alias))
        else:
            queue = self.resolve_queue(args, required=False)
            if queue is not None:
                queues.append(queue)
        return _MultiDoctor(queues, types, self.paths(), self.root, args)


class _MultiDoctor(Doctor):
    """Диагностика нескольких очередей: находки всех, подсказки слиянием."""

    def __init__(self, queues, types, paths, root, args):
        Doctor.__init__(self, queue=queues[0] if queues else None,
                        type_index=types,
                        prose_roots=[paths["skill"]],
                        hints=_type_hints(types, paths))
        self.queues = queues
        self.paths = paths
        self.root = root
        self.args = args

    def run(self, strict=False, prose=True):
        issues = []
        for queue in self.queues:
            self.queue = queue
            issues.extend(Doctor.run(self, strict=strict, prose=False))
            issues.extend(settings_issues(queue.settings))
        self.queue = self.queues[0] if self.queues else None
        flows = FlowIndex(self.paths["flows"], self.paths.get("project_flows"))
        issues.extend(flows.validate_all([t.id for t in self.types.all()]))
        for queue in self.queues:
            issues.extend(state_issues(queue, flows))
        roles = RolesIndex(self.root)
        roles.read()
        issues.extend(roles.validate_all())
        issues.extend(_record_roles(roles, self.queues))
        tools = ToolsIndex(self.root)
        tools.read()
        issues.extend(tools.validate_all())
        issues.extend(tools.bound_issues(self.types))
        issues.extend(self.coverage_issues())
        if prose:
            issues.extend(self.prose_issues())
        issues.extend(_instruction_fallback(self.types, self.paths))
        issues.extend(_long_reference(self.types, self.paths, self.queues))
        return issues


def _type_hints(types, paths):
    """Коды, объявленные типами, сливаются с таблицей подсказок диагностики."""
    return types.codes()


def _queue_of(root, alias):
    from .queue import Queue, Registry
    entry = Registry(root).find(alias)
    return Queue(root, alias, base_dir=(entry or {}).get("path"))


def _record_roles(roles, queues):
    """Роль из записи не объявлена в файле ролей — ROLE_UNKNOWN."""
    issues = []
    known = {r.role for r in roles.all()}
    for queue in queues:
        for record in queue.records:
            owner = record.data.get("owner")
            if owner and owner not in known and roles.all():
                issues.append(Issue("warning", "%s.owner" % record.id,
                                    "роль «%s» не объявлена в файле ролей" % owner,
                                    "ROLE_UNKNOWN",
                                    command="tcheck roles set %s --tier balanced "
                                            "--mode inline --models <модель> "
                                            "--by <имя>" % owner))
    return issues


def _instruction_fallback(types, paths):
    """Инструкция типа без запасного пути для объявленной возможности."""
    issues = []
    for typedef in types.all():
        if not typedef.capabilities:
            continue
        path = os.path.join(paths["types"], typedef.id, "instruction.md")
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read().lower()
        if "запасн" not in text and "без возможности" not in text:
            issues.append(Issue("warning", "types/%s/instruction.md" % typedef.id,
                                "тип объявил возможности, а запасного пути в "
                                "инструкции нет", "CAPABILITY_UNBOUND",
                                command="tcheck types show %s" % typedef.id))
    return issues


def _long_reference(types, paths, queues):
    """Справочник длиннее порога настройки без оглавления с якорями."""
    issues = []
    threshold = 4000
    for queue in queues:
        threshold = int(queue.settings.get("toc_chars", 4000))
        break
    for typedef in types.all():
        folder = os.path.join(paths["types"], typedef.id, "references")
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".md"):
                continue
            path = os.path.join(folder, name)
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            if len(text) > threshold and not text.lstrip().startswith(("# Оглавление",
                                                                       "## Оглавление",
                                                                       "- [")):
                issues.append(Issue("warning", "types/%s/references/%s"
                                    % (typedef.id, name),
                                    "справочник длиннее %d знаков и не начинается "
                                    "оглавлением с якорями" % threshold,
                                    "PROSE_HIDDEN_TEXT",
                                    command="tcheck types show %s" % typedef.id))
    return issues


def _cli_selftest():
    """Каждая объявленная команда имеет обработчик, каждый флаг — справку."""
    from .check_cli import CheckCli
    from .queue_cli import QueueCli
    from .task_cli import TaskCli
    issues = []
    for klass in (QueueCli, TaskCli, CheckCli):
        cli = klass(root=os.getcwd())
        for command in klass.commands:
            handler = getattr(cli, "cmd_%s" % command.name.replace("-", "_"), None)
            if handler is None:
                issues.append(Issue("error", "%s %s" % (klass.entry, command.name),
                                    "у объявленной команды нет обработчика",
                                    "NOT_IMPLEMENTED"))
            if not command.summary:
                issues.append(Issue("error", "%s %s" % (klass.entry, command.name),
                                    "у команды нет назначения", "EMPTY"))
            for flag in command.flags:
                _check_declared_flag(klass.entry, command.name, flag, issues)
            for action in command.nested:
                nested_handler = getattr(
                    cli, "_%s_%s" % (command.name.replace("-", "_"), action), None)
                if nested_handler is None:
                    issues.append(Issue(
                        "error", "%s %s %s" % (klass.entry, command.name, action),
                        "у вложенной команды нет обработчика", "NOT_IMPLEMENTED"))
                for flag in cli.nested_flags(command.name, action):
                    _check_declared_flag("%s %s" % (klass.entry, command.name),
                                         action, flag, issues)
    return issues


def _check_declared_flag(entry, command, flag, issues):
    """У каждого объявленного локального флага есть имя и русская справка."""
    if isinstance(flag, tuple):
        name = flag[0]
        help_text = flag[2] if len(flag) > 2 else None
    else:
        name, help_text = str(flag), None
    if not name:
        issues.append(Issue("error", "%s %s" % (entry, command),
                            "флаг без имени", "EMPTY"))
    if name.startswith("--") and not help_text:
        issues.append(Issue("error", "%s %s %s" % (entry, command, name),
                            "у флага нет справки", "EMPTY"))

def _prose_selftest(skill_root):
    """Невидимые вставки в прозе поставки."""
    doctor = Doctor(prose_roots=[skill_root])
    return doctor.prose_issues()


def _command_count():
    from .check_cli import CheckCli
    from .queue_cli import QueueCli
    from .task_cli import TaskCli
    return sum(len(k.commands) for k in (QueueCli, TaskCli, CheckCli))


#: Контракт схемы данными: имя схемы — её ключи.
SCHEMAS = {
    "AGGREGATE": __import__("tdcore.aggregate", fromlist=["AGGREGATE_KEYS"]).AGGREGATE_KEYS,
    "JIRA_MIRROR": __import__("tdcore.importer", fromlist=["JIRA_MIRROR_KEYS"]).JIRA_MIRROR_KEYS,
    "AUTODOC_BUNDLE": tuple(schema_contract_payload("AUTODOC_BUNDLE")["keys"]),
    "AUTODOC_ENTITY": tuple(schema_contract_payload("AUTODOC_ENTITY")["keys"]),
    "AUTODOC_RELATION": tuple(schema_contract_payload("AUTODOC_RELATION")["keys"]),
    "AUTODOC_SOURCE": tuple(schema_contract_payload("AUTODOC_SOURCE")["keys"]),
    "AUTODOC_DIAGRAM": tuple(schema_contract_payload("AUTODOC_DIAGRAM")["keys"]),
    "AUTODOC_AUDIT": tuple(schema_contract_payload("AUTODOC_AUDIT")["keys"]),
    "AUTODOC_HTML": tuple(schema_contract_payload("AUTODOC_HTML")["keys"]),
    "AUTODOC_RECONSTRUCTION": tuple(schema_contract_payload("AUTODOC_RECONSTRUCTION")["keys"]),
    "AUTODOC_AUDIT_PACKET": tuple(schema_contract_payload("AUTODOC_AUDIT_PACKET")["keys"]),
    "AUTODOC_MARKDOWN": tuple(schema_contract_payload("AUTODOC_MARKDOWN")["keys"]),
    "AUTODOC_PREZA_MIGRATION": tuple(schema_contract_payload("AUTODOC_PREZA_MIGRATION")["keys"]),
    "PREZA_PARITY": tuple(schema_contract_payload("PREZA_PARITY")["keys"]),
    "INTAKE": __import__("tdcore.intake", fromlist=["INTAKE_KEYS"]).INTAKE_KEYS,
    "TASK_AUDIT": __import__("tdcore.intake", fromlist=["AUDIT_KEYS"]).AUDIT_KEYS,
    "DOC_PATH": DOC_PATH_KEYS,
    "TASK": schema.TASK_KEYS,
    "INDEX": schema.INDEX_ITEM_KEYS,
    "TYPE": tuple(schema.TYPE_KEYS) + tuple(schema.TYPE_PLUGIN_KEYS),
    "FIELD": schema.FIELD_KEYS,
    "REF": schema.REF_KEYS,
    "ARTEFACT": schema.ARTEFACT_KEYS,
    "SOURCE": schema.SRC_KEYS,
    "COMMENT": schema.COMMENT_KEYS,
    "REPORT": schema.REPORT_KEYS,
    "CHECK": schema.CHECK_KEYS,
    "CODE": schema.CODE_KEYS,
    "FLOW": schema.FLOW_KEYS,
    "STEP": schema.STEP_KEYS,
    "TOOL": schema.TOOL_KEYS,
    "ROLE": schema.ROLE_KEYS,
    "AGENT": schema.AGENT_KEYS,
    "RETURN_CONTRACT": schema.RETURN_CONTRACT_KEYS,
    "SETTINGS": schema.SETTINGS_KEYS,
    "STATUSES": schema.STATUSES,
    "REF_KINDS": schema.REF_KINDS,
    "ARTEFACT_KINDS": schema.ARTEFACT_KINDS,
    "COMMENT_KINDS": schema.COMMENT_KINDS,
    "SRC_SYSTEMS": schema.SRC_SYSTEMS,
    "CAPABILITIES": schema.CAPABILITIES,
    "TIERS": schema.TIERS,
    "MODES": schema.MODES,
    "READ_MODES": __import__("tdcore.report", fromlist=["READ_MODES"]).READ_MODES,
    "FLOW_CHOICE": schema.FLOW_CHOICE_KEYS,
    "FLOW_STEP_CONTROL": schema.FLOW_STEP_CONTROL_KEYS,
    "FLOW_TRANSITION": schema.FLOW_TRANSITION_KEYS,
    "DOC_POLICY": schema.DOC_POLICY_KEYS,
    "DOC_MODULE": schema.DOC_MODULE_KEYS,
    "DOC_IMPACT": schema.DOC_IMPACT_KEYS,
    "FLOW_DOC": schema.FLOW_DOC_KEYS,
    "DOC_CAPTURE": schema.DOC_CAPTURE_KEYS,
    "DOC_MACHINE": schema.DOC_MACHINE_KEYS,
    "DOC_CLAIM": schema.DOC_CLAIM_KEYS,
    "DOC_PACKET": schema.DOC_PACKET_KEYS,
    "DOC_QUERY": schema.DOC_QUERY_KEYS,
    "DOC_WRITER": schema.DOC_WRITER_KEYS,
}


#: Флаги вложенных команд контроля.
NESTED_FLAGS = {
    ("types", "list"): [],
    ("types", "show"): [("name", None, "имя типа")],
    ("types", "fields"): [("name", None, "имя типа")],
    ("flows", "list"): [],
    ("flows", "show"): [("name", None, "имя потока")],
    ("docs", "init"): [("--workspace-id", None, "stable workspace id"),
                         ("--product-id", None, "product id"),
                         ("--docs-path", None, "workspace write path relative to --root")],
    ("docs", "catalog"): [("--release", None, "release scope"),
                            ("--docs-path", None, "workspace write path relative to --root")],
    ("docs", "show"): [("--key", None, "doc_key"),
                        ("--revision", int, "revision number"),
                        ("--docs-path", None, "workspace write path relative to --root")],
    ("docs", "resolve"): [("--mode", None, "catalog, module, machine, impact, for-task, path, test-map, reconstruct"),
                           ("--key", None, "doc_key"),
                           ("--task-ref", None, "namespaced task ref; repeatable"),
                           ("--file", None, "source file; repeatable"),
                           ("--release", None, "release scope"),
                           ("--chars", int, "bounded chars"),
                           ("--docs-path", None, "workspace write path relative to --root")],
    ("docs", "check"): [("--strict", bool, "warnings as errors"),
                           ("--docs-path", None, "workspace write path relative to --root")],
    ("docs", "stale"): [("--docs-path", None, "workspace write path relative to --root")],
    ("docs", "render"): [("--key", None, "doc_key"),
                          ("--docs-path", None, "workspace write path relative to --root")],
    ("docs", "policy_show"): [("--scope", None, "workspace, flow, task, change" ),
                                ("--docs-path", None, "workspace write path relative to --root")],
    ("docs", "policy_set"): [("--automation", None, "ask, always, manual, disabled"),
                              ("--enforcement", None, "advisory, required, critical"),
                              ("--cadence", None, "slice, aggregate, both, explicit"),
                              ("--update-after", None, "implementation, slice_tests, all_tests, explicit_command"),
                              ("--verify", None, "on_update, after_final_tests, on_close"),
                              ("--scope", None, "workspace, flow, task, change"),
                              ("--scope-ref", None, "identifier for non-workspace scope"),
                              ("--confirm", bool, "explicit approval for workspace disable"),
                              ("--reason", None, "policy decision reason"),
                              ("--docs-path", None, "workspace write path relative to --root")],
    ("aggregate", "scan"): [("--archive", bool, "archive source files in immutable snapshot")],
    ("aggregate", "status"): [],
    ("aggregate", "list"): [("--kind", None, "tasks, documents, workspaces, queues, entities, relations, warnings"),
                              ("--workspace", None, "workspace_id")],
    ("aggregate", "show"): [("ref", None, "global workspace/task/document reference")],
    ("aggregate", "diff"): [("--from-run", None, "older aggregate_run_id"),
                              ("--to-run", None, "newer aggregate_run_id")],
    ("aggregate", "rebuild"): [("--run-id", None, "snapshot run to rebuild")],
    ("aggregate", "verify"): [],
    ("aggregate", "export"): [("--output", None, "deterministic JSON bundle path")],
    ("autodoc", "discover"): [("--legacy-root", None, "legacy preza root"),
                                ("--include", None, "comma-separated source prefixes"),
                                ("--exclude", None, "comma-separated source prefixes")],
    ("autodoc", "bundle"): [("--bundle", None, "AUTODOC-BUNDLE-1 output path"),
                              ("--archive", bool, "embed approved binary source bytes"),
                              ("--redact", bool, "redact policy-selected source content"),
                              ("--legacy-root", None, "legacy preza root"),
                              ("--include", None, "comma-separated source prefixes"),
                              ("--exclude", None, "comma-separated source prefixes")],
    ("autodoc", "render"): [("--bundle", None, "AUTODOC-BUNDLE-1 input path"),
                              ("--html", None, "offline HTML output directory")],
    ("autodoc", "diagram"): [("--bundle", None, "AUTODOC-BUNDLE-1 input path"),
                               ("--html", None, "offline diagram output directory")],
    ("autodoc", "audit"): [("--bundle", None, "AUTODOC-BUNDLE-1 input path"),
                            ("--output", None, "AUTODOC-AUDIT-1 output path"),
                            ("--agent", bool, "write bounded read-only audit packet"),
                            ("--limit", int, "bounded finding/entity count")],
    ("autodoc", "verify"): [("--bundle", None, "AUTODOC-BUNDLE-1 input path"),
                             ("--html", None, "offline HTML output directory")],
    ("autodoc", "reconstruct"): [("--bundle", None, "AUTODOC-BUNDLE-1 input path"),
                                   ("--target", None, "fresh target root; --root is also accepted"),
                                   ("--force", bool, "replace an explicitly declared target")],
    ("autodoc", "generate"): [("--bundle", None, "AUTODOC-BUNDLE-1 output path"),
                               ("--html", None, "offline HTML output directory"),
                               ("--archive", bool, "embed approved binary source bytes"),
                               ("--redact", bool, "redact policy-selected source content"),
                               ("--audit", bool, "write deterministic audit report"),
                               ("--augment-md", bool, "совместимый алиас: поддерживать Mermaid source blocks в Markdown"),
                               ("--no-augment-md", bool, "не изменять Markdown; только собрать производный HTML"),
                               ("--agent", bool, "write bounded read-only audit packet"),
                               ("--legacy-root", None, "legacy preza root"),
                               ("--include", None, "comma-separated source prefixes"),
                               ("--exclude", None, "comma-separated source prefixes"),
                               ("--output", None, "audit report path")],
    ("roles", "list"): [],
    ("roles", "show"): [("name", None, "имя роли")],
    ("roles", "set"): [("name", None, "имя роли"),
                       ("--tier", None,
                        "уровень модели: %s" % ", ".join(schema.TIERS)),
                       ("--mode", None,
                        "режим исполнения: %s" % ", ".join(schema.MODES)),
                       ("--tools", None, "набор инструментов строкой"),
                       ("--models", None, "модели через запятую")],
    ("roles", "unset"): [("name", None, "имя роли")],
    ("tools", "list"): [],
    ("tools", "bind"): [("capability", None,
                         "возможность: %s" % ", ".join(schema.CAPABILITIES)),
                        ("--command", None,
                         "команда или сервер, которыми возможность доступна"),
                        ("--note", None, "как пользоваться и где границы")],
    ("tools", "unbind"): [("capability", None, "возможность")],
    ("import", "jira"): [("--file", None, "дословный файл выгрузки Jira"),
                           ("--id", None, "идентификатор задачи Jira"),
                           ("--title", None, "заголовок, если файл его не содержит")],
    ("import", "openspec"): [("--file", None, "дословный файл OpenSpec"),
                              ("--id", None, "идентификатор изменения"),
                              ("--title", None, "заголовок, если файл его не содержит")],
    ("import", "speckit"): [("--file", None, "дословный файл Spec Kit"),
                             ("--id", None, "идентификатор спецификации"),
                             ("--title", None, "заголовок, если файл его не содержит")],
    ("intake", "start"): [("--title", None, "краткое название постановки"),
                           ("--session", None, "стабильный session id"),
                           ("--persist", bool, "явно создать draft task в очереди")],
    ("intake", "list"): [],
    ("intake", "show"): [("--session", None, "intake session id")],
    ("intake", "capture"): [("--session", None, "intake session id"),
                              ("--text", None, "текст входа"),
                              ("--file", None, "файл или screenshot с provenance"),
                              ("--source", None, "source reference сообщения/ссылки"),
                              ("--source-kind", None, "message, file, screenshot, url, task, document"),
                              ("--status", None, "observed, requested, proposed, accepted, unknown")],
    ("intake", "ask"): [("--session", None, "intake session id"),
                         ("--question", None, "один вопрос"),
                         ("--text", None, "алиас текста вопроса"),
                         ("--choices", None, "choices через запятую"),
                         ("--default", None, "default из choices"),
                         ("--on-decline", None, "ветка отказа из flow definition"),
                         ("--on-disabled", None, "ветка disabled из flow definition")],
    ("intake", "answer"): [("--session", None, "intake session id"),
                            ("--question-id", None, "id открытого вопроса"),
                            ("--value", None, "ответ пользователя"),
                            ("--disabled", bool, "явно отключённый optional step")],
    ("intake", "fix"): [("--session", None, "intake session id"),
                         ("--text", None, "подтверждённый факт"),
                         ("--source", None, "provenance reference"),
                         ("--source-kind", None, "message, file, screenshot, url, task, document")],
    ("intake", "validate"): [("--session", None, "intake session id")],
    ("intake", "finalize"): [("--session", None, "intake session id"),
                              ("--title", None, "заголовок typed task"),
                              ("--type", None, "тип typed task"),
                              ("--problem", None, "проблема"),
                              ("--goals", None, "цели; повторяется"),
                              ("--acceptance", None, "критерии; повторяется"),
                              ("--in-scope", None, "границы; повторяется"),
                              ("--out-of-scope", None, "вне границ; повторяется"),
                              ("--context", None, "контекст; повторяется"),
                              ("--files-hint", None, "файл/символ; повторяется"),
                              ("--steps", None, "шаг; повторяется"),
                              ("--verify", None, "проверка; повторяется"),
                              ("--open-questions", None, "remaining question; повторяется"),
                              ("--change-kind", None, "вид изменения"),
                              ("--allow-open", bool, "явно принять remaining risks/questions")],
    ("intake", "audit"): [("--session", None, "intake session id"),
                           ("--task", None, "целевая task id")],
    ("intake", "cancel"): [("--session", None, "intake session id")],
}

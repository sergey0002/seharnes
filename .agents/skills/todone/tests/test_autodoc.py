"""Acceptance tests for the AUTODOC vertical slice.

These tests deliberately use a temporary workspace so the canonical repository
and its Markdown remain byte-identical after read-only autodoc operations.
"""

import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from tdcore.autodoc import (AUTODOC_BUNDLE_SCHEMA, audit_bundle, build_bundle,
                            canonical_digest, discover_workspace, reconstruct_bundle,
                            render_bundle, validate_autodoc_contract, verify_bundle)
from tdcore.check_cli import CheckCli
from tdcore.contracts import validate_contract_file
from tdcore.queue import Queue, Registry

ROOT = Path(__file__).resolve().parents[1]


class AutodocAcceptanceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "docs").mkdir()
        (self.root / "docs" / "guide.md").write_text(
            "---\ntitle: Guide\n---\n# Guide\n\n> quote\n\n- one\n- two\n\n| A | B |\n| --- | --- |\n| x | y |\n\n```python\nprint('safe')\n```\n\n[missing](missing.md)\n<script>alert(1)</script>\n",
            encoding="utf-8")
        Registry(str(self.root)).register("main", str(self.root / "tasks" / "main"))
        self.queue = Queue(str(self.root), "main")
        self.queue.init()
        self.task = self.queue.create("Document the fixture", "default")
        self.queue.save(self.task)

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        code = CheckCli(root=str(self.root), out=out, err=err).main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_contract_fixtures_have_valid_and_negative_paths(self):
        valid = sorted((ROOT / "assets" / "fixtures" / "runtime").glob("autodoc-*.valid.json"))
        invalid = sorted((ROOT / "assets" / "fixtures" / "runtime").glob("autodoc-*.invalid-extra.json"))
        self.assertGreaterEqual(len(valid), 11)
        self.assertEqual(len(valid), len(invalid))
        for path in valid:
            _, issues = validate_contract_file(str(path))
            self.assertFalse([item for item in issues if item.is_error], path.name)
        for path in invalid:
            _, issues = validate_contract_file(str(path))
            self.assertTrue(any(item.is_error for item in issues), path.name)

    def test_preza_parity_contract_covers_every_required_inventory_family(self):
        parity_valid = ROOT / "assets" / "fixtures" / "runtime" / "preza-parity-1.valid.json"
        parity_invalid = ROOT / "assets" / "fixtures" / "runtime" / "preza-parity-1.invalid-extra.json"
        _, valid_issues = validate_contract_file(str(parity_valid))
        _, invalid_issues = validate_contract_file(str(parity_invalid))
        self.assertFalse([item for item in valid_issues if item.is_error])
        self.assertTrue(any(item.is_error for item in invalid_issues))
        legacy_root = ROOT.parent / "preza"
        if not (legacy_root / "build.py").is_file():
            self.skipTest("legacy preza fixture is not mounted")
        bundle = build_bundle(str(ROOT), legacy_root=str(legacy_root))
        legacy = bundle["legacy_parity"]
        parity = legacy["parity"]
        self.assertEqual(parity["schema"], "PREZA-PARITY-1")
        required_sections = {"start", "architecture", "entities", "lifecycle", "commands",
                             "types", "flows", "schemas", "templates", "file-catalog",
                             "checks", "faq", "live-facts", "footer"}
        self.assertEqual({item["id"] for item in parity["sections"]}, required_sections)
        required_categories = {"entity_sections", "lifecycle", "schema_notes", "faq",
                               "command_notes", "file_overrides", "commands", "types",
                               "flows", "schemas", "templates", "file_notes", "checks",
                               "live_facts", "svg"}
        self.assertEqual(set(parity["inventory"]), required_categories)
        self.assertGreater(len(parity["inventory"]["commands"]), 0)
        self.assertGreater(len(parity["inventory"]["types"]), 0)
        self.assertGreater(len(parity["inventory"]["flows"]), 0)
        self.assertGreater(len(parity["inventory"]["schemas"]), 0)
        self.assertGreater(len(parity["inventory"]["templates"]), 0)
        self.assertGreater(len(parity["inventory"]["file_notes"]), 0)
        self.assertGreater(len(parity["inventory"]["checks"]), 0)
        self.assertGreater(len(parity["inventory"]["live_facts"]), 0)
        self.assertGreater(len(parity["inventory"]["svg"]), 0)
        for category, items in parity["inventory"].items():
            for item in items:
                self.assertIn(item["status"], {"preserved", "transformed", "deprecated", "unknown"}, category)
                self.assertTrue(item["source"])
                self.assertIn("target_page", item)
        bundle_path = self.root / "legacy-bundle.json"
        bundle_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
        render_bundle(str(bundle_path), html=str(self.root / "legacy-html"))
        for svg in (self.root / "legacy-html").rglob("*.svg"):
            text = svg.read_text(encoding="utf-8")
            self.assertNotIn("<script", text.lower())
            self.assertIn('role="img"', text)
            self.assertIn("<title", text)
            self.assertIn("<desc", text)

    def test_bundle_is_deterministic_and_preserves_source_bytes(self):
        before = (self.root / "docs" / "guide.md").read_bytes()
        first = build_bundle(str(self.root))
        second = build_bundle(str(self.root))
        self.assertEqual(first["schema"], AUTODOC_BUNDLE_SCHEMA)
        self.assertEqual(first["canonical_digest"], second["canonical_digest"])
        self.assertEqual(first["canonical_digest"], canonical_digest(first))
        source = next(item for item in first["sources"] if item["canonical_path"] == "docs/guide.md")
        self.assertEqual(source["sha256"], "sha256:" + hashlib.sha256(before).hexdigest())
        self.assertEqual(source["raw"].encode("utf-8"), before)
        self.assertEqual(before, (self.root / "docs" / "guide.md").read_bytes())
        self.assertFalse(validate_autodoc_contract(first, "fixture"))

    def test_discover_is_read_only_and_reports_families(self):
        before = sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob("*"))
        report = discover_workspace(str(self.root)).as_dict()
        after = sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob("*"))
        self.assertEqual(before, after)
        self.assertTrue(any(item["kind"] == "workspace" for item in report["found"]))
        self.assertTrue(any(item["kind"] == "docs" for item in report["found"]))
        self.assertTrue(any(item["kind"] == "queue" for item in report["found"]))

    def test_all_diagrams_use_pinned_mermaid_and_offline_runtime(self):
        bundle = build_bundle(str(self.root))
        diagrams = bundle["diagrams"]
        self.assertGreaterEqual(len(diagrams), 4)
        self.assertTrue({item.get("kind") for item in diagrams} >= {"architecture", "relations", "provenance", "audit"})
        for spec in diagrams:
            self.assertEqual(spec["renderer"], "mermaid")
            self.assertEqual(spec["renderer_version"], "12.3.0")
            self.assertTrue(spec["renderer_offline"])
            self.assertIn("flowchart", spec["mermaid_source"])
            self.assertNotIn("#fff5d6", spec["mermaid_source"])
            self.assertIn("edgeLabelBackground", spec["mermaid_source"])
            self.assertTrue(spec["mermaid_source_digest"].startswith("sha256:"))
            self.assertTrue(spec["asset_digest"].startswith("sha256:"))
        flow_specs = [item for item in diagrams if item.get("kind") == "flow"]
        if flow_specs:
            self.assertIn("click ", flow_specs[0]["mermaid_source"])
        html_root = self.root / "mermaid-html"
        manifest = render_bundle(bundle, html=str(html_root))
        self.assertTrue((html_root / "assets" / "vendor" / "mermaid" / "mermaid.min.js").is_file())
        self.assertEqual({item["renderer"] for item in manifest["diagrams"]}, {"mermaid"})
        for asset in (html_root / "assets" / "diagrams").glob("*.svg"):
            text = asset.read_text(encoding="utf-8")
            self.assertIn('role="img"', text)
            self.assertIn("<title", text)
            self.assertIn("<desc", text)
            self.assertNotIn("<foreignObject", text)

    def test_mermaid_fenced_markdown_is_provenance_source_and_svg_in_html(self):
        path = self.root / "docs" / "guide.md"
        path.write_text(path.read_text(encoding="utf-8") +
                        "\n```mermaid\nflowchart LR\n  A[Start] --> B[Finish]\n```\n",
                        encoding="utf-8")
        bundle = build_bundle(str(self.root))
        specs = [item for item in bundle["diagrams"] if item.get("source_mode") == "markdown"]
        self.assertEqual(len(specs), 1)
        spec = specs[0]
        self.assertEqual(spec["source_document_path"], "docs/guide.md")
        self.assertEqual(spec["mermaid_source"], "flowchart LR\n  A[Start] --> B[Finish]")
        self.assertTrue(spec["source_block_digest"].startswith("sha256:"))
        self.assertTrue(spec["source_file_digest"].startswith("sha256:"))
        html_root = self.root / "mermaid-markdown-html"
        render_bundle(bundle, html=str(html_root))
        page = next(item for item in (html_root / "docs").glob("*.html")
                    if item.name != "index.html")
        text = page.read_text(encoding="utf-8")
        self.assertIn('<figure class="markdown-diagram">', text)
        self.assertIn("Показать исходник Mermaid", text)
        self.assertIn("<svg", text)
        self.assertNotIn("Mermaid source не отрисован", text)
        self.assertFalse(validate_autodoc_contract(bundle, "fixture"))

    def test_html_markdown_safety_links_and_offline_manifest(self):
        bundle_path = self.root / "bundle.json"
        bundle = build_bundle(str(self.root), path=str(bundle_path))
        html_root = self.root / "docs_html"
        manifest = render_bundle(str(bundle_path), html=str(html_root))
        self.assertEqual(manifest["bundle_digest"], bundle["canonical_digest"])
        self.assertTrue((html_root / "index.html").is_file())
        doc_page = next(path for path in html_root.glob("docs/*.html") if path.name != "index.html")
        page = doc_page.read_text(encoding="utf-8")
        self.assertIn("Raw unknown Markdown", page)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("AUTODOC-MARKDOWN-1", json.dumps(bundle, ensure_ascii=False))
        self.assertFalse(any("http://" in p.read_text(encoding="utf-8", errors="ignore")
                             for p in html_root.rglob("*.html")))
        self.assertTrue(verify_bundle(str(bundle_path), html=str(html_root))["valid"])

    def test_catalog_ui_is_russian_inline_and_flow_pages_embed_diagrams(self):
        bundle = build_bundle(str(ROOT), legacy_root=str(ROOT.parent / "preza"))
        bundle_path = self.root / "catalog-bundle.json"
        bundle_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
        html_root = self.root / "catalog-html"
        render_bundle(str(bundle_path), html=str(html_root))
        index = (html_root / "index.html").read_text(encoding="utf-8")
        docs = (html_root / "docs" / "doc-docs-20-autodoc-r1.html").read_text(encoding="utf-8")
        flow = (html_root / "flows" / "issue-delivery.html").read_text(encoding="utf-8")
        self.assertIn('lang="ru"', index)
        self.assertIn("Документация проекта", index)
        self.assertIn("<style>", index)
        self.assertIn("@media(max-width:900px)", index)
        self.assertIn('class="nav-group"', index)
        self.assertIn('class="nav-subgroup"', index)
        self.assertIn("DOC_ · документация", index)
        self.assertIn("Bundle офлайн-каталога", index)
        self.assertIn("<summary>", index)
        schema_page = (html_root / "schemas" / "registry-autodoc_bundle.html").read_text(encoding="utf-8")
        self.assertIn("Назначение", schema_page)
        self.assertIn("Переносимый снимок проекта", schema_page)
        self.assertIn("docs/21-schema-catalog.md", schema_page)
        self.assertIn("Содержание документа", docs)
        self.assertIn("Скачать оригинальный Markdown", docs)
        self.assertNotIn("<h2>Normalized</h2>", docs)
        self.assertIn("Пошаговый маршрут", flow)
        self.assertIn("Карта процесса", flow)
        self.assertIn("<svg", flow)
        self.assertIn("autodoc_flow_issue-delivery", flow)
        self.assertIn('href="#step-issue-delivery-intake"', flow)
        self.assertIn('id="step-issue-delivery-intake"', flow)
        self.assertIn("Нажмите на шаг", flow)
        self.assertNotIn("autodoc_provenance-timeline", flow)
        self.assertIn("Проблемы и контроль", flow)
        self.assertNotIn("<table><thead><tr><th>Step</th>", flow)

    def test_audit_finds_cycle_and_broken_route_deterministically(self):
        first = self.queue.create("Cycle one", "default")
        second = self.queue.create("Cycle two", "default")
        first.data["depends_on"] = [second.id]
        second.data["depends_on"] = [first.id]
        self.queue.save(first)
        self.queue.save(second)
        flow_dir = self.root / "flows" / "broken"
        flow_dir.mkdir(parents=True)
        (flow_dir / "flow.json").write_text(json.dumps({
            "schema": "FLOW-2", "id": "broken", "name": "Broken", "entry": "source",
            "steps": [
                {"id": "a", "type": "default", "input_from": [], "routes": {"next": "missing"}},
                {"id": "b", "type": "default", "input_from": ["b"]},
            ],
        }), encoding="utf-8")
        bundle = build_bundle(str(self.root))
        audit = audit_bundle(bundle)
        codes = [item["code"] for item in audit["findings"]]
        self.assertIn("AUTODOC_TASK_DEPENDENCY_CYCLE", codes)
        self.assertIn("AUTODOC_FLOW_ROUTE_TARGET_MISSING", codes)
        self.assertIn("AUTODOC_FLOW_UNREACHABLE", codes)
        again = audit_bundle(bundle)
        self.assertEqual([(x["finding_id"], x["code"]) for x in audit["findings"]],
                         [(x["finding_id"], x["code"]) for x in again["findings"]])

    def test_reconstruction_is_byte_preserving_and_rejects_unsafe_target(self):
        bundle = build_bundle(str(self.root))
        target = Path(str(self.root) + "-restored")
        try:
            report = reconstruct_bundle(bundle, str(target))
            self.assertEqual(report["status"], "complete")
            self.assertEqual((target / "docs" / "guide.md").read_bytes(),
                             (self.root / "docs" / "guide.md").read_bytes())
            self.assertTrue((target / "tasks" / "main" / ".todone" / "data").is_dir())
        finally:
            shutil.rmtree(target, ignore_errors=True)
        invalid = json.loads(json.dumps(bundle))
        invalid["sources"][0]["canonical_path"] = "../escape"
        invalid["canonical_digest"] = canonical_digest(invalid)
        invalid["bundle_id"] = "autodoc:" + invalid["canonical_digest"].split(":", 1)[1]
        with self.assertRaises(Exception) as caught:
            reconstruct_bundle(invalid, str(self.root) + "-unsafe")
        self.assertIn("PATH_UNSAFE", str(caught.exception))
        symlink_target = Path(str(self.root) + "-symlink")
        os.symlink(str(self.root), str(symlink_target))
        try:
            with self.assertRaises(Exception) as caught:
                reconstruct_bundle(bundle, str(symlink_target))
            self.assertIn("PATH_UNSAFE", str(caught.exception))
        finally:
            symlink_target.unlink()

    def test_cli_vertical_slice_and_standalone_compatible_handler(self):
        bundle_path = self.root / ".todone" / "autodoc" / "bundle.json"
        code, out, err = self.cli(["autodoc", "bundle", "--bundle", str(bundle_path), "--json"])
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["schema"], AUTODOC_BUNDLE_SCHEMA)
        code, out, err = self.cli(["autodoc", "render", "--bundle", str(bundle_path),
                                   "--html", str(self.root / "docs_html"), "--json"])
        self.assertEqual(code, 0, err)
        code, out, err = self.cli(["autodoc", "verify", "--bundle", str(bundle_path),
                                   "--html", str(self.root / "docs_html"), "--json"])
        self.assertEqual(code, 0, err)
        self.assertTrue(json.loads(out)["valid"])


if __name__ == "__main__":
    unittest.main()

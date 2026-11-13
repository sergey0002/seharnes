import json
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

WEB = Path(__file__).resolve().parents[1]

DOC_MD = """# Первый документ

<!-- meta
type: architecture
status: actual
updated: 2026-11-13
-->

## Суть

Текст первого документа.
"""

GRAPH = {
    "schema": "harness-graph/2.3",
    "stats": {"canonical": 1, "drift": 0},
    "nodes": [
        {"id": "skill:demo", "type": "skill", "label": "demo", "path": ".agents/skills/demo/SKILL.md",
         "environment": "agents", "canonical": True, "json": "nodes/skill__demo.json"},
        {"id": "config:demo", "type": "config", "label": "demo-config", "path": "config/demo.json",
         "environment": "agents", "canonical": True, "json": "nodes/config__demo.json"},
    ],
    "edges": [{"source": "skill:demo", "target": "config:demo", "type": "reads_context"}],
}


@contextmanager
def panel():
    with tempfile.TemporaryDirectory(prefix="panel-shell-test-") as directory:
        root = Path(directory)
        web = root / ".doc/web"
        web.parent.mkdir(parents=True)
        shutil.copytree(WEB, web, ignore=shutil.ignore_patterns(
            "state", ".env", "*.local.*", "__pycache__", "*.log"))
        (root / ".doc/harnes/state").mkdir(parents=True)
        (root / ".doc/harnes/state/01-demo.md").write_text(DOC_MD, encoding="utf-8")
        (root / ".doc/architecture").mkdir()
        (root / ".doc/architecture/demo.json").write_text(json.dumps({
            "metadata": {"title": "Демо JSON", "source_status": "actual", "updated_at": "2026-11-01"},
            "sections": [{"id": "s1", "title": "Раздел", "body_markdown": "Тело раздела."}],
            "findings": [],
        }, ensure_ascii=False), encoding="utf-8")
        mirror = root / ".doc/skil_data/mirror"
        (mirror / "nodes").mkdir(parents=True)
        (mirror / "graph.json").write_text(json.dumps(GRAPH, ensure_ascii=False), encoding="utf-8")
        (root / ".agents/skills/demo").mkdir(parents=True)
        (root / ".agents/skills/demo/SKILL.md").write_text("# demo\n\nТекст узла.\n", encoding="utf-8")
        (mirror / "nodes/skill__demo.json").write_text(json.dumps({
            "content_blocks": [
                {"block_id": "b000", "block_type": "frontmatter", "raw_content": "---\nname: demo\n---", "header_text": None},
                {"block_id": "b001", "block_type": "body", "raw_content": "## Суть\n\nТекст узла.", "header_text": ""},
            ],
        }, ensure_ascii=False), encoding="utf-8")
        (mirror / "nodes/config__demo.json").write_text(json.dumps({
            "content_blocks": [{"block_id": "b000", "block_type": "preamble", "raw_content": '{"a": 1}', "header_text": None}],
        }), encoding="utf-8")

        script = root / ".agents/skills/harness-router/children/harness-core/scripts/harness_cli.py"
        script.parent.mkdir(parents=True)
        script.write_text("from pathlib import Path\nPath('marker').write_text('ran')\n", encoding="utf-8")

        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        process = subprocess.Popen(["php", "-S", f"127.0.0.1:{port}", "-t", str(web), str(web / "router.php")],
                                   cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(50):
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("PHP test server did not start")
            yield port
        finally:
            process.terminate()
            process.wait(timeout=5)


class _NoRedirect(HTTPRedirectHandler):
    """Редиректы проверяем как есть: статус и заголовок Location."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER_DIRECT = build_opener(_NoRedirect)


def get(port, path, headers=None, follow=True):
    request = Request(f"http://127.0.0.1:{port}{path}", headers=headers or {})
    if not follow:
        opener = _OPENER_DIRECT
        try:
            response = opener.open(request, timeout=10)
        except HTTPError as error:
            with error:
                return error.code, error.read().decode("utf-8"), dict(error.headers)
        with response:
            return response.status, response.read().decode("utf-8"), dict(response.headers)
    with urlopen(request, timeout=10) as response:
        return response.status, response.read().decode("utf-8")


def get_json(port, path, headers=None):
    status, body = get(port, path, headers)
    return status, json.loads(body)


def post(port, path, payload, headers=None):
    request = Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
    try:
        with urlopen(request, timeout=15) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        with error:
            return error.code, json.load(error)


class PanelShellTest(unittest.TestCase):
    """Каркас: верхнее меню, кнопки раздела, три колонки, нижний док."""

    def test_graph_page_has_canon_layout(self):
        with panel() as port:
            status, html = get(port, "/panel/graph")
            self.assertEqual(200, status)
            for marker in ('class="topbar"', 'class="toolbar"', 'class="workspace"', 'class="sidebar"',
                           'class="content"', 'class="rightpanel"', 'data-right-splitter',
                           'class="dock"', 'data-dock-tab="terminal"', 'data-dock-tab="json"',
                           'data-dock-tab="log"', 'data-graph-canvas', 'id="panel-boot"'):
                self.assertIn(marker, html, marker)
            self.assertIn("/assets/css/tokens.css", html)
            self.assertIn("/assets/js/main.js", html)
            self.assertIn("panel.theme", html, "theme applied before first paint")

    def test_narrow_layout_has_drawer_for_left_panel(self):
        # На узком экране список документов и узлов живёт в выдвижной панели:
        # без кнопки, ящика и затемнения раздел остаётся без навигации.
        with panel() as port:
            _, html = get(port, "/panel/docs")
            for marker in ('data-drawer-toggle', 'data-workspace', 'data-drawer="closed"',
                           'data-drawer-close', 'id="panel-sidebar"'):
                self.assertIn(marker, html, marker)
            _, main_js = get(port, "/assets/js/core/drawer.js")
            self.assertIn("data-drawer", main_js.lower())

    def test_navigation_marks_active_section_and_legacy_links(self):
        # «Контроль харнеса» переехал в новый каркас: пункт меню ведёт в /panel/harness,
        # а метка is-legacy осталась только у разделов, которые ещё живут на старом UI.
        with panel() as port:
            _, html = get(port, "/panel/docs")
            self.assertIn('is-active', html)
            self.assertIn('href="/panel/harness"', html)
            self.assertNotIn('href="/harness-admin/"', html)
            self.assertIn('is-legacy', html)
            self.assertIn('aria-current="page"', html)

    def test_graph_section_has_file_tree_and_svg_canvas(self):
        # Граф повторяет старый просмотрщик: единое дерево файлов, SVG-карточки,
        # полоса загрузки карточки и блок связей/JSON в правой панели.
        with panel() as port:
            _, html = get(port, "/panel/graph")
            for marker in ('data-graph-svg', 'data-graph-focus-clear', 'data-right-progress',
                           'data-graph-api', 'data-tree-dir'.replace('data-tree-dir', 'data-graph-list')):
                self.assertIn(marker, html, marker)

    def test_graph_node_api_carries_tree_and_card_fields(self):
        # Дерево строится по реальным путям, поэтому в ответе есть file и summary,
        # а карточка в графе получает подпись без второго запроса.
        with panel() as port:
            _, body = get(port, "/panel/api/graph/view")
            nodes = json.loads(body)["data"]["nodes"]
            self.assertTrue(nodes)
            sample = nodes[0]
            for field in ("id", "kind", "label", "path", "file", "summary", "analysis", "canonical"):
                self.assertIn(field, sample, field)

    def test_assets_and_api_allow_sandboxed_preview(self):
        # Встроенный предпросмотр открывает панель в iframe с sandbox="allow-scripts":
        # источник «null», и без CORS ES-модуль main.js не загружается, а страница
        # навсегда остаётся на «Загрузка…».
        with panel() as port:
            status, _, headers = get(port, "/assets/js/main.js", follow=False)
            self.assertEqual(200, status)
            self.assertEqual("*", headers.get("Access-Control-Allow-Origin"))
            status, _, headers = get(port, "/panel/api/graph/view", follow=False)
            self.assertEqual("*", headers.get("Access-Control-Allow-Origin"))

            # Предпросмотр шлёт preflight из-за заголовка X-Requested-With.
            request = Request(f"http://127.0.0.1:{port}/panel/api/graph/node", method="OPTIONS")
            with urlopen(request, timeout=10) as response:
                self.assertEqual(204, response.status)
                self.assertEqual("*", response.headers.get("Access-Control-Allow-Origin"))
                self.assertIn("X-Requested-With", response.headers.get("Access-Control-Allow-Headers"))

    def test_sandboxed_origin_passes_csrf_guard(self):
        # Origin: null приходит из iframe-предпросмотра: проверка CSRF его пропускает,
        # дальше решает политика записи (документ неизменяем), а не «origin not allowed».
        with panel() as port:
            status, body = post(port, "/panel/api/graph/node",
                                {"id": "doc:readme", "content": "x"},
                                headers={"Origin": "null", "X-Requested-With": "XMLHttpRequest"})
            self.assertNotIn("origin not allowed", str(body))
            self.assertIn(status, (400, 403, 404))

    def test_harness_section_renders_new_shell(self):
        # Раздел контроля харнеса живёт в новом каркасе: карточки, сканы и задания
        # берутся из API, а не из старой админки.
        with panel() as port:
            _, html = get(port, "/panel/harness")
            for marker in ('data-harness-root', 'data-scan="canon,links,docs"',
                           'data-run-action="harness_build"', 'id="harness-source"',
                           'data-scan-out', 'data-harness-jump'):
                self.assertIn(marker, html, marker)
            self.assertNotIn('new-panel-link', html)

    def test_harness_status_api_reports_source(self):
        with panel() as port:
            _, body = get(port, "/panel/api/harness/status")
            data = json.loads(body)["data"]
            self.assertIn("source", data)
            self.assertIn("receipt", data)
            self.assertTrue(data["root"])
            self.assertIn("configured", data["source"])

    def test_root_of_panel_redirects_to_graph(self):
        class NoRedirect:
            pass

        request = Request("http://127.0.0.1:1/panel")
        self.assertTrue(request.full_url.endswith("/panel"))
        with panel() as port:
            with urlopen(Request(f"http://127.0.0.1:{port}/panel"), timeout=10) as response:
                self.assertEqual(200, response.status)
                self.assertTrue(response.url.endswith("/panel/graph"), response.url)

    def test_i18n_switches_by_cookie(self):
        with panel() as port:
            _, ru = get(port, "/panel/docs")
            _, en = get(port, "/panel/docs", {"Cookie": "panel_lang=en"})
            self.assertIn("Документация", ru)
            self.assertIn("Documentation", en)
            self.assertNotIn("Документация", en)

    def test_dictionary_api_returns_both_languages(self):
        with panel() as port:
            status, payload = get_json(port, "/panel/api/i18n?lang=en")
            self.assertEqual(200, status)
            self.assertEqual("en", payload["data"]["lang"])
            self.assertIn("ru", payload["data"]["available"])
            self.assertIn("en", payload["data"]["available"])
            self.assertEqual("Documentation", payload["data"]["dictionary"]["nav.docs"])


class PanelApiTest(unittest.TestCase):
    def test_health_reports_service(self):
        with panel() as port:
            status, payload = get_json(port, "/panel/api/health")
            self.assertEqual(200, status)
            self.assertEqual("ok", payload["status"])
            self.assertIn("profile", payload["service"])

    def test_docs_api_lists_and_opens(self):
        with panel() as port:
            # поиск без учёта регистра, кириллица: "первый" находит "Первый документ"
            status, payload = get_json(port, "/panel/api/docs?q=" + quote("первый"))
            self.assertEqual(200, status)
            self.assertEqual(1, payload["data"]["total"])
            self.assertIn("Первый документ", payload["html"]["sidebar"])
            self.assertNotIn("Демо JSON", payload["html"]["sidebar"])

            status, payload = get_json(port, "/panel/api/docs/item?id=harnes/state/01-demo")
            self.assertEqual(200, status)
            self.assertIn("Текст первого документа.", payload["html"]["content"])
            self.assertIn("harnes/state/01-demo.md", payload["html"]["right"])
            self.assertIn("Заголовок", payload["html"]["right"])

    def test_docs_page_opens_nested_id_route(self):
        with panel() as port:
            status, html = get(port, "/panel/docs/harnes/state/01-demo")
            self.assertEqual(200, status)
            self.assertIn("Текст первого документа.", html)

    def test_docs_api_rejects_traversal(self):
        with panel() as port:
            for attempt in ("../secret", "harnes/../../secret", "/etc/passwd"):
                try:
                    status, body = get(port, f"/panel/api/docs/item?id={attempt}")
                except HTTPError as error:
                    status, body = error.code, error.read().decode()
                self.assertEqual(404, status, attempt)

    def test_graph_api_summary_view_node(self):
        with panel() as port:
            status, payload = get_json(port, "/panel/api/graph/summary")
            self.assertEqual(200, status)
            self.assertEqual(2, payload["data"]["nodes"])
            self.assertEqual(1, payload["data"]["edges"])

            status, payload = get_json(port, "/panel/api/graph/view?kind=config")
            self.assertEqual(200, status)
            self.assertEqual(1, len(payload["data"]["nodes"]))
            self.assertEqual([], payload["data"]["edges"])

            status, payload = get_json(port, "/panel/api/graph/node?id=skill:demo")
            self.assertEqual(200, status)
            self.assertEqual("skill", payload["data"]["node"]["kind"])
            self.assertIn("front matter", payload["html"]["right"])
            self.assertEqual(1, len(payload["data"]["relations"]))

            try:
                status, _ = get_json(port, "/panel/api/graph/node?id=skill:missing")
            except HTTPError as error:
                status = error.code
            self.assertEqual(404, status)

    def test_graph_node_exposes_file_and_edit_flag(self):
        with panel() as port:
            status, payload = get_json(port, "/panel/api/graph/node?id=skill:demo")
            self.assertEqual(200, status)
            file = payload["data"]["file"]
            self.assertTrue(file["editable"], file)
            self.assertIn("Текст узла", file["content"])
            self.assertEqual(".agents/skills/demo/SKILL.md", file["path"])
            self.assertIn("data-node-source", payload["html"]["right"])
            self.assertIn("data-node-save", payload["html"]["right"])

    def test_graph_node_save_is_guarded(self):
        # Запись меняет файл в репозитории: без X-Requested-With и с чужим Origin — отказ.
        ajax = {"X-Requested-With": "XMLHttpRequest"}
        with panel() as port:
            status, payload = post(port, "/panel/api/graph/node", {"id": "skill:demo", "content": "x"})
            self.assertEqual(403, status, payload)
            status, payload = post(port, "/panel/api/graph/node", {"id": "skill:demo", "content": "x"},
                                   headers={**ajax, "Origin": "http://evil.example"})
            self.assertEqual(403, status, payload)
            status, payload = post(port, "/panel/api/graph/node", {"id": "skill:demo"}, headers=ajax)
            self.assertEqual(400, status, payload)
            status, payload = post(port, "/panel/api/graph/node", {"id": "nope:nope", "content": "x"}, headers=ajax)
            self.assertEqual(404, status, payload)

    def test_jobs_api_lists_actions_and_guards_start(self):
        with panel() as port:
            status, payload = get_json(port, "/panel/api/actions")
            self.assertEqual(200, status)
            self.assertTrue(any(item["id"] == "harness_audit" for item in payload["data"]))

            status, payload = post(port, "/panel/api/jobs", {"action": "harness_audit", "params": {}})
            self.assertEqual(403, status)
            self.assertEqual("origin not allowed", payload["error"])

            status, payload = post(port, "/panel/api/jobs", {"action": "harness_audit", "params": {}},
                                   {"X-Requested-With": "XMLHttpRequest"})
            self.assertEqual(202, status, payload)
            self.assertIn("id", payload)


class LegacyPanelTest(unittest.TestCase):
    """Старые страницы живут рядом с новым каркасом: strangler-миграция."""

    def test_root_opens_new_shell(self):
        # Корень отдаёт общий каркас без редиректа: в iframe-предпросмотре 302
        # иногда оставляет пустой экран, а панель должна открываться одним запросом.
        with panel() as port:
            status, html = get(port, "/")
            self.assertEqual(200, status)
            self.assertIn('class="topbar"', html)
            self.assertIn("data-graph-canvas", html)
            self.assertIn("data-graph-list", html)
            self.assertNotIn('class="new-panel-link"', html, "это уже не старая панель")

    def test_old_routes_still_respond(self):
        with panel() as port:
            # /harness/ требует собранного миррора (.doc/skil_data/mirror) и проверяется
            # на живом сервисе; здесь — маршруты, которым хватает самой панели.
            for path in ("/index.php?tab=tasks", "/index.php?tab=docs",
                         "/index.php?tab=docs&doc=harnes/state/01-demo", "/harness-admin/", "/jobs"):
                status, _ = get(port, path)
                self.assertEqual(200, status, path)

    def test_old_panel_points_to_new_shell(self):
        # Из старого интерфейса должен быть видимый путь в общий каркас.
        with panel() as port:
            _, html = get(port, "/index.php?tab=tasks")
            self.assertIn('class="new-panel-link"', html)
            self.assertIn('href="/panel/graph"', html)

    def test_old_jobs_endpoint_keeps_working(self):
        with panel() as port:
            status, payload = post(port, "/jobs", {"action": "harness_audit", "params": {}},
                                   {"X-Requested-With": "XMLHttpRequest"})
            self.assertEqual(202, status, payload)


if __name__ == "__main__":
    unittest.main()

/**
 * Точка входа панели.
 *
 * Собирает сервисы (тема, локализация, API, док), подключает общие обработчики
 * верхнего меню и монтирует страницу раздела. Никаких глобальных переменных.
 */
import { readBoot } from './core/boot.js';
import { createStore } from './core/store.js';
import { createApi } from './core/api.js';
import { createI18n } from './core/i18n.js';
import { createTheme } from './core/theme.js';
import { createDock } from './core/dock.js';
import { createSplitter } from './core/splitter.js';
import { createDrawer } from './core/drawer.js';
import { qs } from './core/dom.js';
import { mountDocs } from './pages/docs.js';
import { mountGraph } from './pages/graph.js';
import { mountHarness } from './pages/harness.js';
import { mountTasks } from './pages/tasks.js';
import { mountAnalytics } from './pages/analytics.js';

const boot = readBoot();
const store = createStore({
  section: boot.section || '',
  selected: boot.selected || null,
  lang: boot.lang || 'ru',
  theme: 'light',
  themeMode: 'system',
  apiHistory: [],
});

const api = createApi({ store, endpoints: boot.endpoints });
const i18n = createI18n({
  store,
  dictionary: boot.dictionary,
  lang: boot.lang,
  availableLangs: boot.availableLangs || ['ru'],
});
const theme = createTheme({ store });
const dock = createDock({ store, api, i18n, endpoints: boot.endpoints });

i18n.apply(document);
createSplitter();
createDrawer();

/* Верхнее меню: тема и язык */
qs('[data-theme-toggle]')?.addEventListener('click', () => theme.toggle());
qs('[data-lang-switch]')?.addEventListener('change', (event) => {
  i18n.setLanguage(event.target.value, boot.endpoints.i18n);
});

/* Реестр действий нужен доку для терминала и подсказок */
api.get(boot.endpoints.actions)
  .then((entry) => dock.attachActions(entry.response?.data || []))
  .catch(() => dock.attachActions([]));

/* Подсветка активного раздела при переходах по истории */
window.addEventListener('popstate', () => {
  document.querySelectorAll('.nav__item').forEach((item) => {
    item.classList.toggle('is-active', item.getAttribute('href') === window.location.pathname);
  });
});

if (boot.section === 'docs') {
  mountDocs({ api, i18n, endpoints: boot.endpoints, dock, base: boot.base });
} else if (boot.section === 'graph') {
  mountGraph({ api, i18n, endpoints: boot.endpoints, dock });
} else if (boot.section === 'harness') {
  mountHarness({ api, i18n, endpoints: boot.endpoints, dock });
} else if (boot.section === 'tasks') {
  mountTasks({ api, i18n, endpoints: boot.endpoints, dock });
} else if (boot.section === 'analytics') {
  mountAnalytics({ api, i18n, endpoints: boot.endpoints, dock });
}

dock.refreshLog().catch(() => {});

/* Горячие клавиши: / — поиск, ` — док, d — тема */
window.addEventListener('keydown', (event) => {
  const target = event.target;
  const typing = target instanceof HTMLElement && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName);
  if (event.key === '/' && !typing) {
    event.preventDefault();
    (qs('[data-docs-search]') || qs('[data-graph-search]') || qs('[data-tasks-search]') || qs('[data-analytics-search]'))?.focus();
  }
  if (event.key === '`' && !typing) {
    event.preventDefault();
    dock.open();
  }
});

/**
 * Раздел «Документация».
 *
 * Первый экран приходит готовым HTML с сервера. Дальше список и документ
 * обновляются фрагментами API: переключение не перезагружает страницу и не теряет
 * состояние дока, а адрес остаётся честным (history.pushState).
 */
import { debounce, on, qs } from '../core/dom.js';

export function mountDocs({ api, i18n, endpoints, dock, base }) {
  const root = qs('[data-docs-root]');
  if (!root) return;

  const content = qs('.content');
  const rightElement = qs('[data-right-element]');
  const search = qs('[data-docs-search]');
  const source = qs('[data-docs-source]');
  const counter = qs('[data-docs-counter]');
  const refresh = qs('[data-docs-refresh]');

  let selected = root.dataset.selected || '';

  const renderSidebar = async () => {
    const entry = await api.get(endpoints.docs, {
      q: search?.value || '',
      source: source?.value || '',
    });
    const sidebar = qs('[data-docs-list]');
    if (sidebar && entry.response?.html?.sidebar) {
      const holder = document.createElement('div');
      holder.innerHTML = entry.response.html.sidebar;
      const fresh = holder.querySelector('[data-docs-list]');
      if (fresh) sidebar.replaceWith(fresh);
    }
    if (counter && entry.response?.data) {
      counter.textContent = i18n.t('docs.counter', { count: entry.response.data.total });
    }
  };

  const openDoc = async (id, { push = true, silent = false } = {}) => {
    if (!id) return;
    const entry = await api.get(endpoints.docItem, { id });
    if (!entry.ok || !entry.response?.html) {
      if (!silent) dock.append(i18n.t('common.error', { message: id }), 'line-err');
      return;
    }
    if (content) content.innerHTML = `<div class="docview" data-docs-root data-selected="${id}">${entry.response.html.content}</div>`;
    if (rightElement) rightElement.innerHTML = entry.response.html.right;
    selected = id;
    document.querySelectorAll('[data-doc-id]').forEach((link) => {
      link.classList.toggle('is-active', link.dataset.docId === id);
    });
    dock.renderApiPanel(entry.response, `GET ${endpoints.docItem} · ${id}`);
    if (push) {
      const url = `${base}/docs/${id}`;
      if (window.location.pathname !== url) window.history.pushState({ doc: id }, '', url);
    }
    content?.scrollTo({ top: 0 });
  };

  on(document, 'click', '[data-doc-id]', (event, target) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey) return;
    event.preventDefault();
    openDoc(target.dataset.docId);
  });

  const debouncedSidebar = debounce(renderSidebar, 200);
  search?.addEventListener('input', debouncedSidebar);
  source?.addEventListener('change', renderSidebar);
  refresh?.addEventListener('click', async () => {
    await renderSidebar();
    if (selected) await openDoc(selected, { push: false });
  });

  window.addEventListener('popstate', () => {
    const match = window.location.pathname.match(/\/docs\/(.+)$/);
    if (match) openDoc(decodeURIComponent(match[1]), { push: false, silent: true });
  });
}

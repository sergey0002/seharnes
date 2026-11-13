/**
 * Раздел «Аналитика».
 *
 * Первый экран рисует сервер, модуль пересобирает срез по фильтрам через
 * `/panel/api/analytics` и обновляет цифры, разрезы и таблицу без перезагрузки.
 */
import { qs, debounce, escapeHtml } from '../core/dom.js';

const MONEY = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function mountAnalytics({ api, i18n, endpoints }) {
  const root = qs('[data-analytics-root]');
  if (!root) return;

  const state = {
    q: qs('[data-analytics-search]')?.value || '',
    release: qs('[data-analytics-filter="release"]')?.value || '',
    assignee: qs('[data-analytics-filter="assignee"]')?.value || '',
    project: qs('[data-analytics-filter="project"]')?.value || '',
  };

  const t = (key) => i18n.t(key);
  const money = (value) => MONEY.format(Number(value) || 0);
  const minutes = (ms) => (Number(ms) > 0 ? String(Math.round(Number(ms) / 60000)) : '—');

  const syncUrl = () => {
    const params = new URLSearchParams();
    if (state.q) params.set('q', state.q);
    if (state.release) params.set('release', state.release);
    if (state.assignee) params.set('assignee', state.assignee);
    if (state.project) params.set('project', state.project);
    const query = params.toString();
    history.replaceState(null, '', query ? `?${query}` : location.pathname);
  };

  const factsHtml = (totals) => {
    const tokens = (Number(totals.tokens_in) || 0) + (Number(totals.tokens_out) || 0) + (Number(totals.tokens_reasoning) || 0);
    return [
      [t('analytics.tasks'), Number(totals.tasks) || 0],
      [t('analytics.sessions'), Number(totals.sessions) || 0],
      [t('analytics.requests'), Number(totals.requests) || 0],
      [t('tasks.tokens'), tokens],
      [t('tasks.cost'), money(totals.cost)],
      [t('analytics.active'), minutes(totals.active_ms)],
    ].map(([label, value]) => `
      <div class="fact"><span class="fact__label">${escapeHtml(label)}</span>
      <span class="fact__value">${escapeHtml(String(value))}</span></div>`).join('');
  };

  const taskRowsHtml = (rows) => rows.map((row) => `
    <tr>
      <td><a class="tbl__link" href="/panel/tasks?id=${escapeHtml(String(row.id))}">#${escapeHtml(String(row.id))}</a></td>
      <td class="tbl__wrap" title="${escapeHtml(row.title)}">${escapeHtml(row.title)}</td>
      <td class="num">${row.sessions}</td>
      <td class="num">${row.tokens}</td>
      <td class="num">${row.requests}</td>
      <td class="num">${escapeHtml(minutes(row.active_ms))}</td>
      <td class="num">${money(row.cost)}</td>
    </tr>`).join('');

  const barBlocksHtml = (data) => {
    const blocks = [
      ['analytics.models', data.models], ['analytics.tools', data.tools], ['analytics.mcp', data.mcp],
      ['analytics.providers', data.providers], ['analytics.roles', data.roles],
    ];
    let peak = 1;
    blocks.forEach(([, rows]) => rows.forEach((row) => { peak = Math.max(peak, Number(row.value) || 0); }));
    return blocks.map(([key, rows]) => `
      <div class="bargrid__block">
        <h3 class="block-head">${escapeHtml(t(key))}</h3>
        ${rows.length === 0 ? `<p class="empty">${escapeHtml(t('analytics.noData'))}</p>` : `
        <ul class="barlist">
          ${rows.map((row) => `
            <li class="barlist__item">
              <span class="barlist__label" title="${escapeHtml(row.label)}">${escapeHtml(row.label)}</span>
              <span class="barlist__bar" style="width: ${Math.round(100 * (Number(row.value) || 0) / peak)}%"></span>
              <span class="barlist__value">${Number(row.value) || 0}</span>
            </li>`).join('')}
        </ul>`}
      </div>`).join('');
  };

  const unassignedHtml = (rows) => rows.map((row) => `
    <tr>
      <td><code>${escapeHtml(String(row.id).slice(0, 14))}…</code></td>
      <td>${escapeHtml(row.project || '—')}</td>
      <td>${escapeHtml(row.model || '—')}</td>
      <td class="num">${row.requests}</td>
      <td class="num">${row.tokens}</td>
      <td>${escapeHtml(row.date)}</td>
    </tr>`).join('');

  const render = (data) => {
    const totals = qs('#analytics-totals .facts');
    if (totals) totals.innerHTML = factsHtml(data.totals || {});

    const taskBody = qs('#analytics-tasks tbody');
    const taskTable = qs('#analytics-tasks .tbl');
    const taskEmpty = qs('[data-analytics-empty]');
    if (taskBody) taskBody.innerHTML = taskRowsHtml(data.tasks || []);
    if (taskTable) taskTable.hidden = (data.tasks || []).length === 0;
    if (taskEmpty) taskEmpty.hidden = (data.tasks || []).length !== 0;

    const bars = qs('#analytics-breakdown .bargrid');
    if (bars) bars.innerHTML = barBlocksHtml(data);

    const unassignedBody = qs('#analytics-unassigned tbody');
    if (unassignedBody) unassignedBody.innerHTML = unassignedHtml(data.unassigned?.rows || []);

    const apiPanel = qs('[data-dock-api-panel]');
    if (apiPanel) {
      apiPanel.innerHTML = `<pre class="json-view__body">${escapeHtml(JSON.stringify({
        totals: data.totals, filters: data.filters,
      }, null, 2))}</pre>`;
    }
  };

  let requestSeq = 0;
  const reload = async () => {
    const seq = ++requestSeq;
    const params = { q: state.q, release: state.release, assignee: state.assignee, project: state.project };
    Object.keys(params).forEach((key) => params[key] === '' && delete params[key]);
    const progress = qs('[data-right-progress]');
    if (progress) progress.hidden = false;
    const entry = await api.get(endpoints.analytics, params);
    if (progress) progress.hidden = true;
    if (seq !== requestSeq || entry.response?.status !== 'ok') return;
    render(entry.response.data);
    syncUrl();
  };

  const reloadSoon = debounce(reload, 220);
  qs('[data-analytics-search]')?.addEventListener('input', (event) => {
    state.q = event.target.value.trim();
    reloadSoon();
  });
  root.querySelectorAll('[data-analytics-filter]').forEach((select) => {
    select.addEventListener('change', () => {
      state[select.getAttribute('data-analytics-filter')] = select.value;
      reload();
    });
  });
  qs('[data-analytics-reset]')?.addEventListener('click', () => {
    state.q = '';
    state.release = '';
    state.assignee = '';
    state.project = '';
    const search = qs('[data-analytics-search]');
    if (search) search.value = '';
    root.querySelectorAll('[data-analytics-filter]').forEach((select) => { select.value = ''; });
    reload();
  });

  root.querySelectorAll('[data-analytics-jump]').forEach((link) => {
    link.addEventListener('click', (event) => {
      event.preventDefault();
      const target = qs(`#${link.getAttribute('data-analytics-jump')}`);
      target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
}

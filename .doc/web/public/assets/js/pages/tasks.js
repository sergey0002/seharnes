/**
 * Раздел «Задачи».
 *
 * Сервер отдаёт первый экран целиком (таблица, сводка, дерево задач), а модуль
 * добавляет живое поведение: фильтры пересобирают срез через `/panel/api/tasks`,
 * выбор задачи подтягивает детали через `/panel/api/tasks/item` и сразу показывает
 * их справа вместе с JSON ответа. Состояние среза держим в адресе страницы.
 */
import { qs, on, debounce, escapeHtml } from '../core/dom.js';

const MONEY = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function mountTasks({ api, i18n, endpoints }) {
  const root = qs('[data-tasks-root]');
  if (!root) return;

  const state = {
    q: qs('[data-tasks-search]')?.value || '',
    release: qs('[data-tasks-filter="release"]')?.value || '',
    assignee: qs('[data-tasks-filter="assignee"]')?.value || '',
    project: qs('[data-tasks-filter="project"]')?.value || '',
    unassigned: qs('[data-tasks-unassigned]')?.checked || false,
    selected: root.dataset.selected || '',
  };

  const t = (key) => i18n.t(key);
  const money = (value) => MONEY.format(Number(value) || 0);

  /* ---------------------------- Адрес страницы ---------------------------- */
  const syncUrl = () => {
    const params = new URLSearchParams();
    if (state.q) params.set('q', state.q);
    if (state.release) params.set('release', state.release);
    if (state.assignee) params.set('assignee', state.assignee);
    if (state.project) params.set('project', state.project);
    if (state.unassigned) params.set('unassigned', '1');
    if (state.selected) params.set('id', state.selected);
    const query = params.toString();
    history.replaceState(null, '', query ? `?${query}` : location.pathname);
  };

  /* ------------------------------- Рендер -------------------------------- */
  const renderTotals = (totals) => {
    const map = {
      '[data-tasks-total-tasks]': totals.tasks,
      '[data-tasks-total-dialogs]': totals.dialogs,
      '[data-tasks-total-tokens]': totals.tokens,
      '[data-tasks-total-cost]': money(totals.cost),
      '[data-tasks-total-unassigned]': totals.unassigned,
    };
    Object.entries(map).forEach(([selector, value]) => {
      const node = qs(selector);
      if (node) node.textContent = String(value);
    });
    const counter = qs('[data-tasks-counter]');
    if (counter) counter.textContent = String(totals.tasks);
    const sideCount = qs('[data-tasks-side-count]');
    if (sideCount) sideCount.textContent = String(totals.tasks);
  };

  const rowHtml = (row) => `
    <tr data-task-row="${escapeHtml(row.id)}"${row.id === state.selected ? ' class="is-selected"' : ''}>
      <td><a class="tbl__link" href="/panel/tasks?id=${escapeHtml(row.id)}" data-task-link="${escapeHtml(row.id)}">#${escapeHtml(row.id)}</a></td>
      <td class="tbl__wrap" title="${escapeHtml(row.title)}">${escapeHtml(row.title)}</td>
      <td>${escapeHtml(row.release)}</td>
      <td>${escapeHtml(row.assignee || '—')}</td>
      <td><span class="pill pill--sm">${escapeHtml(row.status || '—')}</span></td>
      <td class="num">${row.dialogs}</td>
      <td class="num">${row.tokens}</td>
      <td class="num">${money(row.cost)}</td>
      <td>${escapeHtml(row.updated || row.touched || '')}</td>
    </tr>`;

  const sideHtml = (row) => {
    const params = new URLSearchParams({ id: row.id });
    if (state.q) params.set('q', state.q);
    if (state.release) params.set('release', state.release);
    if (state.assignee) params.set('assignee', state.assignee);
    if (state.project) params.set('project', state.project);
    if (state.unassigned) params.set('unassigned', '1');
    const dialogs = row.dialogs > 0 ? ` · ${row.dialogs}` : '';
    return `
      <li class="tasklist__item">
        <a class="tasklist__link" href="/panel/tasks?${params.toString()}" data-task-link="${escapeHtml(row.id)}">
          <span class="tasklist__id">#${escapeHtml(row.id)}</span>
          <span class="tasklist__title" title="${escapeHtml(row.title)}">${escapeHtml(row.title)}</span>
          <span class="tasklist__meta">${escapeHtml(row.release)}${dialogs}</span>
        </a>
      </li>`;
  };

  const unassignedHtml = (row) => `
    <tr data-session-row="${escapeHtml(row.id)}">
      <td><code>${escapeHtml(row.id.slice(0, 14))}…</code></td>
      <td>${escapeHtml(row.project || '—')}</td>
      <td class="tbl__wrap" title="${escapeHtml(row.title)}">${escapeHtml(row.title)}</td>
      <td>${escapeHtml(row.model || '—')}</td>
      <td class="num">${row.requests}</td>
      <td class="num">${row.tokens}</td>
      <td>${escapeHtml(row.date)}</td>
    </tr>`;

  const render = (data) => {
    renderTotals(data.totals);

    const body = qs('[data-tasks-rows]');
    const table = qs('[data-tasks-table]');
    const emptyRow = qs('[data-tasks-table-empty]');
    if (body) body.innerHTML = data.rows.map(rowHtml).join('');
    if (table) table.hidden = data.rows.length === 0;
    if (emptyRow) {
      emptyRow.hidden = data.rows.length !== 0;
      emptyRow.textContent = t('tasks.empty');
    }

    const side = qs('[data-tasks-side-list]');
    if (side) side.innerHTML = data.rows.map(sideHtml).join('');
    const sideEmpty = qs('[data-tasks-empty]');
    if (sideEmpty) sideEmpty.hidden = data.rows.length !== 0;

    const card = qs('[data-tasks-unassigned-card]');
    if (card) card.classList.toggle('is-hidden', !state.unassigned);
    const unassignedBody = qs('[data-tasks-unassigned-table] tbody');
    if (unassignedBody) unassignedBody.innerHTML = data.unassigned.map(unassignedHtml).join('');
    const unassignedEmpty = qs('[data-tasks-unassigned-empty]');
    if (unassignedEmpty) unassignedEmpty.hidden = data.unassigned.length !== 0;
  };

  /* ------------------------------- Запросы ------------------------------- */
  let requestSeq = 0;
  const reload = async () => {
    const seq = ++requestSeq;
    const params = {
      q: state.q, release: state.release, assignee: state.assignee, project: state.project,
      unassigned: state.unassigned ? '1' : '',
    };
    Object.keys(params).forEach((key) => params[key] === '' && delete params[key]);
    const entry = await api.get(endpoints.tasksList, params);
    if (seq !== requestSeq) return; // пришёл ответ на устаревший фильтр
    if (entry.response?.status !== 'ok') return;
    render(entry.response.data);
    syncUrl();
  };

  const selectTask = async (id) => {
    state.selected = id;
    document.querySelectorAll('[data-task-row]').forEach((row) => {
      row.classList.toggle('is-selected', row.getAttribute('data-task-row') === id);
    });
    syncUrl();
    const panel = qs('[data-right-element]');
    const progress = qs('[data-right-progress]');
    if (progress) progress.hidden = false;
    const entry = await api.get(endpoints.taskItem, { id, project: state.project });
    if (progress) progress.hidden = true;
    if (entry.response?.status !== 'ok' || !panel) return;
    panel.innerHTML = detailHtml(entry.response.data, id);
    api.paint?.(entry);
    const dock = qs('[data-dock-api-panel]');
    if (dock) {
      const hint = qs('[data-right-api-hint]');
      if (hint) hint.textContent = `GET task · ${id}`;
      dock.innerHTML = `<pre class="json-view__body">${escapeHtml(JSON.stringify(entry.response.data, null, 2))}</pre>`;
    }
  };

  const detailHtml = (detail, id) => {
    const summary = detail.summary || {};
    const totals = detail.dialogs_total || {};
    const activity = (detail.activity || []).map((event) => `
      <li class="feed__item">
        <span class="feed__kind">${escapeHtml(event.kind || '')}</span>
        <span class="feed__author">${escapeHtml(event.author || '')}</span>
        <time class="feed__time">${escapeHtml(event.at || '')}</time>
        <p class="feed__text">${escapeHtml((event.text || '').slice(0, 160))}</p>
      </li>`).join('');
    const sessions = (detail.sessions || []).map((session) => `
      <li class="feed__item">
        <span class="feed__kind">${escapeHtml(session.role || 'session')}</span>
        <span class="feed__author">${escapeHtml(session.model || '')}</span>
        <span class="feed__time">${session.tokens} · ${money(session.cost)}</span>
        <p class="feed__text">${escapeHtml(session.title || session.id)}</p>
      </li>`).join('');
    return `
      <div class="taskdetail" data-task-detail="${escapeHtml(id)}">
        <h3 class="taskdetail__title">${escapeHtml(summary.title || `#${id}`)}</h3>
        <p class="taskdetail__meta">
          <span class="badge">#${escapeHtml(id)}</span>
          <span class="badge">${escapeHtml(summary.release || '')}</span>
          ${summary.jira_status ? `<span class="pill pill--sm">${escapeHtml(summary.jira_status)}</span>` : ''}
        </p>
        <dl class="kv kv--tight">
          <div class="kv__row"><dt>${t('tasks.col.assignee')}</dt><dd>${escapeHtml(summary.assignee || '—')}</dd></div>
          <div class="kv__row"><dt>${t('tasks.col.updated')}</dt><dd>${escapeHtml(summary.jira_updated || '—')}</dd></div>
          <div class="kv__row"><dt>${t('tasks.col.files')}</dt><dd>${summary.n_files || 0}</dd></div>
          <div class="kv__row"><dt>${t('tasks.col.dialogs')}</dt><dd>${totals.sessions || 0}</dd></div>
          <div class="kv__row"><dt>${t('tasks.cost')}</dt><dd>${money(totals.cost)}</dd></div>
        </dl>
        ${activity ? `<h4 class="block-head">${t('tasks.activity')}</h4><ul class="feed">${activity}</ul>` : ''}
        ${sessions ? `<h4 class="block-head">${t('tasks.sessions')}</h4><ul class="feed">${sessions}</ul>` : ''}
      </div>`;
  };

  /* ------------------------------- События ------------------------------- */
  const reloadSoon = debounce(reload, 200);
  qs('[data-tasks-search]')?.addEventListener('input', (event) => {
    state.q = event.target.value.trim();
    reloadSoon();
  });
  root.querySelectorAll('[data-tasks-filter]').forEach((select) => {
    select.addEventListener('change', () => {
      state[select.getAttribute('data-tasks-filter')] = select.value;
      reload();
    });
  });
  qs('[data-tasks-unassigned]')?.addEventListener('change', (event) => {
    state.unassigned = event.target.checked;
    reload();
  });
  qs('[data-tasks-reset]')?.addEventListener('click', () => {
    state.q = '';
    state.release = '';
    state.assignee = '';
    state.project = '';
    state.unassigned = false;
    const search = qs('[data-tasks-search]');
    if (search) search.value = '';
    root.querySelectorAll('[data-tasks-filter]').forEach((select) => { select.value = ''; });
    const checkbox = qs('[data-tasks-unassigned]');
    if (checkbox) checkbox.checked = false;
    reload();
  });

  // Выбор задачи: и из таблицы, и из дерева слева, и по прямой ссылке.
  on(document, 'click', '[data-task-link]', (event, link) => {
    event.preventDefault();
    const id = link.getAttribute('data-task-link');
    if (id) selectTask(id);
  });

  if (state.selected) selectTask(state.selected);
}

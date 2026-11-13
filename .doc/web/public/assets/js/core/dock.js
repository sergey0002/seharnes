/**
 * Нижний док: терминал действий, инспектор JSON, живой лог.
 *
 * Док ничего не знает о разделах: он принимает команды и показывает ответы.
 * Запуск действий идёт через POST /panel/api/jobs, наблюдение — через /panel/api/jobs/status.
 */
import { escapeHtml, formatDuration, on, qs, qsa } from './dom.js';

const POLL_INTERVAL = 700;

export function createDock({ store, api, i18n, endpoints }) {
  const root = qs('[data-dock]');
  if (!root) return { run: async () => {}, open() {}, refreshLog() {} };

  const output = qs('[data-dock-output]', root);
  const form = qs('[data-dock-form]', root);
  const input = qs('[data-dock-input]', root);
  const actionsList = qs('[data-dock-actions]', root);
  const stateLabel = qs('[data-dock-state]', root);
  const dot = qs('[data-dock-dot]', root);
  const collapseBtn = qs('[data-dock-collapse]', root);
  const jsonList = qs('[data-dock-json-list]', root);
  const jsonBody = qs('[data-dock-json-body]', root);
  const jsonHead = qs('[data-dock-json-head]', root);
  const jsonCount = qs('[data-dock-json-count]', root);
  const logBody = qs('[data-dock-log-body]', root);
  const apiPanel = qs('[data-dock-api-panel]') || qs('[data-right-api]');
  const apiHint = qs('[data-right-api-hint]');

  const state = { actions: [], knownActions: new Set(), activeJob: null, timer: null, selectedJson: null };

  /* ------------------------------ Вывод ------------------------------ */
  // Автопрокрутка держится за низ, пока пользователь не отлистал вывод вверх:
  // иначе чтение лога задания срывается на каждой новой строке.
  const stuckToBottom = (el) => el.scrollHeight - el.scrollTop - el.clientHeight < 48;

  const append = (text, className = '') => {
    const stick = stuckToBottom(output);
    const span = document.createElement('span');
    if (className) span.className = className;
    span.textContent = text.endsWith('\n') ? text : `${text}\n`;
    output.appendChild(span);
    if (stick) output.scrollTop = output.scrollHeight;
  };

  const clearOutput = () => {
    output.textContent = '';
  };

  const setStatus = (key, kind = '') => {
    stateLabel.textContent = i18n.t(key);
    dot.className = `status-dot ${kind}`;
  };

  /* --------------------------- Tabs / открытие --------------------------- */
  const setTab = (name) => {
    qsa('[data-dock-tab]', root).forEach((tab) => {
      const active = tab.dataset.dockTab === name;
      tab.classList.toggle('is-active', active);
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    qsa('[data-dock-pane]', root).forEach((pane) => {
      pane.classList.toggle('is-active', pane.dataset.dockPane === name);
    });
  };

  const setOpen = (open) => {
    root.dataset.open = open ? 'true' : 'false';
    collapseBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    collapseBtn.querySelector('[data-i18n]')?.setAttribute('data-i18n', open ? 'dock.collapse' : 'dock.expand');
    const label = collapseBtn.querySelector('span');
    if (label) label.textContent = i18n.t(open ? 'dock.collapse' : 'dock.expand');
    if (open) document.body.style.setProperty('--dock-open', '1');
  };

  const open = (tab) => {
    setOpen(true);
    if (tab) setTab(tab);
  };

  /* ------------------------------ JSON tab ------------------------------ */
  const renderJsonList = () => {
    const entries = store.get('apiHistory', []);
    jsonCount.textContent = String(entries.length);
    jsonCount.hidden = entries.length === 0;
    jsonList.innerHTML = entries.map((entry) => `
      <li class="json-list__item${state.selectedJson === entry.id ? ' is-active' : ''}" data-json-id="${entry.id}">
        <span class="json-list__status ${entry.ok ? 'is-ok' : 'is-err'}">${entry.status || '×'}</span>
        <span class="json-list__path">${escapeHtml(entry.method)} ${escapeHtml(entry.path)}</span>
      </li>`).join('');
    if (state.selectedJson === null && entries[0]) selectJson(entries[0].id);
  };

  const selectJson = (id) => {
    const entry = (store.get('apiHistory', []) || []).find((item) => String(item.id) === String(id));
    if (!entry) return;
    state.selectedJson = entry.id;
    jsonBody.textContent = JSON.stringify(entry.response, null, 2);
    jsonHead.textContent = `${entry.method} ${entry.url} → ${entry.status} · ${entry.ms} ms`;
    qsa('.json-list__item', jsonList).forEach((item) => {
      item.classList.toggle('is-active', String(item.dataset.jsonId) === String(entry.id));
    });
  };

  on(jsonList, 'click', '[data-json-id]', (event, target) => selectJson(target.dataset.jsonId));

  on(root, 'click', '[data-dock-json-copy]', async () => {
    try {
      await navigator.clipboard.writeText(jsonBody.textContent || '');
      const button = qs('[data-dock-json-copy]', root).querySelector('span');
      if (button) {
        const original = button.textContent;
        button.textContent = i18n.t('common.copied');
        window.setTimeout(() => { button.textContent = original; }, 1200);
      }
    } catch (error) { /* clipboard может быть запрещён — молча игнорируем */ }
  });

  /* ------------------------------ Лог заданий ------------------------------ */
  const statusLabel = (value) => `<span class="status status--${escapeHtml(value)}">${escapeHtml(i18n.t(`dock.${value === 'ok' ? 'done' : value === 'failed' ? 'failed' : 'running'}`))}</span>`;

  const refreshLog = async () => {
    const entry = await api.get(endpoints.jobs, null, { quiet: true });
    const jobs = entry.response?.data || [];
    const logScroll = logBody.closest('[data-dock-pane]');
    const stickLog = logScroll ? stuckToBottom(logScroll) : true;
    logBody.innerHTML = jobs.map((job) => {
      const started = job.started_at ? new Date(job.started_at) : null;
      const ended = job.ended_at ? new Date(job.ended_at) : null;
      const duration = started && ended ? (ended - started) / 1000 : NaN;
      return `<tr>
        <td><code>${escapeHtml(job.action || job.id)}</code></td>
        <td>${statusLabel(job.status || 'queued')}</td>
        <td>${started ? started.toLocaleTimeString() : '—'}</td>
        <td>${formatDuration(duration)}</td>
        <td><button type="button" class="ghost-btn" data-job-open="${escapeHtml(job.id)}">${escapeHtml(i18n.t('common.open'))}</button></td>
      </tr>`;
    }).join('') || `<tr><td colspan="5" class="muted">${escapeHtml(i18n.t('dock.jsonEmpty'))}</td></tr>`;
    if (logScroll && stickLog) logScroll.scrollTop = logScroll.scrollHeight;
    return jobs;
  };

  on(logBody, 'click', '[data-job-open]', async (event, target) => {
    open('terminal');
    const jobId = target.dataset.jobOpen;
    const entry = await api.get(`${endpoints.jobStatus}?id=${encodeURIComponent(jobId)}`);
    const payload = entry.response?.data;
    if (!payload) {
      append(`${i18n.t('common.error', { message: jobId })}`, 'line-err');
      return;
    }
    clearOutput();
    append(`# ${payload.action} · ${jobId}`, 'line-dim');
    (payload.log_tail || []).forEach((line) => append(line));
    setStatus(payload.status === 'ok' ? 'dock.done' : payload.status === 'failed' ? 'dock.failed' : 'dock.running',
      payload.status === 'ok' ? 'is-ok' : payload.status === 'failed' ? 'is-failed' : 'is-running');
  });

  /* --------------------------- Правая панель: API --------------------------- */
  const renderApiPanel = (payload, hint) => {
    if (apiHint) apiHint.textContent = hint || '';
    if (!apiPanel) return;
    apiPanel.innerHTML = `<pre class="api-json">${escapeHtml(JSON.stringify(payload, null, 2))}</pre>`;
  };

  /* ------------------------------ Запуск ------------------------------ */
  const poll = (jobId) => {
    window.clearTimeout(state.timer);
    let printed = 0;
    const tick = async () => {
      const entry = await api.get(`${endpoints.jobStatus}?id=${encodeURIComponent(jobId)}`, null, { quiet: true });
      const payload = entry.response?.data;
      if (!payload) {
        state.timer = window.setTimeout(tick, POLL_INTERVAL);
        return;
      }
      const tail = payload.log_tail || [];
      for (let index = printed; index < tail.length; index += 1) {
        append(tail[index]);
      }
      printed = Math.max(printed, tail.length);
      const running = ['queued', 'running', 'cancelling'].includes(payload.status);
      setStatus(running ? 'dock.running' : payload.status === 'ok' ? 'dock.done' : 'dock.failed',
        running ? 'is-running' : payload.status === 'ok' ? 'is-ok' : 'is-failed');
      if (running) {
        state.timer = window.setTimeout(tick, POLL_INTERVAL);
      } else {
        state.activeJob = null;
        append(`# ${i18n.t(payload.status === 'ok' ? 'dock.done' : 'dock.failed')} · ${payload.action}`, payload.status === 'ok' ? 'line-ok' : 'line-err');
        refreshLog().catch(() => {});
        store.set({ lastJob: payload });
      }
    };
    tick();
  };

  const run = async (actionId, params = {}) => {
    const id = String(actionId || '').trim();
    if (!id) return;
    if (state.knownActions.size && !state.knownActions.has(id)) {
      open('terminal');
      append(i18n.t('dock.unknownAction', { action: id }), 'line-err');
      return;
    }
    open('terminal');
    append(`$ ${id}`, 'line-cmd');
    setStatus('dock.running', 'is-running');
    const entry = await api.post(endpoints.jobs, { action: id, params });
    const payload = entry.response || {};
    if (entry.status >= 300 || payload.status === 'failed') {
      append(`${payload.error || entry.status}`, 'line-err');
      setStatus('dock.failed', 'is-failed');
      return;
    }
    const jobId = payload.id;
    if (!jobId) {
      append(JSON.stringify(payload), 'line-dim');
      return;
    }
    state.activeJob = jobId;
    append(`# job ${jobId}`, 'line-dim');
    poll(jobId);
  };

  /* ------------------------------ Команды ------------------------------ */
  const commands = {
    help: () => {
      append('# actions: ' + state.actions.map((action) => action.id).join(', '), 'line-dim');
      append('# commands: help, clear, actions, <action-id>', 'line-dim');
    },
    clear: () => clearOutput(),
    actions: () => {
      state.actions.forEach((action) => append(`  ${action.id.padEnd(28)} ${action.label}`, 'line-dim'));
    },
  };

  form?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const value = (input?.value || '').trim();
    if (!value) return;
    input.value = '';
    const [command, ...rest] = value.split(/\s+/);
    if (commands[command]) {
      commands[command](rest);
      return;
    }
    await run(command);
  });

  on(root, 'click', '[data-dock-tab]', (event, target) => setTab(target.dataset.dockTab));
  on(root, 'click', '[data-dock-clear]', () => clearOutput());
  collapseBtn?.addEventListener('click', () => {
    setOpen(root.dataset.open !== 'true');
  });
  // Кнопки действий живут в панели кнопок раздела, а не внутри дока, поэтому
  // обработчик висит на документе: иначе кнопки «Пересобрать граф» и соседние
  // выглядят живыми, но ничего не запускают.
  on(document, 'click', '[data-run-action]', (event, target) => {
    const actionId = target.dataset.runAction;
    if (target.dataset.confirm === '1' && !window.confirm(i18n.t('dock.confirm', { action: actionId }))) return;
    run(actionId);
  });

  store.on('apiHistory', renderJsonList);

  const attachActions = (actions) => {
    state.actions = actions || [];
    state.knownActions = new Set(state.actions.map((action) => action.id));
    if (actionsList) {
      actionsList.innerHTML = state.actions
        .map((action) => `<option value="${escapeHtml(action.id)}">${escapeHtml(action.label)}</option>`)
        .join('');
    }
  };

  return { run, open, refreshLog, attachActions, renderApiPanel, append, setStatus, setTab };
}

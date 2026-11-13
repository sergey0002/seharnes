/**
 * Раздел «Контроль харнеса».
 *
 * Задания (обновление из Git, сборка, проверки, синхронизация зеркал) запускает
 * общий док через [data-run-action] — здесь их дублировать не нужно. Страница
 * отвечает за сканы: они синхронные, читают дерево и возвращают отчёт, который
 * показывается и в карточке, и в правой панели.
 */
import { escapeHtml, on, qs, qsa } from '../core/dom.js';

export function mountHarness({ api, i18n, endpoints }) {
  const out = qs('[data-scan-out]');
  const summary = qs('[data-scan-summary]');
  const stateLabel = qs('[data-scan-state]');
  const json = qs('[data-right-api]');
  const buttons = qsa('[data-scan]');

  if (!out) return;

  const setState = (key, tone = '') => {
    if (!stateLabel) return;
    stateLabel.textContent = i18n.t(key);
    stateLabel.className = `card__state${tone ? ` card__state--${tone}` : ''}`;
  };

  const setBusy = (busy) => {
    buttons.forEach((button) => { button.disabled = busy; });
  };

  const pill = (passed) => `<span class="pill pill--sm pill--${passed ? 'ok' : 'bad'}">${escapeHtml(i18n.t(passed ? 'harness.passed' : 'harness.failed'))}</span>`;

  /** Проверка канона: обязательные файлы, секреты, мусор, вью, runtime-состояние. */
  const canonHtml = (check) => {
    const missing = (check.missing_required || []).length;
    const secrets = check.secrets?.count ?? 0;
    const junk = check.junk || { count: 0, tops: [], sample: [] };
    const views = check.generated_views?.count ?? 0;
    const runtime = check.runtime_state?.count ?? 0;
    return `
      <dl class="facts facts--compact">
        <div class="facts__row"><dt>${escapeHtml(i18n.t('harness.canonRequired'))}</dt>
          <dd>${missing ? `<span class="pill pill--sm pill--bad">${missing}</span>` : '<span class="pill pill--sm pill--ok">OK</span>'}</dd></div>
        <div class="facts__row"><dt>${escapeHtml(i18n.t('harness.canonSecrets'))}</dt><dd><b>${secrets}</b></dd></div>
        <div class="facts__row"><dt>${escapeHtml(i18n.t('harness.canonJunk'))}</dt>
          <dd><b>${junk.count}</b>${junk.tops?.length ? ` <span class="muted">(${escapeHtml(junk.tops.join(', '))})</span>` : ''}</dd></div>
        <div class="facts__row"><dt>${escapeHtml(i18n.t('harness.canonViews'))}</dt><dd><b>${views}</b></dd></div>
        <div class="facts__row"><dt>${escapeHtml(i18n.t('harness.canonRuntime'))}</dt><dd><b>${runtime}</b></dd></div>
      </dl>
      ${junk.sample?.length ? `<pre class="scan-out__pre">${escapeHtml(junk.sample.join('\n'))}</pre>` : ''}`;
  };

  /** Битые ссылки: сколько и в каких файлах. */
  const linksHtml = (check) => `
    <p class="scan-out__lead">${escapeHtml(i18n.t('harness.linksLead', {
      count: check.broken_total ?? 0,
      files: check.files ?? 0,
    }))}</p>
    <table class="table table--compact">
      <thead><tr>
        <th>${escapeHtml(i18n.t('harness.colFile'))}</th>
        <th>${escapeHtml(i18n.t('harness.colLinks'))}</th>
        <th>${escapeHtml(i18n.t('harness.colSamples'))}</th>
      </tr></thead>
      <tbody>
        ${(check.top || []).slice(0, 15).map((row) => `
          <tr>
            <td><code>${escapeHtml(row.file)}</code></td>
            <td>${Number(row.count) || 0}</td>
            <td>${(row.links || []).slice(0, 3).map((link) => `<code>${escapeHtml(link)}</code>`).join(', ')}</td>
          </tr>`).join('')}
      </tbody>
    </table>`;

  /** Документация и JSON: ошибки парсинга, front matter, индекс. */
  const docsHtml = (check) => `
    <dl class="facts facts--compact">
      <div class="facts__row"><dt>${escapeHtml(i18n.t('harness.docsJson'))}</dt><dd><b>${(check.json_errors || []).length}</b></dd></div>
      <div class="facts__row"><dt>${escapeHtml(i18n.t('harness.docsFrontMatter'))}</dt><dd><b>${(check.missing_front_matter || []).length}</b></dd></div>
      <div class="facts__row"><dt>${escapeHtml(i18n.t('harness.docsUnindexed'))}</dt><dd><b>${(check.unindexed || []).length}</b></dd></div>
    </dl>
    ${(check.json_errors || []).length
      ? `<pre class="scan-out__pre">${escapeHtml((check.json_errors || []).map((error) => `${error.file}: ${error.error}`).join('\n'))}</pre>`
      : ''}`;

  const renderScan = (report) => {
    if (!report || !Array.isArray(report.checks)) {
      out.innerHTML = `<pre class="scan-out__pre">${escapeHtml(JSON.stringify(report, null, 2))}</pre>`;
      return;
    }
    const passed = report.checks.filter((check) => check.status === 'passed').length;
    setState(i18n.t('harness.scanDone', { passed, total: report.checks.length }),
      passed === report.checks.length ? 'ok' : 'bad');
    out.innerHTML = report.checks.map((check) => {
      const body = check.check === 'canon' ? canonHtml(check)
        : check.check === 'links' ? linksHtml(check)
          : docsHtml(check);
      return `
        <article class="scan-card">
          <header class="scan-card__head">
            <h3 class="scan-card__title">${escapeHtml(check.check)}</h3>
            ${pill(check.status === 'passed')}
            ${check.check === 'links' ? `<span class="muted">${escapeHtml(i18n.t('harness.brokenTotal', { count: check.broken_total ?? 0 }))}</span>` : ''}
          </header>
          <div class="scan-card__body">${body}</div>
        </article>`;
    }).join('');
    if (summary) {
      summary.innerHTML = report.checks.map((check) => `
        <div class="scan-summary__row">
          <b>${escapeHtml(check.check)}</b>
          ${pill(check.status === 'passed')}
        </div>`).join('');
    }
    if (json) {
      json.textContent = JSON.stringify(report, null, 2);
    }
  };

  const runScan = async (checks) => {
    setBusy(true);
    setState(i18n.t('harness.scanRunning'), 'busy');
    out.innerHTML = `<p class="muted">${escapeHtml(i18n.t('harness.scanRunning'))}</p>`;
    const entry = await api.get(endpoints.harnessAudit, { checks });
    setBusy(false);
    const report = entry.response;
    if (!entry.ok || !report) {
      setState(i18n.t('harness.scanFailed'), 'bad');
      out.innerHTML = `<p class="pill pill--bad">${escapeHtml(i18n.t('harness.scanFailed'))}</p>`
        + `<pre class="scan-out__pre">${escapeHtml(JSON.stringify(report, null, 2))}</pre>`;
      return;
    }
    renderScan(report);
  };

  on(document, 'click', '[data-scan]', (event, target) => {
    if (target.disabled) return;
    runScan(target.dataset.scan || '');
  });

  /* Навигация по блокам: якорь без прыжка страницы, но с прокруткой контента. */
  on(document, 'click', '[data-harness-jump]', (event, target) => {
    const section = document.getElementById(target.dataset.harnessJump || '');
    if (!section) return;
    event.preventDefault();
    section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    section.classList.add('is-flash');
    window.setTimeout(() => section.classList.remove('is-flash'), 900);
  });

  /* История заданий: перечитать после завершения задания в доке. */
  on(document, 'click', '[data-harness-refresh]', () => window.location.reload());

  setState(i18n.t('harness.scanIdle'));
}

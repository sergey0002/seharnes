<?php
/**
 * Нижний док: терминал действий, инспектор JSON и живой лог.
 *
 * @var \Seharnes\Panel\Support\I18n $i18n
 */
use Seharnes\Panel\Core\View;
?>
<section class="dock" data-dock data-open="false" aria-label="<?= View::e($i18n->t('dock.label')) ?>">
  <div class="dock__bar">
    <div class="dock__tabs" role="tablist">
      <button type="button" class="dock__tab is-active" role="tab" data-dock-tab="terminal" aria-selected="true">
        <span data-i18n="dock.terminal"><?= View::e($i18n->t('dock.terminal')) ?></span>
      </button>
      <button type="button" class="dock__tab" role="tab" data-dock-tab="json" aria-selected="false">
        <span data-i18n="dock.json"><?= View::e($i18n->t('dock.json')) ?></span>
        <span class="badge" data-dock-json-count hidden>0</span>
      </button>
      <button type="button" class="dock__tab" role="tab" data-dock-tab="log" aria-selected="false">
        <span data-i18n="dock.log"><?= View::e($i18n->t('dock.log')) ?></span>
      </button>
    </div>
    <div class="dock__status">
      <span class="status-dot" data-dock-dot aria-hidden="true"></span>
      <span class="dock__status-text" data-dock-state><?= View::e($i18n->t('dock.idle')) ?></span>
    </div>
    <div class="dock__tools">
      <button type="button" class="ghost-btn" data-dock-clear>
        <span data-i18n="dock.clear"><?= View::e($i18n->t('dock.clear')) ?></span>
      </button>
      <button type="button" class="ghost-btn" data-dock-collapse aria-expanded="false">
        <span data-i18n="dock.expand"><?= View::e($i18n->t('dock.expand')) ?></span>
      </button>
    </div>
  </div>

  <div class="dock__body">
    <div class="dock__pane is-active" data-dock-pane="terminal">
      <pre class="dock__output" data-dock-output aria-live="polite"></pre>
      <form class="dock__prompt" data-dock-form autocomplete="off">
        <span class="dock__prompt-sign" aria-hidden="true">$</span>
        <input type="text" name="command" list="dock-actions" data-dock-input
               placeholder="<?= View::e($i18n->t('dock.placeholder')) ?>"
               aria-label="<?= View::e($i18n->t('dock.placeholder')) ?>">
        <datalist id="dock-actions" data-dock-actions></datalist>
        <button type="submit" class="primary-btn" data-i18n="dock.run"><?= View::e($i18n->t('dock.run')) ?></button>
      </form>
    </div>

    <div class="dock__pane" data-dock-pane="json">
      <div class="dock__split">
        <ol class="json-list" data-dock-json-list></ol>
        <div class="json-view">
          <div class="json-view__head">
            <span data-dock-json-head class="muted" data-i18n="dock.jsonEmpty"><?= View::e($i18n->t('dock.jsonEmpty')) ?></span>
            <button type="button" class="ghost-btn" data-dock-json-copy>
              <span data-i18n="common.copy"><?= View::e($i18n->t('common.copy')) ?></span>
            </button>
          </div>
          <pre class="json-view__body" data-dock-json-body></pre>
        </div>
      </div>
    </div>

    <div class="dock__pane" data-dock-pane="log">
      <table class="log-table">
        <thead>
          <tr>
            <th data-i18n="dock.logAction"><?= View::e($i18n->t('dock.logAction')) ?></th>
            <th data-i18n="dock.logStatus"><?= View::e($i18n->t('dock.logStatus')) ?></th>
            <th data-i18n="dock.logStarted"><?= View::e($i18n->t('dock.logStarted')) ?></th>
            <th data-i18n="dock.logDuration"><?= View::e($i18n->t('dock.logDuration')) ?></th>
            <th></th>
          </tr>
        </thead>
        <tbody data-dock-log-body></tbody>
      </table>
    </div>
  </div>
</section>

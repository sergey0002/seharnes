<?php
/**
 * Содержимое «Контроля харнеса»: состояние переноса, задания, сканы, история.
 *
 * @var array<string, mixed> $status
 * @var list<array<string, mixed>> $history
 * @var \Seharnes\Panel\Support\I18n $i18n
 */
use Seharnes\Panel\Core\View;

$source = $status['source'];
$receipt = $status['receipt'];
$jobLabel = static function (array $job) use ($i18n): string {
    $key = 'action.' . (string) ($job['action'] ?? '');
    $value = $i18n->t($key);
    if ($value !== $key) {
        return $value;
    }
    return (string) ($job['label'] ?? $job['action'] ?? '');
};

$statusPill = static function (string $value): string {
    return match ($value) {
        'ok', 'done', 'passed' => 'ok',
        'failed', 'error' => 'bad',
        default => 'warn',
    };
};
$updates = [
    ['id' => 'harness_update', 'key' => 'harness.updatePreview', 'confirm' => true],
    ['id' => 'harness_update_apply', 'key' => 'harness.updateApply', 'confirm' => true, 'primary' => true],
];
$builds = [
    ['id' => 'harness_build', 'key' => 'action.harness_build'],
    ['id' => 'harness_check', 'key' => 'action.harness_check'],
    ['id' => 'harness_structure_strict', 'key' => 'action.harness_structure_strict'],
    ['id' => 'sync_views', 'key' => 'action.sync_views', 'confirm' => true],
];
?>
<section class="card" id="harness-source">
  <header class="card__head">
    <h2 class="card__title" data-i18n="harness.navSource"><?= View::e($i18n->t('harness.navSource')) ?></h2>
    <span class="card__hint" data-i18n="harness.navSourceHint"><?= View::e($i18n->t('harness.navSourceHint')) ?></span>
    <span class="card__state">
      <span class="pill pill--sm <?= $source['configured'] ? 'pill--ok' : 'pill--warn' ?>" data-harness-source-pill>
        <span data-i18n="<?= $source['configured'] ? 'harness.sourceOn' : 'harness.sourceOff' ?>"><?= View::e($i18n->t($source['configured'] ? 'harness.sourceOn' : 'harness.sourceOff')) ?></span>
      </span>
      <span class="pill pill--sm <?= $receipt['present'] ? 'pill--ok' : 'pill--warn' ?>" data-harness-receipt-pill>
        <span data-i18n="<?= $receipt['present'] ? 'harness.receiptOn' : 'harness.receiptOff' ?>"><?= View::e($i18n->t($receipt['present'] ? 'harness.receiptOn' : 'harness.receiptOff')) ?></span>
      </span>
    </span>
  </header>
  <div class="card__body">
    <dl class="facts">
      <div class="facts__row">
        <dt data-i18n="harness.source"><?= View::e($i18n->t('harness.source')) ?></dt>
        <dd>
          <?php if ($source['configured']): ?>
            <code><?= View::e($source['url']) ?></code>
            <span class="muted">ref <code><?= View::e($source['ref']) ?></code></span>
            <span class="muted" data-i18n="harness.profile"><?= View::e($i18n->t('harness.profile')) ?></span>
            <code><?= View::e($source['profile']) ?></code>
          <?php else: ?>
            <span class="pill pill--warn"><?= View::e($i18n->t('harness.sourceOff')) ?></span>
            <span class="muted">
              <span data-i18n="harness.sourceOffHint"><?= View::e($i18n->t('harness.sourceOffHint')) ?></span>
              <code>.doc/harness-source.json</code>
            </span>
          <?php endif; ?>
        </dd>
      </div>
      <div class="facts__row">
        <dt data-i18n="harness.receipt"><?= View::e($i18n->t('harness.receipt')) ?></dt>
        <dd>
          <?php if ($receipt['present']): ?>
            <span class="muted" data-i18n="harness.profile"><?= View::e($i18n->t('harness.profile')) ?></span>
            <code><?= View::e($receipt['profile']) ?></code>
            <span class="muted" data-i18n="harness.commit"><?= View::e($i18n->t('harness.commit')) ?></span>
            <code><?= View::e($receipt['commit']) ?></code>
            <span class="muted" data-i18n="harness.files"><?= View::e($i18n->t('harness.files')) ?></span>
            <b><?= (int) $receipt['files'] ?></b>
            <span class="muted"><?= View::e($receipt['mtime']) ?></span>
          <?php else: ?>
            <span class="pill pill--warn" data-i18n="harness.receiptOff"><?= View::e($i18n->t('harness.receiptOff')) ?></span>
            <span class="muted" data-i18n="harness.receiptOffHint"><?= View::e($i18n->t('harness.receiptOffHint')) ?></span>
          <?php endif; ?>
        </dd>
      </div>
      <div class="facts__row">
        <dt data-i18n="harness.root"><?= View::e($i18n->t('harness.root')) ?></dt>
        <dd><code><?= View::e((string) $status['root']) ?></code></dd>
      </div>
    </dl>
  </div>
</section>

<section class="card" id="harness-actions">
  <header class="card__head">
    <h2 class="card__title" data-i18n="harness.navActions"><?= View::e($i18n->t('harness.navActions')) ?></h2>
    <span class="card__hint" data-i18n="harness.navActionsHint"><?= View::e($i18n->t('harness.navActionsHint')) ?></span>
  </header>
  <div class="card__body">
    <div class="action-grid">
      <div class="action-block">
        <h3 class="action-block__title" data-i18n="harness.groupUpdate"><?= View::e($i18n->t('harness.groupUpdate')) ?></h3>
        <p class="action-block__note" data-i18n="harness.groupUpdateNote"><?= View::e($i18n->t('harness.groupUpdateNote')) ?></p>
        <div class="action-block__buttons">
          <?php foreach ($updates as $job): ?>
            <button type="button" class="ghost-btn<?= !empty($job['primary']) ? ' ghost-btn--primary' : '' ?>"
                    data-run-action="<?= View::e($job['id']) ?>"
                    <?= !empty($job['confirm']) ? 'data-confirm="1"' : '' ?>>
              <span data-i18n="<?= View::e($job['key']) ?>"><?= View::e($i18n->t($job['key'])) ?></span>
            </button>
          <?php endforeach; ?>
        </div>
      </div>
      <div class="action-block">
        <h3 class="action-block__title" data-i18n="harness.groupBuild"><?= View::e($i18n->t('harness.groupBuild')) ?></h3>
        <p class="action-block__note" data-i18n="harness.groupBuildNote"><?= View::e($i18n->t('harness.groupBuildNote')) ?></p>
        <div class="action-block__buttons">
          <?php foreach ($builds as $job): ?>
            <button type="button" class="ghost-btn" data-run-action="<?= View::e($job['id']) ?>"
                    <?= !empty($job['confirm']) ? 'data-confirm="1"' : '' ?>>
              <span data-i18n="<?= View::e($job['key']) ?>"><?= View::e($i18n->t($job['key'])) ?></span>
            </button>
          <?php endforeach; ?>
        </div>
      </div>
    </div>
  </div>
</section>

<section class="card" id="harness-scans">
  <header class="card__head">
    <h2 class="card__title" data-i18n="harness.navScans"><?= View::e($i18n->t('harness.navScans')) ?></h2>
    <span class="card__hint" data-i18n="harness.navScansHint"><?= View::e($i18n->t('harness.navScansHint')) ?></span>
    <span class="card__state" data-scan-state></span>
  </header>
  <div class="card__body">
    <div class="card__actions">
      <button type="button" class="ghost-btn" data-scan="canon"><span data-i18n="harness.scanCanon"><?= View::e($i18n->t('harness.scanCanon')) ?></span></button>
      <button type="button" class="ghost-btn" data-scan="links"><span data-i18n="harness.scanLinks"><?= View::e($i18n->t('harness.scanLinks')) ?></span></button>
      <button type="button" class="ghost-btn" data-scan="docs"><span data-i18n="harness.scanDocs"><?= View::e($i18n->t('harness.scanDocs')) ?></span></button>
      <button type="button" class="ghost-btn ghost-btn--primary" data-scan="canon,links,docs"><span data-i18n="harness.scanAll"><?= View::e($i18n->t('harness.scanAll')) ?></span></button>
    </div>
    <div class="scan-out" data-scan-out>
      <p class="muted" data-i18n="harness.scanIdle"><?= View::e($i18n->t('harness.scanIdle')) ?></p>
    </div>
  </div>
</section>

<section class="card" id="harness-history">
  <header class="card__head">
    <h2 class="card__title" data-i18n="harness.navHistory"><?= View::e($i18n->t('harness.navHistory')) ?></h2>
    <span class="card__hint" data-i18n="harness.navHistoryHint"><?= View::e($i18n->t('harness.navHistoryHint')) ?></span>
  </header>
  <div class="card__body">
    <?php if ($history === []): ?>
      <p class="muted" data-i18n="harness.noJobs"><?= View::e($i18n->t('harness.noJobs')) ?></p>
    <?php else: ?>
      <table class="table" data-harness-jobs>
        <thead>
          <tr>
            <th data-i18n="harness.colAction"><?= View::e($i18n->t('harness.colAction')) ?></th>
            <th data-i18n="harness.colStatus"><?= View::e($i18n->t('harness.colStatus')) ?></th>
            <th data-i18n="harness.colStarted"><?= View::e($i18n->t('harness.colStarted')) ?></th>
            <th data-i18n="harness.colEnded"><?= View::e($i18n->t('harness.colEnded')) ?></th>
            <th data-i18n="harness.colExit"><?= View::e($i18n->t('harness.colExit')) ?></th>
          </tr>
        </thead>
        <tbody>
          <?php foreach ($history as $job): ?>
            <tr>
              <td><?= View::e($jobLabel($job)) ?> <code class="muted"><?= View::e((string) ($job['action'] ?? '')) ?></code></td>
              <td><span class="pill pill--sm pill--<?= View::e($statusPill((string) ($job['status'] ?? ''))) ?>"><?= View::e((string) ($job['status'] ?? '?')) ?></span></td>
              <td><?= View::e(substr((string) ($job['started_at'] ?? ''), 11, 8)) ?></td>
              <td><?= View::e(substr((string) ($job['ended_at'] ?? ''), 11, 8)) ?></td>
              <td><?= View::e((string) ($job['exit_code'] ?? '')) ?></td>
            </tr>
          <?php endforeach; ?>
        </tbody>
      </table>
    <?php endif; ?>
  </div>
</section>

<?php
/**
 * Правая панель «Аналитики»: как считается срез и что в него входит.
 *
 * @var array<string, mixed> $data
 * @var \Seharnes\Panel\Support\I18n $i18n
 */
use Seharnes\Panel\Core\View;

$totals = $data['totals'];
$filters = $data['filters'];
$money = static fn (float $value): string => number_format($value, 2, ',', ' ');
$labels = [
    'q' => 'tasks.search',
    'project' => 'tasks.project',
    'release' => 'tasks.release',
    'assignee' => 'tasks.assignee',
];
?>
<div class="analyticdetail" data-analytics-detail>
  <h3 class="taskdetail__title" data-i18n="analytics.sliceTitle"><?= View::e($i18n->t('analytics.sliceTitle')) ?></h3>
  <dl class="kv kv--tight">
    <?php foreach ($labels as $key => $labelKey): ?>
      <div class="kv__row">
        <dt data-i18n="<?= View::e($labelKey) ?>"><?= View::e($i18n->t($labelKey)) ?></dt>
        <dd><?= View::e((string) ($filters[$key] ?? '') !== '' ? (string) $filters[$key] : $i18n->t('analytics.all')) ?></dd>
      </div>
    <?php endforeach; ?>
  </dl>

  <h4 class="block-head" data-i18n="analytics.tokensTitle"><?= View::e($i18n->t('analytics.tokensTitle')) ?></h4>
  <dl class="kv kv--tight">
    <div class="kv__row"><dt data-i18n="analytics.tokensIn"><?= View::e($i18n->t('analytics.tokensIn')) ?></dt>
      <dd><?= (int) ($totals['tokens_in'] ?? 0) ?></dd></div>
    <div class="kv__row"><dt data-i18n="analytics.tokensOut"><?= View::e($i18n->t('analytics.tokensOut')) ?></dt>
      <dd><?= (int) ($totals['tokens_out'] ?? 0) ?></dd></div>
    <div class="kv__row"><dt data-i18n="analytics.cacheRead"><?= View::e($i18n->t('analytics.cacheRead')) ?></dt>
      <dd><?= (int) ($totals['cache_read'] ?? 0) ?></dd></div>
    <div class="kv__row"><dt data-i18n="analytics.cacheWrite"><?= View::e($i18n->t('analytics.cacheWrite')) ?></dt>
      <dd><?= (int) ($totals['cache_write'] ?? 0) ?></dd></div>
    <div class="kv__row"><dt data-i18n="tasks.cost"><?= View::e($i18n->t('tasks.cost')) ?></dt>
      <dd><?= View::e($money((float) ($totals['cost'] ?? 0))) ?></dd></div>
  </dl>

  <h4 class="block-head" data-i18n="analytics.unassignedTitle"><?= View::e($i18n->t('analytics.unassignedTitle')) ?></h4>
  <p class="note">
    <?= View::e($i18n->t('analytics.unassignedNote', ['count' => (string) ($data['unassigned']['count'] ?? 0)])) ?>
  </p>
</div>

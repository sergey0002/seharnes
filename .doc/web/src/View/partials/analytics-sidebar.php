<?php
/**
 * Левая панель «Аналитики»: навигация по блокам и краткая сводка.
 *
 * @var array<string, mixed> $data
 * @var \Seharnes\Panel\Support\I18n $i18n
 */
use Seharnes\Panel\Core\View;

$totals = $data['totals'];
$sections = [
    ['id' => 'analytics-totals', 'key' => 'analytics.navTotals'],
    ['id' => 'analytics-tasks', 'key' => 'analytics.navTasks'],
    ['id' => 'analytics-breakdown', 'key' => 'analytics.navBreakdown'],
    ['id' => 'analytics-unassigned', 'key' => 'analytics.navUnassigned'],
];
?>
<div class="sidebar__head">
  <span class="sidebar__title" data-i18n="analytics.title"><?= View::e($i18n->t('analytics.title')) ?></span>
  <span class="counter counter--sm"><?= (int) ($totals['sessions'] ?? 0) ?></span>
</div>
<nav class="tree tree--nav" aria-label="<?= View::e($i18n->t('analytics.title')) ?>">
  <?php foreach ($sections as $item): ?>
    <a class="tree__item tree__item--link" href="#<?= View::e($item['id']) ?>" data-analytics-jump="<?= View::e($item['id']) ?>">
      <span data-i18n="<?= View::e($item['key']) ?>"><?= View::e($i18n->t($item['key'])) ?></span>
    </a>
  <?php endforeach; ?>
</nav>
<div class="sidebar__head sidebar__head--sub">
  <span class="sidebar__title" data-i18n="analytics.slice"><?= View::e($i18n->t('analytics.slice')) ?></span>
</div>
<dl class="kv kv--tight">
  <div class="kv__row"><dt data-i18n="analytics.sessions"><?= View::e($i18n->t('analytics.sessions')) ?></dt>
    <dd><?= (int) ($totals['sessions'] ?? 0) ?></dd></div>
  <div class="kv__row"><dt data-i18n="analytics.tasks"><?= View::e($i18n->t('analytics.tasks')) ?></dt>
    <dd><?= (int) ($totals['tasks'] ?? 0) ?></dd></div>
  <div class="kv__row"><dt data-i18n="analytics.requests"><?= View::e($i18n->t('analytics.requests')) ?></dt>
    <dd><?= (int) ($totals['requests'] ?? 0) ?></dd></div>
  <div class="kv__row"><dt data-i18n="tasks.unassigned"><?= View::e($i18n->t('tasks.unassigned')) ?></dt>
    <dd><?= (int) ($data['unassigned']['count'] ?? 0) ?></dd></div>
</dl>

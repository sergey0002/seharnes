<?php
/**
 * Правая панель «Задач»: детали выбранной задачи.
 *
 * @var array<string, mixed> $detail
 * @var string $id
 * @var \Seharnes\Panel\Support\I18n $i18n
 */
use Seharnes\Panel\Core\View;

$summary = $detail['summary'];
$totals = $detail['dialogs_total'];
$money = static fn (float $value): string => number_format($value, 2, ',', ' ');
?>
<div class="taskdetail" data-task-detail="<?= View::e($id) ?>">
  <h3 class="taskdetail__title"><?= View::e((string) $summary['title']) ?></h3>
  <p class="taskdetail__meta">
    <span class="badge">#<?= View::e((string) $summary['id']) ?></span>
    <span class="badge"><?= View::e((string) $summary['release']) ?></span>
    <?php if (($summary['jira_status'] ?? '') !== ''): ?>
      <span class="pill pill--sm"><?= View::e((string) $summary['jira_status']) ?></span>
    <?php endif; ?>
  </p>
  <dl class="kv kv--tight">
    <div class="kv__row"><dt data-i18n="tasks.col.assignee"><?= View::e($i18n->t('tasks.col.assignee')) ?></dt>
      <dd><?= View::e((string) ($summary['assignee'] ?: '—')) ?></dd></div>
    <div class="kv__row"><dt data-i18n="tasks.col.updated"><?= View::e($i18n->t('tasks.col.updated')) ?></dt>
      <dd><?= View::e((string) ($summary['jira_updated'] ?: '—')) ?></dd></div>
    <div class="kv__row"><dt data-i18n="tasks.col.files"><?= View::e($i18n->t('tasks.col.files')) ?></dt>
      <dd><?= (int) ($summary['n_files'] ?? 0) ?></dd></div>
    <div class="kv__row"><dt data-i18n="tasks.col.dialogs"><?= View::e($i18n->t('tasks.col.dialogs')) ?></dt>
      <dd><?= (int) ($totals['sessions'] ?? 0) ?></dd></div>
    <div class="kv__row"><dt data-i18n="tasks.cost"><?= View::e($i18n->t('tasks.cost')) ?></dt>
      <dd><?= View::e($money((float) ($totals['cost'] ?? 0))) ?></dd></div>
  </dl>

  <?php if ($detail['activity'] !== []): ?>
    <h4 class="block-head" data-i18n="tasks.activity"><?= View::e($i18n->t('tasks.activity')) ?></h4>
    <ul class="feed">
      <?php foreach ($detail['activity'] as $event): ?>
        <li class="feed__item">
          <span class="feed__kind"><?= View::e((string) ($event['kind'] ?? '')) ?></span>
          <span class="feed__author"><?= View::e((string) ($event['author'] ?? '')) ?></span>
          <time class="feed__time"><?= View::e((string) ($event['at'] ?? '')) ?></time>
          <p class="feed__text"><?= View::e(\Seharnes\Panel\Support\Cut::text((string) ($event['text'] ?? ''), 160)) ?></p>
        </li>
      <?php endforeach; ?>
    </ul>
  <?php endif; ?>

  <?php if ($detail['sessions'] !== []): ?>
    <h4 class="block-head" data-i18n="tasks.sessions"><?= View::e($i18n->t('tasks.sessions')) ?></h4>
    <ul class="feed">
      <?php foreach ($detail['sessions'] as $session): ?>
        <li class="feed__item">
          <span class="feed__kind"><?= View::e($session['role'] !== '' ? $session['role'] : 'session') ?></span>
          <span class="feed__author"><?= View::e($session['model']) ?></span>
          <span class="feed__time"><?= (int) $session['tokens'] ?> · <?= View::e($money((float) $session['cost'])) ?></span>
          <p class="feed__text"><?= View::e($session['title'] !== '' ? $session['title'] : $session['id']) ?></p>
        </li>
      <?php endforeach; ?>
    </ul>
  <?php endif; ?>

  <?php if ($detail['reports'] !== []): ?>
    <h4 class="block-head" data-i18n="tasks.reports"><?= View::e($i18n->t('tasks.reports')) ?></h4>
    <ul class="feed">
      <?php foreach ($detail['reports'] as $report): ?>
        <li class="feed__item">
          <a class="feed__link" href="/files/tasks/<?= View::e($id) ?>/reports/<?= View::e((string) ($report['report'] ?? '')) ?>/report.html">
            <?= View::e((string) ($report['report'] ?? '')) ?>
          </a>
          <span class="feed__time"><?= count((array) ($report['sources'] ?? [])) ?> src</span>
        </li>
      <?php endforeach; ?>
    </ul>
  <?php endif; ?>
</div>

<?php
/**
 * Содержимое «Задач»: сводка среза, таблица задач и, по запросу, диалоги без задачи.
 *
 * @var array<string, mixed> $list
 * @var string $selected
 * @var \Seharnes\Panel\Support\I18n $i18n
 */
use Seharnes\Panel\Core\View;

$totals = $list['totals'];
$rows = $list['rows'];
$money = static fn (float $value): string => number_format($value, 2, ',', ' ');
?>
<section class="card" data-tasks-summary>
  <div class="card__head">
    <h2 class="card__title" data-i18n="tasks.summary"><?= View::e($i18n->t('tasks.summary')) ?></h2>
    <span class="card__hint" data-tasks-summary-hint>
      <?= View::e($i18n->t('tasks.sliceHint')) ?>
    </span>
  </div>
  <div class="facts facts--compact">
    <div class="fact"><span class="fact__label" data-i18n="tasks.tasks"><?= View::e($i18n->t('tasks.tasks')) ?></span>
      <span class="fact__value" data-tasks-total-tasks><?= (int) $totals['tasks'] ?></span></div>
    <div class="fact"><span class="fact__label" data-i18n="tasks.dialogs"><?= View::e($i18n->t('tasks.dialogs')) ?></span>
      <span class="fact__value" data-tasks-total-dialogs><?= (int) $totals['dialogs'] ?></span></div>
    <div class="fact"><span class="fact__label" data-i18n="tasks.tokens"><?= View::e($i18n->t('tasks.tokens')) ?></span>
      <span class="fact__value" data-tasks-total-tokens><?= (int) $totals['tokens'] ?></span></div>
    <div class="fact"><span class="fact__label" data-i18n="tasks.cost"><?= View::e($i18n->t('tasks.cost')) ?></span>
      <span class="fact__value" data-tasks-total-cost><?= View::e($money((float) $totals['cost'])) ?></span></div>
    <div class="fact"><span class="fact__label" data-i18n="tasks.unassigned"><?= View::e($i18n->t('tasks.unassigned')) ?></span>
      <span class="fact__value" data-tasks-total-unassigned><?= (int) $totals['unassigned'] ?></span></div>
  </div>
</section>

<section class="card" data-tasks-table-card>
  <div class="card__head">
    <h2 class="card__title" data-i18n="tasks.tableTitle"><?= View::e($i18n->t('tasks.tableTitle')) ?></h2>
    <span class="card__hint" data-i18n="tasks.tableHint"><?= View::e($i18n->t('tasks.tableHint')) ?></span>
  </div>
  <?php if ($rows === []): ?>
    <p class="empty" data-tasks-table-empty>
      <?= View::e($i18n->t('tasks.empty')) ?>
      <?php if (!$list['available']): ?><br><span class="empty__hint"><?= View::e($i18n->t('tasks.noSource')) ?></span><?php endif; ?>
    </p>
  <?php else: ?>
    <table class="tbl" data-tasks-table>
      <thead>
        <tr>
          <th><?= View::e($i18n->t('tasks.col.id')) ?></th>
          <th><?= View::e($i18n->t('tasks.col.title')) ?></th>
          <th><?= View::e($i18n->t('tasks.col.release')) ?></th>
          <th><?= View::e($i18n->t('tasks.col.assignee')) ?></th>
          <th><?= View::e($i18n->t('tasks.col.status')) ?></th>
          <th class="num"><?= View::e($i18n->t('tasks.col.dialogs')) ?></th>
          <th class="num"><?= View::e($i18n->t('tasks.col.tokens')) ?></th>
          <th class="num"><?= View::e($i18n->t('tasks.col.cost')) ?></th>
          <th><?= View::e($i18n->t('tasks.col.updated')) ?></th>
        </tr>
      </thead>
      <tbody data-tasks-rows>
        <?php foreach ($rows as $row): ?>
          <tr data-task-row="<?= View::e($row['id']) ?>"
              class="<?= $row['id'] === $selected ? 'is-selected' : '' ?>">
            <td><a class="tbl__link" href="/panel/tasks?id=<?= View::e($row['id']) ?>" data-task-link="<?= View::e($row['id']) ?>">#<?= View::e($row['id']) ?></a></td>
            <td class="tbl__wrap" title="<?= View::e($row['title']) ?>"><?= View::e($row['title']) ?></td>
            <td><?= View::e($row['release']) ?></td>
            <td><?= View::e($row['assignee'] !== '' ? $row['assignee'] : '—') ?></td>
            <td><span class="pill pill--sm"><?= View::e($row['status'] !== '' ? $row['status'] : '—') ?></span></td>
            <td class="num"><?= (int) $row['dialogs'] ?></td>
            <td class="num"><?= (int) $row['tokens'] ?></td>
            <td class="num"><?= View::e($money((float) $row['cost'])) ?></td>
            <td><?= View::e($row['updated'] !== '' ? $row['updated'] : $row['touched']) ?></td>
          </tr>
        <?php endforeach; ?>
      </tbody>
    </table>
  <?php endif; ?>
</section>

<section class="card<?= $list['unassigned'] === [] ? ' is-hidden' : '' ?>" data-tasks-unassigned-card>
  <div class="card__head">
    <h2 class="card__title" data-i18n="tasks.unassignedTitle"><?= View::e($i18n->t('tasks.unassignedTitle')) ?></h2>
    <span class="card__hint" data-i18n="tasks.unassignedHint"><?= View::e($i18n->t('tasks.unassignedHint')) ?></span>
  </div>
  <?php if ($list['unassigned'] === []): ?>
    <p class="empty" data-tasks-unassigned-empty data-i18n="tasks.unassignedEmpty"><?= View::e($i18n->t('tasks.unassignedEmpty')) ?></p>
  <?php else: ?>
    <table class="tbl" data-tasks-unassigned-table>
      <thead>
        <tr>
          <th><?= View::e($i18n->t('tasks.col.session')) ?></th>
          <th><?= View::e($i18n->t('tasks.col.project')) ?></th>
          <th><?= View::e($i18n->t('tasks.col.title')) ?></th>
          <th><?= View::e($i18n->t('tasks.col.model')) ?></th>
          <th class="num"><?= View::e($i18n->t('tasks.col.requests')) ?></th>
          <th class="num"><?= View::e($i18n->t('tasks.col.tokens')) ?></th>
          <th><?= View::e($i18n->t('tasks.col.date')) ?></th>
        </tr>
      </thead>
      <tbody>
        <?php foreach ($list['unassigned'] as $row): ?>
          <tr data-session-row="<?= View::e($row['id']) ?>">
            <td><code><?= View::e(substr($row['id'], 0, 14)) ?>…</code></td>
            <td><?= View::e($row['project'] !== '' ? $row['project'] : '—') ?></td>
            <td class="tbl__wrap" title="<?= View::e($row['title']) ?>"><?= View::e($row['title']) ?></td>
            <td><?= View::e($row['model'] !== '' ? $row['model'] : '—') ?></td>
            <td class="num"><?= (int) $row['requests'] ?></td>
            <td class="num"><?= (int) $row['tokens'] ?></td>
            <td><?= View::e($row['date']) ?></td>
          </tr>
        <?php endforeach; ?>
      </tbody>
    </table>
  <?php endif; ?>
</section>

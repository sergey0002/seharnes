<?php
/**
 * Левая панель «Задач»: сам список задач как дерево-навигация.
 *
 * @var array<string, mixed> $list
 * @var \Seharnes\Panel\Support\I18n $i18n
 */
use Seharnes\Panel\Core\View;

$rows = $list['rows'];
$query = (string) $list['filters']['q'];
$release = (string) $list['filters']['release'];
$assignee = (string) $list['filters']['assignee'];
$project = (string) $list['filters']['project'];
$unassigned = (bool) $list['filters']['unassigned'];
$link = static function (array $extra) use ($query, $release, $assignee, $project, $unassigned): string {
    $params = array_filter([
        'q' => $query, 'release' => $release, 'assignee' => $assignee, 'project' => $project,
        'unassigned' => $unassigned ? '1' : '',
    ], static fn (string $value): bool => $value !== '');
    return '/panel/tasks?' . http_build_query($params + $extra);
};
?>
<div class="sidebar__head">
  <span class="sidebar__title" data-i18n="tasks.listTitle"><?= View::e($i18n->t('tasks.listTitle')) ?></span>
  <span class="counter counter--sm" data-tasks-side-count><?= count($rows) ?></span>
</div>
<?php if ($rows === []): ?>
  <p class="empty" data-tasks-empty data-i18n="tasks.empty"><?= View::e($i18n->t('tasks.empty')) ?></p>
<?php else: ?>
  <ul class="tasklist" data-tasks-side-list>
    <?php foreach ($rows as $row): ?>
      <li class="tasklist__item">
        <a class="tasklist__link" href="<?= View::e($link(['id' => $row['id']])) ?>"
           data-task-link="<?= View::e($row['id']) ?>">
          <span class="tasklist__id">#<?= View::e($row['id']) ?></span>
          <span class="tasklist__title" title="<?= View::e($row['title']) ?>"><?= View::e($row['title']) ?></span>
          <span class="tasklist__meta">
            <?= View::e($row['release']) ?><?php if ($row['dialogs'] > 0): ?> · <?= (int) $row['dialogs'] ?><?php endif; ?>
          </span>
        </a>
      </li>
    <?php endforeach; ?>
  </ul>
<?php endif; ?>

<div class="sidebar__head sidebar__head--sub">
  <span class="sidebar__title" data-i18n="tasks.withoutTask"><?= View::e($i18n->t('tasks.withoutTask')) ?></span>
  <span class="counter counter--sm"><?= (int) $list['totals']['unassigned'] ?></span>
</div>
<a class="ghost-btn ghost-btn--block" href="<?= View::e($link(['unassigned' => $unassigned ? '' : '1', 'id' => ''])) ?>"
   data-tasks-unassigned-link>
  <span data-i18n="<?= $unassigned ? 'tasks.hideUnassigned' : 'tasks.showUnassigned' ?>">
    <?= View::e($i18n->t($unassigned ? 'tasks.hideUnassigned' : 'tasks.showUnassigned')) ?>
  </span>
</a>

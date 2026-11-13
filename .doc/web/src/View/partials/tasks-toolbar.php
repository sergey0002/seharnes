<?php
/**
 * Кнопки раздела «Задачи»: поиск и срез по проекту, релизу, ответственному.
 *
 * Фильтры уходят в строку запроса (ссылку можно переслать) и в API `/panel/api/tasks`,
 * поэтому обновление списка не перерисовывает страницу.
 *
 * @var array<string, mixed> $filters
 * @var array<string, mixed> $options
 * @var array<string, mixed> $totals
 * @var \Seharnes\Panel\Support\I18n $i18n
 */
use Seharnes\Panel\Core\View;

$select = static function (string $name, string $labelKey, string $current, array $values, $i18n, string $allKey): void {
    ?>
    <label class="select">
      <span class="visually-hidden" data-i18n="<?= View::e($labelKey) ?>"><?= View::e($i18n->t($labelKey)) ?></span>
      <select data-tasks-filter="<?= View::e($name) ?>">
        <option value="" data-i18n="<?= View::e($allKey) ?>"><?= View::e($i18n->t($allKey)) ?></option>
        <?php foreach ($values as $value): ?>
          <?php $value = is_array($value) ? $value : ['id' => (string) $value, 'label' => (string) $value]; ?>
          <option value="<?= View::e((string) $value['id']) ?>"<?= (string) $value['id'] === $current ? ' selected' : '' ?>>
            <?= View::e((string) $value['label']) ?>
          </option>
        <?php endforeach; ?>
      </select>
    </label>
    <?php
};
?>
<div class="toolbar__group toolbar__group--grow">
  <label class="search">
    <span class="visually-hidden" data-i18n="tasks.search"><?= View::e($i18n->t('tasks.search')) ?></span>
    <input type="search" placeholder="<?= View::e($i18n->t('tasks.search')) ?>"
           value="<?= View::e((string) $filters['q']) ?>" data-tasks-search data-i18n-placeholder="tasks.search">
  </label>
  <?php
  $select('project', 'tasks.project', (string) $filters['project'], $options['projects'], $i18n, 'tasks.allProjects');
  $select('release', 'tasks.release', (string) $filters['release'], $options['releases'], $i18n, 'tasks.allReleases');
  $select('assignee', 'tasks.assignee', (string) $filters['assignee'], $options['assignees'], $i18n, 'tasks.allAssignees');
  ?>
  <label class="check">
    <input type="checkbox" data-tasks-unassigned<?= $filters['unassigned'] ? ' checked' : '' ?>>
    <span data-i18n="tasks.withoutTask"><?= View::e($i18n->t('tasks.withoutTask')) ?></span>
  </label>
</div>
<div class="toolbar__group">
  <span class="counter counter--sm" data-tasks-counter
        title="<?= View::e($i18n->t('tasks.tasks')) ?>"><?= (int) $totals['tasks'] ?></span>
  <button type="button" class="ghost-btn" data-tasks-reset>
    <span data-i18n="tasks.reset"><?= View::e($i18n->t('tasks.reset')) ?></span>
  </button>
</div>

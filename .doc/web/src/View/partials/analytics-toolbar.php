<?php
/**
 * Кнопки раздела «Аналитика»: тот же срез, что у «Задач», плюс кнопка обновления.
 *
 * @var array<string, mixed> $filters
 * @var array<string, mixed> $options
 * @var \Seharnes\Panel\Support\I18n $i18n
 */
use Seharnes\Panel\Core\View;

$select = static function (string $name, string $labelKey, string $current, array $values, $i18n, string $allKey): void {
    ?>
    <label class="select">
      <span class="visually-hidden" data-i18n="<?= View::e($labelKey) ?>"><?= View::e($i18n->t($labelKey)) ?></span>
      <select data-analytics-filter="<?= View::e($name) ?>">
        <option value=""><?= View::e($i18n->t($allKey)) ?></option>
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
    <span class="visually-hidden"><?= View::e($i18n->t('tasks.search')) ?></span>
    <input type="search" placeholder="<?= View::e($i18n->t('tasks.search')) ?>"
           value="<?= View::e((string) $filters['q']) ?>" data-analytics-search>
  </label>
  <?php
  $select('project', 'tasks.project', (string) $filters['project'], $options['projects'], $i18n, 'tasks.allProjects');
  $select('release', 'tasks.release', (string) $filters['release'], $options['releases'], $i18n, 'tasks.allReleases');
  $select('assignee', 'tasks.assignee', (string) $filters['assignee'], $options['assignees'], $i18n, 'tasks.allAssignees');
  ?>
</div>
<div class="toolbar__group">
  <button type="button" class="ghost-btn" data-analytics-reset>
    <span data-i18n="tasks.reset"><?= View::e($i18n->t('tasks.reset')) ?></span>
  </button>
</div>

<?php
/**
 * Правая панель «Задач», пока ничего не выбрано.
 *
 * @var \Seharnes\Panel\Support\I18n $i18n
 */
use Seharnes\Panel\Core\View;
?>
<div class="placeholder" data-task-detail-empty>
  <p class="placeholder__title" data-i18n="tasks.pickTitle"><?= View::e($i18n->t('tasks.pickTitle')) ?></p>
  <p class="placeholder__text" data-i18n="tasks.pickHint"><?= View::e($i18n->t('tasks.pickHint')) ?></p>
</div>

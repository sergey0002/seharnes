<?php
/**
 * Правая панель «Контроля харнеса»: сводка последнего скана.
 *
 * До первого скана показывает, что именно проверяет каждый скан: пустая панель
 * выглядит как поломка, поэтому здесь всегда есть объяснение.
 *
 * @var array<string, mixed> $status
 * @var \Seharnes\Panel\Support\I18n $i18n
 */
use Seharnes\Panel\Core\View;
?>
<div class="scan-summary" data-scan-summary>
  <p class="muted" data-i18n="harness.scanIdle"><?= View::e($i18n->t('harness.scanIdle')) ?></p>
  <ul class="scan-summary__list">
    <li>
      <b data-i18n="harness.scanCanon"><?= View::e($i18n->t('harness.scanCanon')) ?></b>
      <span data-i18n="harness.scanCanonNote"><?= View::e($i18n->t('harness.scanCanonNote')) ?></span>
    </li>
    <li>
      <b data-i18n="harness.scanLinks"><?= View::e($i18n->t('harness.scanLinks')) ?></b>
      <span data-i18n="harness.scanLinksNote"><?= View::e($i18n->t('harness.scanLinksNote')) ?></span>
    </li>
    <li>
      <b data-i18n="harness.scanDocs"><?= View::e($i18n->t('harness.scanDocs')) ?></b>
      <span data-i18n="harness.scanDocsNote"><?= View::e($i18n->t('harness.scanDocsNote')) ?></span>
    </li>
  </ul>
</div>

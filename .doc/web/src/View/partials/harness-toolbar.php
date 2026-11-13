<?php
/**
 * Кнопки раздела «Контроль харнеса».
 *
 * Слева — сканы (они не меняют дерево), справа — задания (меняют и потому спрашивают
 * подтверждение). Каждая кнопка привязана к реальному действию: задание уходит в док,
 * скан отвечает прямо на страницу.
 *
 * @var array<string, mixed> $status
 * @var \Seharnes\Panel\Support\I18n $i18n
 */
use Seharnes\Panel\Core\View;

$scans = [
    ['id' => 'canon', 'key' => 'harness.scanCanon'],
    ['id' => 'links', 'key' => 'harness.scanLinks'],
    ['id' => 'docs', 'key' => 'harness.scanDocs'],
    ['id' => 'canon,links,docs', 'key' => 'harness.scanAll'],
];
$jobs = [
    ['id' => 'harness_build', 'key' => 'action.harness_build'],
    ['id' => 'harness_check', 'key' => 'action.harness_check'],
    ['id' => 'harness_structure_strict', 'key' => 'action.harness_structure_strict'],
    ['id' => 'sync_views', 'key' => 'action.sync_views'],
];
?>
<div class="toolbar__group toolbar__group--grow">
  <span class="toolbar__title" data-i18n="harness.scansTitle"><?= View::e($i18n->t('harness.scansTitle')) ?></span>
  <?php foreach ($scans as $scan): ?>
    <button type="button" class="ghost-btn" data-scan="<?= View::e($scan['id']) ?>">
      <span data-i18n="<?= View::e($scan['key']) ?>"><?= View::e($i18n->t($scan['key'])) ?></span>
    </button>
  <?php endforeach; ?>
</div>
<div class="toolbar__group">
  <?php foreach ($jobs as $job): ?>
    <button type="button" class="ghost-btn" data-run-action="<?= View::e($job['id']) ?>">
      <span data-i18n="<?= View::e($job['key']) ?>"><?= View::e($i18n->t($job['key'])) ?></span>
    </button>
  <?php endforeach; ?>
</div>

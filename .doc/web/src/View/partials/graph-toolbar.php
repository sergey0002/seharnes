<?php
/**
 * Кнопки раздела «Граф харнеса»: фильтры и действия (задания).
 *
 * @var array<string, mixed> $summary
 * @var \Seharnes\Panel\Support\I18n $i18n
 */
use Seharnes\Panel\Core\View;

$jobs = [
    ['id' => 'harness_build', 'key' => 'action.harness_build'],
    ['id' => 'harness_check', 'key' => 'action.harness_check'],
    ['id' => 'harness_structure_strict', 'key' => 'action.harness_structure_strict'],
    ['id' => 'sync_views', 'key' => 'action.sync_views', 'confirm' => true],
];
?>
<div class="toolbar__group toolbar__group--grow">
  <label class="search">
    <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>
    <input type="search" data-graph-search
           placeholder="<?= View::e($i18n->t('graph.searchPlaceholder')) ?>"
           aria-label="<?= View::e($i18n->t('graph.searchPlaceholder')) ?>">
  </label>
  <label class="select">
    <span class="select__label" data-i18n="graph.kindLabel"><?= View::e($i18n->t('graph.kindLabel')) ?></span>
    <select data-graph-kind>
      <option value="" data-i18n="graph.kindAll"><?= View::e($i18n->t('graph.kindAll')) ?></option>
      <?php foreach ($summary['kinds'] as $kind => $count): ?>
        <option value="<?= View::e($kind) ?>"><?= View::e($kind) ?> · <?= (int) $count ?></option>
      <?php endforeach; ?>
    </select>
  </label>
</div>
<div class="toolbar__group">
  <span class="stats">
    <span class="stat"><b data-stat-nodes><?= (int) $summary['nodes'] ?></b> <span data-i18n="graph.nodes"><?= View::e($i18n->t('graph.nodes')) ?></span></span>
    <span class="stat"><b data-stat-edges><?= (int) $summary['edges'] ?></b> <span data-i18n="graph.edges"><?= View::e($i18n->t('graph.edges')) ?></span></span>
  </span>
  <?php foreach ($jobs as $job): ?>
    <button type="button" class="ghost-btn" data-run-action="<?= View::e($job['id']) ?>"
            <?= !empty($job['confirm']) ? 'data-confirm="1"' : '' ?>>
      <span data-i18n="<?= View::e($job['key']) ?>"><?= View::e($i18n->t($job['key'])) ?></span>
    </button>
  <?php endforeach; ?>
</div>

<?php
/**
 * Левая панель графа: фильтры и дерево файлов.
 *
 * Дерево строится клиентом из компактного ответа /api/graph/view: один запрос на
 * весь граф. Здесь только каркас — узлы, папки и подсветку рисует graph.js.
 *
 * @var array<string, mixed> $summary
 * @var array<string, int> $kinds
 * @var \Seharnes\Panel\Support\I18n $i18n
 */
use Seharnes\Panel\Core\View;
?>
<div class="sidebar__head">
  <span class="sidebar__title" data-i18n="graph.elements"><?= View::e($i18n->t('graph.elements')) ?></span>
  <span class="counter counter--sm" data-graph-count><?= (int) $summary['nodes'] ?></span>
</div>

<div class="tree__filters">
  <label class="check">
    <input type="checkbox" data-graph-linked>
    <span data-i18n="graph.linkedOnly"><?= View::e($i18n->t('graph.linkedOnly')) ?></span>
  </label>
  <label class="check">
    <input type="checkbox" data-graph-isolated>
    <span data-i18n="graph.isolatedOnly"><?= View::e($i18n->t('graph.isolatedOnly')) ?></span>
  </label>
  <label class="check">
    <input type="checkbox" data-graph-edges checked>
    <span data-i18n="graph.showEdges"><?= View::e($i18n->t('graph.showEdges')) ?></span>
  </label>
  <label class="check">
    <input type="checkbox" data-graph-mirrors>
    <span data-i18n="graph.withMirrors"><?= View::e($i18n->t('graph.withMirrors')) ?></span>
  </label>
</div>

<?php if (!$summary['available']): ?>
  <div class="note note--warn">
    <strong data-i18n="graph.notBuilt"><?= View::e($i18n->t('graph.notBuilt')) ?></strong>
    <p data-i18n="graph.notBuiltHint"><?= View::e($i18n->t('graph.notBuiltHint')) ?></p>
  </div>
<?php endif; ?>

<nav class="tree tree--nodes" data-graph-list aria-label="<?= View::e($i18n->t('graph.elements')) ?>">
  <p class="muted" data-i18n="common.loading"><?= View::e($i18n->t('common.loading')) ?></p>
</nav>

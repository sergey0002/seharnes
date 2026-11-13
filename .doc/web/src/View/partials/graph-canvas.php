<?php
/**
 * Центр графа: SVG-канвас с карточками, зум, панорамирование, фокус и легенда.
 *
 * Карточки рисует graph.js: раскладка по колонкам типов повторяет старый
 * просмотрщик миррора, поэтому имена типов и их порядок заданы здесь же.
 *
 * @var array<string, mixed> $summary
 * @var \Seharnes\Panel\Support\I18n $i18n
 */
use Seharnes\Panel\Core\View;
?>
<div class="canvas-wrap" data-graph-canvas-wrap>
  <div class="canvas" data-graph-canvas>
    <svg class="canvas__svg" data-graph-svg role="img"
         aria-label="<?= View::e($i18n->t('graph.canvasLabel')) ?>"></svg>
  </div>
  <div class="canvas__empty" data-graph-empty<?= $summary['available'] ? ' hidden' : '' ?>>
    <h2 data-i18n="graph.notBuilt"><?= View::e($i18n->t('graph.notBuilt')) ?></h2>
    <p data-i18n="graph.notBuiltHint"><?= View::e($i18n->t('graph.notBuiltHint')) ?></p>
  </div>
  <div class="canvas__hud">
    <button type="button" class="icon-btn" data-graph-zoom="in" title="+">+</button>
    <button type="button" class="icon-btn" data-graph-zoom="out" title="−">−</button>
    <button type="button" class="icon-btn" data-graph-zoom="fit" title="<?= View::e($i18n->t('graph.fit')) ?>">⤢</button>
  </div>
  <button type="button" class="canvas__focus" data-graph-focus-clear hidden>
    <span data-graph-focus-label></span>
    <b aria-hidden="true">×</b>
  </button>
  <div class="canvas__legend" data-graph-legend>
    <?php foreach ($summary['kinds'] as $kind => $count): ?>
      <span class="legend__item"><i class="dot dot--<?= View::e($kind) ?>" aria-hidden="true"></i><?= View::e($kind) ?><b><?= (int) $count ?></b></span>
    <?php endforeach; ?>
  </div>
</div>

<?php
/**
 * Низ правой панели графа: связи выбранного элемента и JSON узла.
 *
 * Пока элемент не выбран, здесь объяснение, что появится: пустая панель читается
 * как поломка. После выбора содержимое рисует graph.js из ответа `GET graph/node`.
 *
 * @var \Seharnes\Panel\Support\I18n $i18n
 */
use Seharnes\Panel\Core\View;
?>
<div class="api-blocks" data-graph-api>
  <p class="muted" data-i18n="graph.apiIdle"><?= View::e($i18n->t('graph.apiIdle')) ?></p>
</div>

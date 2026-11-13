<?php
/**
 * Левая панель документации: список, сгруппированный по источнику.
 *
 * @var array<string, list<\Seharnes\Panel\Domain\Doc\DocItem>> $groups
 * @var string|null $selected
 * @var int $total
 * @var \Seharnes\Panel\Support\I18n $i18n
 * @var string $base
 */
use Seharnes\Panel\Core\View;
?>
<div class="sidebar__head">
  <span class="sidebar__title" data-i18n="docs.listTitle"><?= View::e($i18n->t('docs.listTitle')) ?></span>
  <span class="counter counter--sm"><?= (int) $total ?></span>
</div>
<nav class="tree" data-docs-list>
  <?php if ($groups === []): ?>
    <p class="empty" data-i18n="docs.noResults"><?= View::e($i18n->t('docs.noResults')) ?></p>
  <?php endif; ?>
  <?php foreach ($groups as $source => $items): ?>
    <div class="tree__group" data-source="<?= View::e($source) ?>">
      <div class="tree__group-head">
        <span class="tree__group-title" data-i18n="docs.source.<?= View::e($source) ?>"><?= View::e($i18n->t('docs.source.' . $source)) ?></span>
        <span class="counter counter--sm"><?= count($items) ?></span>
      </div>
      <ul class="tree__list">
        <?php foreach ($items as $item): ?>
          <li>
            <a class="tree__item<?= $item->id === $selected ? ' is-active' : '' ?>"
               href="<?= View::e($base . '/docs/' . $item->id) ?>"
               data-doc-id="<?= View::e($item->id) ?>"
               title="<?= View::e($item->path) ?>">
              <span class="tree__label"><?= View::e($item->title) ?></span>
              <span class="tree__meta"><?= View::e($item->path) ?></span>
            </a>
          </li>
        <?php endforeach; ?>
      </ul>
    </div>
  <?php endforeach; ?>
</nav>

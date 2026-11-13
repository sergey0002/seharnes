<?php
/**
 * Кнопки раздела «Документация».
 *
 * @var string $query
 * @var string $source
 * @var list<string> $sources
 * @var int $total
 * @var \Seharnes\Panel\Support\I18n $i18n
 */
use Seharnes\Panel\Core\View;
?>
<div class="toolbar__group toolbar__group--grow">
  <label class="search">
    <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>
    <input type="search" data-docs-search value="<?= View::e($query) ?>"
           placeholder="<?= View::e($i18n->t('docs.searchPlaceholder')) ?>"
           aria-label="<?= View::e($i18n->t('docs.searchPlaceholder')) ?>">
  </label>
  <label class="select">
    <span class="select__label" data-i18n="docs.sourceLabel"><?= View::e($i18n->t('docs.sourceLabel')) ?></span>
    <select data-docs-source>
      <option value="" data-i18n="docs.sourceAll"><?= View::e($i18n->t('docs.sourceAll')) ?></option>
      <?php foreach ($sources as $code): ?>
        <option value="<?= View::e($code) ?>"<?= $code === $source ? ' selected' : '' ?>
                data-i18n="docs.source.<?= View::e($code) ?>"><?= View::e($i18n->t('docs.source.' . $code)) ?></option>
      <?php endforeach; ?>
    </select>
  </label>
</div>
<div class="toolbar__group">
  <span class="counter" data-docs-counter><?= View::e($i18n->t('docs.counter', ['count' => $total])) ?></span>
  <button type="button" class="ghost-btn" data-docs-refresh title="<?= View::e($i18n->t('toolbar.refresh')) ?>">
    <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/></svg>
    <span data-i18n="toolbar.refresh"><?= View::e($i18n->t('toolbar.refresh')) ?></span>
  </button>
</div>

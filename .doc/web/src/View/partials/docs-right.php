<?php
/**
 * Правая панель для документа: повторное использование того же компонента, что и в графе.
 *
 * @var \Seharnes\Panel\Domain\Doc\DocItem|null $doc
 * @var \Seharnes\Panel\Support\I18n $i18n
 */
use Seharnes\Panel\Core\View;

if ($doc === null): ?>
  <p class="muted" data-i18n="right.selectElement"><?= View::e($i18n->t('right.selectElement')) ?></p>
  <?php return; endif; ?>
<dl class="kv">
  <div class="kv__row"><dt data-i18n="docs.title"><?= View::e($i18n->t('docs.title')) ?></dt><dd><?= View::e($doc->title) ?></dd></div>
  <div class="kv__row"><dt data-i18n="docs.file"><?= View::e($i18n->t('docs.file')) ?></dt><dd><code><?= View::e($doc->path) ?></code></dd></div>
  <div class="kv__row"><dt data-i18n="docs.sourceLabel"><?= View::e($i18n->t('docs.sourceLabel')) ?></dt><dd data-i18n="docs.source.<?= View::e($doc->source) ?>"><?= View::e($i18n->t('docs.source.' . $doc->source)) ?></dd></div>
  <div class="kv__row"><dt data-i18n="docs.format"><?= View::e($i18n->t('docs.format')) ?></dt><dd><?= View::e(strtoupper($doc->format)) ?></dd></div>
  <div class="kv__row"><dt data-i18n="docs.status"><?= View::e($i18n->t('docs.status')) ?></dt><dd><?= View::e($doc->status !== '' ? $doc->status : $i18n->t('common.notSet')) ?></dd></div>
  <div class="kv__row"><dt data-i18n="docs.updated"><?= View::e($i18n->t('docs.updated')) ?></dt><dd><?= View::e($doc->updated) ?></dd></div>
  <div class="kv__row"><dt data-i18n="docs.toc"><?= View::e($i18n->t('docs.toc')) ?></dt><dd><?= count($doc->toc) ?></dd></div>
</dl>

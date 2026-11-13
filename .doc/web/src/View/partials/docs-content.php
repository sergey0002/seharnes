<?php
/**
 * Центральная часть документа: шапка, оглавление, тело, находки.
 *
 * @var \Seharnes\Panel\Domain\Doc\DocItem|null $doc
 * @var \Seharnes\Panel\Support\I18n $i18n
 * @var string $base
 */
use Seharnes\Panel\Core\View;
use Seharnes\Panel\Support\Markdown;

if ($doc === null): ?>
  <div class="placeholder" data-docs-placeholder>
    <div class="placeholder__icon" aria-hidden="true">
      <svg viewBox="0 0 24 24"><path d="M6 3.5h8l4 4v13H6z"/><path d="M14 3.5v4h4"/><path d="M9 12h6M9 16h6"/></svg>
    </div>
    <h1 class="placeholder__title" data-i18n="docs.placeholderTitle"><?= View::e($i18n->t('docs.placeholderTitle')) ?></h1>
    <p class="placeholder__text" data-i18n="docs.placeholderText"><?= View::e($i18n->t('docs.placeholderText')) ?></p>
  </div>
  <?php return; endif; ?>

<article class="doc" data-doc-view="<?= View::e($doc->id) ?>">
  <header class="doc__head">
    <div class="doc__crumbs">
      <a href="<?= View::e($base . '/docs') ?>" data-i18n="nav.docs"><?= View::e($i18n->t('nav.docs')) ?></a>
      <span aria-hidden="true">/</span>
      <span data-i18n="docs.source.<?= View::e($doc->source) ?>"><?= View::e($i18n->t('docs.source.' . $doc->source)) ?></span>
    </div>
    <h1 class="doc__title"><?= View::e($doc->title) ?></h1>
    <dl class="doc__facts">
      <div class="fact"><dt data-i18n="docs.file"><?= View::e($i18n->t('docs.file')) ?></dt><dd><code><?= View::e($doc->path) ?></code></dd></div>
      <div class="fact"><dt data-i18n="docs.status"><?= View::e($i18n->t('docs.status')) ?></dt><dd><?= View::e($doc->status !== '' ? $doc->status : $i18n->t('common.notSet')) ?></dd></div>
      <div class="fact"><dt data-i18n="docs.updated"><?= View::e($i18n->t('docs.updated')) ?></dt><dd><?= View::e($doc->updated) ?></dd></div>
    </dl>
  </header>

  <?php if ($doc->toc !== []): ?>
    <nav class="toc" aria-label="<?= View::e($i18n->t('docs.toc')) ?>">
      <h2 class="toc__title" data-i18n="docs.toc"><?= View::e($i18n->t('docs.toc')) ?></h2>
      <ul class="toc__list">
        <?php foreach ($doc->toc as $entry): ?>
          <li class="toc__item toc__item--l<?= (int) $entry['level'] ?>">
            <a href="#<?= View::e($entry['id']) ?>"><?= View::e($entry['title']) ?></a>
          </li>
        <?php endforeach; ?>
      </ul>
    </nav>
  <?php endif; ?>

  <div class="doc__body prose">
    <?php if ($doc->markdown !== null): ?>
      <?= Markdown::renderDocument($doc->markdown) ?>
    <?php endif; ?>
    <?php foreach ($doc->sections as $section): ?>
      <section id="<?= View::e($section['id']) ?>">
        <h2><?= View::e($section['title']) ?></h2>
        <?= Markdown::render($section['body_markdown']) ?>
      </section>
    <?php endforeach; ?>
  </div>

  <?php if ($doc->findings !== []): ?>
    <section class="findings">
      <h2 data-i18n="docs.findings"><?= View::e($i18n->t('docs.findings')) ?> (<?= count($doc->findings) ?>)</h2>
      <?php foreach ($doc->findings as $finding): ?>
        <article class="finding">
          <h3 class="finding__title"><?= View::e(trim($finding['id'] . ' ' . $finding['title'])) ?></h3>
          <div class="prose"><?= Markdown::render($finding['statement']) ?></div>
        </article>
      <?php endforeach; ?>
    </section>
  <?php endif; ?>
</article>

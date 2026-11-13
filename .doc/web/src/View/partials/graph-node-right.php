<?php
/**
 * Правая панель графа: карточка выбранного элемента.
 *
 * Верх карточки — что это за файл; дальше содержимое: просмотр и, если сервер
 * разрешил запись (EditPolicy), редактор с сохранением в канонический файл.
 *
 * @var array<string, mixed>|null $detail
 * @var \Seharnes\Panel\Support\I18n $i18n
 */
use Seharnes\Panel\Core\View;
use Seharnes\Panel\Support\Markdown;

if ($detail === null): ?>
  <p class="muted" data-i18n="graph.selectNode"><?= View::e($i18n->t('graph.selectNode')) ?></p>
  <?php return; endif;

$node = $detail['node'];
$relations = $detail['relations'];
$file = is_array($detail['file'] ?? null) ? $detail['file'] : ['editable' => false, 'reason' => 'no-path', 'path' => ''];
$blocks = $detail['blocks'] ?? [];
$nodeKind = (string) ($detail['node_kind'] ?? $node['kind']);
?>
<div class="node-card" data-node-card data-node-id="<?= View::e($node['id']) ?>">
  <div class="node-card__head">
    <span class="chip chip--<?= View::e($node['kind']) ?>"><?= View::e($node['kind']) ?></span>
    <h3 class="node-card__title"><?= View::e($node['label']) ?></h3>
    <?php if (!$node['canonical']): ?>
      <span class="tag tag--warn" data-i18n="graph.copyTag"><?= View::e($i18n->t('graph.copyTag')) ?></span>
    <?php endif; ?>
    <button type="button" class="ghost-btn ghost-btn--sm" data-node-focus="<?= View::e($node['id']) ?>">
      <span data-i18n="graph.focus"><?= View::e($i18n->t('graph.focus')) ?></span>
    </button>
  </div>

  <dl class="kv kv--tight">
    <div class="kv__row"><dt data-i18n="graph.nodeId"><?= View::e($i18n->t('graph.nodeId')) ?></dt><dd><code><?= View::e($node['id']) ?></code></dd></div>
    <?php if ($node['path'] !== ''): ?>
      <div class="kv__row"><dt data-i18n="graph.nodePath"><?= View::e($i18n->t('graph.nodePath')) ?></dt>
        <dd><code data-node-path><?= View::e($node['path']) ?></code></dd></div>
    <?php endif; ?>
    <div class="kv__row"><dt data-i18n="graph.nodeEnv"><?= View::e($i18n->t('graph.nodeEnv')) ?></dt><dd><?= View::e($node['environment'] !== '' ? $node['environment'] : '—') ?></dd></div>
    <div class="kv__row"><dt data-i18n="graph.nodeCanonical"><?= View::e($i18n->t('graph.nodeCanonical')) ?></dt>
      <dd><?= $node['canonical'] ? View::e($i18n->t('common.yes')) : View::e($i18n->t('common.no')) ?></dd></div>
  </dl>

  <section class="node-card__file" data-node-file
           data-editable="<?= $file['editable'] ? '1' : '0' ?>"
           data-reason="<?= View::e((string) ($file['reason'] ?? '')) ?>">
    <div class="editor__bar">
      <span class="editor__title" data-i18n="graph.fileTitle"><?= View::e($i18n->t('graph.fileTitle')) ?></span>
      <span class="editor__state muted" data-editor-state></span>
      <?php if ($file['editable']): ?>
        <button type="button" class="ghost-btn ghost-btn--sm" data-node-edit data-i18n="graph.edit"><?= View::e($i18n->t('graph.edit')) ?></button>
        <button type="button" class="primary-btn primary-btn--sm" data-node-save hidden data-i18n="graph.save"><?= View::e($i18n->t('graph.save')) ?></button>
        <button type="button" class="ghost-btn ghost-btn--sm" data-node-reset hidden data-i18n="graph.reset"><?= View::e($i18n->t('graph.reset')) ?></button>
      <?php else: ?>
        <span class="tag" data-i18n="graph.readOnly"><?= View::e($i18n->t('graph.readOnly')) ?></span>
      <?php endif; ?>
      <button type="button" class="ghost-btn ghost-btn--sm" data-node-reload data-i18n="graph.reload"><?= View::e($i18n->t('graph.reload')) ?></button>
    </div>

    <div class="node-card__content prose" data-node-preview>
      <?php foreach ($blocks as $block): ?>
        <?php if ($block['header'] !== ''): ?><h4 class="block-head"><?= View::e($block['header']) ?></h4><?php endif; ?>
        <?php if ($block['type'] === 'frontmatter'): ?>
          <details class="frontmatter"><summary>front matter</summary>
            <pre class="code"><code><?= View::e($block['raw']) ?></code></pre>
          </details>
        <?php elseif (in_array($nodeKind, ['script', 'config'], true)): ?>
          <pre class="code"><code><?= View::e($block['raw']) ?></code></pre>
        <?php else: ?>
          <?= Markdown::render($block['raw']) ?>
        <?php endif; ?>
      <?php endforeach; ?>
      <?php if ($blocks === [] && ($detail['status'] ?? '') === 'empty'): ?>
        <p class="muted" data-i18n="graph.noContent"><?= View::e($i18n->t('graph.noContent')) ?></p>
      <?php endif; ?>
    </div>

    <?php if ($file['editable']): ?>
      <textarea class="node-card__source" data-node-source hidden spellcheck="false"
                aria-label="<?= View::e($i18n->t('graph.fileTitle')) ?>"><?= View::e((string) ($file['content'] ?? '')) ?></textarea>
    <?php endif; ?>
  </section>

</div>

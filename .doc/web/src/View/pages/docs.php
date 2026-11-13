<?php
/**
 * Страница раздела «Документация».
 *
 * @var string $contentHtml
 * @var array<string, mixed> $boot
 */
use Seharnes\Panel\Core\View;
?>
<div class="docview" data-docs-root data-selected="<?= View::e((string) ($boot['selected'] ?? '')) ?>">
  <?= $contentHtml ?>
</div>

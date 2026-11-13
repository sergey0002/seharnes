<?php
/**
 * Левая панель «Контроля харнеса»: навигация по блокам и последние задания.
 *
 * @var array<string, mixed> $status
 * @var list<array<string, mixed>> $history
 * @var \Seharnes\Panel\Support\I18n $i18n
 */
use Seharnes\Panel\Core\View;

$sections = [
    ['id' => 'harness-source', 'key' => 'harness.navSource'],
    ['id' => 'harness-actions', 'key' => 'harness.navActions'],
    ['id' => 'harness-scans', 'key' => 'harness.navScans'],
    ['id' => 'harness-history', 'key' => 'harness.navHistory'],
];
$jobLabel = static function (array $job) use ($i18n): string {
    $key = 'action.' . (string) ($job['action'] ?? '');
    $value = $i18n->t($key);
    if ($value !== $key) {
        return $value;
    }
    return (string) ($job['label'] ?? $job['action'] ?? '');
};

$statusPill = static function (string $value): string {
    return match ($value) {
        'ok', 'done', 'passed' => 'ok',
        'failed', 'error' => 'bad',
        default => 'warn',
    };
};
?>
<div class="sidebar__head">
  <span class="sidebar__title" data-i18n="harness.title"><?= View::e($i18n->t('harness.title')) ?></span>
  <span class="counter counter--sm"><?= count($history) ?></span>
</div>
<nav class="tree tree--nav" aria-label="<?= View::e($i18n->t('harness.title')) ?>">
  <?php foreach ($sections as $item): ?>
    <a class="tree__item tree__item--link" href="#<?= View::e($item['id']) ?>" data-harness-jump="<?= View::e($item['id']) ?>">
      <span data-i18n="<?= View::e($item['key']) ?>"><?= View::e($i18n->t($item['key'])) ?></span>
    </a>
  <?php endforeach; ?>
</nav>

<div class="sidebar__head sidebar__head--sub">
  <span class="sidebar__title" data-i18n="harness.recentJobs"><?= View::e($i18n->t('harness.recentJobs')) ?></span>
</div>
<?php if ($history === []): ?>
  <p class="empty" data-i18n="harness.noJobs"><?= View::e($i18n->t('harness.noJobs')) ?></p>
<?php else: ?>
  <ul class="joblist" data-harness-history>
    <?php foreach ($history as $job): ?>
      <li class="joblist__item">
        <span class="pill pill--sm pill--<?= View::e($statusPill((string) ($job['status'] ?? ''))) ?>">
          <?= View::e((string) ($job['status'] ?? '?')) ?>
        </span>
        <span class="joblist__action" title="<?= View::e((string) ($job['id'] ?? '')) ?>">
          <?= View::e($jobLabel($job)) ?>
        </span>
        <time class="joblist__time"><?= View::e(substr((string) ($job['started_at'] ?? ''), 11, 8)) ?></time>
      </li>
    <?php endforeach; ?>
  </ul>
<?php endif; ?>

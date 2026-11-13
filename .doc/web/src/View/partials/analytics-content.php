<?php
/**
 * Содержимое «Аналитики»: итоги среза, задачи, разрезы и диалоги без задачи.
 *
 * @var array<string, mixed> $data
 * @var \Seharnes\Panel\Support\I18n $i18n
 */
use Seharnes\Panel\Core\View;

$totals = $data['totals'];
$money = static fn (float $value): string => number_format($value, 2, ',', ' ');
$minutes = static fn (int|float $ms): string => $ms <= 0 ? '—' : (string) round(((float) $ms) / 60000);
$tokens = (int) ($totals['tokens_in'] ?? 0) + (int) ($totals['tokens_out'] ?? 0) + (int) ($totals['tokens_reasoning'] ?? 0);
?>
<section class="card" id="analytics-totals">
  <div class="card__head">
    <h2 class="card__title" data-i18n="analytics.totalsTitle"><?= View::e($i18n->t('analytics.totalsTitle')) ?></h2>
    <span class="card__hint" data-i18n="analytics.totalsHint"><?= View::e($i18n->t('analytics.totalsHint')) ?></span>
  </div>
  <div class="facts facts--compact">
    <div class="fact"><span class="fact__label" data-i18n="analytics.tasks"><?= View::e($i18n->t('analytics.tasks')) ?></span>
      <span class="fact__value"><?= (int) ($totals['tasks'] ?? 0) ?></span></div>
    <div class="fact"><span class="fact__label" data-i18n="analytics.sessions"><?= View::e($i18n->t('analytics.sessions')) ?></span>
      <span class="fact__value"><?= (int) ($totals['sessions'] ?? 0) ?></span></div>
    <div class="fact"><span class="fact__label" data-i18n="analytics.requests"><?= View::e($i18n->t('analytics.requests')) ?></span>
      <span class="fact__value"><?= (int) ($totals['requests'] ?? 0) ?></span></div>
    <div class="fact"><span class="fact__label" data-i18n="tasks.tokens"><?= View::e($i18n->t('tasks.tokens')) ?></span>
      <span class="fact__value"><?= (int) $tokens ?></span></div>
    <div class="fact"><span class="fact__label" data-i18n="tasks.cost"><?= View::e($i18n->t('tasks.cost')) ?></span>
      <span class="fact__value"><?= View::e($money((float) ($totals['cost'] ?? 0))) ?></span></div>
    <div class="fact"><span class="fact__label" data-i18n="analytics.active"><?= View::e($i18n->t('analytics.active')) ?></span>
      <span class="fact__value"><?= View::e($minutes((float) ($totals['active_ms'] ?? 0))) ?></span></div>
  </div>
</section>

<section class="card" id="analytics-tasks">
  <div class="card__head">
    <h2 class="card__title" data-i18n="analytics.byTask"><?= View::e($i18n->t('analytics.byTask')) ?></h2>
    <span class="card__hint" data-i18n="analytics.byTaskHint"><?= View::e($i18n->t('analytics.byTaskHint')) ?></span>
  </div>
  <?php if ($data['tasks'] === []): ?>
    <p class="empty" data-analytics-empty>
      <?= View::e($i18n->t('analytics.empty')) ?>
      <?php if (!$data['available']): ?><br><span class="empty__hint"><?= View::e($i18n->t('tasks.noSource')) ?></span><?php endif; ?>
    </p>
  <?php else: ?>
    <table class="tbl">
      <thead>
        <tr>
          <th><?= View::e($i18n->t('tasks.col.id')) ?></th>
          <th><?= View::e($i18n->t('tasks.col.title')) ?></th>
          <th class="num"><?= View::e($i18n->t('analytics.sessions')) ?></th>
          <th class="num"><?= View::e($i18n->t('tasks.tokens')) ?></th>
          <th class="num"><?= View::e($i18n->t('analytics.requests')) ?></th>
          <th class="num"><?= View::e($i18n->t('analytics.active')) ?></th>
          <th class="num"><?= View::e($i18n->t('tasks.cost')) ?></th>
        </tr>
      </thead>
      <tbody>
        <?php foreach ($data['tasks'] as $row): ?>
          <tr>
            <td><a class="tbl__link" href="/panel/tasks?id=<?= View::e((string) $row['id']) ?>">#<?= View::e((string) $row['id']) ?></a></td>
            <td class="tbl__wrap" title="<?= View::e((string) $row['title']) ?>"><?= View::e((string) $row['title']) ?></td>
            <td class="num"><?= (int) $row['sessions'] ?></td>
            <td class="num"><?= (int) $row['tokens'] ?></td>
            <td class="num"><?= (int) $row['requests'] ?></td>
            <td class="num"><?= View::e($minutes((float) $row['active_ms'])) ?></td>
            <td class="num"><?= View::e($money((float) $row['cost'])) ?></td>
          </tr>
        <?php endforeach; ?>
      </tbody>
    </table>
  <?php endif; ?>
</section>

<section class="card" id="analytics-breakdown">
  <div class="card__head">
    <h2 class="card__title" data-i18n="analytics.breakdown"><?= View::e($i18n->t('analytics.breakdown')) ?></h2>
    <span class="card__hint" data-i18n="analytics.breakdownHint"><?= View::e($i18n->t('analytics.breakdownHint')) ?></span>
  </div>
  <div class="bargrid">
    <?php
    $blocks = [
        ['key' => 'analytics.models', 'rows' => $data['models']],
        ['key' => 'analytics.tools', 'rows' => $data['tools']],
        ['key' => 'analytics.mcp', 'rows' => $data['mcp']],
        ['key' => 'analytics.providers', 'rows' => $data['providers']],
        ['key' => 'analytics.roles', 'rows' => $data['roles']],
    ];
    $peak = 1;
    foreach ($blocks as $block) {
        foreach ($block['rows'] as $row) {
            $peak = max($peak, (int) $row['value']);
        }
    }
    ?>
    <?php foreach ($blocks as $block): ?>
      <div class="bargrid__block">
        <h3 class="block-head" data-i18n="<?= View::e($block['key']) ?>"><?= View::e($i18n->t($block['key'])) ?></h3>
        <?php if ($block['rows'] === []): ?>
          <p class="empty" data-i18n="analytics.noData"><?= View::e($i18n->t('analytics.noData')) ?></p>
        <?php else: ?>
          <ul class="barlist">
            <?php foreach ($block['rows'] as $row): ?>
              <li class="barlist__item">
                <span class="barlist__label" title="<?= View::e($row['label']) ?>"><?= View::e($row['label']) ?></span>
                <span class="barlist__bar" style="width: <?= (int) round(100 * $row['value'] / $peak) ?>%"></span>
                <span class="barlist__value"><?= (int) $row['value'] ?></span>
              </li>
            <?php endforeach; ?>
          </ul>
        <?php endif; ?>
      </div>
    <?php endforeach; ?>
  </div>
</section>

<section class="card" id="analytics-unassigned">
  <div class="card__head">
    <h2 class="card__title" data-i18n="tasks.unassignedTitle"><?= View::e($i18n->t('tasks.unassignedTitle')) ?></h2>
    <span class="card__hint" data-i18n="tasks.unassignedHint"><?= View::e($i18n->t('tasks.unassignedHint')) ?></span>
  </div>
  <?php if ($data['unassigned']['rows'] === []): ?>
    <p class="empty" data-i18n="tasks.unassignedEmpty"><?= View::e($i18n->t('tasks.unassignedEmpty')) ?></p>
  <?php else: ?>
    <table class="tbl">
      <thead>
        <tr>
          <th><?= View::e($i18n->t('tasks.col.session')) ?></th>
          <th><?= View::e($i18n->t('tasks.col.project')) ?></th>
          <th><?= View::e($i18n->t('tasks.col.model')) ?></th>
          <th class="num"><?= View::e($i18n->t('tasks.col.requests')) ?></th>
          <th class="num"><?= View::e($i18n->t('tasks.col.tokens')) ?></th>
          <th><?= View::e($i18n->t('tasks.col.date')) ?></th>
        </tr>
      </thead>
      <tbody>
        <?php foreach ($data['unassigned']['rows'] as $row): ?>
          <tr>
            <td><code><?= View::e(substr($row['id'], 0, 14)) ?>…</code></td>
            <td><?= View::e($row['project'] !== '' ? $row['project'] : '—') ?></td>
            <td><?= View::e($row['model'] !== '' ? $row['model'] : '—') ?></td>
            <td class="num"><?= (int) $row['requests'] ?></td>
            <td class="num"><?= (int) $row['tokens'] ?></td>
            <td><?= View::e($row['date']) ?></td>
          </tr>
        <?php endforeach; ?>
      </tbody>
    </table>
  <?php endif; ?>
</section>

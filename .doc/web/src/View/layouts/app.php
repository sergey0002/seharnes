<?php
/**
 * Каркас страницы: верхнее меню, кнопки раздела, три колонки, нижний док.
 *
 * @var string $content
 * @var string $toolbar
 * @var string $sidebar
 * @var string $right
 * @var string $section
 * @var string $title
 * @var array<string, mixed> $boot
 * @var \Seharnes\Panel\Support\I18n $i18n
 * @var string $base
 */
use Seharnes\Panel\Core\View;

$sections = [
    ['id' => 'graph', 'href' => $base . '/graph', 'key' => 'nav.graph', 'legacy' => false],
    ['id' => 'docs', 'href' => $base . '/docs', 'key' => 'nav.docs', 'legacy' => false],
    ['id' => 'tasks', 'href' => $base . '/tasks', 'key' => 'nav.tasks', 'legacy' => false],
    ['id' => 'analytics', 'href' => $base . '/analytics', 'key' => 'nav.analytics', 'legacy' => false],
    ['id' => 'harness', 'href' => $base . '/harness', 'key' => 'nav.admin', 'legacy' => false],
];
$langs = $i18n->available();
// Версия статики: браузер не должен держать старый main.js после правок панели.
// Иначе новый HTML работает со старым модулем — и раздел «просто не работает».
$assetFiles = [
    __DIR__ . '/../../../public/assets/js/main.js',
    __DIR__ . '/../../../public/assets/js/pages/graph.js',
    __DIR__ . '/../../../public/assets/css/graph.css',
    __DIR__ . '/../../../public/assets/css/layout.css',
];
$assetVersion = substr((string) max(array_map(static fn (string $file): int => is_file($file) ? (int) filemtime($file) : 0, $assetFiles)), -6);
?><!DOCTYPE html>
<html lang="<?= View::e($i18n->lang()) ?>" data-theme="system">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= View::e($title) ?> · <?= View::e($i18n->t('app.title')) ?></title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%232f7bf6'/%3E%3Cpath d='M9 21V11l7 5 7-5v10' fill='none' stroke='%23fff' stroke-width='2.2' stroke-linejoin='round'/%3E%3C/svg%3E">
<link rel="stylesheet" href="/assets/css/tokens.css?v=<?= $assetVersion ?>">
<link rel="stylesheet" href="/assets/css/base.css?v=<?= $assetVersion ?>">
<link rel="stylesheet" href="/assets/css/layout.css?v=<?= $assetVersion ?>">
<link rel="stylesheet" href="/assets/css/components.css?v=<?= $assetVersion ?>">
<link rel="stylesheet" href="/assets/css/graph.css?v=<?= $assetVersion ?>">
<link rel="stylesheet" href="/assets/css/harness.css?v=<?= $assetVersion ?>">
<link rel="stylesheet" href="/assets/css/tasks.css?v=<?= $assetVersion ?>">
<script>
/* Тема применяется до первой отрисовки, чтобы не было вспышки светлой темы. */
(function () {
  try {
    var mode = localStorage.getItem('panel.theme') || 'system';
    var dark = mode === 'dark' || (mode === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
    document.documentElement.dataset.themeMode = mode;
  } catch (e) {}
})();
</script>
</head>
<body class="app" data-section="<?= View::e($section) ?>">
<a class="skip-link" href="#main"><?= View::e($i18n->t('a11y.skipToContent')) ?></a>

<header class="topbar">
  <button type="button" class="icon-btn topbar__drawer" data-drawer-toggle
          title="<?= View::e($i18n->t('sidebar.toggle')) ?>"
          aria-label="<?= View::e($i18n->t('sidebar.toggle')) ?>"
          aria-controls="panel-sidebar" aria-expanded="false">
    <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>
  </button>
  <a class="brand" href="<?= View::e($base) ?>/graph">
    <span class="brand__mark" aria-hidden="true"></span>
    <span class="brand__text">
      <strong data-i18n="app.title"><?= View::e($i18n->t('app.title')) ?></strong>
      <small data-i18n="app.subtitle"><?= View::e($i18n->t('app.subtitle')) ?></small>
    </span>
  </a>

  <nav class="nav" aria-label="<?= View::e($i18n->t('nav.sections')) ?>">
    <?php foreach ($sections as $item): ?>
      <a class="nav__item<?= $item['id'] === $section ? ' is-active' : '' ?><?= $item['legacy'] ? ' is-legacy' : '' ?>"
         href="<?= View::e($item['href']) ?>"
         <?= $item['id'] === $section ? 'aria-current="page"' : '' ?>>
        <span data-i18n="<?= View::e($item['key']) ?>"><?= View::e($i18n->t($item['key'])) ?></span>
        <?php if ($item['legacy']): ?><span class="nav__dot" title="<?= View::e($i18n->t('nav.legacyHint')) ?>"></span><?php endif; ?>
      </a>
    <?php endforeach; ?>
  </nav>

  <div class="topbar__tools">
    <label class="select select--compact" title="<?= View::e($i18n->t('lang.label')) ?>">
      <span class="visually-hidden"><?= View::e($i18n->t('lang.label')) ?></span>
      <select data-lang-switch>
        <?php foreach ($langs as $lang): ?>
          <option value="<?= View::e($lang) ?>"<?= $lang === $i18n->lang() ? ' selected' : '' ?>><?= View::e(strtoupper($lang)) ?></option>
        <?php endforeach; ?>
      </select>
    </label>
    <button type="button" class="icon-btn" data-theme-toggle
            title="<?= View::e($i18n->t('theme.toggle')) ?>"
            aria-label="<?= View::e($i18n->t('theme.toggle')) ?>">
      <svg class="icon icon--sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1"/></svg>
      <svg class="icon icon--moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/></svg>
    </button>
  </div>
</header>

<div class="toolbar" role="toolbar" aria-label="<?= View::e($i18n->t('toolbar.section')) ?>">
  <?= $toolbar ?>
</div>

<div class="workspace" data-workspace data-drawer="closed">
  <div class="drawer-scrim" data-drawer-close aria-hidden="true"></div>
  <aside class="sidebar" id="panel-sidebar" aria-label="<?= View::e($i18n->t('sidebar.label')) ?>">
    <?= $sidebar ?>
  </aside>

  <main class="content" id="main" tabindex="-1">
    <?= $content ?>
  </main>

  <aside class="rightpanel" aria-label="<?= View::e($i18n->t('rightpanel.label')) ?>" data-right-panel>
    <div class="rightpanel__top" data-right-top>
      <div class="panel-head">
        <h2 class="panel-head__title"><?= View::e($rightTitle ?? $i18n->t('right.title.element')) ?></h2>
        <span class="panel-head__hint" data-right-kind></span>
        <span class="panel-head__progress" data-right-progress hidden aria-hidden="true"></span>
      </div>
      <div class="panel-body" data-right-element><?= $right ?? '' ?></div>
    </div>
    <div class="rightpanel__splitter" role="separator" aria-orientation="horizontal" tabindex="0"
         aria-label="<?= View::e($i18n->t('rightpanel.resize')) ?>" data-right-splitter></div>
    <div class="rightpanel__bottom" data-right-bottom>
      <div class="panel-head">
        <h2 class="panel-head__title"><?= View::e($rightApiTitle ?? $i18n->t('right.title.api')) ?></h2>
        <span class="panel-head__hint" data-right-api-hint><?= View::e($rightApiHint ?? '') ?></span>
      </div>
      <div class="panel-body" data-right-api>
        <?php if (!empty($rightApiHtml)): ?>
          <?= $rightApiHtml ?>
        <?php elseif (!empty($rightApi)): ?>
          <?php /* Первый экран отдаётся сервером: та же нагрузка, что придёт из API, видна до JS. */ ?>
          <pre class="api-json"><?= View::e((string) json_encode(
              $rightApi,
              JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES
          )) ?></pre>
        <?php else: ?>
          <p class="muted" data-i18n="right.empty"><?= View::e($i18n->t('right.empty')) ?></p>
        <?php endif; ?>
      </div>
    </div>
  </aside>
</div>

<?php require __DIR__ . '/../partials/dock.php'; ?>

<script type="application/json" id="panel-boot"><?= json_encode($boot + [
    'base' => $base,
    'lang' => $i18n->lang(),
    'availableLangs' => $langs,
    'dictionary' => $i18n->dictionary(),
    'endpoints' => [
        'health' => $base . '/api/health',
        'actions' => $base . '/api/actions',
        'docs' => $base . '/api/docs',
        'docItem' => $base . '/api/docs/item',
        'graphSummary' => $base . '/api/graph/summary',
        'graphView' => $base . '/api/graph/view',
        'graphNode' => $base . '/api/graph/node',
        'tasksList' => $base . '/api/tasks',
        'taskItem' => $base . '/api/tasks/item',
        'analytics' => $base . '/api/analytics',
        'harnessStatus' => $base . '/api/harness/status',
        'harnessAudit' => $base . '/api/harness/audit',
        'jobs' => $base . '/api/jobs',
        'jobStatus' => $base . '/api/jobs/status',
        'i18n' => $base . '/api/i18n',
    ],
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_HEX_TAG | JSON_HEX_AMP) ?></script>
<script type="module" src="/assets/js/main.js?v=<?= $assetVersion ?>"></script>
</body>
</html>

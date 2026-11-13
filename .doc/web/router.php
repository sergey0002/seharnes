<?php
// Роутер для php -S (docroot .doc/web): все ведет в public/.
// Статика отдается вручную, страницы рендерит public/index.php.
// Панель часто открывают во встроенном предпросмотре: страница живёт в iframe с
// sandbox="allow-scripts", её источник — «null». Для такого окна ES-модули и fetch
// считаются кросс-доменными запросами, поэтому отдаём CORS-заголовки всем ответам.
// Предпросмотр без этого вообще не запускает JS: дерево навсегда остаётся «Загрузка…».
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Headers: X-Requested-With, Content-Type');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Cross-Origin-Resource-Policy: cross-origin');
if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'OPTIONS') {
    http_response_code(204);
    return true;
}

$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$public = realpath(__DIR__ . '/public');

// Корень отдаёт новый каркас без редиректа: предпросмотр и закладка открывают панель
// одним запросом (302 в iframe-предпросмотре иногда даёт пустой экран). Меняем только
// путь запроса — дальше работает обычная ветка /panel/.
// Старая панель не удалена: её страницы живут по своим адресам
// (/index.php?tab=tasks|docs, /harness/, /harness-admin/, /jobs).
if ($path === '/' || $path === '') {
    $_SERVER['REQUEST_URI'] = '/panel/graph';
    $path = '/panel/graph';
}
require_once __DIR__ . '/app/lib.php';
require_once __DIR__ . '/app/harness.php';
require_once __DIR__ . '/app/harness_admin.php';
require_once __DIR__ . '/app/jobs.php';

// Новый каркас панели: /panel/... (документация и граф). Старые маршруты работают как раньше.
if ($path === '/panel' || strpos($path, '/panel/') === 0) {
    require_once __DIR__ . '/src/Autoload.php';
    \Seharnes\Panel\Autoload::register(__DIR__ . '/src');
    \Seharnes\Panel\App::boot(__DIR__)
        ->handle(\Seharnes\Panel\Core\Request::capture())
        ->send();
    return true;
}
// Прямые пути public: /index.php, /assets/*
if ($path === '/index.php') {
    require __DIR__ . '/public/index.php';
    return true;
}
if (strpos($path, '/assets/') === 0) {
    $file = realpath(__DIR__ . '/public' . $path);
    if ($file !== false && strpos($file, $public) === 0 && is_file($file)) {
        $ext = strtolower(pathinfo($file, PATHINFO_EXTENSION));
        $types = array(
            'css' => 'text/css; charset=utf-8', 'js' => 'application/javascript; charset=utf-8',
            'mjs' => 'application/javascript; charset=utf-8', 'json' => 'application/json; charset=utf-8',
            'map' => 'application/json; charset=utf-8', 'png' => 'image/png', 'jpg' => 'image/jpeg',
            'svg' => 'image/svg+xml', 'ico' => 'image/x-icon', 'woff2' => 'font/woff2',
            'webmanifest' => 'application/manifest+json',
        );
        header('Content-Type: ' . (isset($types[$ext]) ? $types[$ext] : 'application/octet-stream'));
        // Панель правится каждый день: старый модуль из кеша ломает новый HTML.
        header('Cache-Control: no-store, must-revalidate');
        readfile($file);
        return true;
    }
    http_response_code(404);
    echo 'not found';
    return true;
}
// Внутренние каталоги сервиса не отдаются наружу.
if (strpos($path, '/bin/') === 0 || strpos($path, '/config/') === 0) {
    http_response_code(404);
    echo 'not found';
    return true;
}
// Задания панели: /jobs
if ($path === '/jobs' || strpos($path, '/jobs/') === 0) {
    jobs_handle($path);
    return true;
}
// Админка харнеса: контроль канона, обновление из Git, сканы. До /harness/.
if ($path === '/harness-admin' || strpos($path, '/harness-admin/') === 0) {
    harness_admin_serve($path);
    return true;
}
// Просмотрщик и API харнес-миррора: /harness/
if ($path === '/harness' || strpos($path, '/harness/') === 0) {
    harness_serve($path);
    return true;
}
// Статика .doc для отчётов: /files/tasks/{N}/reports/change-report/report.html
// и относительные картинки отчёта. Только чтение, только внутри .doc.
if (strpos($path, '/files/') === 0) {
    $docRoot = realpath(__DIR__ . '/..');
    $relative = rawurldecode(substr($path, 7));
    $safe = $docRoot !== false && preg_match('~^tasks/([0-9]+)/reports/change-report/(.+)$~D', $relative, $match);
    $candidate = $docRoot;
    if ($safe) {
        foreach (explode('/', $relative) as $segment) {
            if ($segment === '' || $segment[0] === '.' || strpos($segment, chr(0)) !== false || strpos($segment, chr(92)) !== false || strpos($segment, ':') !== false) {
                $safe = false;
                break;
            }
            $candidate .= DIRECTORY_SEPARATOR . $segment;
            if (is_link($candidate)) {
                $safe = false;
                break;
            }
        }
    }
    $expectedRoot = $safe ? $docRoot . DIRECTORY_SEPARATOR . 'tasks' . DIRECTORY_SEPARATOR . $match[1] . DIRECTORY_SEPARATOR . 'reports' . DIRECTORY_SEPARATOR . 'change-report' : false;
    $reportRoot = $safe ? realpath($expectedRoot) : false;
    $rootMatches = $reportRoot !== false && (DIRECTORY_SEPARATOR === chr(92) ? strcasecmp($reportRoot, $expectedRoot) === 0 : $reportRoot === $expectedRoot);
    $file = $safe ? realpath($candidate) : false;
    if ($file !== false && $rootMatches && is_file($file) && strpos($file, $reportRoot . DIRECTORY_SEPARATOR) === 0) {
        $ext = strtolower(pathinfo($file, PATHINFO_EXTENSION));
        $types = array(
            'html' => 'text/html; charset=utf-8', 'css' => 'text/css', 'js' => 'application/javascript',
            'png' => 'image/png', 'jpg' => 'image/jpeg', 'jpeg' => 'image/jpeg', 'gif' => 'image/gif',
            'webp' => 'image/webp', 'svg' => 'image/svg+xml', 'ico' => 'image/x-icon',
            'json' => 'application/json', 'md' => 'text/plain; charset=utf-8',
            'txt' => 'text/plain; charset=utf-8', 'pdf' => 'application/pdf',
        );
        if (!isset($types[$ext])) {
            http_response_code(404);
            echo 'file not found';
            return true;
        }
        header('X-Content-Type-Options: nosniff');
        header('Content-Type: ' . $types[$ext]);
        readfile($file);
        return true;
    }
    http_response_code(404);
    echo 'file not found';
    return true;
}
if (preg_match('~^/report/(\d+)$~', $path, $m)) {
    header('Location: /files/tasks/' . $m[1] . '/reports/change-report/report.html', true, 302);
    return true;
}
// Красивые пути старой панели: /docs, /analytics, /tasks, /task/2605, /index.php.
// Любой другой адрес — 404, а не «старая панель по умолчанию»: раньше случайный путь
// (например, чужой /leaderboard?_rsc=…) молча отдавал старый интерфейс, и его принимали
// за новый. Неизвестный адрес теперь честно говорит, что его нет, и даёт ссылку на /panel/graph.
$legacy = $path === '/index.php' || $path === '/tasks' || strpos($path, '/docs') === 0
    || strpos($path, '/analytics') === 0 || preg_match('~^/task/\d+~', $path) === 1;
if (!$legacy) {
    http_response_code(404);
    header('Content-Type: text/html; charset=utf-8');
    header('Cache-Control: no-store');
    echo '<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><title>Нет такой страницы</title></head>'
        . '<body style="margin:0;display:grid;place-items:center;height:100vh;background:#14161a;color:#e6e9ee;'
        . 'font:15px/1.5 system-ui,sans-serif"><div style="text-align:center;max-width:34rem;padding:24px">'
        . '<p style="font:600 20px/1.3 system-ui,sans-serif;margin:0 0 8px">Страница не найдена</p>'
        . '<p style="margin:0 0 16px;color:#9aa4b2">Здесь нет панели: ' . htmlspecialchars($path, ENT_QUOTES, 'UTF-8') . '</p>'
        . '<p style="margin:0"><a href="/panel/graph" style="display:inline-block;padding:8px 16px;border-radius:8px;'
        . 'background:#2f7bf6;color:#fff;text-decoration:none">Открыть граф панели</a></p>'
        . '<p style="margin:16px 0 0;color:#6b7280;font-size:13px">Старые разделы: '
        . '<a href="/index.php?tab=tasks" style="color:#9aa4b2">Задачи</a> · '
        . '<a href="/docs" style="color:#9aa4b2">Документация</a> · '
        . '<a href="/harness/" style="color:#9aa4b2">Просмотрщик зеркала</a></p>'
        . '</div></body></html>';
    return true;
}
if (strpos($path, '/docs') === 0) {
    $_GET['tab'] = 'docs';
} elseif (strpos($path, '/analytics') === 0) {
    $_GET['tab'] = 'analytics';
} elseif (preg_match('~^/task/(\d+)~', $path, $m)) {
    $_GET['tab'] = 'tasks';
    $_GET['id'] = $m[1];
} else {
    $_GET['tab'] = 'tasks';
}
require __DIR__ . '/public/index.php';

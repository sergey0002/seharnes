<?php
// Роутер для php -S (docroot .doc/web): все ведет в public/.
// Статика отдается вручную, страницы рендерит public/index.php.
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$public = realpath(__DIR__ . '/public');
require_once __DIR__ . '/app/lib.php';
require_once __DIR__ . '/app/harness.php';
require_once __DIR__ . '/app/jobs.php';

// Прямые пути public: /index.php, /assets/*
if ($path === '/index.php' || $path === '/' || $path === '') {
    require __DIR__ . '/public/index.php';
    return true;
}
if (strpos($path, '/assets/') === 0) {
    $file = realpath(__DIR__ . '/public' . $path);
    if ($file !== false && strpos($file, $public) === 0 && is_file($file)) {
        $ext = strtolower(pathinfo($file, PATHINFO_EXTENSION));
        $types = array('css' => 'text/css', 'js' => 'application/javascript', 'png' => 'image/png', 'svg' => 'image/svg+xml', 'ico' => 'image/x-icon');
        header('Content-Type: ' . (isset($types[$ext]) ? $types[$ext] : 'application/octet-stream'));
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
// Красивые пути /docs, /analytics, /tasks, /task/2605 и т.п.
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

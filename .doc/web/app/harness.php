<?php
// Harness mirror inside the panel: read-only static viewer and API.
// PHP 7.1 compatible.

function harness_config() {
    static $cfg = null;
    if ($cfg !== null) {
        return $cfg;
    }
    $defaults = array(
        'schema' => 1,
        'name' => 'copytrust-tools',
        'version' => '0.1.0',
        'data_dir' => '.doc/skil_data/mirror',
        'state_dir' => '.doc/web/state',
        'writable' => false,
    );
    $path = __DIR__ . '/../config/service.json';
    $raw = @file_get_contents($path);
    $data = $raw === false ? null : json_decode($raw, true);
    $cfg = is_array($data) ? array_merge($defaults, $data) : $defaults;
    return $cfg;
}

function harness_data_dir() {
    static $dir = null;
    if ($dir !== null) {
        return $dir;
    }
    $root = repo_root();
    $rel = (string) harness_config()['data_dir'];
    $dir = $root !== false ? realpath($root . '/' . $rel) : false;
    return $dir;
}

function harness_contained($abs) {
    $real = realpath($abs);
    $base = harness_data_dir();
    if ($real === false || $base === false) {
        return false;
    }
    return $real === $base || strpos($real, $base . DIRECTORY_SEPARATOR) === 0;
}

function harness_read_json($abs) {
    if (!harness_contained($abs)) {
        return null;
    }
    $raw = @file_get_contents($abs);
    if ($raw === false) {
        return null;
    }
    $data = json_decode($raw, true);
    return is_array($data) ? $data : null;
}

function harness_graph() {
    static $graph = null;
    if ($graph !== null) {
        return $graph;
    }
    $dir = harness_data_dir();
    $graph = $dir !== false ? harness_read_json($dir . '/graph.json') : null;
    return $graph;
}

function harness_stats() {
    $graph = harness_graph();
    return is_array($graph) && isset($graph['stats']) && is_array($graph['stats']) ? $graph['stats'] : array();
}

function harness_send_json($payload, $code = 200) {
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    header('X-Content-Type-Options: nosniff');
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    return true;
}

function harness_find_node($id) {
    if (!is_string($id) || preg_match('/^[A-Za-z0-9:_@.\\-]+$/', $id) !== 1) {
        return null;
    }
    $graph = harness_graph();
    if (!is_array($graph) || !isset($graph['nodes']) || !is_array($graph['nodes'])) {
        return null;
    }
    foreach ($graph['nodes'] as $row) {
        if (isset($row['id']) && (string) $row['id'] === $id) {
            if (!isset($row['json'])) {
                return null;
            }
            $dir = harness_data_dir();
            $path = $dir !== false ? realpath($dir . '/' . $row['json']) : false;
            if ($path === false || !harness_contained($path) || !is_file($path)) {
                return null;
            }
            return harness_read_json($path);
        }
    }
    return null;
}

function harness_content_type($ext) {
    $types = array(
        'html' => 'text/html; charset=utf-8',
        'json' => 'application/json; charset=utf-8',
        'js' => 'application/javascript; charset=utf-8',
        'css' => 'text/css; charset=utf-8',
        'svg' => 'image/svg+xml',
        'png' => 'image/png',
        'ico' => 'image/x-icon',
    );
    return isset($types[$ext]) ? $types[$ext] : 'application/octet-stream';
}

function harness_serve_file($relative) {
    $relative = rawurldecode((string) $relative);
    if ($relative === '' || strpos($relative, '..') !== false || strpos($relative, "\0") !== false) {
        http_response_code(404);
        echo 'not found';
        return true;
    }
    $dir = harness_data_dir();
    $file = $dir !== false ? realpath($dir . '/' . $relative) : false;
    if ($file === false || !harness_contained($file) || !is_file($file)) {
        http_response_code(404);
        echo 'not found';
        return true;
    }
    $ext = strtolower(pathinfo($file, PATHINFO_EXTENSION));
    if (!in_array($ext, array('html', 'json', 'js', 'css', 'svg', 'png', 'ico'), true)) {
        http_response_code(404);
        echo 'not found';
        return true;
    }
    header('Content-Type: ' . harness_content_type($ext));
    header('Content-Length: ' . filesize($file));
    header('Cache-Control: no-store');
    header('X-Content-Type-Options: nosniff');
    readfile($file);
    return true;
}

function harness_run($argv, $cwd) {
    $cmd = implode(' ', array_map('escapeshellarg', $argv));
    $descriptors = array(
        0 => array('file', '/dev/null', 'r'),
        1 => array('pipe', 'w'),
        2 => array('pipe', 'w'),
    );
    $proc = @proc_open($cmd, $descriptors, $pipes, $cwd);
    if (!is_resource($proc)) {
        return array(1, '', 'cannot start process');
    }
    $out = stream_get_contents($pipes[1]);
    $err = stream_get_contents($pipes[2]);
    fclose($pipes[1]);
    fclose($pipes[2]);
    $code = proc_close($proc);
    return array($code, (string) $out, (string) $err);
}

function harness_origin_allowed() {
    if (function_exists('jobs_origin_allowed')) {
        return jobs_origin_allowed();
    }
    $host = isset($_SERVER['HTTP_HOST']) ? (string) $_SERVER['HTTP_HOST'] : '';
    $hostname = $host !== '' ? parse_url('http://' . $host, PHP_URL_HOST) : '';
    return in_array($hostname, array('127.0.0.1', 'localhost', '::1'), true);
}

function harness_state_dir() {
    $root = repo_root();
    $rel = (string) harness_config()['state_dir'];
    return $root !== false ? $root . '/' . $rel : null;
}

function harness_mirror_script() {
    $root = repo_root();
    return $root !== false ? $root . '/.agents/skills/harness-router/children/mirror/scripts/harness_mirror.py' : '';
}

function harness_write_node($id, $raw) {
    if (!harness_origin_allowed()) {
        return harness_send_json(array('status' => 'failed', 'error' => 'origin not allowed'), 403);
    }
    if (!harness_config()['writable']) {
        return harness_send_json(array('status' => 'failed', 'error' => 'write disabled'), 403);
    }
    if (strlen($raw) > 2 * 1024 * 1024) {
        return harness_send_json(array('status' => 'failed', 'error' => 'file too large'), 413);
    }
    $node = harness_find_node($id);
    if ($node === null || !isset($node['meta']) || !is_array($node['meta'])) {
        return harness_send_json(array('status' => 'failed', 'error' => 'node not found'), 404);
    }
    $meta = $node['meta'];
    if (empty($meta['canonical']) || !in_array(isset($meta['type']) ? $meta['type'] : '', array('rule', 'skill'), true)) {
        return harness_send_json(array('status' => 'failed', 'error' => 'editable types are rule, skill'), 400);
    }
    $state = harness_state_dir();
    $script = harness_mirror_script();
    $root = repo_root();
    if ($state === null || $script === '' || !is_file($script)) {
        return harness_send_json(array('status' => 'failed', 'error' => 'service is incomplete'), 500);
    }
    if (!is_dir($state . '/tmp') && !@mkdir($state . '/tmp', 0775, true)) {
        return harness_send_json(array('status' => 'failed', 'error' => 'cannot create tmp dir'), 500);
    }
    $tmp = $state . '/tmp/' . $id . '.tmp';
    $tmp = preg_replace('/[^A-Za-z0-9_\.\/\-]/', '_', $tmp);
    if (@file_put_contents($tmp, $raw) === false) {
        return harness_send_json(array('status' => 'failed', 'error' => 'cannot write tmp file'), 500);
    }
    $lock_path = $state . '/harness.lock';
    $lock = @fopen($lock_path, 'c');
    if ($lock === false || !flock($lock, LOCK_EX)) {
        @unlink($tmp);
        return harness_send_json(array('status' => 'failed', 'error' => 'busy'), 409);
    }
    $data_rel = (string) harness_config()['data_dir'];
    list($code, $out, $err) = harness_run(array(
        'python3', $script, '--root', $root, '--data', $data_rel,
        'set', '--node', $id, '--file', '--content', $tmp,
    ), $root);
    if ($code !== 0) {
        flock($lock, LOCK_UN);
        fclose($lock);
        @unlink($tmp);
        return harness_send_json(array('status' => 'failed', 'error' => trim($err !== '' ? $err : $out)), 500);
    }
    list($build_code, $build_out, $build_err) = harness_run(array(
        'python3', $script, '--root', $root, '--data', $data_rel, 'rebuild',
    ), $root);
    list($check_code, $check_out, $check_err) = harness_run(array(
        'python3', $script, '--root', $root, '--data', $data_rel, 'check',
    ), $root);
    flock($lock, LOCK_UN);
    fclose($lock);
    @unlink($tmp);
    if ($build_code !== 0 || $check_code !== 0) {
        return harness_send_json(array(
            'status' => 'failed',
            'error' => trim($build_err . ' ' . $check_err),
            'set' => json_decode($out, true),
            'build' => json_decode($build_out, true),
            'check' => json_decode($check_out, true),
        ), 500);
    }
    $fresh = harness_find_node($id);
    return harness_send_json(array(
        'status' => 'ok',
        'node' => $fresh,
        'stats' => harness_stats(),
    ));
}

function harness_rebuild() {
    if (!harness_origin_allowed()) {
        return harness_send_json(array('status' => 'failed', 'error' => 'origin not allowed'), 403);
    }
    if (!harness_config()['writable']) {
        return harness_send_json(array('status' => 'failed', 'error' => 'write disabled'), 403);
    }
    $state = harness_state_dir();
    $script = harness_mirror_script();
    $root = repo_root();
    if ($state === null || $script === '' || !is_file($script)) {
        return harness_send_json(array('status' => 'failed', 'error' => 'service is incomplete'), 500);
    }
    $lock = @fopen($state . '/harness.lock', 'c');
    if ($lock === false || !flock($lock, LOCK_EX)) {
        return harness_send_json(array('status' => 'failed', 'error' => 'busy'), 409);
    }
    list($code, $out, $err) = harness_run(array(
        'python3', $script, '--root', $root, '--data', (string) harness_config()['data_dir'], 'rebuild',
    ), $root);
    flock($lock, LOCK_UN);
    fclose($lock);
    if ($code !== 0) {
        return harness_send_json(array('status' => 'failed', 'error' => trim($err !== '' ? $err : $out)), 500);
    }
    return harness_send_json(array('status' => 'ok', 'stats' => harness_stats()));
}

function harness_serve($path) {
    if ($path === '/harness') {
        header('Location: /harness/', true, 301);
        return true;
    }
    if (strpos($path, '/harness/api/') === 0) {
        $method = isset($_SERVER['REQUEST_METHOD']) ? strtoupper((string) $_SERVER['REQUEST_METHOD']) : 'GET';
        if ($path === '/harness/api/health') {
            if ($method !== 'GET') {
                return harness_send_json(array('status' => 'failed', 'error' => 'method not allowed'), 405);
            }
            return harness_send_json(array(
                'status' => 'ok',
                'writable' => (bool) harness_config()['writable'],
                'stats' => harness_stats(),
            ));
        }
        if ($path === '/harness/api/node') {
            $id = isset($_GET['id']) ? (string) $_GET['id'] : '';
            if ($method === 'GET') {
                $node = harness_find_node($id);
                if ($node === null) {
                    return harness_send_json(array('status' => 'failed', 'error' => 'node not found'), 404);
                }
                return harness_send_json(array('status' => 'ok', 'node' => $node));
            }
            if ($method === 'PUT') {
                $raw = file_get_contents('php://input');
                $body = $raw === '' ? array() : json_decode($raw, true);
                if (!is_array($body) || !isset($body['raw_file']) || !is_string($body['raw_file'])) {
                    return harness_send_json(array('status' => 'failed', 'error' => 'raw_file required'), 400);
                }
                return harness_write_node($id, $body['raw_file']);
            }
            return harness_send_json(array('status' => 'failed', 'error' => 'method not allowed'), 405);
        }
        if ($path === '/harness/api/rebuild') {
            if ($method !== 'POST') {
                return harness_send_json(array('status' => 'failed', 'error' => 'method not allowed'), 405);
            }
            return harness_rebuild();
        }
        return harness_send_json(array('status' => 'failed', 'error' => 'unknown endpoint'), 404);
    }
    $prefix = '/harness/';
    if (strpos($path, $prefix) === 0) {
        $relative = substr($path, strlen($prefix));
        return harness_serve_file($relative === '' ? 'index.html' : $relative);
    }
    http_response_code(404);
    echo 'not found';
    return true;
}

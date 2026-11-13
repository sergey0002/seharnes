<?php
// Job registry and runner API for the panel. PHP 7.1 compatible.
require_once __DIR__ . '/lib.php';

function jobs_service_config() {
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
        'profile' => 'full',
    );
    $raw = @file_get_contents(__DIR__ . '/../config/service.json');
    $data = $raw === false ? null : json_decode($raw, true);
    $cfg = is_array($data) ? array_merge($defaults, $data) : $defaults;
    return $cfg;
}

function jobs_state_dir() {
    static $dir = null;
    if ($dir !== null) {
        return $dir;
    }
    $root = repo_root();
    $rel = (string) jobs_service_config()['state_dir'];
    $dir = $root !== false ? $root . '/' . $rel : null;
    return $dir;
}

function jobs_json($payload, $code = 200) {
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    header('X-Content-Type-Options: nosniff');
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    return true;
}

function jobs_origin_allowed() {
    $host = isset($_SERVER['HTTP_HOST']) ? (string) $_SERVER['HTTP_HOST'] : '';
    $hostname = $host !== '' ? parse_url('http://' . $host, PHP_URL_HOST) : '';
    $loopback = array('127.0.0.1', 'localhost', '::1');
    if (!in_array($hostname, $loopback, true)) {
        return false;
    }
    $origin = isset($_SERVER['HTTP_ORIGIN']) ? (string) $_SERVER['HTTP_ORIGIN'] : '';
    if ($origin !== '') {
        $origin_host = parse_url($origin, PHP_URL_HOST);
        if (!in_array($origin_host, $loopback, true)) {
            return false;
        }
    }
    $method = isset($_SERVER['REQUEST_METHOD']) ? strtoupper((string) $_SERVER['REQUEST_METHOD']) : 'GET';
    if ($method !== 'GET') {
        $requested = isset($_SERVER['HTTP_X_REQUESTED_WITH']) ? strtoupper((string) $_SERVER['HTTP_X_REQUESTED_WITH']) : '';
        if ($requested !== 'XMLHTTPREQUEST') {
            return false;
        }
    }
    return true;
}

function jobs_load_actions() {
    static $actions = null;
    if ($actions !== null) {
        return $actions;
    }
    $base = @file_get_contents(__DIR__ . '/../config/actions.json');
    $data = $base === false ? null : json_decode($base, true);
    $list = is_array($data) && isset($data['actions']) && is_array($data['actions']) ? $data['actions'] : array();
    $by_id = array();
    foreach ($list as $row) {
        if (is_array($row) && isset($row['id'])) {
            $by_id[(string) $row['id']] = $row;
        }
    }
    $local_path = __DIR__ . '/../config/actions.local.json';
    if (is_file($local_path)) {
        $raw = @file_get_contents($local_path);
        $local = $raw === false ? null : json_decode($raw, true);
        if (is_array($local) && isset($local['actions']) && is_array($local['actions'])) {
            foreach ($local['actions'] as $row) {
                if (is_array($row) && isset($row['id'])) {
                    $id = (string) $row['id'];
                    $by_id[$id] = isset($by_id[$id]) ? array_merge($by_id[$id], $row) : $row;
                }
            }
        }
    }
    $actions = array_values($by_id);
    return $actions;
}

function jobs_find_action($id) {
    foreach (jobs_load_actions() as $row) {
        if (isset($row['id']) && (string) $row['id'] === (string) $id) {
            return $row;
        }
    }
    return null;
}

function jobs_action_allowed_for_profile($action, $profile) {
    if (!is_array($action) || empty($action['enabled']) || !in_array($profile, array('core', 'full'), true)) {
        return false;
    }
    return !(!empty($action['profile']) && $action['profile'] === 'full' && $profile === 'core');
}

function jobs_visible_actions($task_id = '', $groups = null) {
    $out = array();
    $profile = (string) jobs_service_config()['profile'];
    foreach (jobs_load_actions() as $row) {
        if (!jobs_action_allowed_for_profile($row, $profile)) {
            continue;
        }
        if (isset($row['group']) && $row['group'] === 'task' && !valid_task_id($task_id)) {
            continue;
        }
        if (is_array($groups) && (!isset($row['group']) || !in_array($row['group'], $groups, true))) {
            continue;
        }
        $out[] = $row;
    }
    return $out;
}

function jobs_valid_script($relative) {
    $relative = (string) $relative;
    if ($relative === '' || strpos($relative, '..') !== false) {
        return false;
    }
    $root = repo_root();
    $abs = $root !== false ? realpath($root . '/' . $relative) : false;
    if ($abs === false || !is_file($abs)) {
        return false;
    }
    $rel = str_replace('\\', '/', substr($abs, strlen($root) + 1));
    $allowed = array('.agents/skills/', '.cursor/scripts/', '.cursor/mcp-stack/', '.doc/');
    foreach ($allowed as $prefix) {
        if (strpos($rel, $prefix) === 0) {
            return true;
        }
    }
    return false;
}

function jobs_build_argv($action, $params) {
    $argv = array((string) $action['interpreter'], (string) $action['script']);
    $args = isset($action['args']) && is_array($action['args']) ? $action['args'] : array();
    $task = isset($params['task']) ? (string) $params['task'] : '';
    foreach ($args as $arg) {
        $arg = (string) $arg;
        if (strpos($arg, '{task}') !== false) {
            if (!valid_task_id($task)) {
                return null;
            }
            $arg = str_replace('{task}', $task, $arg);
        }
        if (strpos($arg, '{workspace}') !== false) {
            $arg = str_replace('{workspace}', panel_workspace_root(), $arg);
        }
        $argv[] = $arg;
    }
    return $argv;
}

function jobs_validate_params($action, $params) {
    $declared = isset($action['params']) && is_array($action['params']) ? $action['params'] : array();
    foreach ($params as $key => $value) {
        if (!isset($declared[$key]) || $declared[$key] !== 'int' || !valid_task_id($value)) {
            return false;
        }
    }
    foreach ($declared as $key => $type) {
        if ($type === 'int' && (!isset($params[$key]) || !valid_task_id($params[$key]))) {
            return false;
        }
    }
    return true;
}

function jobs_action_busy($action_id) {
    $dir = jobs_state_dir();
    if ($dir === null) {
        return '';
    }
    $lock_path = $dir . '/jobs/' . preg_replace('/[^a-z0-9_]/', '_', (string) $action_id) . '.lock';
    $handle = @fopen($lock_path, 'c');
    if ($handle === false) {
        return '';
    }
    $free = flock($handle, LOCK_EX | LOCK_NB);
    if ($free) {
        flock($handle, LOCK_UN);
        fclose($handle);
        return '';
    }
    fclose($handle);
    $current = @file_get_contents($dir . '/jobs/' . preg_replace('/[^a-z0-9_]/', '_', (string) $action_id) . '.current');
    return $current === false ? 'busy' : trim($current);
}

function jobs_new_id() {
    return 'job_' . gmdate('Ymd_His') . '_' . bin2hex(random_bytes(2));
}

function jobs_write_json($path, $data) {
    $tmp = $path . '.tmp.' . getmypid();
    $raw = json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n";
    if (@file_put_contents($tmp, $raw) === false) {
        return false;
    }
    return @rename($tmp, $path);
}

function jobs_log_tail($path, $lines = 200) {
    if (!is_file($path)) {
        return array();
    }
    $raw = @file($path, FILE_IGNORE_NEW_LINES);
    if (!is_array($raw)) {
        return array();
    }
    return array_slice($raw, -1 * (int) $lines);
}

function jobs_status_payload($id) {
    $dir = jobs_state_dir();
    if ($dir === null || !preg_match('/^job_[0-9]{8}_[0-9]{6}_[a-f0-9]{4}$/', (string) $id)) {
        return null;
    }
    $job_dir = $dir . '/jobs/' . $id;
    $status = @file_get_contents($job_dir . '/status.json');
    $data = $status === false ? null : json_decode($status, true);
    if (!is_array($data)) {
        return null;
    }
    $data['log_tail'] = jobs_log_tail($job_dir . '/log.txt', 200);
    $data['can_cancel'] = in_array($data['status'], array('queued', 'running', 'cancelling'), true);
    return $data;
}

function jobs_start($action_id, $params) {
    if (!jobs_origin_allowed()) {
        return jobs_json(array('status' => 'failed', 'error' => 'origin not allowed'), 403);
    }
    $action = jobs_find_action($action_id);
    if ($action === null || empty($action['enabled'])) {
        return jobs_json(array('status' => 'failed', 'error' => 'unknown action'), 400);
    }
    if (!jobs_action_allowed_for_profile($action, (string) jobs_service_config()['profile'])) {
        return jobs_json(array('status' => 'failed', 'error' => 'action unavailable for profile'), 403);
    }
    if (!jobs_valid_script(isset($action['script']) ? $action['script'] : '')) {
        return jobs_json(array('status' => 'failed', 'error' => 'script outside allowed roots'), 400);
    }
    $declared = isset($action['params']) && is_array($action['params']) ? $action['params'] : array();
    $params = array_intersect_key($params, $declared);
    if (!jobs_validate_params($action, $params)) {
        return jobs_json(array('status' => 'failed', 'error' => 'bad params'), 400);
    }
    $argv = jobs_build_argv($action, $params);
    if ($argv === null) {
        return jobs_json(array('status' => 'failed', 'error' => 'bad task id'), 400);
    }
    $busy = jobs_action_busy($action_id);
    if ($busy !== '') {
        return jobs_json(array('status' => 'failed', 'error' => 'already running', 'id' => $busy), 409);
    }
    $dir = jobs_state_dir();
    if ($dir === null) {
        return jobs_json(array('status' => 'failed', 'error' => 'state dir missing'), 500);
    }
    $id = jobs_new_id();
    $job_dir = $dir . '/jobs/' . $id;
    if (!@mkdir($job_dir, 0775, true)) {
        return jobs_json(array('status' => 'failed', 'error' => 'cannot create job dir'), 500);
    }
    $root = repo_root();
    $cwd_rel = isset($action['cwd']) ? (string) $action['cwd'] : '.';
    $cwd = realpath($root . '/' . $cwd_rel);
    if ($cwd === false || !repo_contained($cwd)) {
        $cwd = $root;
    }
    $job = array(
        'id' => $id,
        'action' => (string) $action['id'],
        'label' => isset($action['label']) ? (string) $action['label'] : (string) $action['id'],
        'argv' => $argv,
        'cwd' => $cwd,
        'timeout' => isset($action['timeout']) ? (int) $action['timeout'] : 300,
        'params' => $params,
        'progress_regex' => isset($action['progress_regex']) ? (string) $action['progress_regex'] : '',
        'write_scope' => isset($action['write_scope']) && is_array($action['write_scope']) ? $action['write_scope'] : array(),
        'created_at' => gmdate('Y-m-d\TH:i:s\Z'),
    );
    jobs_write_json($job_dir . '/job.json', $job);
    jobs_write_json($job_dir . '/status.json', array(
        'id' => $id,
        'action' => $job['action'],
        'label' => $job['label'],
        'status' => 'queued',
        'phase' => 'queued',
        'progress' => 0,
        'message' => 'в очереди',
        'started_at' => null,
        'ended_at' => null,
        'exit_code' => null,
        'can_cancel' => true,
    ));
    @file_put_contents($dir . '/jobs/' . preg_replace('/[^a-z0-9_]/', '_', (string) $action['id']) . '.current', $id);

    $runner = __DIR__ . '/../bin/job-runner.php';
    $cmd = 'setsid ' . escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg($runner) . ' ' . escapeshellarg($id) . ' > /dev/null 2>&1 & echo $!';
    $pid = trim((string) @shell_exec($cmd));
    if ($pid !== '') {
        @file_put_contents($job_dir . '/pid', $pid);
    }
    return jobs_json(array('status' => 'queued', 'id' => $id, 'poll' => '/jobs/status?id=' . $id), 202);
}

function jobs_cancel($id) {
    if (!jobs_origin_allowed()) {
        return jobs_json(array('status' => 'failed', 'error' => 'origin not allowed'), 403);
    }
    $dir = jobs_state_dir();
    if ($dir === null || !preg_match('/^job_[0-9]{8}_[0-9]{6}_[a-f0-9]{4}$/', (string) $id)) {
        return jobs_json(array('status' => 'failed', 'error' => 'bad id'), 400);
    }
    $job_dir = $dir . '/jobs/' . $id;
    if (!is_dir($job_dir)) {
        return jobs_json(array('status' => 'failed', 'error' => 'job not found'), 404);
    }
    @file_put_contents($job_dir . '/cancel', '1');
    $status = jobs_status_payload($id);
    if (is_array($status)) {
        $status['status'] = 'cancelling';
        $status['can_cancel'] = true;
        jobs_write_json($job_dir . '/status.json', $status);
    }
    return jobs_json(array('status' => 'cancelling', 'id' => $id), 202);
}

function jobs_list() {
    $dir = jobs_state_dir();
    if ($dir === null) {
        return array();
    }
    $out = array();
    foreach (glob($dir . '/jobs/job_*', GLOB_ONLYDIR) as $job_dir) {
        $id = basename($job_dir);
        $status = jobs_status_payload($id);
        if (is_array($status)) {
            $out[] = array(
                'id' => $id,
                'action' => $status['action'],
                'label' => $status['label'],
                'status' => $status['status'],
                'progress' => $status['progress'],
                'started_at' => $status['started_at'],
                'ended_at' => $status['ended_at'],
            );
        }
    }
    usort($out, function ($a, $b) {
        return strcmp((string) $b['started_at'], (string) $a['started_at']);
    });
    return array_slice($out, 0, 20);
}

function jobs_handle($path) {
    $method = isset($_SERVER['REQUEST_METHOD']) ? strtoupper((string) $_SERVER['REQUEST_METHOD']) : 'GET';
    $body = array();
    if ($method === 'POST') {
        $raw = file_get_contents('php://input');
        $decoded = $raw === '' ? array() : json_decode($raw, true);
        $body = is_array($decoded) ? $decoded : array();
    }
    if ($path === '/jobs' && $method === 'GET') {
        return jobs_json(array('status' => 'ok', 'jobs' => jobs_list()));
    }
    if ($path === '/jobs' && $method === 'POST') {
        $action = isset($body['action']) ? (string) $body['action'] : '';
        $params = isset($body['params']) && is_array($body['params']) ? $body['params'] : array();
        return jobs_start($action, $params);
    }
    if ($path === '/jobs/status' && $method === 'GET') {
        $id = isset($_GET['id']) ? (string) $_GET['id'] : '';
        $status = jobs_status_payload($id);
        return $status === null
            ? jobs_json(array('status' => 'failed', 'error' => 'job not found'), 404)
            : jobs_json($status);
    }
    if ($path === '/jobs/cancel' && $method === 'POST') {
        return jobs_cancel(isset($body['id']) ? (string) $body['id'] : '');
    }
    return jobs_json(array('status' => 'failed', 'error' => 'method not allowed'), 405);
}

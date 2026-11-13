<?php
// .doc/web/app/lib.php - слой данных панели. JSON/MD из .doc и read-only провайдеры из Kilo DB.
// Совместимость: PHP 7.1 (без arrow functions, без типизированных свойств).

require_once __DIR__ . '/pricing.php';
require_once __DIR__ . '/providers.php';

function doc_dir() {
    static $d = null;
    if ($d === null) {
        $d = realpath(__DIR__ . '/../..');
    }
    return $d;
}

function repo_root() {
    static $r = null;
    if ($r === null) {
        $r = realpath(__DIR__ . '/../../..');
    }
    return $r;
}

// Хост-путь рабочей области для заданий панели: .env или SERVICE_WORKSPACE.
function panel_workspace_root() {
    $env = getenv('SERVICE_WORKSPACE');
    if (is_string($env) && $env !== '') {
        return rtrim($env, '/\\');
    }
    $env_file = __DIR__ . '/../.env';
    if (is_file($env_file)) {
        $lines = file($env_file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
        if (is_array($lines)) {
            foreach ($lines as $line) {
                $line = trim($line);
                if (strpos($line, 'SERVICE_WORKSPACE=') !== 0) {
                    continue;
                }
                $value = trim(substr($line, strlen('SERVICE_WORKSPACE=')));
                $value = trim($value, "\"'");
                if ($value !== '') {
                    return rtrim($value, '/\\');
                }
            }
        }
    }
    return repo_root();
}

// Путь внутри .doc (контент можно отдавать в браузер).
function doc_contained($abs) {
    $real = realpath($abs);
    if ($real === false) {
        return false;
    }
    $doc = doc_dir();
    return $real === $doc || strpos($real, $doc . DIRECTORY_SEPARATOR) === 0;
}

// Путь внутри корня репо (только для хеширования freshness, контент наружу не отдаем).
function repo_contained($abs) {
    $real = realpath($abs);
    if ($real === false) {
        return false;
    }
    $repo = repo_root();
    return $real === $repo || strpos($real, $repo . DIRECTORY_SEPARATOR) === 0;
}

function read_json_file($abs) {
    static $cache = array();
    if (isset($cache[$abs])) {
        return $cache[$abs];
    }
    if (!doc_contained($abs)) {
        return null;
    }
    $raw = @file_get_contents($abs);
    if ($raw === false) {
        return null;
    }
    $data = json_decode($raw, true);
    $cache[$abs] = is_array($data) ? $data : null;
    return $cache[$abs];
}

function read_text_file($abs) {
    if (!doc_contained($abs)) {
        return null;
    }
    $raw = @file_get_contents($abs);
    return $raw === false ? null : $raw;
}

function valid_task_id($id) {
    return is_string($id) && preg_match('/^\d+$/', $id) === 1;
}

function valid_doc_name($name) {
    return is_string($name) && preg_match('/^[a-z0-9][a-z0-9\-]*$/', $name) === 1;
}

function task_meta_summary(array $d, $id) {
    $m = isset($d['metadata']) && is_array($d['metadata']) ? $d['metadata'] : array();
    $rel = isset($m['release']) && $m['release'] !== '' && $m['release'] !== null
        ? (string)$m['release'] : 'no-release';
    $touched = task_last_touched((string)$id);
    $jira = task_jira_updated((string)$id);
    return array(
        'id' => (string)$id,
        'title' => isset($m['title']) ? (string)$m['title'] : ('Задача ' . $id),
        'release' => $rel,
        'branch' => isset($m['branch']) ? (string)$m['branch'] : '',
        'status' => isset($m['source_status']) ? (string)$m['source_status'] : '',
        'updated' => isset($m['updated_at']) ? (string)$m['updated_at'] : '',
        'updated_fmt' => fmt_iso(isset($m['updated_at']) ? (string)$m['updated_at'] : ''),
        'revision' => isset($d['revision']) ? (int)$d['revision'] : 0,
        'n_sections' => isset($d['sections']) && is_array($d['sections']) ? count($d['sections']) : 0,
        'n_files' => isset($d['files']) && is_array($d['files']) ? count($d['files']) : 0,
        'n_findings' => isset($d['findings']) && is_array($d['findings']) ? count($d['findings']) : 0,
        'n_dialogs' => task_dialogs_count((string)$id),
        'analytics_tokens' => task_analytics_tokens((string)$id),
        'analytics_cost' => task_analytics_cost((string)$id),
        'last_touched_ts' => $touched,
        'last_touched' => fmt_dt($touched),
        'jira_updated_ts' => $jira,
        'jira_updated' => fmt_dt_utc($jira),
        'jira_created_ts' => task_jira_created((string)$id),
        'jira_created' => fmt_dt_utc(task_jira_created((string)$id)),
        'jira_status' => task_jira_status((string)$id, isset($m['status']) ? (string)$m['status'] : ''),
        'assignee' => task_assignee((string)$id),
        'sort_ts' => $jira > 0 ? $jira : $touched,
    );
}

// Полный список задач из task.json. Тяжелые поля не читаем - только метаданные и счетчики.
function list_tasks() {
    $out = array();
    foreach (glob(doc_dir() . '/tasks/*/task.json') as $f) {
        $id = basename(dirname($f));
        if (!valid_task_id($id)) {
            continue;
        }
        $d = read_json_file($f);
        if ($d === null) {
            continue;
        }
        $out[] = task_meta_summary($d, $id);
    }
    usort($out, function ($a, $b) {
        if ($a['sort_ts'] !== $b['sort_ts']) {
            return $b['sort_ts'] - $a['sort_ts'];
        }
        return ((int)$b['id']) - ((int)$a['id']);
    });
    return $out;
}

function list_releases(array $tasks) {
    $rels = array();
    foreach ($tasks as $t) {
        $rels[$t['release']] = true;
    }
    $out = array_keys($rels);
    sort($out);
    return $out;
}

// Разбор компактного diff.files.md: число unique files + плоский список из "## All files".
function parse_diff_files($abs) {
    $res = array('unique' => 0, 'files' => array(), 'present' => false);
    $raw = read_text_file($abs);
    if ($raw === null) {
        return $res;
    }
    $res['present'] = true;
    $raw = preg_replace('/^\xEF\xBB\xBF/', '', $raw); // BOM
    if (preg_match('/Unique files\s*\|\s*(\d+)/', $raw, $m)) {
        $res['unique'] = (int)$m[1];
    }
    $lines = preg_split('/\r?\n/', $raw);
    $in_all = false;
    foreach ($lines as $line) {
        $t = trim($line);
        if (strpos($t, '## All files') === 0) {
            $in_all = true;
            continue;
        }
        if ($in_all && strpos($t, '## ') === 0) {
            break;
        }
        if ($in_all && $t !== '' && strpos($t, '|') === false && strpos($t, '#') !== 0
            && strpos($t, '**') !== 0 && strpos($t, '>') !== 0) {
            $res['files'][] = $t;
        }
    }
    return $res;
}

// Отчеты задачи: все reports/*/workflow-context.json со сверкой свежести источников.
function task_reports($id) {
    $out = array();
    $base = doc_dir() . '/tasks/' . $id . '/reports';
    if (!is_dir($base)) {
        return $out;
    }
    foreach (glob($base . '/*/workflow-context.json') as $f) {
        if (!doc_contained($f)) {
            continue;
        }
        $d = read_json_file($f);
        if ($d === null) {
            continue;
        }
        $report = basename(dirname($f));
        $sources = array();
        if (isset($d['sources']) && is_array($d['sources'])) {
            foreach ($d['sources'] as $s) {
                $p = isset($s['path']) ? (string)$s['path'] : '';
                $want = isset($s['sha256']) ? (string)$s['sha256'] : '';
                $state = 'missing';
                $abs = repo_root() . '/' . ltrim($p, '/');
                if ($p !== '' && repo_contained($abs) && is_file($abs)) {
                    $now = hash_file('sha256', $abs);
                    if ($want === '') {
                        $state = 'no-hash';
                    } elseif (strcasecmp($now, $want) === 0) {
                        $state = 'fresh';
                    } else {
                        $state = 'stale';
                    }
                }
                $sources[] = array(
                    'path' => $p,
                    'role' => isset($s['role']) ? (string)$s['role'] : '',
                    'state' => $state,
                );
            }
        }
        $scope = isset($d['scope']) && is_array($d['scope']) ? $d['scope'] : array();
        $steps = isset($d['steps']) && is_array($d['steps']) ? $d['steps'] : array();
        $out[] = array(
            'report' => $report,
            'scope_files' => isset($scope['files']) && is_array($scope['files']) ? $scope['files'] : array(),
            'scope_commits' => isset($scope['commits']) && is_array($scope['commits']) ? $scope['commits'] : array(),
            'n_steps' => count($steps),
            'sources' => $sources,
        );
    }
    return $out;
}

function get_task_detail($id) {
    if (!valid_task_id($id)) {
        return null;
    }
    $json_path = doc_dir() . '/tasks/' . $id . '/task.json';
    $d = read_json_file($json_path);
    if ($d === null) {
        return null;
    }
    $task_md = read_text_file(doc_dir() . '/tasks/' . $id . '/task.md');
    $diff = parse_diff_files(doc_dir() . '/tasks/' . $id . '/diff.files.md');
    $tracker = isset($d['tracker']) && is_array($d['tracker']) ? $d['tracker'] : array();
    $snap = isset($tracker['snapshot']) && is_array($tracker['snapshot']) ? $tracker['snapshot'] : array();
    $cov = isset($snap['coverage']) && is_array($snap['coverage']) ? $snap['coverage'] : array();
    return array(
        'summary' => task_meta_summary($d, $id),
        'sections' => isset($d['sections']) && is_array($d['sections']) ? $d['sections'] : array(),
        'files' => isset($d['files']) && is_array($d['files']) ? $d['files'] : array(),
        'findings' => isset($d['findings']) && is_array($d['findings']) ? $d['findings'] : array(),
        'decisions' => isset($d['decisions']) && is_array($d['decisions']) ? $d['decisions'] : array(),
        'relations' => isset($d['relations']) && is_array($d['relations']) ? $d['relations'] : array(),
        'tags' => isset($d['tags']) && is_array($d['tags']) ? $d['tags'] : array(),
        'issue_key' => isset($tracker['issue_key']) ? (string)$tracker['issue_key'] : '',
        'exported_at' => isset($tracker['exported_at']) ? (string)$tracker['exported_at'] : '',
        'comments_n' => isset($cov['comments']['retrieved']) ? (int)$cov['comments']['retrieved'] : 0,
        'task_md' => $task_md,
        'diff' => $diff,
        'reports' => task_reports($id),
        'jira_comments' => isset($d['tracker']['snapshot']['comments']) && is_array($d['tracker']['snapshot']['comments'])
            ? $d['tracker']['snapshot']['comments'] : array(),
        'jira_changelog' => isset($d['tracker']['snapshot']['changelog']) && is_array($d['tracker']['snapshot']['changelog'])
            ? $d['tracker']['snapshot']['changelog'] : array(),
        'jira_activity' => task_jira_activity($id),
        'business_logic' => isset($d['business_logic']) && is_array($d['business_logic'])
            ? $d['business_logic'] : array(),
        'change_report' => task_change_report($id),
    );
}

function task_jira_activity($id) {
    $doc = read_json_file(doc_dir() . '/tasks/' . $id . '/task.json');
    if ($doc === null) {
        return array();
    }
    $snapshot = isset($doc['tracker']['snapshot']) && is_array($doc['tracker']['snapshot'])
        ? $doc['tracker']['snapshot'] : array();
    $events = array();
    foreach (isset($snapshot['comments']) && is_array($snapshot['comments']) ? $snapshot['comments'] : array() as $comment) {
        $events[] = array(
            'kind' => 'comment',
            'at' => isset($comment['created_at']) ? (string)$comment['created_at'] : '',
            'ts' => isset($comment['created_at']) ? (int)strtotime((string)$comment['created_at']) : 0,
            'author' => isset($comment['author']) ? (string)$comment['author'] : '',
            'text' => isset($comment['text']) ? (string)$comment['text'] : '',
            'body' => isset($comment['body']) ? $comment['body'] : null,
        );
    }
    foreach (isset($snapshot['changelog']) && is_array($snapshot['changelog']) ? $snapshot['changelog'] : array() as $change) {
        $items = array();
        foreach (isset($change['items']) && is_array($change['items']) ? $change['items'] : array() as $item) {
            $items[] = array(
                'field' => isset($item['field']) ? (string)$item['field'] : 'field',
                'from' => isset($item['fromString']) ? (string)$item['fromString'] : '',
                'to' => isset($item['toString']) ? (string)$item['toString'] : '',
            );
        }
        $events[] = array(
            'kind' => 'change',
            'at' => isset($change['created_at']) ? (string)$change['created_at'] : '',
            'ts' => isset($change['created_at']) ? (int)strtotime((string)$change['created_at']) : 0,
            'author' => isset($change['author']) ? (string)$change['author'] : '',
            'items' => $items,
        );
    }
    usort($events, function ($a, $b) {
        if ($a['ts'] === $b['ts']) {
            return 0;
        }
        return $a['ts'] > $b['ts'] ? -1 : 1;
    });
    return $events;
}

function task_change_report($id) {
    $base = doc_dir() . '/tasks/' . $id . '/reports/change-report';
    $model = read_json_file($base . '/report-model.json');
    if ($model === null) {
        return null;
    }
    $model['_has_html'] = is_file($base . '/report.html');
    return $model;
}

function arch_meta_summary(array $d, $name) {
    $m = isset($d['metadata']) && is_array($d['metadata']) ? $d['metadata'] : array();
    $id = '';
    $touched = 0;
    $jira = 0;
    return array(
        'name' => $name,
        'title' => isset($m['title']) ? (string)$m['title'] : $name,
        'status' => isset($m['source_status']) ? (string)$m['source_status'] : '',
        'updated' => isset($m['updated_at']) ? (string)$m['updated_at'] : '',
        'updated_fmt' => fmt_iso(isset($m['updated_at']) ? (string)$m['updated_at'] : ''),
        'n_sections' => isset($d['sections']) && is_array($d['sections']) ? count($d['sections']) : 0,
        'n_findings' => isset($d['findings']) && is_array($d['findings']) ? count($d['findings']) : 0,
        'n_dialogs' => task_dialogs_count((string)$id),
        'analytics_tokens' => task_analytics_tokens((string)$id),
        'analytics_cost' => task_analytics_cost((string)$id),
        'last_touched_ts' => $touched,
        'last_touched' => fmt_dt($touched),
        'jira_updated_ts' => $jira,
        'jira_updated' => fmt_dt_utc($jira),
        'jira_created_ts' => task_jira_created((string)$id),
        'jira_created' => fmt_dt_utc(task_jira_created((string)$id)),
        'jira_status' => task_jira_status((string)$id, isset($m['status']) ? (string)$m['status'] : ''),
        'assignee' => task_assignee((string)$id),
        'sort_ts' => $jira > 0 ? $jira : $touched,
    );
}

function list_arch_docs() {
    $out = array();
    foreach (glob(doc_dir() . '/architecture/*.json') as $f) {
        $name = basename($f, '.json');
        if (strpos($name, '_') === 0) {
            continue;
        }
        $d = read_json_file($f);
        if ($d === null) {
            continue;
        }
        $out[] = arch_meta_summary($d, $name);
    }
    usort($out, function ($a, $b) {
        return strcmp($a['title'], $b['title']);
    });
    return $out;
}

function get_arch_doc($name) {
    if (!valid_doc_name($name)) {
        return null;
    }
    $d = read_json_file(doc_dir() . '/architecture/' . $name . '.json');
    if ($d === null) {
        return null;
    }
    return array(
        'summary' => arch_meta_summary($d, $name),
        'sections' => isset($d['sections']) && is_array($d['sections']) ? $d['sections'] : array(),
        'files' => isset($d['files']) && is_array($d['files']) ? $d['files'] : array(),
        'findings' => isset($d['findings']) && is_array($d['findings']) ? $d['findings'] : array(),
        'decisions' => isset($d['decisions']) && is_array($d['decisions']) ? $d['decisions'] : array(),
        'md_fallback' => read_text_file(doc_dir() . '/architecture/' . $name . '.md'),
    );
}

// --- Аналитика диалогов (task-analytics) -----------------------------------

function valid_analysis_file($name) {
    return is_string($name) && preg_match('/^ses_[A-Za-z0-9]+\.json$/', $name) === 1;
}

function task_last_touched($id) {
    if (!valid_task_id($id)) {
        return 0;
    }
    $base = doc_dir() . '/tasks/' . $id;
    $names = array(
        'task.md', 'task.json', 'doc.md', 'plan.md', 'diff.md', 'diff.files.md',
        'test.md', 'acceptance.md', 'task-diff.md',
        '_dialogs/anchor.json', '_dialogs/plan-state.json', 'dialogs/index.json',
    );
    $max = 0;
    foreach ($names as $name) {
        $path = $base . '/' . $name;
        if (is_file($path)) {
            $max = max($max, (int)filemtime($path));
        }
    }
    foreach (glob($base . '/*/plan.md') as $path) {
        if (is_file($path)) {
            $max = max($max, (int)filemtime($path));
        }
    }
    foreach (glob($base . '/reports/*/workflow-context.json') as $path) {
        if (is_file($path)) {
            $max = max($max, (int)filemtime($path));
        }
    }
    return $max;
}

function task_dialogs_index($id) {
    if (!valid_task_id($id)) {
        return null;
    }
    return read_json_file(doc_dir() . '/tasks/' . $id . '/dialogs/index.json');
}

function task_dialogs_count($id) {
    $d = task_dialogs_index($id);
    return ($d !== null && isset($d['sessions']) && is_array($d['sessions'])) ? count($d['sessions']) : 0;
}

function task_analytics_tokens($id) {
    $d = task_dialogs_index($id);
    if ($d === null || !isset($d['sessions']) || !is_array($d['sessions'])) {
        return 0;
    }
    $sum = 0;
    foreach ($d['sessions'] as $row) {
        $sum += isset($row['tokens']) ? (int)$row['tokens'] : 0;
    }
    return $sum;
}

function task_analytics_cost($id) {
    $d = task_dialogs_index($id);
    if ($d === null || !isset($d['sessions']) || !is_array($d['sessions'])) {
        return 0.0;
    }
    $ids = array();
    foreach ($d['sessions'] as $row) {
        if (isset($row['session_id'])) {
            $ids[] = (string)$row['session_id'];
        }
    }
    $providers = session_provider_map($ids);
    $sum = 0.0;
    foreach ($d['sessions'] as $row) {
        $sid = isset($row['session_id']) ? (string)$row['session_id'] : '';
        $provider = isset($providers[$sid]['provider']) ? (string)$providers[$sid]['provider'] : '';
        $cost = price_cost(
            isset($row['model']) ? (string)$row['model'] : '',
            isset($row['tokens_in']) ? (int)$row['tokens_in'] : 0,
            isset($row['tokens_out']) ? (int)$row['tokens_out'] : 0,
            isset($row['cache_read']) ? (int)$row['cache_read'] : 0,
            isset($row['cache_write']) ? (int)$row['cache_write'] : 0,
            $provider
        );
        if ($cost <= 0 && isset($row['cost']) && (float)$row['cost'] > 0) {
            $cost = (float)$row['cost'];
        }
        $sum += $cost;
    }
    return $sum;
}

function task_jira_updated($id) {
    static $cache = array();
    if (isset($cache[$id])) {
        return $cache[$id];
    }
    $doc = read_json_file(doc_dir() . '/tasks/' . $id . '/task.json');
    if ($doc !== null && isset($doc['tracker']['snapshot']['updated_at'])) {
        $ts = strtotime((string)$doc['tracker']['snapshot']['updated_at']);
        if ($ts !== false) {
            $cache[$id] = $ts;
            return $ts;
        }
    }
    $raw = read_text_file(doc_dir() . '/tasks/' . $id . '/task.md');
    $ts = 0;
    if ($raw !== null && preg_match('/^\|\s*Updated\s*\|\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2})\s*UTC\s*\|/m', $raw, $m)) {
        $ts = gmmktime((int)$m[4], (int)$m[5], 0, (int)$m[2], (int)$m[1], (int)$m[3]);
    }
    $cache[$id] = $ts;
    return $ts;
}

function task_jira_created($id) {
    static $cache = array();
    if (isset($cache[$id])) {
        return $cache[$id];
    }
    $doc = read_json_file(doc_dir() . '/tasks/' . $id . '/task.json');
    $ts = 0;
    if ($doc !== null && isset($doc['tracker']['snapshot']['created_at'])) {
        $parsed = strtotime((string)$doc['tracker']['snapshot']['created_at']);
        if ($parsed !== false) {
            $ts = $parsed;
        }
    }
    $cache[$id] = $ts;
    return $ts;
}

function task_assignee($id, $fallback = '') {
    static $cache = array();
    if (isset($cache[$id])) {
        return $cache[$id];
    }
    $doc = read_json_file(doc_dir() . '/tasks/' . $id . '/task.json');
    if ($doc !== null && isset($doc['tracker']['snapshot']['assignee'])) {
        $raw = $doc['tracker']['snapshot']['assignee'];
        if (is_array($raw)) {
            if (isset($raw['name'])) {
                $raw = $raw['name'];
            } elseif (isset($raw['displayName'])) {
                $raw = $raw['displayName'];
            } elseif (isset($raw[0])) {
                $raw = is_array($raw[0]) ? (isset($raw[0]['name']) ? $raw[0]['name'] : '') : $raw[0];
            } else {
                $raw = '';
            }
        }
        $value = trim((string)$raw);
        if ($value !== '') {
            $cache[$id] = $value;
            return $value;
        }
    }
    $raw = read_text_file(doc_dir() . '/tasks/' . $id . '/task.md');
    if ($raw !== null && preg_match('/^\|\s*Assignee\s*\|\s*([^|]+?)\s*\|/m', $raw, $match)) {
        $value = trim($match[1]);
        if ($value !== '' && $value !== '-' && $value !== '—'
            && strcasecmp($value, 'Unassigned') !== 0
            && strcasecmp($value, 'Unknown') !== 0) {
            $cache[$id] = $value;
            return $value;
        }
    }
    $cache[$id] = $fallback;
    return $cache[$id];
}

function list_assignees($tasks) {
    $out = array();
    foreach ($tasks as $task) {
        $name = isset($task['assignee']) ? $task['assignee'] : '';
        if ($name === '') {
            continue;
        }
        $out[$name] = isset($out[$name]) ? $out[$name] + 1 : 1;
    }
    ksort($out, SORT_NATURAL | SORT_FLAG_CASE);
    return $out;
}

function task_jira_status($id, $fallback = '') {
    static $cache = array();
    if (isset($cache[$id])) {
        return $cache[$id];
    }
    $doc = read_json_file(doc_dir() . '/tasks/' . $id . '/task.json');
    if ($doc !== null && isset($doc['tracker']['snapshot']['status']['name'])) {
        $status = (string)$doc['tracker']['snapshot']['status']['name'];
        $cache[$id] = $status;
        return $status;
    }
    $raw = read_text_file(doc_dir() . '/tasks/' . $id . '/task.md');
    if ($raw !== null && preg_match('/^\|\s*State\s*\|\s*([^|]+?)\s*\|/m', $raw, $match)) {
        $cache[$id] = trim($match[1]);
        return $cache[$id];
    }
    $cache[$id] = $fallback !== '' ? $fallback : 'unknown';
    return $cache[$id];
}

function task_title($id) {
    static $cache = array();
    if (isset($cache[$id])) {
        return $cache[$id];
    }
    $d = read_json_file(doc_dir() . '/tasks/' . $id . '/task.json');
    $title = 'Задача ' . $id;
    if ($d !== null && isset($d['metadata']['title'])) {
        $title = (string)$d['metadata']['title'];
    }
    $cache[$id] = $title;
    return $title;
}

function fmt_dt($ts) {
    return ((int)$ts) > 0 ? date('d.m.Y H:i:s', (int)$ts) : '';
}

function fmt_dt_utc($ts) {
    return ((int)$ts) > 0 ? gmdate('d.m.Y H:i:s', (int)$ts) . ' UTC' : '';
}

function fmt_iso($value) {
    if (!is_string($value) || $value === '') {
        return '';
    }
    $ts = strtotime($value);
    return $ts === false ? $value : fmt_dt($ts);
}

function fmt_iso_utc($value) {
    if (!is_string($value) || $value === '') {
        return '';
    }
    $ts = strtotime($value);
    return $ts === false ? $value : gmdate('d.m.Y H:i:s', $ts) . ' UTC';
}

function fmt_num($value) {
    $value = (float)$value;
    if ($value >= 1000000000) {
        return rtrim(rtrim(number_format($value / 1000000000, 2, '.', ''), '0'), '.') . 'B';
    }
    if ($value >= 1000000) {
        return rtrim(rtrim(number_format($value / 1000000, 2, '.', ''), '0'), '.') . 'M';
    }
    if ($value >= 1000) {
        return rtrim(rtrim(number_format($value / 1000, 1, '.', ''), '0'), '.') . 'K';
    }
    return (string)(int)$value;
}

function fmt_minutes($ms) {
    $minutes = ((int)$ms) / 60000;
    if ($minutes >= 60) {
        return round($minutes / 60, 1) . ' ч';
    }
    return round($minutes) . ' мин';
}

function empty_analytics() {
    return array(
        'present' => false,
        'sessions' => array(),
        'totals' => array(
            'sessions' => 0, 'tokens_in' => 0, 'tokens_out' => 0, 'tokens_reasoning' => 0,
            'cache_read' => 0, 'cache_write' => 0, 'requests' => 0, 'cost' => 0.0, 'active_ms' => 0,
            'duration_ms' => 0, 'findings' => 0, 'errors' => 0,
        ),
        'findings' => array(),
        'tools' => array(),
        'mcp' => array(),
        'cli' => array(),
        'models' => array(),
        'providers' => array(),
        'roles' => array(),
        'slices' => array(),
        'plan_state' => null,
    );
}

function task_dialogs($id, $project_filter = '') {
    if (!valid_task_id($id)) {
        return empty_analytics();
    }
    $base = doc_dir() . '/tasks/' . $id . '/dialogs';
    $index = read_json_file($base . '/index.json');
    if ($index === null) {
        return empty_analytics();
    }
    $result = empty_analytics();
    $result['present'] = true;
    $rows = isset($index['sessions']) && is_array($index['sessions']) ? $index['sessions'] : array();
    $session_ids = array();
    foreach ($rows as $row) {
        if (isset($row['session_id'])) {
            $session_ids[] = (string)$row['session_id'];
        }
    }
    $provider_map = session_provider_map($session_ids);
    $project_map = session_project_map($session_ids);
    $providers = array();
    $findings = array();
    $tools = array();
    $cli = array();
    $mcp = array();
    $cli = array();
    $models = array();
    $roles = array();
    $slices = array();
    $sessions = array();
    foreach ($rows as $row) {
        $name = isset($row['analysis']) ? basename((string)$row['analysis']) : '';
        if (!valid_analysis_file($name)) {
            continue;
        }
        $a = read_json_file($base . '/' . $name);
        if ($a === null) {
            continue;
        }
        $sid = isset($a['session_id']) ? (string)$a['session_id']
            : (isset($row['session_id']) ? (string)$row['session_id'] : '');
        $project_row = isset($project_map[$sid]) ? $project_map[$sid] : array();
        $project_key = '';
        if (isset($project_row['project_id']) && $project_row['project_id'] !== '') {
            $project_key = (string)$project_row['project_id'];
        } elseif (isset($project_row['project'])) {
            $project_key = (string)$project_row['project'];
        }
        if ($project_filter !== '' && $project_key !== $project_filter) {
            continue;
        }
        $prov = isset($provider_map[$sid]['provider']) ? (string)$provider_map[$sid]['provider'] : '';
        $session_model = isset($a['model']) && $a['model'] !== null ? (string)$a['model'] : '';
        $ledger = isset($a['token_ledger']) && is_array($a['token_ledger']) ? $a['token_ledger'] : array();
        $tokens_in = isset($ledger['input_total']) ? (int)$ledger['input_total'] : 0;
        $tokens_out = isset($ledger['output']) ? (int)$ledger['output'] : 0;
        $reasoning = isset($ledger['reasoning']) ? (int)$ledger['reasoning'] : 0;
        $cache_read = isset($ledger['cache_read']) ? (int)$ledger['cache_read'] : 0;
        $cache_write = isset($ledger['cache_write']) ? (int)$ledger['cache_write'] : 0;
        $requests = isset($ledger['requests']) ? (int)$ledger['requests'] : 0;
        $cost = isset($ledger['cost']) ? (float)$ledger['cost'] : 0.0;
        $active = isset($a['active_ms']) ? (int)$a['active_ms'] : 0;
        $duration = isset($a['duration_ms']) ? (int)$a['duration_ms'] : 0;
        $result['totals']['tokens_in'] += $tokens_in;
        $result['totals']['tokens_out'] += $tokens_out;
        $result['totals']['tokens_reasoning'] += $reasoning;
        $result['totals']['cache_read'] += $cache_read;
        $result['totals']['cache_write'] += $cache_write;
        $result['totals']['requests'] += $requests;
        $result['totals']['active_ms'] += $active;
        $result['totals']['duration_ms'] += $duration;
        foreach (isset($a['findings']) && is_array($a['findings']) ? $a['findings'] : array() as $f) {
            $code = isset($f['code']) ? (string)$f['code'] : 'unknown';
            $findings[$code] = isset($findings[$code]) ? $findings[$code] + 1 : 1;
        }
        foreach (isset($a['tools']) && is_array($a['tools']) ? $a['tools'] : array() as $tool) {
            $name_t = isset($tool['name']) ? (string)$tool['name'] : 'unknown';
            if (!isset($tools[$name_t])) {
                $tools[$name_t] = array('name' => $name_t, 'calls' => 0, 'errors' => 0, 'timeouts' => 0);
            }
            $tools[$name_t]['calls'] += isset($tool['calls']) ? (int)$tool['calls'] : 0;
            $tools[$name_t]['errors'] += isset($tool['errors']) ? (int)$tool['errors'] : 0;
            $tools[$name_t]['timeouts'] += isset($tool['timeouts']) ? (int)$tool['timeouts'] : 0;
        }
        foreach (isset($a['mcp_servers']) && is_array($a['mcp_servers']) ? $a['mcp_servers'] : array() as $server) {
            $sname = isset($server['server']) ? (string)$server['server'] : 'unknown';
            if (!isset($mcp[$sname])) {
                $mcp[$sname] = array(
                    'server' => $sname, 'calls' => 0, 'errors' => 0,
                    'tokens_in' => 0, 'cache' => 0, 'tokens_out' => 0, 'cost' => 0.0,
                    'tools' => array(),
                );
            }
            $mcp[$sname]['calls'] += isset($server['calls']) ? (int)$server['calls'] : 0;
            $mcp[$sname]['errors'] += isset($server['errors']) ? (int)$server['errors'] : 0;
            if (isset($server['tools']) && is_array($server['tools'])) {
                foreach ($server['tools'] as $tool_name => $tool_calls) {
                    $tool_name = (string)$tool_name;
                    $mcp[$sname]['tools'][$tool_name] = isset($mcp[$sname]['tools'][$tool_name])
                        ? $mcp[$sname]['tools'][$tool_name] + (int)$tool_calls
                        : (int)$tool_calls;
                }
            }
            $mt = isset($server['tokens']) && is_array($server['tokens']) ? $server['tokens'] : array();
            $mcp[$sname]['tokens_in'] += isset($mt['input']) ? (int)$mt['input'] : 0;
            $mcp[$sname]['cache'] += (isset($mt['cache_read']) ? (int)$mt['cache_read'] : 0)
                + (isset($mt['cache_write']) ? (int)$mt['cache_write'] : 0);
            $mcp[$sname]['tokens_out'] += isset($mt['output']) ? (int)$mt['output'] : 0;
            $mcp[$sname]['cost'] += price_cost(
                $session_model,
                isset($mt['input']) ? (int)$mt['input'] : 0,
                isset($mt['output']) ? (int)$mt['output'] : 0,
                isset($mt['cache_read']) ? (int)$mt['cache_read'] : 0,
                isset($mt['cache_write']) ? (int)$mt['cache_write'] : 0,
                $prov
            );
        }
        $by_model = isset($ledger['by_model']) && is_array($ledger['by_model']) ? $ledger['by_model'] : array();
        $session_cost = 0.0;
        foreach ($by_model as $model => $slot) {
            $model = (string)$model;
            if (!isset($models[$model])) {
                $models[$model] = array(
                    'model' => $model, 'tokens_in' => 0, 'cache' => 0,
                    'cache_read' => 0, 'cache_write' => 0,
                    'tokens_out' => 0, 'reasoning' => 0, 'cost' => 0,
                );
            }
            $slot_in = isset($slot['input']) ? (int)$slot['input'] : 0;
            $slot_out = isset($slot['output']) ? (int)$slot['output'] : 0;
            $slot_cr = isset($slot['cache_read']) ? (int)$slot['cache_read'] : 0;
            $slot_cw = isset($slot['cache_write']) ? (int)$slot['cache_write'] : 0;
            $slot_cost = isset($slot['cost']) ? (float)$slot['cost'] : 0.0;
            $calculated = price_cost($model, $slot_in, $slot_out, $slot_cr, $slot_cw, $prov);
            if ($calculated > 0) {
                $slot_cost = $calculated;
            }
            $models[$model]['tokens_in'] += $slot_in;
            $models[$model]['cache_read'] += $slot_cr;
            $models[$model]['cache_write'] += $slot_cw;
            $models[$model]['cache'] += $slot_cr + $slot_cw;
            $models[$model]['tokens_out'] += $slot_out;
            $models[$model]['reasoning'] += isset($slot['reasoning']) ? (int)$slot['reasoning'] : 0;
            $models[$model]['cost'] += $slot_cost;
            $session_cost += $slot_cost;
        }
        if ($session_cost <= 0 && $cost > 0) {
            $session_cost = $cost;
        }
        if ($session_cost <= 0 && isset($provider_map[$sid]['cost']) && $provider_map[$sid]['cost'] > 0) {
            $session_cost = (float)$provider_map[$sid]['cost'];
        }
        $result['totals']['cost'] += $session_cost;
        foreach (isset($a['cli_tools']) && is_array($a['cli_tools']) ? $a['cli_tools'] : array() as $tool) {
            $cname = isset($tool['name']) ? (string)$tool['name'] : 'bash';
            if (!isset($cli[$cname])) {
                $cli[$cname] = array('name' => $cname, 'calls' => 0, 'errors' => 0,
                    'tokens_in' => 0, 'cache' => 0, 'tokens_out' => 0, 'cost' => 0.0);
            }
            $cli[$cname]['calls'] += isset($tool['calls']) ? (int)$tool['calls'] : 0;
            $cli[$cname]['errors'] += isset($tool['errors']) ? (int)$tool['errors'] : 0;
            $ct = isset($tool['tokens']) && is_array($tool['tokens']) ? $tool['tokens'] : array();
            $cli[$cname]['tokens_in'] += isset($ct['input']) ? (int)$ct['input'] : 0;
            $cli[$cname]['cache'] += (isset($ct['cache_read']) ? (int)$ct['cache_read'] : 0)
                + (isset($ct['cache_write']) ? (int)$ct['cache_write'] : 0);
            $cli[$cname]['tokens_out'] += isset($ct['output']) ? (int)$ct['output'] : 0;
            $cli[$cname]['cost'] += price_cost(
                $session_model,
                isset($ct['input']) ? (int)$ct['input'] : 0,
                isset($ct['output']) ? (int)$ct['output'] : 0,
                isset($ct['cache_read']) ? (int)$ct['cache_read'] : 0,
                isset($ct['cache_write']) ? (int)$ct['cache_write'] : 0,
                $prov
            );
        }
        $pkey = $prov !== '' ? $prov : 'unknown';
        if (!isset($providers[$pkey])) {
            $providers[$pkey] = array(
                'provider' => $pkey, 'sessions' => 0,
                'tokens_in' => 0, 'cache' => 0, 'tokens_out' => 0, 'cost' => 0.0,
            );
        }
        $providers[$pkey]['sessions']++;
        $providers[$pkey]['tokens_in'] += $tokens_in;
        $providers[$pkey]['cache'] += $cache_read + $cache_write;
        $providers[$pkey]['tokens_out'] += $tokens_out;
        $providers[$pkey]['cost'] += $session_cost;
        $role = isset($a['role']) ? (string)$a['role'] : (isset($row['role']) ? (string)$row['role'] : 'task');
        $roles[$role] = isset($roles[$role]) ? $roles[$role] + 1 : 1;
        foreach (isset($a['slices']) && is_array($a['slices']) ? $a['slices'] : array() as $slice) {
            $outcome = isset($slice['outcome']) ? (string)$slice['outcome'] : 'unknown';
            $slices[$outcome] = isset($slices[$outcome]) ? $slices[$outcome] + 1 : 1;
        }
        $sessions[] = array(
            'session_id' => $sid,
            'project_id' => $project_key,
            'project_label' => isset($project_row['project_label']) ? (string)$project_row['project_label'] : '',
            'date' => isset($row['date']) ? (string)$row['date'] : '',
            'role' => $role,
            'provider' => $prov,
            'model' => isset($a['model']) && $a['model'] !== null ? (string)$a['model'] : '',
            'tokens' => $tokens_in + $tokens_out + $reasoning,
            'tokens_in' => $tokens_in,
            'tokens_out' => $tokens_out,
            'reasoning' => $reasoning,
            'cache_read' => $cache_read,
            'cache_write' => $cache_write,
            'requests' => $requests,
            'cost' => $session_cost,
            'active_ms' => $active,
            'duration_ms' => $duration,
            'final' => !empty($a['final']),
            'findings' => isset($a['findings']) && is_array($a['findings']) ? count($a['findings']) : 0,
            'status' => isset($a['attribution_status']) ? (string)$a['attribution_status'] : 'assigned',
        );
    }
    usort($sessions, function ($x, $y) {
        return strcmp($y['date'], $x['date']);
    });
    arsort($findings);
    uasort($tools, function ($x, $y) {
        return $y['calls'] - $x['calls'];
    });
    uasort($mcp, function ($x, $y) {
        return $y['calls'] - $x['calls'];
    });
    foreach ($mcp as $sname => $server) {
        arsort($mcp[$sname]['tools']);
    }
    arsort($roles);
    arsort($slices);
    $result['sessions'] = $sessions;
    $result['totals']['sessions'] = count($sessions);
    foreach ($findings as $count) {
        $result['totals']['findings'] += (int)$count;
    }
    $result['findings'] = $findings;
    $result['tools'] = array_values($tools);
    uasort($cli, function ($a, $b) {
        return $b['calls'] - $a['calls'];
    });
    uasort($models, function ($a, $b) {
        return ($b['tokens_in'] + $b['cache'] + $b['tokens_out']) - ($a['tokens_in'] + $a['cache'] + $a['tokens_out']);
    });
    $result['cli'] = array_values($cli);
    $result['models'] = array_values($models);
    $result['mcp'] = array_values($mcp);
    uasort($providers, function ($x, $y) {
        return $y['sessions'] - $x['sessions'];
    });
    $result['providers'] = array_values($providers);
    $result['roles'] = $roles;
    $result['slices'] = $slices;
    $result['plan_state'] = read_json_file(doc_dir() . '/tasks/' . $id . '/_dialogs/plan-state.json');
    return $result;
}

function unassigned_analytics($rows = null) {
    $out = array('sessions' => 0, 'tokens' => 0, 'active_ms' => 0);
    if (is_array($rows)) {
        foreach ($rows as $row) {
            $out['sessions']++;
            $out['tokens'] += isset($row['tokens']) ? (int)$row['tokens'] : 0;
            $out['active_ms'] += isset($row['active_ms']) ? (int)$row['active_ms'] : 0;
        }
        return $out;
    }
    $base = doc_dir() . '/task-analytics/out/unassigned';
    if (!is_dir($base)) {
        return $out;
    }
    foreach (glob($base . '/ses_*.json') as $file) {
        $a = read_json_file($file);
        if ($a === null) {
            continue;
        }
        $ledger = isset($a['token_ledger']) && is_array($a['token_ledger']) ? $a['token_ledger'] : array();
        $out['sessions']++;
        $out['tokens'] += (isset($ledger['input_total']) ? (int)$ledger['input_total'] : 0)
            + (isset($ledger['output']) ? (int)$ledger['output'] : 0)
            + (isset($ledger['reasoning']) ? (int)$ledger['reasoning'] : 0);
        $out['active_ms'] += isset($a['active_ms']) ? (int)$a['active_ms'] : 0;
    }
    return $out;
}

function valid_session_id($id) {
    return is_string($id) && preg_match('/^ses_[A-Za-z0-9]+$/', $id) === 1;
}

// Человеческое имя проекта: name из kilo.db, иначе последний сегмент пути.
function project_display_label($path, $name = '') {
    $name = is_string($name) ? trim($name) : '';
    if ($name !== '') {
        return $name;
    }
    $path = is_string($path) ? rtrim($path, '/\\') : '';
    if ($path === '') {
        return '';
    }
    return basename($path);
}

// Проект сессии из kilo.db: project.id, worktree и name. Read-only, как providers.
function session_project_map($ids) {
    static $cache = array();
    $ids = array_values(array_unique(array_filter(array_map('strval', $ids))));
    $missing = array();
    foreach ($ids as $id) {
        if (!array_key_exists($id, $cache)) {
            $missing[] = $id;
        }
    }
    if ($missing) {
        $db = kilo_connect();
        $found = array();
        if ($db !== null) {
            $placeholders = implode(',', array_fill(0, count($missing), '?'));
            try {
                $stmt = $db->prepare(
                    'SELECT s.id, s.directory, s.project_id, p.worktree, p.name FROM session s'
                    . ' LEFT JOIN project p ON p.id = s.project_id'
                    . ' WHERE s.id IN (' . $placeholders . ')'
                );
                $stmt->execute($missing);
                foreach ($stmt->fetchAll(PDO::FETCH_ASSOC) as $row) {
                    $found[(string)$row['id']] = $row;
                }
            } catch (Exception $e) {
                try {
                    $stmt = $db->prepare('SELECT id, directory FROM session WHERE id IN (' . $placeholders . ')');
                    $stmt->execute($missing);
                    foreach ($stmt->fetchAll(PDO::FETCH_ASSOC) as $row) {
                        $found[(string)$row['id']] = $row;
                    }
                } catch (Exception $e2) {
                    $found = array();
                }
            }
        }
        foreach ($missing as $id) {
            $row = isset($found[$id]) ? $found[$id] : array();
            $directory = isset($row['directory']) ? (string)$row['directory'] : '';
            $worktree = isset($row['worktree']) ? (string)$row['worktree'] : '';
            $label_path = $worktree !== '' ? $worktree : $directory;
            $cache[$id] = array(
                'project_id' => isset($row['project_id']) ? (string)$row['project_id'] : '',
                'project' => $directory,
                'project_label' => project_display_label($label_path, isset($row['name']) ? $row['name'] : ''),
            );
        }
    }
    $out = array();
    foreach ($ids as $id) {
        $out[$id] = $cache[$id];
    }
    return $out;
}

// Проекты, которые встречаются в диалогах без задачи и в диалогах задач.
function list_dialog_projects($unassigned_rows = array()) {
    $known = array();
    $project_keys = array();
    $labels = array();
    foreach ($unassigned_rows as $row) {
        $sid = isset($row['session_id']) ? (string)$row['session_id'] : '';
        if ($sid === '') {
            continue;
        }
        $key = $row['project_id'] !== '' ? $row['project_id'] : $row['project'];
        if ($key === '') {
            continue;
        }
        $known[$sid] = true;
        $project_keys[$sid] = $key;
        if (!isset($labels[$key])) {
            $labels[$key] = $row['project_label'] !== '' ? $row['project_label'] : $key;
        }
    }
    $pending = array();
    foreach (glob(doc_dir() . '/tasks/*/dialogs/index.json') as $index_path) {
        $index = read_json_file($index_path);
        if (!is_array($index) || !isset($index['sessions']) || !is_array($index['sessions'])) {
            continue;
        }
        foreach ($index['sessions'] as $row) {
            $sid = isset($row['session_id']) ? (string)$row['session_id'] : '';
            if ($sid === '' || isset($known[$sid])) {
                continue;
            }
            $known[$sid] = true;
            $pending[] = $sid;
        }
    }
    $map = $pending ? session_project_map($pending) : array();
    foreach ($pending as $sid) {
        $row = isset($map[$sid]) ? $map[$sid] : array();
        $key = isset($row['project_id']) && $row['project_id'] !== ''
            ? (string)$row['project_id']
            : (isset($row['project']) ? (string)$row['project'] : '');
        if ($key === '') {
            continue;
        }
        $project_keys[$sid] = $key;
        if (!isset($labels[$key])) {
            $labels[$key] = isset($row['project_label']) && $row['project_label'] !== ''
                ? (string)$row['project_label'] : $key;
        }
    }
    $out = array();
    foreach ($project_keys as $key) {
        if (!isset($out[$key])) {
            $out[$key] = array('id' => $key, 'label' => $labels[$key], 'count' => 0);
        }
        $out[$key]['count']++;
    }
    return $out;
}

function unassigned_session_row(array $a) {
    $ledger = isset($a['token_ledger']) && is_array($a['token_ledger']) ? $a['token_ledger'] : array();
    $totals = isset($a['totals']) && is_array($a['totals']) ? $a['totals'] : array();
    $started = isset($a['started_at']) ? (int)$a['started_at'] : 0;
    $started_ts = $started > 100000000000 ? (int)round($started / 1000) : $started;
    $tokens_in = isset($ledger['input_total']) ? (int)$ledger['input_total'] : 0;
    $tokens_out = isset($ledger['output']) ? (int)$ledger['output'] : 0;
    $reasoning = isset($ledger['reasoning']) ? (int)$ledger['reasoning'] : 0;
    $cache_read = isset($ledger['cache_read']) ? (int)$ledger['cache_read'] : 0;
    $cache_write = isset($ledger['cache_write']) ? (int)$ledger['cache_write'] : 0;
    $project_path = isset($a['project']) ? (string)$a['project'] : '';
    return array(
        'session_id' => isset($a['session_id']) ? (string)$a['session_id'] : '',
        'project_id' => isset($a['project_id']) ? (string)$a['project_id'] : '',
        'project' => $project_path,
        'project_label' => $project_path !== ''
            ? project_display_label($project_path, isset($a['project_name']) ? $a['project_name'] : '')
            : '',
        'title' => isset($a['first_user_text']) ? trim((string)$a['first_user_text']) : '',
        'started_ts' => $started_ts,
        'date' => fmt_dt($started_ts),
        'model' => isset($a['model']) && $a['model'] !== null ? (string)$a['model'] : '',
        'role' => isset($a['role']) ? (string)$a['role'] : '',
        'requests' => isset($ledger['requests']) ? (int)$ledger['requests'] : 0,
        'tokens_in' => $tokens_in,
        'tokens_out' => $tokens_out,
        'reasoning' => $reasoning,
        'cache_read' => $cache_read,
        'cache_write' => $cache_write,
        'tokens' => $tokens_in + $tokens_out + $reasoning,
        'context' => $tokens_in + $cache_read + $cache_write,
        'active_ms' => isset($a['active_ms']) ? (int)$a['active_ms'] : 0,
        'duration_ms' => isset($a['duration_ms']) ? (int)$a['duration_ms'] : 0,
        'tool_calls' => isset($totals['tool_calls']) ? (int)$totals['tool_calls'] : 0,
        'mcp_calls' => isset($totals['mcp_calls']) ? (int)$totals['mcp_calls'] : 0,
        'findings' => isset($a['findings']) && is_array($a['findings']) ? count($a['findings']) : 0,
        'final' => !empty($a['final']),
        'provider' => '',
        'cost' => 0.0,
        'status' => isset($a['attribution_status']) ? (string)$a['attribution_status'] : 'unassigned',
    );
}

function session_ledger_cost(array $a, $provider = '') {
    $ledger = isset($a['token_ledger']) && is_array($a['token_ledger']) ? $a['token_ledger'] : array();
    $by_model = isset($ledger['by_model']) && is_array($ledger['by_model']) ? $ledger['by_model'] : array();
    $cost = 0.0;
    foreach ($by_model as $model => $slot) {
        $cost += price_cost(
            (string)$model,
            isset($slot['input']) ? (int)$slot['input'] : 0,
            isset($slot['output']) ? (int)$slot['output'] : 0,
            isset($slot['cache_read']) ? (int)$slot['cache_read'] : 0,
            isset($slot['cache_write']) ? (int)$slot['cache_write'] : 0,
            $provider
        );
    }
    if ($cost <= 0 && isset($ledger['cost']) && (float)$ledger['cost'] > 0) {
        $cost = (float)$ledger['cost'];
    }
    return $cost;
}

function list_unassigned_sessions() {
    $out = array();
    $analyses = array();
    $base = doc_dir() . '/task-analytics/out/unassigned';
    if (!is_dir($base)) {
        return $out;
    }
    foreach (glob($base . '/ses_*.json') as $file) {
        $a = read_json_file($file);
        if ($a === null) {
            continue;
        }
        $row = unassigned_session_row($a);
        if ($row['session_id'] === '') {
            $row['session_id'] = basename($file, '.json');
        }
        $analyses[$row['session_id']] = $a;
        $out[] = $row;
    }
    $providers = session_provider_map(array_keys($analyses));
    $projects = session_project_map(array_keys($analyses));
    foreach ($out as $i => $row) {
        $sid = $row['session_id'];
        $provider = isset($providers[$sid]['provider']) ? (string)$providers[$sid]['provider'] : '';
        $out[$i]['provider'] = $provider;
        $out[$i]['cost'] = isset($analyses[$sid]) ? session_ledger_cost($analyses[$sid], $provider) : 0.0;
        if (isset($projects[$sid]) && ($projects[$sid]['project'] !== '' || $projects[$sid]['project_label'] !== '')) {
            $out[$i]['project_id'] = (string)$projects[$sid]['project_id'];
            $out[$i]['project'] = (string)$projects[$sid]['project'];
            $out[$i]['project_label'] = (string)$projects[$sid]['project_label'];
        } elseif ($out[$i]['project'] !== '' && $out[$i]['project_label'] === '') {
            $out[$i]['project_label'] = project_display_label($out[$i]['project']);
        }
    }
    usort($out, function ($x, $y) {
        if ($x['started_ts'] === $y['started_ts']) {
            return strcmp($y['session_id'], $x['session_id']);
        }
        return $y['started_ts'] - $x['started_ts'];
    });
    return $out;
}

function unassigned_session_detail($id) {
    if (!valid_session_id($id)) {
        return null;
    }
    $a = read_json_file(doc_dir() . '/task-analytics/out/unassigned/' . $id . '.json');
    if ($a === null) {
        return null;
    }
    $row = unassigned_session_row($a);
    $provider_info = session_provider_map(array($row['session_id']));
    $row['provider'] = isset($provider_info[$row['session_id']]['provider'])
        ? (string)$provider_info[$row['session_id']]['provider'] : '';
    $project_info = session_project_map(array($row['session_id']));
    if (isset($project_info[$row['session_id']])
        && ($project_info[$row['session_id']]['project'] !== '' || $project_info[$row['session_id']]['project_label'] !== '')) {
        $row['project_id'] = (string)$project_info[$row['session_id']]['project_id'];
        $row['project'] = (string)$project_info[$row['session_id']]['project'];
        $row['project_label'] = (string)$project_info[$row['session_id']]['project_label'];
    }
    $tools = array();
    foreach (isset($a['tools']) && is_array($a['tools']) ? $a['tools'] : array() as $tool) {
        $tools[] = array(
            'name' => isset($tool['name']) ? (string)$tool['name'] : 'unknown',
            'calls' => isset($tool['calls']) ? (int)$tool['calls'] : 0,
            'errors' => isset($tool['errors']) ? (int)$tool['errors'] : 0,
            'timeouts' => isset($tool['timeouts']) ? (int)$tool['timeouts'] : 0,
            'median_ms' => isset($tool['median_ms']) ? (int)$tool['median_ms'] : 0,
            'p95_ms' => isset($tool['p95_ms']) ? (int)$tool['p95_ms'] : 0,
        );
    }
    usort($tools, function ($x, $y) {
        return $y['calls'] - $x['calls'];
    });
    $mcp = array();
    foreach (isset($a['mcp_servers']) && is_array($a['mcp_servers']) ? $a['mcp_servers'] : array() as $server) {
        $tokens = isset($server['tokens']) && is_array($server['tokens']) ? $server['tokens'] : array();
        $tool_rows = array();
        if (isset($server['tools']) && is_array($server['tools'])) {
            foreach ($server['tools'] as $tool_name => $tool_calls) {
                $tool_rows[] = array('name' => (string)$tool_name, 'calls' => (int)$tool_calls);
            }
            usort($tool_rows, function ($x, $y) { return $y['calls'] - $x['calls']; });
        }
        $mcp[] = array(
            'server' => isset($server['server']) ? (string)$server['server'] : 'unknown',
            'calls' => isset($server['calls']) ? (int)$server['calls'] : 0,
            'errors' => isset($server['errors']) ? (int)$server['errors'] : 0,
            'tools' => count($tool_rows),
            'tool_rows' => $tool_rows,
            'tokens_in' => isset($tokens['input']) ? (int)$tokens['input'] : 0,
            'cache' => (isset($tokens['cache_read']) ? (int)$tokens['cache_read'] : 0)
                + (isset($tokens['cache_write']) ? (int)$tokens['cache_write'] : 0),
            'tokens_out' => isset($tokens['output']) ? (int)$tokens['output'] : 0,
            'cost' => price_cost(
                $row['model'],
                isset($tokens['input']) ? (int)$tokens['input'] : 0,
                isset($tokens['output']) ? (int)$tokens['output'] : 0,
                isset($tokens['cache_read']) ? (int)$tokens['cache_read'] : 0,
                isset($tokens['cache_write']) ? (int)$tokens['cache_write'] : 0,
                $row['provider']
            ),
        );
    }
    usort($mcp, function ($x, $y) {
        return $y['calls'] - $x['calls'];
    });
    $cli = array();
    foreach (isset($a['cli_tools']) && is_array($a['cli_tools']) ? $a['cli_tools'] : array() as $tool) {
        $tokens = isset($tool['tokens']) && is_array($tool['tokens']) ? $tool['tokens'] : array();
        $cli[] = array(
            'name' => isset($tool['name']) ? (string)$tool['name'] : 'bash',
            'calls' => isset($tool['calls']) ? (int)$tool['calls'] : 0,
            'errors' => isset($tool['errors']) ? (int)$tool['errors'] : 0,
            'tokens_in' => isset($tokens['input']) ? (int)$tokens['input'] : 0,
            'cache' => (isset($tokens['cache_read']) ? (int)$tokens['cache_read'] : 0)
                + (isset($tokens['cache_write']) ? (int)$tokens['cache_write'] : 0),
            'tokens_out' => isset($tokens['output']) ? (int)$tokens['output'] : 0,
            'cost' => price_cost(
                $row['model'],
                isset($tokens['input']) ? (int)$tokens['input'] : 0,
                isset($tokens['output']) ? (int)$tokens['output'] : 0,
                isset($tokens['cache_read']) ? (int)$tokens['cache_read'] : 0,
                isset($tokens['cache_write']) ? (int)$tokens['cache_write'] : 0,
                $row['provider']
            ),
        );
    }
    usort($cli, function ($x, $y) {
        return $y['calls'] - $x['calls'];
    });
    $models = array();
    $ledger = isset($a['token_ledger']) && is_array($a['token_ledger']) ? $a['token_ledger'] : array();
    $by_model = isset($ledger['by_model']) && is_array($ledger['by_model']) ? $ledger['by_model'] : array();
    $session_cost = 0.0;
    foreach ($by_model as $model => $slot) {
        $slot_in = isset($slot['input']) ? (int)$slot['input'] : 0;
        $slot_out = isset($slot['output']) ? (int)$slot['output'] : 0;
        $slot_cr = isset($slot['cache_read']) ? (int)$slot['cache_read'] : 0;
        $slot_cw = isset($slot['cache_write']) ? (int)$slot['cache_write'] : 0;
        $slot_cost = isset($slot['cost']) ? (float)$slot['cost'] : 0.0;
        $calculated = price_cost((string)$model, $slot_in, $slot_out, $slot_cr, $slot_cw, $row['provider']);
        if ($calculated > 0) {
            $slot_cost = $calculated;
        }
        $session_cost += $slot_cost;
        $models[] = array(
            'model' => (string)$model,
            'tokens_in' => $slot_in,
            'cache' => $slot_cr + $slot_cw,
            'cache_read' => $slot_cr,
            'cache_write' => $slot_cw,
            'tokens_out' => $slot_out,
            'reasoning' => isset($slot['reasoning']) ? (int)$slot['reasoning'] : 0,
            'cost' => $slot_cost,
        );
    }
    $ledger_cost = isset($ledger['cost']) ? (float)$ledger['cost'] : 0.0;
    if ($session_cost <= 0 && $ledger_cost > 0) {
        $session_cost = $ledger_cost;
    }
    if ($session_cost <= 0 && isset($provider_info[$row['session_id']]['cost']) && $provider_info[$row['session_id']]['cost'] > 0) {
        $session_cost = (float)$provider_info[$row['session_id']]['cost'];
    }
    $row['cost'] = $session_cost;
    usort($models, function ($x, $y) {
        return ($y['tokens_in'] + $y['cache'] + $y['tokens_out'])
            - ($x['tokens_in'] + $x['cache'] + $x['tokens_out']);
    });
    $findings = array();
    foreach (isset($a['findings']) && is_array($a['findings']) ? $a['findings'] : array() as $finding) {
        $findings[] = array(
            'code' => isset($finding['code']) ? (string)$finding['code'] : 'unknown',
            'count' => isset($finding['count']) ? (int)$finding['count'] : 1,
            'detail' => isset($finding['detail']) ? (string)$finding['detail'] : '',
        );
    }
    $workflow = isset($a['workflow']) && is_array($a['workflow']) ? $a['workflow'] : array();
    return array(
        'summary' => $row,
        'tools' => $tools,
        'mcp' => $mcp,
        'cli' => $cli,
        'models' => $models,
        'findings' => $findings,
        'warnings' => isset($a['warnings']) && is_array($a['warnings']) ? $a['warnings'] : array(),
        'workflow' => $workflow,
    );
}

function analytics_dataset($allowed_task_ids = null, $project_filter = '', $unassigned_stats = null) {
    $allowed = null;
    if (is_array($allowed_task_ids)) {
        $allowed = array();
        foreach ($allowed_task_ids as $allowed_id) {
            $allowed[(string)$allowed_id] = true;
        }
    }
    $result = array(
        'tasks' => array(),
        'totals' => array(
            'sessions' => 0, 'tasks' => 0, 'tokens_in' => 0, 'tokens_out' => 0,
            'tokens_reasoning' => 0, 'cache_read' => 0, 'cache_write' => 0,
            'requests' => 0, 'cost' => 0.0, 'active_ms' => 0, 'duration_ms' => 0,
        ),
        'findings' => array(),
        'tools' => array(),
        'mcp' => array(),
        'cli' => array(),
        'models' => array(),
        'providers' => array(),
        'roles' => array(),
        'slices' => array(),
        'unassigned' => $unassigned_stats !== null ? $unassigned_stats : unassigned_analytics(),
    );
    $findings = array();
    $tools = array();
    $mcp = array();
    $cli = array();
    $models = array();
    $providers = array();
    $roles = array();
    $slices = array();
    foreach (glob(doc_dir() . '/tasks/*/dialogs/index.json') as $index_path) {
        $id = basename(dirname(dirname($index_path)));
        if (!valid_task_id($id)) {
            continue;
        }
        if ($allowed !== null && !isset($allowed[$id])) {
            continue;
        }
        $dialogs = task_dialogs($id, $project_filter);
        if (!$dialogs['present'] || (int)$dialogs['totals']['sessions'] === 0) {
            continue;
        }
        $t = $dialogs['totals'];
        $row = array(
            'id' => $id,
            'title' => task_title($id),
            'sessions' => $t['sessions'],
            'tokens' => $t['tokens_in'] + $t['tokens_out'] + $t['tokens_reasoning'],
            'tokens_in' => $t['tokens_in'],
            'tokens_out' => $t['tokens_out'],
            'cache_read' => $t['cache_read'],
            'requests' => $t['requests'],
            'active_ms' => $t['active_ms'],
            'cost' => $t['cost'],
            'findings' => $t['findings'],
        );
        $result['tasks'][] = $row;
        $result['totals']['tasks']++;
        $result['totals']['sessions'] += $t['sessions'];
        foreach (array('tokens_in', 'tokens_out', 'tokens_reasoning', 'cache_read', 'cache_write',
                       'requests', 'active_ms', 'duration_ms') as $key) {
            $result['totals'][$key] += isset($t[$key]) ? $t[$key] : 0;
        }
        $result['totals']['cost'] += $t['cost'];
        foreach ($dialogs['findings'] as $code => $count) {
            $findings[$code] = isset($findings[$code]) ? $findings[$code] + $count : $count;
        }
        foreach ($dialogs['tools'] as $tool) {
            $name = $tool['name'];
            if (!isset($tools[$name])) {
                $tools[$name] = array('name' => $name, 'calls' => 0, 'errors' => 0);
            }
            $tools[$name]['calls'] += $tool['calls'];
            $tools[$name]['errors'] += $tool['errors'];
        }
        foreach ($dialogs['mcp'] as $server) {
            $name = $server['server'];
            if (!isset($mcp[$name])) {
                $mcp[$name] = array(
                    'server' => $name, 'calls' => 0, 'errors' => 0,
                    'tokens_in' => 0, 'cache' => 0, 'tokens_out' => 0, 'cost' => 0.0,
                    'tools' => array(),
                );
            }
            $mcp[$name]['calls'] += $server['calls'];
            $mcp[$name]['errors'] += $server['errors'];
            if (isset($server['tools']) && is_array($server['tools'])) {
                foreach ($server['tools'] as $tool_name => $tool_calls) {
                    $tool_name = (string)$tool_name;
                    $mcp[$name]['tools'][$tool_name] = isset($mcp[$name]['tools'][$tool_name])
                        ? $mcp[$name]['tools'][$tool_name] + (int)$tool_calls
                        : (int)$tool_calls;
                }
            }
            $mcp[$name]['tokens_in'] += isset($server['tokens_in']) ? $server['tokens_in'] : 0;
            $mcp[$name]['cache'] += isset($server['cache']) ? $server['cache'] : 0;
            $mcp[$name]['tokens_out'] += isset($server['tokens_out']) ? $server['tokens_out'] : 0;
            $mcp[$name]['cost'] += isset($server['cost']) ? (float)$server['cost'] : 0.0;
        }
        foreach ($dialogs['cli'] as $tool) {
            $name = $tool['name'];
            if (!isset($cli[$name])) {
                $cli[$name] = array('name' => $name, 'calls' => 0, 'errors' => 0,
                    'tokens_in' => 0, 'cache' => 0, 'tokens_out' => 0, 'cost' => 0.0);
            }
            $cli[$name]['calls'] += $tool['calls'];
            $cli[$name]['errors'] += $tool['errors'];
            $cli[$name]['tokens_in'] += $tool['tokens_in'];
            $cli[$name]['cache'] += $tool['cache'];
            $cli[$name]['tokens_out'] += $tool['tokens_out'];
            $cli[$name]['cost'] += isset($tool['cost']) ? (float)$tool['cost'] : 0.0;
        }
        foreach ($dialogs['models'] as $model) {
            $name = $model['model'];
            if (!isset($models[$name])) {
                $models[$name] = array(
                    'model' => $name, 'tokens_in' => 0, 'cache' => 0,
                    'cache_read' => 0, 'cache_write' => 0,
                    'tokens_out' => 0, 'reasoning' => 0, 'cost' => 0,
                );
            }
            $models[$name]['tokens_in'] += $model['tokens_in'];
            $models[$name]['cache'] += $model['cache'];
            $models[$name]['cache_read'] += isset($model['cache_read']) ? $model['cache_read'] : 0;
            $models[$name]['cache_write'] += isset($model['cache_write']) ? $model['cache_write'] : 0;
            $models[$name]['tokens_out'] += $model['tokens_out'];
            $models[$name]['reasoning'] += $model['reasoning'];
            $models[$name]['cost'] += $model['cost'];
        }
        foreach ($dialogs['providers'] as $provider) {
            $name = $provider['provider'];
            if (!isset($providers[$name])) {
                $providers[$name] = array(
                    'provider' => $name, 'sessions' => 0,
                    'tokens_in' => 0, 'cache' => 0, 'tokens_out' => 0, 'cost' => 0.0,
                );
            }
            $providers[$name]['sessions'] += $provider['sessions'];
            $providers[$name]['tokens_in'] += $provider['tokens_in'];
            $providers[$name]['cache'] += $provider['cache'];
            $providers[$name]['tokens_out'] += $provider['tokens_out'];
            $providers[$name]['cost'] += $provider['cost'];
        }
        foreach ($dialogs['roles'] as $role => $count) {
            $roles[$role] = isset($roles[$role]) ? $roles[$role] + $count : $count;
        }
        foreach ($dialogs['slices'] as $outcome => $count) {
            $slices[$outcome] = isset($slices[$outcome]) ? $slices[$outcome] + $count : $count;
        }
    }
    usort($result['tasks'], function ($a, $b) {
        return $b['tokens'] - $a['tokens'];
    });
    arsort($findings);
    uasort($tools, function ($a, $b) {
        return $b['calls'] - $a['calls'];
    });
    uasort($mcp, function ($a, $b) {
        return $b['calls'] - $a['calls'];
    });
    arsort($roles);
    arsort($slices);
    uasort($models, function ($a, $b) {
        return ($b['tokens_in'] + $b['cache'] + $b['tokens_out']) - ($a['tokens_in'] + $a['cache'] + $a['tokens_out']);
    });
    uasort($providers, function ($a, $b) {
        return $b['sessions'] - $a['sessions'];
    });
    $result['findings'] = $findings;
    uasort($cli, function ($a, $b) {
        return $b['calls'] - $a['calls'];
    });
    $result['cli'] = array_slice(array_values($cli), 0, 15);
    $result['models'] = array_slice(array_values($models), 0, 10);
    $result['providers'] = array_slice(array_values($providers), 0, 10);
    $result['tools'] = array_slice(array_values($tools), 0, 12);
    foreach ($mcp as $name => $server) {
        arsort($mcp[$name]['tools']);
    }
    $result['mcp'] = array_slice(array_values($mcp), 0, 10);
    $result['roles'] = $roles;
    $result['slices'] = $slices;
    return $result;
}


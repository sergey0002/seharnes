<?php
// Provider lookup from the Kilo SQLite database. Read-only. PHP 7.1 compatible.

function kilo_db_path() {
    $env = getenv('KILO_DB');
    if (is_string($env) && $env !== '' && is_file($env)) {
        return $env;
    }
    $raw = @file_get_contents(__DIR__ . '/../config/service.json');
    $cfg = $raw === false ? null : json_decode($raw, true);
    if (is_array($cfg) && isset($cfg['kilo_db']) && is_file((string) $cfg['kilo_db'])) {
        return (string) $cfg['kilo_db'];
    }
    $home = getenv('HOME');
    if (is_string($home) && $home !== '') {
        $fallback = $home . '/.local/share/kilo/kilo.db';
        if (is_file($fallback)) {
            return $fallback;
        }
    }
    return '';
}

function kilo_connect() {
    static $pdo = false;
    if ($pdo !== false) {
        return $pdo;
    }
    $path = kilo_db_path();
    if ($path === '') {
        $pdo = null;
        return null;
    }
    try {
        $pdo = new PDO('sqlite:' . $path);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $pdo->exec('PRAGMA query_only = ON');
    } catch (Exception $e) {
        $pdo = null;
    }
    return $pdo;
}

function session_provider_map($ids) {
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
        if ($db !== null) {
            $placeholders = implode(',', array_fill(0, count($missing), '?'));
            try {
                $stmt = $db->prepare('SELECT id, model, cost FROM session WHERE id IN (' . $placeholders . ')');
                $stmt->execute($missing);
                $found = array();
                foreach ($stmt->fetchAll(PDO::FETCH_ASSOC) as $row) {
                    $model = isset($row['model']) ? json_decode((string) $row['model'], true) : null;
                    $found[(string) $row['id']] = array(
                        'provider' => is_array($model) && isset($model['providerID']) ? (string) $model['providerID'] : '',
                        'model' => is_array($model) && isset($model['id']) ? (string) $model['id'] : '',
                    );
                }
                foreach ($missing as $id) {
                    $cache[$id] = isset($found[$id]) ? $found[$id] : array('provider' => '', 'model' => '', 'cost' => 0.0);
                }
            } catch (Exception $e) {
                foreach ($missing as $id) {
                    $cache[$id] = array('provider' => '', 'model' => '', 'cost' => 0.0);
                }
            }
        } else {
            foreach ($missing as $id) {
                $cache[$id] = array('provider' => '', 'model' => '', 'cost' => 0.0);
            }
        }
    }
    $out = array();
    foreach ($ids as $id) {
        $out[$id] = $cache[$id];
    }
    return $out;
}

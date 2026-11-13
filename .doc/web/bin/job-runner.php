<?php
// Runs one whitelisted action in the background. PHP 7.1 compatible.
// Usage: php job-runner.php <job_id>

function runner_write_json($path, $data) {
    $tmp = $path . '.tmp.' . getmypid();
    $raw = json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n";
    if (@file_put_contents($tmp, $raw) === false) {
        return false;
    }
    return @rename($tmp, $path);
}

function runner_redact($line) {
    $line = preg_replace('/(token|password|passwd|secret|api[_-]?key)\s*[:=]\s*\S+/i', '$1=***', $line);
    $line = preg_replace('/Bearer\s+[A-Za-z0-9._\-]+/i', 'Bearer ***', $line);
    return $line;
}

function runner_progress($line, $regex) {
    if ($regex !== '') {
        $pattern = '~' . str_replace('~', '\\~', $regex) . '~u';
        if (@preg_match($pattern, $line, $m) === 1) {
            if (isset($m[1], $m[2]) && (int) $m[2] > 0) {
                return (int) floor(((int) $m[1] / (int) $m[2]) * 100);
            }
            if (isset($m[1])) {
                return max(0, min(100, (int) $m[1]));
            }
        }
    }
    if (preg_match('/PROGRESS\s+(\d+)/i', $line, $m) === 1) {
        return max(0, min(100, (int) $m[1]));
    }
    if (preg_match('/\[\s*(\d+)\s*\/\s*(\d+)\s*\]/', $line, $m) === 1 && (int) $m[2] > 0) {
        return (int) floor(((int) $m[1] / (int) $m[2]) * 100);
    }
    if (preg_match('/шаг\s+(\d+)\s+из\s+(\d+)/u', $line, $m) === 1 && (int) $m[2] > 0) {
        return (int) floor(((int) $m[1] / (int) $m[2]) * 100);
    }
    return null;
}

function runner_append_log($path, $line) {
    @file_put_contents($path, runner_redact($line) . "\n", FILE_APPEND);
    clearstatcache(true, $path);
    if (@filesize($path) > 5 * 1024 * 1024) {
        $raw = @file_get_contents($path);
        if ($raw !== false) {
            @file_put_contents($path, substr($raw, -1024 * 1024));
        }
    }
}

function runner_stop($proc) {
    if (!is_resource($proc)) {
        return;
    }
    @proc_terminate($proc, 15);
    usleep(500000);
    @proc_terminate($proc, 9);
}

function runner_main($argv) {
    $id = isset($argv[1]) ? (string) $argv[1] : '';
    if (!preg_match('/^job_[0-9]{8}_[0-9]{6}_[a-f0-9]{4}$/', $id)) {
        fwrite(STDERR, "bad job id\n");
        return 2;
    }
    $root = realpath(__DIR__ . '/../../..');
    $config_raw = @file_get_contents(__DIR__ . '/../config/service.json');
    $config = $config_raw === false ? array() : json_decode($config_raw, true);
    $state_rel = is_array($config) && isset($config['state_dir']) ? (string) $config['state_dir'] : '.doc/web/state';
    $state = $root . '/' . $state_rel;
    $job_dir = $state . '/jobs/' . $id;
    $job_raw = @file_get_contents($job_dir . '/job.json');
    $job = $job_raw === false ? null : json_decode($job_raw, true);
    if (!is_array($job) || !isset($job['argv']) || !is_array($job['argv'])) {
        return 2;
    }
    $lock_path = $state . '/jobs/' . preg_replace('/[^a-z0-9_]/', '_', (string) $job['action']) . '.lock';
    $lock = @fopen($lock_path, 'c');
    if ($lock === false || !flock($lock, LOCK_EX | LOCK_NB)) {
        runner_write_json($job_dir . '/status.json', array(
            'id' => $id,
            'action' => (string) $job['action'],
            'label' => (string) $job['label'],
            'status' => 'failed',
            'phase' => 'done',
            'progress' => null,
            'message' => 'already running',
            'started_at' => gmdate('Y-m-d\TH:i:s\Z'),
            'ended_at' => gmdate('Y-m-d\TH:i:s\Z'),
            'exit_code' => 1,
            'can_cancel' => false,
        ));
        return 1;
    }

    $status_path = $job_dir . '/status.json';
    $log_path = $job_dir . '/log.txt';
    $started = gmdate('Y-m-d\TH:i:s\Z');
    $status = array(
        'id' => $id,
        'action' => (string) $job['action'],
        'label' => (string) $job['label'],
        'status' => 'running',
        'phase' => 'start',
        'progress' => 5,
        'message' => 'запуск',
        'started_at' => $started,
        'ended_at' => null,
        'exit_code' => null,
        'can_cancel' => true,
    );
    runner_write_json($status_path, $status);
    @file_put_contents($job_dir . '/pid', (string) getmypid());

    $env = array(
        'PATH' => (string) getenv('PATH'),
        'HOME' => (string) getenv('HOME'),
        'LANG' => (string) getenv('LANG'),
        'LC_ALL' => (string) getenv('LC_ALL'),
        'PROJECT_ROOT' => $root,
        'PYTHONUNBUFFERED' => '1',
        'TERM' => 'dumb',
    );
    if (isset($job['params']['task'])) {
        $env['TASK_ID'] = (string) $job['params']['task'];
    }
    $cmd = 'setsid ' . implode(' ', array_map('escapeshellarg', $job['argv']));
    $descriptors = array(
        0 => array('file', '/dev/null', 'r'),
        1 => array('pipe', 'w'),
        2 => array('pipe', 'w'),
    );
    $cwd = isset($job['cwd']) && is_dir($job['cwd']) ? $job['cwd'] : $root;
    $proc = @proc_open($cmd, $descriptors, $pipes, $cwd, $env);
    if (!is_resource($proc)) {
        $status['status'] = 'failed';
        $status['phase'] = 'done';
        $status['progress'] = 100;
        $status['message'] = 'cannot start process';
        $status['ended_at'] = gmdate('Y-m-d\TH:i:s\Z');
        $status['exit_code'] = 1;
        runner_write_json($status_path, $status);
        flock($lock, LOCK_UN);
        fclose($lock);
        return 1;
    }

    stream_set_blocking($pipes[1], false);
    stream_set_blocking($pipes[2], false);
    $timeout = isset($job['timeout']) ? (int) $job['timeout'] : 300;
    $progress_regex = isset($job['progress_regex']) ? (string) $job['progress_regex'] : '';
    $start = microtime(true);
    $last_write = 0.0;
    $timed_out = false;
    $cancelled = false;
    $exit_code = null;

    while (true) {
        foreach (array(1, 2) as $fd) {
            while (($line = fgets($pipes[$fd])) !== false) {
                $line = rtrim($line, "\r\n");
                runner_append_log($log_path, $line);
                $p = runner_progress($line, $progress_regex);
                if ($p !== null && $p !== $status['progress']) {
                    $status['progress'] = $p;
                    $status['phase'] = 'run';
                    $status['message'] = $line === '' ? 'выполняется' : substr($line, 0, 160);
                }
            }
        }
        $proc_status = proc_get_status($proc);
        if (!$proc_status['running']) {
            $exit_code = $proc_status['exitcode'];
            break;
        }
        if (is_file($job_dir . '/cancel') && !$cancelled) {
            $cancelled = true;
            $status['status'] = 'cancelling';
            $status['message'] = 'отмена';
            runner_write_json($status_path, $status);
            runner_stop($proc);
        }
        if (!$cancelled && (microtime(true) - $start) > $timeout) {
            $timed_out = true;
            runner_stop($proc);
        }
        $now = microtime(true);
        if ($now - $last_write >= 0.5) {
            runner_write_json($status_path, $status);
            $last_write = $now;
        }
        usleep(100000);
    }

    foreach (array(1, 2) as $fd) {
        if (isset($pipes[$fd]) && is_resource($pipes[$fd])) {
            while (($line = fgets($pipes[$fd])) !== false) {
                runner_append_log($log_path, rtrim($line, "\r\n"));
            }
            fclose($pipes[$fd]);
        }
    }
    proc_close($proc);

    if ($cancelled) {
        $status['status'] = 'cancelled';
        $status['message'] = 'отменено';
        $exit_code = 130;
    } elseif ($timed_out) {
        $status['status'] = 'timeout';
        $status['message'] = 'превышен таймаут';
        $exit_code = 124;
    } elseif ((int) $exit_code === 0) {
        $status['status'] = 'ok';
        $status['message'] = 'готово';
    } else {
        $status['status'] = 'failed';
        $status['message'] = 'ошибка, код ' . (int) $exit_code;
    }
    $status['phase'] = 'done';
    $status['progress'] = 100;
    $status['ended_at'] = gmdate('Y-m-d\TH:i:s\Z');
    $status['exit_code'] = (int) $exit_code;
    $status['can_cancel'] = false;
    runner_write_json($status_path, $status);
    @unlink($state . '/jobs/' . preg_replace('/[^a-z0-9_]/', '_', (string) $job['action']) . '.current');
    @unlink($job_dir . '/pid');
    flock($lock, LOCK_UN);
    fclose($lock);
    return 0;
}

$argv = isset($_SERVER['argv']) ? $_SERVER['argv'] : array();
exit(runner_main($argv));

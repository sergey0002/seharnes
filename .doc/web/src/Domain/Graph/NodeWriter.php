<?php
declare(strict_types=1);

namespace Seharnes\Panel\Domain\Graph;

use Seharnes\Panel\Core\Config;
use RuntimeException;

/**
 * Запись канонического файла узла.
 *
 * Пишем через тот же движок, что и раньше: `harness_mirror.py set --file` —
 * он сам обновляет канонический файл и пересобирает граф, поэтому панель не
 * заводит второй путь записи и второй формат мира.
 *
 * Гарантии: файл только канонический и только внутри репозитория (EditPolicy),
 * запись атомарная (временный файл + переименование), параллельные записи
 * разводит файловая блокировка, размер и кодировка проверяются до записи.
 */
final class NodeWriter
{
    public function __construct(
        private readonly Config $config,
        private readonly GraphRepository $graph,
    ) {
    }

    /**
     * @return array{status: string, error?: string, detail?: array<string, mixed>, stats?: array<string, mixed>|null}
     */
    public function save(string $id, string $content): array
    {
        if (!$this->config->isWritable()) {
            return ['status' => 'failed', 'error' => 'write disabled'];
        }
        $node = $this->graph->find($id);
        if ($node === null) {
            return ['status' => 'failed', 'error' => 'node not found'];
        }
        $policy = EditPolicy::check($node, $this->config->rootDir());
        if (!$policy['editable']) {
            return ['status' => 'failed', 'error' => 'not editable: ' . $policy['reason']];
        }
        if (strlen($content) > EditPolicy::MAX_BYTES) {
            return ['status' => 'failed', 'error' => 'file too large'];
        }
        if (str_contains($content, "\0") || preg_match('//u', $content) !== 1) {
            return ['status' => 'failed', 'error' => 'not a utf-8 text'];
        }
        $script = $this->mirrorScript();
        if ($script === null) {
            return ['status' => 'failed', 'error' => 'mirror script not found'];
        }
        $tmp = $this->writeTemp($id, $content);
        if ($tmp === null) {
            return ['status' => 'failed', 'error' => 'cannot write temp file'];
        }
        $lock = $this->lock();
        if ($lock === null) {
            @unlink($tmp);
            return ['status' => 'failed', 'error' => 'busy'];
        }
        try {
            [$code, $out, $err] = $this->run([
                'python3', $script,
                '--root', $this->config->rootDir(),
                '--data', $this->dataDirRelative(),
                'set', '--node', $id, '--file', '--content', $tmp,
            ]);
            if ($code !== 0) {
                return [
                    'status' => 'failed',
                    'error' => trim($err !== '' ? $err : $out) ?: 'mirror set failed',
                ];
            }
            $result = json_decode($out, true);
            if (is_array($result) && ($result['status'] ?? '') === 'failed') {
                return ['status' => 'failed', 'error' => (string) ($result['error'] ?? 'mirror set failed')];
            }
            return [
                'status' => 'ok',
                'detail' => is_array($result) ? $result : [],
                'stats' => is_array($result['stats'] ?? null) ? $result['stats'] : null,
            ];
        } finally {
            flock($lock, LOCK_UN);
            fclose($lock);
            @unlink($tmp);
        }
    }

    /** Абсолютный путь к скрипту миррора; панель без него писать не умеет. */
    private function mirrorScript(): ?string
    {
        $candidates = [
            $this->config->rootDir() . '/.agents/skills/harness-router/children/mirror/scripts/harness_mirror.py',
        ];
        foreach ($candidates as $file) {
            if (is_file($file)) {
                return $file;
            }
        }
        return null;
    }

    private function dataDirRelative(): string
    {
        $data = $this->config->dataDir();
        $root = rtrim($this->config->rootDir(), '/');
        if (str_starts_with($data, $root . '/')) {
            return substr($data, strlen($root) + 1);
        }
        return $data;
    }

    private function writeTemp(string $id, string $content): ?string
    {
        $dir = $this->config->stateDir() . '/tmp';
        if (!is_dir($dir) && !@mkdir($dir, 0775, true) && !is_dir($dir)) {
            return null;
        }
        $file = $dir . '/' . preg_replace('/[^A-Za-z0-9_.-]/', '_', $id) . '.tmp';
        return @file_put_contents($file, $content) === false ? null : $file;
    }

    /** @return resource|null */
    private function lock()
    {
        $dir = $this->config->stateDir();
        if (!is_dir($dir) && !@mkdir($dir, 0775, true) && !is_dir($dir)) {
            return null;
        }
        $handle = @fopen($dir . '/harness.lock', 'c');
        if ($handle === false) {
            return null;
        }
        if (!flock($handle, LOCK_EX)) {
            fclose($handle);
            return null;
        }
        return $handle;
    }

    /**
     * Запуск процесса без оболочки: массив аргументов исключает подстановки.
     *
     * @param list<string> $command
     * @return array{0: int, 1: string, 2: string}
     */
    private function run(array $command, int $timeout = 180): array
    {
        $descriptors = [1 => ['pipe', 'w'], 2 => ['pipe', 'w']];
        $process = @proc_open($command, $descriptors, $pipes, $this->config->rootDir());
        if (!is_resource($process)) {
            throw new RuntimeException('cannot start mirror process');
        }
        stream_set_blocking($pipes[1], false);
        stream_set_blocking($pipes[2], false);
        $out = '';
        $err = '';
        $deadline = time() + $timeout;
        while (true) {
            $out .= (string) stream_get_contents($pipes[1]);
            $err .= (string) stream_get_contents($pipes[2]);
            $status = proc_get_status($process);
            if (!$status['running']) {
                $out .= (string) stream_get_contents($pipes[1]);
                $err .= (string) stream_get_contents($pipes[2]);
                fclose($pipes[1]);
                fclose($pipes[2]);
                proc_close($process);
                return [(int) $status['exitcode'], $out, $err];
            }
            if (time() > $deadline) {
                proc_terminate($process, 9);
                fclose($pipes[1]);
                fclose($pipes[2]);
                proc_close($process);
                return [124, $out, $err !== '' ? $err : 'timeout'];
            }
            usleep(50_000);
        }
    }
}

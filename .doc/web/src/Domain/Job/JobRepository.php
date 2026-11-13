<?php
declare(strict_types=1);

namespace Seharnes\Panel\Domain\Job;

use Seharnes\Panel\Support\PathGuard;

/**
 * Чтение состояния заданий панели (каталог state/jobs).
 *
 * Репозиторий только читает: запуск и остановку выполняет слой /jobs,
 * который остался прежним. Новый интерфейс не дублирует эту логику, а наблюдает за ней.
 */
final class JobRepository
{
    public function __construct(private readonly string $stateDir)
    {
    }

    /** @return list<array<string, mixed>> Свежие задания, новые сверху. */
    public function recent(int $limit = 20): array
    {
        $dir = $this->stateDir . '/jobs';
        if (!is_dir($dir)) {
            return [];
        }
        $jobs = [];
        foreach (glob($dir . '/job_*', GLOB_ONLYDIR) ?: [] as $jobDir) {
            $status = $this->status(basename($jobDir), 0);
            if ($status === null) {
                continue;
            }
            $jobs[] = array_intersect_key($status, array_flip([
                'id', 'action', 'label', 'status', 'progress', 'started_at', 'ended_at', 'exit_code',
            ]));
        }
        usort($jobs, static fn (array $a, array $b): int => strcmp((string) ($b['started_at'] ?? ''), (string) ($a['started_at'] ?? '')));
        return array_slice($jobs, 0, $limit);
    }

    /** @return array<string, mixed>|null */
    public function status(string $id, int $tailLines = 120): ?array
    {
        if (preg_match('/^job_[0-9]{8}_[0-9]{6}_[a-f0-9]{4}$/', $id) !== 1) {
            return null;
        }
        $raw = $this->read($id, 'status.json');
        if ($raw === null) {
            return null;
        }
        $data = json_decode($raw, true);
        if (!is_array($data)) {
            return null;
        }
        $data['id'] = $id;
        $data['can_cancel'] = in_array($data['status'] ?? '', ['queued', 'running', 'cancelling'], true);
        $data['log_tail'] = $tailLines > 0 ? $this->tail($id, $tailLines) : [];
        return $data;
    }

    /** @return list<string> */
    public function tail(string $id, int $lines = 120): array
    {
        $raw = $this->read($id, 'log.txt');
        if ($raw === null) {
            return [];
        }
        $all = preg_split('/\r?\n/', rtrim($raw, "\r\n")) ?: [];
        return array_slice($all, -max(1, $lines));
    }

    private function read(string $id, string $file): ?string
    {
        if (preg_match('/^job_[0-9]{8}_[0-9]{6}_[a-f0-9]{4}$/', $id) !== 1) {
            return null;
        }
        $path = PathGuard::fileWithin($this->stateDir . '/jobs/' . $id, $file);
        if ($path === null) {
            return null;
        }
        $raw = @file_get_contents($path);
        return $raw === false ? null : $raw;
    }
}

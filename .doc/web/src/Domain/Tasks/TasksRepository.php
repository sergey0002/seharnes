<?php
declare(strict_types=1);

namespace Seharnes\Panel\Domain\Tasks;

/**
 * Задачи, диалоги и аналитика в новом каркасе.
 *
 * Источник данных пока старый слой `.doc/web/app/lib.php`: он читает `task.json` каждой задачи в `.doc/tasks/<id>/`,
 * `dialogs/index.json` задач и выгрузки `.doc/task-analytics/out/unassigned/`. Это осознанный шаг
 * переноса (strangler): страницы и API уже новые, а чтение данных переедет сюда позже,
 * поэтому все вызовы идут через один мост и легко заменяются по одному.
 */
final class TasksRepository
{
    /** Есть ли старый слой данных: без него раздел показывает пустое состояние. */
    public function available(): bool
    {
        return function_exists('list_tasks');
    }

    /**
     * Справочники для тулбара: релизы, ответственные, проекты диалогов.
     *
     * @return array{releases: list<string>, assignees: list<string>, projects: list<array{id: string, label: string}>}
     */
    public function filters(): array
    {
        $tasks = $this->call('list_tasks', [], []);
        $releases = $this->call('list_releases', [$tasks], []);
        $assignees = $this->call('list_assignees', [$tasks], []);
        $unassigned = $this->call('list_unassigned_sessions', [], []);
        $projects = $this->call('list_dialog_projects', [$unassigned], []);

        $projectList = [];
        foreach ($projects as $id => $row) {
            $projectList[] = [
                'id' => (string) ($row['id'] ?? $id),
                'label' => (string) ($row['label'] ?? $id),
            ];
        }

        return [
            'releases' => array_values(array_map('strval', $releases)),
            'assignees' => array_values(array_map('strval', $assignees)),
            'projects' => $projectList,
        ];
    }

    /**
     * Список задач под фильтры раздела.
     *
     * @param array{q?: string, release?: string, assignee?: string, project?: string, unassigned?: bool} $filters
     * @return array<string, mixed>
     */
    public function list(array $filters): array
    {
        $query = trim((string) ($filters['q'] ?? ''));
        $release = trim((string) ($filters['release'] ?? ''));
        $assignee = trim((string) ($filters['assignee'] ?? ''));
        $project = trim((string) ($filters['project'] ?? ''));
        $withUnassigned = (bool) ($filters['unassigned'] ?? false);

        $tasks = $this->call('list_tasks', [], []);
        $rows = [];
        $allowedIds = [];
        foreach ($tasks as $task) {
            if ($release !== '' && (string) $task['release'] !== $release) {
                continue;
            }
            if ($assignee !== '' && (string) $task['assignee'] !== $assignee) {
                continue;
            }
            if ($query !== '' && stripos($task['id'] . ' ' . $task['title'], $query) === false) {
                continue;
            }
            $allowedIds[] = (string) $task['id'];
            $rows[] = [
                'id' => (string) $task['id'],
                'title' => (string) $task['title'],
                'release' => (string) $task['release'],
                'assignee' => (string) $task['assignee'],
                'status' => (string) $task['jira_status'],
                'updated' => (string) $task['jira_updated'],
                'touched' => (string) $task['last_touched'],
                'dialogs' => (int) $task['n_dialogs'],
                'tokens' => (int) $task['analytics_tokens'],
                'cost' => (float) $task['analytics_cost'],
                'findings' => (int) $task['n_findings'],
                'files' => (int) $task['n_files'],
            ];
        }

        $unassigned = $this->unassignedRows($query, $project);

        $totals = ['tasks' => count($rows), 'dialogs' => 0, 'tokens' => 0, 'cost' => 0.0, 'findings' => 0];
        foreach ($rows as $row) {
            $totals['dialogs'] += $row['dialogs'];
            $totals['tokens'] += $row['tokens'];
            $totals['cost'] += $row['cost'];
            $totals['findings'] += $row['findings'];
        }
        $totals['unassigned'] = count($unassigned);

        return [
            'available' => $this->available(),
            'rows' => $rows,
            'totals' => $totals,
            'unassigned' => $withUnassigned ? $unassigned : [],
            'filters' => [
                'q' => $query,
                'release' => $release,
                'assignee' => $assignee,
                'project' => $project,
                'unassigned' => $withUnassigned,
            ],
            'allowed_ids' => $allowedIds,
        ];
    }

    /**
     * Детали задачи для правой панели: метаданные, Jira, диалоги, отчёты, файлы.
     *
     * @return array<string, mixed>|null
     */
    public function detail(string $id, string $project = ''): ?array
    {
        $detail = $this->call('get_task_detail', [$id], null);
        if (!is_array($detail)) {
            return null;
        }
        $dialogs = $this->call('task_dialogs', [$id, $project], []);
        $sessions = [];
        foreach ((array) ($dialogs['sessions'] ?? []) as $session) {
            $sessions[] = [
                'id' => (string) ($session['session_id'] ?? ''),
                'role' => (string) ($session['role'] ?? ''),
                'model' => (string) ($session['model'] ?? ''),
                'provider' => (string) ($session['provider'] ?? ''),
                'date' => (string) ($session['date'] ?? ''),
                'requests' => (int) ($session['requests'] ?? 0),
                'tokens' => (int) ($session['tokens'] ?? 0),
                'cost' => (float) ($session['cost'] ?? 0.0),
                'title' => (string) ($session['title'] ?? ''),
            ];
        }
        usort($sessions, static fn (array $a, array $b): int => $b['tokens'] <=> $a['tokens']);

        return [
            'summary' => $detail['summary'] ?? [],
            'issue_key' => (string) ($detail['issue_key'] ?? ''),
            'exported_at' => (string) ($detail['exported_at'] ?? ''),
            'sections' => array_slice((array) ($detail['sections'] ?? []), 0, 20),
            'files' => array_slice((array) ($detail['files'] ?? []), 0, 40),
            'findings' => array_slice((array) ($detail['findings'] ?? []), 0, 20),
            'reports' => array_slice((array) ($detail['reports'] ?? []), 0, 10),
            'activity' => array_slice((array) ($detail['jira_activity'] ?? []), 0, 8),
            'dialogs_total' => (array) ($dialogs['totals'] ?? []),
            'sessions' => array_slice($sessions, 0, 12),
        ];
    }

    /**
     * Аналитика по срезу фильтров: итоги, строки задач, разрезы и «диалоги без задачи».
     *
     * @param array{q?: string, release?: string, assignee?: string, project?: string, unassigned?: bool} $filters
     * @return array<string, mixed>
     */
    public function analytics(array $filters): array
    {
        $slice = $this->list($filters);
        $project = (string) ($slice['filters']['project'] ?? '');
        $unassignedStats = $this->call('unassigned_analytics', [$this->unassignedRows('', $project)], []);
        $dataset = $this->call('analytics_dataset', [$slice['allowed_ids'], $project, $unassignedStats], []);

        return [
            'available' => $this->available(),
            'filters' => $slice['filters'],
            'totals' => (array) ($dataset['totals'] ?? []),
            'tasks' => array_slice((array) ($dataset['tasks'] ?? []), 0, 200),
            'models' => $this->top((array) ($dataset['models'] ?? [])),
            'tools' => $this->top((array) ($dataset['tools'] ?? [])),
            'mcp' => $this->top((array) ($dataset['mcp'] ?? [])),
            'providers' => $this->top((array) ($dataset['providers'] ?? [])),
            'roles' => $this->top((array) ($dataset['roles'] ?? [])),
            'unassigned' => [
                'totals' => (array) ($unassignedStats['totals'] ?? $unassignedStats ?: []),
                'rows' => (array) ($slice['unassigned'] ?? []),
                'count' => (int) ($slice['totals']['unassigned'] ?? 0),
            ],
        ];
    }

    /**
     * Строки «диалоги без задачи» под фильтры.
     *
     * @return list<array<string, mixed>>
     */
    public function unassignedRows(string $query, string $project): array
    {
        $rows = [];
        foreach ($this->call('list_unassigned_sessions', [], []) as $session) {
            $key = (string) ($session['project_id'] ?? '') !== '' ? (string) $session['project_id'] : (string) ($session['project'] ?? '');
            if ($project !== '' && $key !== $project) {
                continue;
            }
            $haystack = ($session['session_id'] ?? '') . ' ' . ($session['role'] ?? '') . ' '
                . ($session['model'] ?? '') . ' ' . ($session['title'] ?? '') . ' ' . ($session['project_label'] ?? '');
            if ($query !== '' && stripos($haystack, $query) === false) {
                continue;
            }
            $rows[] = [
                'id' => (string) ($session['session_id'] ?? ''),
                'project' => (string) ($session['project_label'] ?? ''),
                'title' => (string) ($session['title'] ?? ''),
                'date' => (string) ($session['date'] ?? ''),
                'model' => (string) ($session['model'] ?? ''),
                'role' => (string) ($session['role'] ?? ''),
                'requests' => (int) ($session['requests'] ?? 0),
                'tokens' => (int) ($session['tokens'] ?? 0),
                'cost' => (float) ($session['cost'] ?? 0.0),
                'status' => (string) ($session['status'] ?? ''),
            ];
        }

        return $rows;
    }

    /**
     * Разрез аналитики в вид «подпись + число», отсортированный по убыванию.
     *
     * @param array<mixed> $bucket
     * @return list<array{label: string, value: int, cost: float}>
     */
    private function top(array $bucket): array
    {
        $rows = [];
        foreach ($bucket as $key => $value) {
            if (is_array($value)) {
                $rows[] = [
                    'label' => (string) ($value['label'] ?? $key),
                    'value' => (int) ($value['count'] ?? $value['sessions'] ?? $value['value'] ?? 0),
                    'cost' => (float) ($value['cost'] ?? 0.0),
                ];
                continue;
            }
            $rows[] = ['label' => (string) $key, 'value' => (int) $value, 'cost' => 0.0];
        }
        usort($rows, static fn (array $a, array $b): int => $b['value'] <=> $a['value']);

        return array_slice($rows, 0, 8);
    }

    /**
     * @param list<mixed> $args
     */
    private function call(string $function, array $args, mixed $default): mixed
    {
        if (!function_exists($function)) {
            return $default;
        }

        try {
            return $function(...$args);
        } catch (\Throwable) {
            return $default;
        }
    }
}

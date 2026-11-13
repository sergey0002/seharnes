<?php
declare(strict_types=1);

namespace Seharnes\Panel\Domain\Harness;

/**
 * Сканы харнеса: канон и мусор, битые ссылки, документация и JSON.
 *
 * Сканы синхронные и только читают дерево, поэтому запускаются прямо из запроса.
 * Вся тяжёлая работа остаётся в harness-core/audit_harness.py: панель не дублирует
 * правила канона, иначе они разъедутся с CLI.
 */
final class HarnessAudit
{
    /** Разрешённые сканы: всё, что пришло извне, фильтруется по этому списку. */
    public const CHECKS = ['canon', 'links', 'docs'];

    private const SCRIPT = '/.agents/skills/harness-router/children/harness-core/scripts/audit_harness.py';

    public function __construct(private readonly string $rootDir)
    {
    }

    /** Путь к скрипту аудита: по нему же видно, установлен ли харнес. */
    public function script(): string
    {
        return $this->rootDir . self::SCRIPT;
    }

    public function available(): bool
    {
        return is_file($this->script());
    }

    /**
     * Нормализует список сканов: пустой ввод означает «все».
     *
     * @param  array<int, mixed>|string $checks
     * @return array<int, string>
     */
    public function normalize(array|string $checks): array
    {
        $items = is_array($checks) ? $checks : explode(',', $checks);
        $selected = [];
        foreach ($items as $item) {
            $item = strtolower(trim((string) $item));
            if (in_array($item, self::CHECKS, true) && !in_array($item, $selected, true)) {
                $selected[] = $item;
            }
        }
        return $selected === [] ? self::CHECKS : $selected;
    }

    /**
     * Запустить выбранные сканы.
     *
     * @param  array<int, mixed>|string $checks
     * @return array<string, mixed> отчёт: status, checks[], selected[], ms
     */
    public function run(array|string $checks): array
    {
        $selected = $this->normalize($checks);
        if (!$this->available()) {
            return [
                'status' => 'failed',
                'error' => 'audit script missing',
                'selected' => $selected,
                'checks' => [],
            ];
        }

        $started = microtime(true);
        $command = sprintf(
            'python3 %s --root %s --checks %s --json',
            escapeshellarg($this->script()),
            escapeshellarg($this->rootDir),
            escapeshellarg(implode(',', $selected)),
        );
        [$code, $stdout, $stderr] = $this->exec($command);
        $report = json_decode(trim($stdout), true);
        if (!is_array($report)) {
            return [
                'status' => 'failed',
                'error' => 'audit failed',
                'selected' => $selected,
                'exit' => $code,
                'raw' => $this->tail($stdout . "\n" . $stderr),
                'checks' => [],
            ];
        }

        $report['selected'] = $selected;
        $report['exit'] = $code;
        $report['ms'] = (int) round((microtime(true) - $started) * 1000);
        return $report;
    }

    /**
     * Запуск внешней команды без оболочки-обёртки: stdout и stderr раздельно,
     * чтобы JSON-отчёт не смешивался с предупреждениями Python.
     *
     * @return array{0: int, 1: string, 2: string}
     */
    private function exec(string $command): array
    {
        $descriptors = [1 => ['pipe', 'w'], 2 => ['pipe', 'w']];
        $process = @proc_open($command, $descriptors, $pipes);
        if (!is_resource($process)) {
            return [-1, '', 'proc_open failed'];
        }
        $stdout = stream_get_contents($pipes[1]) ?: '';
        $stderr = stream_get_contents($pipes[2]) ?: '';
        fclose($pipes[1]);
        fclose($pipes[2]);
        $code = proc_close($process);
        return [$code, $stdout, $stderr];
    }

    private function tail(string $text, int $limit = 2000): string
    {
        $text = trim($text);
        return strlen($text) <= $limit ? $text : substr($text, -$limit);
    }
}

<?php
declare(strict_types=1);

namespace Seharnes\Panel\Domain\Job;

use Seharnes\Panel\Core\Config;
use Throwable;

/**
 * Шов между новым интерфейсом и существующим исполнителем заданий.
 *
 * Запуск действия со всеми проверками (профиль, allow-list скриптов, lock, argv)
 * уже реализован и проверен тестами в app/jobs.php. Дублировать его нельзя:
 * новый каркас вызывает его через этот адаптер. Когда исполнитель переедет
 * в src/Domain/Job — поменяется только тело класса, контроллеры не заметят.
 *
 * Исполнитель печатает JSON сам и выставляет статус ответа. Здесь его вывод
 * перехватывается, а статус восстанавливается, чтобы ответ формировал только
 * новый слой (Response). Заголовки исполнителя совпадают с нашими по значению.
 */
final class JobStarter
{
    public function __construct(private readonly Config $config)
    {
    }

    /**
     * @param array<string, mixed> $params
     * @return array<string, mixed>
     */
    public function start(string $actionId, array $params): array
    {
        if (!function_exists('jobs_start')) {
            $file = $this->config->webDir() . '/app/jobs.php';
            if (!is_file($file)) {
                return ['status' => 'failed', 'error' => 'job runner is not available'];
            }
            require_once $file;
        }
        if (!function_exists('jobs_start')) {
            return ['status' => 'failed', 'error' => 'job runner is not available'];
        }
        $previousStatus = http_response_code();
        ob_start();
        try {
            jobs_start($actionId, $params);
        } catch (Throwable $error) {
            ob_end_clean();
            http_response_code(is_int($previousStatus) ? $previousStatus : 200);
            return ['status' => 'failed', 'error' => 'job runner failed: ' . $error->getMessage()];
        }
        $raw = (string) ob_get_clean();
        http_response_code(is_int($previousStatus) ? $previousStatus : 200);
        $decoded = json_decode($raw, true);
        return is_array($decoded) ? $decoded : ['status' => 'failed', 'error' => 'bad runner response'];
    }
}

<?php

declare(strict_types=1);

namespace Tests\Support\Helper;

use Codeception\Module;
use Codeception\TestInterface;

/**
 * Видимый браузер и читаемые действия.
 *
 * Требование проекта: Acceptance всегда headed (никакого --headless).
 * По умолчанию паузы между шагами нет: 0.4с на шаг добавляли около 20с
 * к одному тесту. Для демонстрации кликов включить QA_VISIBLE_DELAY=0.3.
 *
 * 0 = без паузы (только окно Chrome). По умолчанию 0.
 */
final class VisibleBrowser extends Module
{
    /** @var array{delay: float} */
    protected array $config = [
        'delay' => 0.0,
    ];

    public function _initialize(): void
    {
        $fromEnv = getenv('QA_VISIBLE_DELAY');
        if ($fromEnv !== false && $fromEnv !== '') {
            $this->config['delay'] = (float) $fromEnv;
        }

        $this->debugSection(
            'VisibleBrowser',
            sprintf(
                'headed only, pause after step: %.2fs (QA_VISIBLE_DELAY)',
                $this->config['delay']
            )
        );
    }

    public function _before(TestInterface $test): void
    {
        // Напоминание в лог прогона: окно должно быть на экране WSLg.
        $this->debug('Браузер: видимое окно Chrome (headed). Headless запрещён.');
    }

    /**
     * После зелёного метода Cest пишет evidence в ac-results.json
     * по матрице .doc/tasks/{N}/ac-matrix.json (гейт G12).
     */
    public function _passed(TestInterface $test): void
    {
        $file = getenv('QA_AC_RESULTS_FILE');
        if ($file === false || $file === '') {
            return;
        }

        $method = $test->getMetadata()->getName();
        $taskDir = dirname(dirname(dirname($file)));
        $matrixPath = $taskDir . '/ac-matrix.json';
        if (!is_file($matrixPath)) {
            return;
        }

        $matrix = json_decode((string) file_get_contents($matrixPath), true);
        if (!is_array($matrix) || !is_array($matrix['requirements'] ?? null)) {
            return;
        }

        $ids = [];
        foreach ($matrix['requirements'] as $item) {
            $testName = (string) ($item['test'] ?? '');
            if ($testName !== '' && str_ends_with($testName, '::' . $method)) {
                $ids[] = (string) $item['id'];
            }
        }
        if ($ids === []) {
            return;
        }

        $payload = ['results' => []];
        if (is_file($file)) {
            $decoded = json_decode((string) file_get_contents($file), true);
            if (is_array($decoded) && is_array($decoded['results'] ?? null)) {
                $payload = $decoded;
            }
        }
        $byId = [];
        foreach ($payload['results'] as $item) {
            if (is_array($item) && isset($item['id'])) {
                $byId[(string) $item['id']] = $item;
            }
        }
        foreach ($ids as $id) {
            $byId[$id] = [
                'id' => $id,
                'status' => 'passed',
                'method' => $method,
                'evidence' => 'Codeception passed ' . $method,
            ];
        }
        $payload['results'] = array_values($byId);
        file_put_contents(
            $file,
            json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT) . PHP_EOL,
            LOCK_EX
        );
    }

    public function _afterStep(\Codeception\Step $step): void
    {
        $delay = (float) $this->config['delay'];
        if ($delay <= 0) {
            return;
        }

        // Не тормозить мета-шаги вроде comment/wantTo.
        $name = $step->getAction();
        if (in_array($name, ['comment', 'wantTo', 'wantToTest', 'amGoingTo', 'expect', 'expectTo', 'am'], true)) {
            return;
        }

        usleep((int) round($delay * 1_000_000));
    }
}

<?php
declare(strict_types=1);

namespace Seharnes\Panel\Core;

use RuntimeException;

/**
 * Конфигурация сервиса: единственная точка, где известны пути и файлы настроек.
 *
 * Источники: config/service.json (профиль, data_dir, state_dir), config/actions.json.
 * Класс неизменяемый: после конструктора значения только читаются.
 */
final class Config
{
    /** @var array<string, mixed> */
    private array $service;
    /** @var array<string, mixed> */
    private array $actions;

    public function __construct(
        private readonly string $webDir,
        private readonly string $rootDir,
    ) {
        $this->service = self::readJson($this->webDir . '/config/service.json') ?? [];
        $actions = self::readJson($this->webDir . '/config/actions.json') ?? [];
        $this->actions = is_array($actions['actions'] ?? null) ? $actions['actions'] : [];
    }

    public static function fromWebDir(string $webDir): self
    {
        $real = realpath($webDir);
        if ($real === false) {
            throw new RuntimeException('web directory not found: ' . $webDir);
        }
        $root = realpath($real . '/../..');
        if ($root === false) {
            throw new RuntimeException('repository root not found above ' . $real);
        }
        return new self($real, $root);
    }

    public function webDir(): string
    {
        return $this->webDir;
    }

    public function rootDir(): string
    {
        return $this->rootDir;
    }

    /** Каталог документации проекта: <root>/.doc */
    public function docDir(): string
    {
        return $this->rootDir . '/.doc';
    }

    public function publicDir(): string
    {
        return $this->webDir . '/public';
    }

    public function assetsDir(): string
    {
        return $this->publicDir() . '/assets';
    }

    /** Каталог словарей интерфейса. */
    public function langDir(): string
    {
        return $this->webDir . '/resources/lang';
    }

    /** Каталог сгенерированного графа харнеса. */
    public function dataDir(): string
    {
        $rel = (string) ($this->service['data_dir'] ?? '.doc/skil_data/mirror');
        return self::absolute($rel);
    }

    /** Каталог состояния заданий панели. */
    public function stateDir(): string
    {
        $rel = (string) ($this->service['state_dir'] ?? '.doc/web/state');
        return self::absolute($rel);
    }

    /** Профиль сервиса: core | developer | full. */
    public function profile(): string
    {
        return (string) ($this->service['profile'] ?? 'full');
    }

    public function isWritable(): bool
    {
        return (bool) ($this->service['writable'] ?? false);
    }

    /** @return array<string, mixed> */
    public function service(): array
    {
        return $this->service;
    }

    /** @return list<array<string, mixed>> */
    public function actions(): array
    {
        return array_values($this->actions);
    }

    public function action(string $id): ?array
    {
        foreach ($this->actions as $action) {
            if (($action['id'] ?? null) === $id) {
                return $action;
            }
        }
        return null;
    }

    /** Абсолютный путь из относительного (относительно корня репозитория). */
    private function absolute(string $relative): string
    {
        if ($relative !== '' && ($relative[0] === '/' || preg_match('~^[A-Za-z]:[\\\\/]~', $relative) === 1)) {
            return rtrim($relative, '/\\');
        }
        return $this->rootDir . '/' . trim($relative, '/');
    }

    /** @return array<string, mixed>|null */
    private static function readJson(string $file): ?array
    {
        if (!is_file($file)) {
            return null;
        }
        $raw = @file_get_contents($file);
        if ($raw === false) {
            return null;
        }
        $data = json_decode($raw, true);
        return is_array($data) ? $data : null;
    }
}

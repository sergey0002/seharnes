<?php
declare(strict_types=1);

namespace Seharnes\Panel\Core;

/**
 * Минимальный DI-контейнер: ленивые фабрики по имени сервиса.
 *
 * Правило архитектуры: зависимости передаются через конструктор (внедрение зависимостей),
 * контейнер используется только в точке сборки — Seharnes\Panel\App.
 */
final class Container
{
    /** @var array<string, callable(self): mixed> */
    private array $factories = [];
    /** @var array<string, mixed> */
    private array $instances = [];

    /** @param callable(self): mixed $factory */
    public function set(string $id, callable $factory): void
    {
        $this->factories[$id] = $factory;
        unset($this->instances[$id]);
    }

    public function has(string $id): bool
    {
        return isset($this->factories[$id]) || isset($this->instances[$id]);
    }

    public function get(string $id): mixed
    {
        if (array_key_exists($id, $this->instances)) {
            return $this->instances[$id];
        }
        if (!isset($this->factories[$id])) {
            throw new \RuntimeException('service not found in container: ' . $id);
        }
        $instance = ($this->factories[$id])($this);
        $this->instances[$id] = $instance;
        return $instance;
    }

    /** Подмена готового экземпляра — для тестов. */
    public function replace(string $id, mixed $instance): void
    {
        $this->instances[$id] = $instance;
    }
}

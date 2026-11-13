<?php
declare(strict_types=1);

namespace Seharnes\Panel\Domain\Graph;

use Seharnes\Panel\Support\PathGuard;

/**
 * Правило редактирования узла: какие файлы панель имеет право менять.
 *
 * Одно место, где решается «можно ли писать». Его спрашивают и правая панель
 * (показать редактор), и доменный писатель (разрешить запись). Разъехавшиеся
 * копии правил в интерфейсе и на сервере — прямой путь к записи не туда.
 *
 * Разрешено: канонический файл внутри репозитория, текстовое расширение,
 * размер до 2 МиБ. Копии (`canonical: false`) и файлы вне корня закрыты.
 */
final class EditPolicy
{
    public const MAX_BYTES = 2 * 1024 * 1024;

    private const TEXT_EXTENSIONS = [
        'md', 'markdown', 'mdc', 'json', 'yaml', 'yml', 'txt',
        'sh', 'bash', 'py', 'ps1', 'js', 'mjs', 'toml', 'ini', 'cfg', 'conf',
    ];

    /**
     * @return array{editable: bool, reason: string, absolute: string|null, size: int}
     */
    public static function check(GraphNode $node, string $rootDir): array
    {
        $deny = static fn (string $reason): array => [
            'editable' => false,
            'reason' => $reason,
            'absolute' => null,
            'size' => 0,
        ];

        if (!(bool) ($node->raw['canonical'] ?? false)) {
            return $deny('copy');
        }
        $path = $node->path;
        if ($path === '') {
            return $deny('no-path');
        }
        $extension = strtolower(pathinfo($path, PATHINFO_EXTENSION));
        if (!in_array($extension, self::TEXT_EXTENSIONS, true)) {
            return $deny('binary');
        }
        if ($rootDir === '') {
            return $deny('no-root');
        }
        $absolute = PathGuard::fileWithin($rootDir, $path);
        if ($absolute === null || !is_file($absolute)) {
            return $deny('outside-repo');
        }
        $size = (int) @filesize($absolute);
        if ($size > self::MAX_BYTES) {
            return $deny('too-large');
        }
        return ['editable' => true, 'reason' => '', 'absolute' => $absolute, 'size' => $size];
    }
}

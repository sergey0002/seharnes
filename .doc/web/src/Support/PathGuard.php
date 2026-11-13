<?php
declare(strict_types=1);

namespace Seharnes\Panel\Support;

/**
 * Единая точка проверки путей: любой доступ к файлу проекта идёт через неё.
 *
 * Задача — не дать выйти за разрешённый каталог через ../, симлинки, NUL-байты
 * и абсолютные пути. Ошибка не бросается: возвращается null, вызывающий сам решает.
 */
final class PathGuard
{
    public static function realDirectory(string $path): ?string
    {
        $real = realpath($path);
        return ($real !== false && is_dir($real)) ? $real : null;
    }

    /** Путь внутри $base и существует как файл. */
    public static function fileWithin(string $base, string $relative): ?string
    {
        $baseReal = self::realDirectory($base);
        if ($baseReal === null) {
            return null;
        }
        $candidates = [$baseReal . '/' . ltrim($relative, '/')];
        if (!str_contains($relative, '/')) {
            $candidates[] = $baseReal . '/' . $relative;
        }
        foreach ($candidates as $candidate) {
            $real = realpath($candidate);
            if ($real === false || !is_file($real)) {
                continue;
            }
            if ($real === $baseReal || str_starts_with($real, $baseReal . DIRECTORY_SEPARATOR)) {
                return $real;
            }
        }
        return null;
    }

    /**
     * Идентификатор вида "harnes/state/14-project-migration": сегменты без .., пустых и скрытых.
     */
    public static function safeId(string $id, int $maxLength = 300): bool
    {
        if ($id === '' || strlen($id) > $maxLength) {
            return false;
        }
        foreach (explode('/', $id) as $segment) {
            if ($segment === '' || $segment === '.' || $segment === '..') {
                return false;
            }
            if (preg_match('/^[\p{L}\p{N}][\p{L}\p{N}._\-]*$/u', $segment) !== 1) {
                return false;
            }
        }
        return true;
    }

    /** Относительный путь от каталога: для отображения в интерфейсе. */
    public static function relative(string $base, string $absolute): string
    {
        $prefix = rtrim($base, '/') . '/';
        return str_starts_with($absolute, $prefix) ? substr($absolute, strlen($prefix)) : $absolute;
    }
}

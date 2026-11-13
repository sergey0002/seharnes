<?php
declare(strict_types=1);

namespace Seharnes\Panel;

/**
 * PSR-4 автозагрузка для пространства имён Seharnes\Panel\.
 *
 * Карта: Seharnes\Panel\Core\Request -> <srcDir>/Core/Request.php
 * Никаких зависимостей и composer: панель работает на голом PHP 8.
 */
final class Autoload
{
    private const PREFIX = 'Seharnes\\Panel\\';

    public static function register(string $srcDir): void
    {
        $srcDir = rtrim($srcDir, '/\\');
        spl_autoload_register(static function (string $class) use ($srcDir): void {
            if (!str_starts_with($class, self::PREFIX)) {
                return;
            }
            $relative = substr($class, strlen(self::PREFIX));
            $file = $srcDir . '/' . str_replace('\\', '/', $relative) . '.php';
            if (is_file($file)) {
                require_once $file;
            }
        });
    }
}

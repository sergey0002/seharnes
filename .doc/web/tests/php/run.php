<?php
declare(strict_types=1);

/**
 * Мини-раннер юнит-тестов панели: без composer и PHPUnit.
 *
 * Каждый файл tests/php/*Test.php возвращает массив «имя теста => callable».
 * Тест проходит, если callable не бросил исключение. Код выхода 0/1.
 *
 * Запуск: php tests/php/run.php [фильтр]
 */

require_once __DIR__ . '/../../src/Autoload.php';

\Seharnes\Panel\Autoload::register(dirname(__DIR__, 2) . '/src');

final class Assert
{
    public static function true(bool $value, string $message = 'expected true'): void
    {
        if (!$value) {
            throw new RuntimeException($message);
        }
    }

    public static function false(bool $value, string $message = 'expected false'): void
    {
        self::true(!$value, $message);
    }

    public static function same(mixed $expected, mixed $actual, string $message = ''): void
    {
        if ($expected !== $actual) {
            throw new RuntimeException(sprintf(
                '%sexpected %s, got %s',
                $message !== '' ? $message . ': ' : '',
                var_export($expected, true),
                var_export($actual, true),
            ));
        }
    }

    public static function contains(string $needle, string $haystack, string $message = ''): void
    {
        if (!str_contains($haystack, $needle)) {
            throw new RuntimeException(sprintf(
                '%sstring does not contain %s',
                $message !== '' ? $message . ': ' : '',
                var_export($needle, true),
            ));
        }
    }

    public static function notContains(string $needle, string $haystack, string $message = ''): void
    {
        if (str_contains($haystack, $needle)) {
            throw new RuntimeException(sprintf(
                '%sstring unexpectedly contains %s',
                $message !== '' ? $message . ': ' : '',
                var_export($needle, true),
            ));
        }
    }

    public static function notNull(mixed $value, string $message = 'expected non-null'): void
    {
        if ($value === null) {
            throw new RuntimeException($message);
        }
    }
}

/** Временный каталог с автоматической уборкой. */
function withTempDir(callable $fn): mixed
{
    $dir = sys_get_temp_dir() . '/panel-test-' . bin2hex(random_bytes(6));
    mkdir($dir, 0777, true);
    try {
        return $fn($dir);
    } finally {
        $remove = static function (string $path) use (&$remove): void {
            foreach (glob($path . '/*') ?: [] as $child) {
                is_dir($child) ? $remove($child) : @unlink($child);
            }
            @rmdir($path);
        };
        $remove($dir);
    }
}

function writeFile(string $path, string $content): void
{
    $dir = dirname($path);
    if (!is_dir($dir)) {
        mkdir($dir, 0777, true);
    }
    file_put_contents($path, $content);
}

$filter = $argv[1] ?? '';
$passed = 0;
$failed = 0;
$failures = [];

foreach (glob(__DIR__ . '/*Test.php') ?: [] as $file) {
    $tests = require $file;
    if (!is_array($tests)) {
        continue;
    }
    $suite = basename($file, 'Test.php');
    foreach ($tests as $name => $test) {
        $label = $suite . ' :: ' . $name;
        if ($filter !== '' && !str_contains(strtolower($label), strtolower($filter))) {
            continue;
        }
        try {
            $test();
            $passed++;
            echo "  ok   {$label}\n";
        } catch (Throwable $error) {
            $failed++;
            $failures[$label] = $error;
            echo "  FAIL {$label}\n";
        }
    }
}

echo "\n";
foreach ($failures as $label => $error) {
    echo "--- {$label}\n    {$error->getMessage()}\n    at {$error->getFile()}:{$error->getLine()}\n";
}
echo $failed === 0
    ? "OK ({$passed} tests)\n"
    : "FAILED ({$failed} of " . ($passed + $failed) . ")\n";

exit($failed === 0 ? 0 : 1);

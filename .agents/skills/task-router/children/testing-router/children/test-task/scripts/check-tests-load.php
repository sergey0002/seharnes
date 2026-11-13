<?php

/**
 * Загружает все Cest без браузера: ловит битые симлинки задач,
 * синтаксис, коллизии имён классов.
 *
 * Нужен потому, что обычный прогон требует стенда и chromedriver, а эти
 * три проблемы видны и без них. Отдельно ловит случай "симлинк задачи
 * уходит за пределы docker-маунта" — тогда Codeception молча находит
 * 0 тестов задачи и прогон выглядит зелёным.
 *
 * Запуск через check-tests.sh, PHP 8.2+; первый аргумент задает каталог Codeception.
 * или через раннер:
 *     bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/check-tests.sh
 */

declare(strict_types=1);

$codeceptDir = $argv[1] ?? dirname(__DIR__, 8) . '/.tools/codeception';
if (!is_file($codeceptDir . '/vendor/autoload.php')) {
    fwrite(STDERR, "Codeception autoload not found in: " . $codeceptDir . "\n");
    exit(2);
}
require_once $codeceptDir . '/vendor/autoload.php';

$suiteDir = $codeceptDir . '/tests/Acceptance';

$finder = Symfony\Component\Finder\Finder::create()
    ->files()
    ->name('*Cest.php')
    ->in($suiteDir)
    ->followLinks()
    ->sortByName();

$seen = [];
$problems = [];
$byTask = [];

foreach ($finder as $file) {
    $rel = $file->getRelativePathname();
    $before = get_declared_classes();

    try {
        require_once $file->getRealPath();
    } catch (Throwable $e) {
        $problems[] = sprintf('%s: не загрузился — %s', $rel, $e->getMessage());
        continue;
    }

    $new = array_values(array_diff(get_declared_classes(), $before));
    if ($new === []) {
        $problems[] = sprintf('%s: файл не объявил ни одного класса', $rel);
        continue;
    }

    foreach ($new as $class) {
        if (isset($seen[$class])) {
            $problems[] = sprintf('%s: класс %s уже объявлен в %s', $rel, $class, $seen[$class]);
        }
        $seen[$class] = $rel;

        if (preg_match('#^Task/(\d+)/#', $rel, $m)) {
            $byTask[$m[1]][] = $class;
        }
    }
}

// Симлинк есть, а тестов за ним нет — почти наверняка битая ссылка.
foreach (glob($suiteDir . '/Task/*') ?: [] as $entry) {
    if (!is_link($entry)) {
        continue;
    }
    $task = basename($entry);
    if (!isset($byTask[$task])) {
        $problems[] = sprintf(
            'Task/%s: симлинк есть, но за ним не нашлось Cest (цель: %s)',
            $task,
            readlink($entry) ?: '?'
        );
    }
}

printf("Cest-классов загружено: %d\n", count($seen));
printf("Задач с тестами: %d (%s)\n", count($byTask), implode(', ', array_keys($byTask)));

if ($problems !== []) {
    echo "\nПроблемы:\n";
    foreach ($problems as $p) {
        echo '  ' . $p . "\n";
    }
    exit(1);
}

echo "Проблем нет.\n";
exit(0);

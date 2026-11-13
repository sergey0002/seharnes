<?php
/**
 * Логгер runtime-депрекаций для миграции на PHP 8.5.
 *
 * Подключается через auto_prepend_file, чтобы поймать E_DEPRECATED и
 * E_USER_DEPRECATED из ядра PHP, расширений и библиотек, которые статический
 * сканер не видит (например, передача null в строковые функции PHP 8.1+,
 * динамические свойства, устаревшие сигнатуры методов).
 *
 * Включение (пример для php:8.5-apache):
 *
 *   PHP85_DEPRECATION_LOG=/var/log/php85-deprecations.log
 *   php_value auto_prepend_file /var/www/html/.tools/php85-scan/deprecation-logger.php
 *
 * Или для CLI:
 *
 *   PHP85_DEPRECATION_LOG=/tmp/php85.log \
 *     php -d auto_prepend_file=.tools/php85-scan/deprecation-logger.php script.php
 *
 * Формат строки (TSV):
 *   timestamp  errno  file:line  message
 */

if (getenv('PHP85_DEPRECATION_LOG') === false || getenv('PHP85_DEPRECATION_LOG') === '') {
    return;
}

$GLOBALS['__php85_deprecation_log'] = getenv('PHP85_DEPRECATION_LOG');

set_error_handler(function ($errno, $errstr, $errfile, $errline) {
    $log = isset($GLOBALS['__php85_deprecation_log']) ? $GLOBALS['__php85_deprecation_log'] : null;
    if ($log === null || $log === '') {
        return false;
    }

    // Уважаем @ и error_reporting(), иначе получим шум от подавленных вызовов.
    if (!(error_reporting() & $errno)) {
        return false;
    }

    if ($errno === E_DEPRECATED || $errno === E_USER_DEPRECATED) {
        $line = date('c') . "\t" . $errno . "\t" . $errfile . ':' . $errline . "\t"
            . str_replace(array("\r", "\n", "\t"), ' ', $errstr) . "\n";
        @file_put_contents($log, $line, FILE_APPEND | LOCK_EX);
        // Не показываем депрекации в HTML, но не глушим остальные ошибки.
        return true;
    }

    return false;
});

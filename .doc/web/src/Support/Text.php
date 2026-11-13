<?php
declare(strict_types=1);

namespace Seharnes\Panel\Support;

/**
 * Работа со строками без обязательного расширения mbstring.
 *
 * В образе php:8.4-cli расширения может не быть, поэтому регистронезависимый
 * поиск не должен зависеть от него. Для кириллицы применяется явная карта.
 */
final class Text
{
    private const CYRILLIC = [
        'А' => 'а', 'Б' => 'б', 'В' => 'в', 'Г' => 'г', 'Д' => 'д', 'Е' => 'е', 'Ё' => 'ё',
        'Ж' => 'ж', 'З' => 'з', 'И' => 'и', 'Й' => 'й', 'К' => 'к', 'Л' => 'л', 'М' => 'м',
        'Н' => 'н', 'О' => 'о', 'П' => 'п', 'Р' => 'р', 'С' => 'с', 'Т' => 'т', 'У' => 'у',
        'Ф' => 'ф', 'Х' => 'х', 'Ц' => 'ц', 'Ч' => 'ч', 'Ш' => 'ш', 'Щ' => 'щ', 'Ъ' => 'ъ',
        'Ы' => 'ы', 'Ь' => 'ь', 'Э' => 'э', 'Ю' => 'ю', 'Я' => 'я',
    ];

    public static function lower(string $value): string
    {
        if (function_exists('mb_strtolower')) {
            return mb_strtolower($value, 'UTF-8');
        }
        return strtr(strtolower($value), self::CYRILLIC);
    }

    /** Поиск подстроки без учёта регистра для русского и английского. */
    public static function contains(string $haystack, string $needle): bool
    {
        return $needle === '' || str_contains(self::lower($haystack), self::lower($needle));
    }
}

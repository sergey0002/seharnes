<?php
declare(strict_types=1);

namespace Seharnes\Panel\Support;

/**
 * Обрезка текста без mbstring.
 *
 * В окружении панели нет расширения mbstring, поэтому длину считаем по байтам,
 * но режем по границе слова и не разрываем многобайтовый символ.
 */
final class Cut
{
    public static function text(string $value, int $limit): string
    {
        $value = trim(preg_replace('/\s+/u', ' ', $value) ?? $value);
        if ($limit <= 0 || strlen($value) <= $limit) {
            return $value;
        }
        $head = substr($value, 0, $limit);
        // Отбрасываем хвост, разорванный посреди многобайтового символа.
        while ($head !== '' && ord($head[strlen($head) - 1]) >= 0x80) {
            $head = substr($head, 0, -1);
        }
        $lastSpace = strrpos($head, ' ');
        if ($lastSpace !== false) {
            $head = substr($head, 0, $lastSpace);
        }

        return rtrim($head, " \t.,;:—-") . '…';
    }
}

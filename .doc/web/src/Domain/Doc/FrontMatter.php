<?php
declare(strict_types=1);

namespace Seharnes\Panel\Domain\Doc;

use Seharnes\Panel\Support\Markdown;

/**
 * Разбор front matter документа: YAML-блок --- или HTML-комментарий <!-- meta -->.
 */
final class FrontMatter
{
    /** @return array<string, string> */
    public static function parse(?string $raw): array
    {
        if ($raw === null || $raw === '') {
            return [];
        }
        $block = '';
        if (preg_match('/^---\s*\n([\s\S]*?)\n---/', $raw, $m) === 1) {
            $block = $m[1];
        } elseif (preg_match('/<!--\s*meta\s*\n([\s\S]*?)-->/', $raw, $m) === 1) {
            $block = $m[1];
        }
        if ($block === '') {
            return [];
        }
        $meta = [];
        foreach (explode("\n", $block) as $line) {
            if (preg_match('/^([A-Za-z_][A-Za-z0-9_\-]*)\s*:\s*(.+?)\s*$/', $line, $m) !== 1) {
                continue;
            }
            $value = trim($m[2]);
            if (strlen($value) > 1 && in_array($value[0], ['[', '"', "'"], true)) {
                continue;
            }
            $meta[$m[1]] = Markdown::plain($value);
        }
        return $meta;
    }
}

<?php
declare(strict_types=1);

namespace Seharnes\Panel\Support;

/**
 * Рендер markdown без внешних библиотек.
 *
 * Поддерживает то, что реально встречается в документации харнеса: заголовки, списки,
 * таблицы, блоки кода, инлайн-код, жирный, чекбоксы и безопасные ссылки.
 * Вход считается недоверенным: сначала экранирование, потом разметка.
 */
final class Markdown
{
    public static function escape(string $value): string
    {
        return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }

    public static function render(string $text): string
    {
        $text = (string) preg_replace('/<!--[\s\S]*?-->/', '', $text);
        $text = str_replace(["\r\n", "\r"], "\n", $text);
        $chunks = preg_split('/(```[\s\S]*?```)/', $text, -1, PREG_SPLIT_DELIM_CAPTURE) ?: [];
        $html = '';
        foreach ($chunks as $index => $chunk) {
            if ($index % 2 === 1) {
                $code = (string) preg_replace('/^```[a-zA-Z0-9+\-]*\n?/', '', $chunk);
                $code = (string) preg_replace('/```\s*$/', '', $code);
                $html .= '<pre class="code"><code>' . self::escape($code) . '</code></pre>';
                continue;
            }
            $html .= self::blocks($chunk);
        }
        return $html;
    }

    /**
     * Рендер целого документа: первый H1 убирается (он уже в шапке страницы),
     * заголовки ## и ### получают якоря sec-N в том же порядке, что и self::toc().
     */
    public static function renderDocument(string $text): string
    {
        $text = (string) preg_replace('/\A\s*#\s+.*(\n|$)/', '', $text, 1);
        $html = self::render($text);
        $counter = 0;
        return (string) preg_replace_callback('/<(h[45])>/', static function (array $m) use (&$counter): string {
            $counter++;
            return '<' . $m[1] . ' id="sec-' . $counter . '">';
        }, $html);
    }

    /** @return list<array{id: string, title: string, level: int}> */
    public static function toc(string $text): array
    {
        if (preg_match_all('/^(#{2,3})\s+(.+?)\s*$/m', $text, $matches, PREG_SET_ORDER) === false) {
            return [];
        }
        $toc = [];
        foreach ($matches as $match) {
            $toc[] = [
                'id' => 'sec-' . (count($toc) + 1),
                'title' => self::plain($match[2]),
                'level' => strlen($match[1]),
            ];
        }
        return $toc;
    }

    /** Убирает инлайн-разметку: для заголовков в списках и поиска. */
    public static function plain(string $value): string
    {
        $value = (string) preg_replace('/`([^`]*)`/', '$1', $value);
        $value = (string) preg_replace('/\*\*([^*]+)\*\*/', '$1', $value);
        $value = (string) preg_replace('/\[([^\]]+)\]\([^)]*\)/', '$1', $value);
        return trim($value);
    }

    public static function firstHeading(string $text, string $fallback): string
    {
        if (preg_match('/^#\s+(.+?)\s*$/m', $text, $m) === 1) {
            return self::plain($m[1]);
        }
        return $fallback;
    }

    private static function blocks(string $text): string
    {
        $lines = explode("\n", $text);
        $html = '';
        $paragraph = [];
        $list = [];
        $table = [];

        $flushParagraph = static function () use (&$html, &$paragraph): void {
            if ($paragraph !== []) {
                $html .= '<p>' . nl2br(self::inline(implode("\n", $paragraph))) . '</p>';
                $paragraph = [];
            }
        };
        $flushList = static function () use (&$html, &$list, $flushParagraph): void {
            $flushParagraph();
            if ($list !== []) {
                $html .= '<ul>';
                foreach ($list as $item) {
                    $html .= '<li>' . self::inline($item) . '</li>';
                }
                $html .= '</ul>';
                $list = [];
            }
        };
        $flushTable = static function () use (&$html, &$table, $flushList): void {
            $flushList();
            if ($table === []) {
                return;
            }
            $html .= '<table>';
            foreach ($table as $index => $row) {
                if (preg_match('/^[\s|:\-]+$/', $row) === 1) {
                    continue;
                }
                $cells = array_map('trim', explode('|', trim($row, ' |')));
                $tag = $index === 0 ? 'th' : 'td';
                $html .= '<tr>';
                foreach ($cells as $cell) {
                    $html .= '<' . $tag . '>' . self::inline($cell) . '</' . $tag . '>';
                }
                $html .= '</tr>';
            }
            $html .= '</table>';
            $table = [];
        };

        foreach ($lines as $line) {
            $trimmed = rtrim($line);
            if (preg_match('/^(#{1,4})\s+(.*)$/', $trimmed, $m) === 1) {
                $flushTable();
                $level = strlen($m[1]) + 2;
                $html .= '<h' . $level . '>' . self::inline($m[2]) . '</h' . $level . '>';
            } elseif (preg_match('/^(\d+\.\s+|[-*]\s+)(.*)$/', $trimmed, $m) === 1) {
                $flushParagraph();
                $flushTable();
                $list[] = $m[2];
            } elseif (str_contains($trimmed, '|') && substr_count($trimmed, '|') >= 2) {
                $flushParagraph();
                $flushList();
                $table[] = $trimmed;
            } elseif (preg_match('/^([-*_])\1{2,}$/', trim($trimmed)) === 1) {
                $flushTable();
                $flushList();
                $flushParagraph();
                $html .= '<hr>';
            } elseif (trim($trimmed) === '') {
                $flushTable();
                $flushList();
                $flushParagraph();
            } else {
                $flushTable();
                $flushList();
                $paragraph[] = $trimmed;
            }
        }
        $flushTable();
        $flushList();
        $flushParagraph();
        return $html;
    }

    private static function inline(string $text): string
    {
        $text = self::escape($text);
        $text = (string) preg_replace('/`([^`]+)`/', '<code>$1</code>', $text);
        $text = (string) preg_replace('/\[x\]/i', '<span class="check done">✓</span>', $text);
        $text = (string) preg_replace('/\[ \]/', '<span class="check todo">□</span>', $text);
        $text = (string) preg_replace('/\*\*([^*]+)\*\*/', '<strong>$1</strong>', $text);
        return (string) preg_replace_callback('/\[([^\]]+)\]\(([^)]+)\)/', static function (array $m): string {
            $url = $m[2];
            if (preg_match('~^(https?://|#|/|mailto:)~', $url) !== 1) {
                return $m[1];
            }
            return '<a href="' . self::escape($url) . '" rel="noreferrer noopener">' . $m[1] . '</a>';
        }, $text);
    }
}

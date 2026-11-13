<?php

final class AdfTextConverter
{
    /** @var bool */
    private $inTableCell = false;

    public function toText($value)
    {
        if ($value === null) {
            return '';
        }

        if (is_string($value)) {
            return $value;
        }

        if (!is_array($value)) {
            return '';
        }

        if (!isset($value['type'])) {
            return '';
        }

        return rtrim($this->renderNode($value));
    }

    private function renderNode(array $node)
    {
        $type = isset($node['type']) ? $node['type'] : '';
        $content = isset($node['content']) && is_array($node['content']) ? $node['content'] : array();

        switch ($type) {
            case 'doc':
                return $this->renderChildren($content, "\n\n");

            case 'paragraph':
                $text = $this->renderChildren($content, '');
                return $this->renderSectionHeadingParagraph($text);

            case 'text':
                return $this->renderTextNode($node);

            case 'hardBreak':
                return "\n";

            case 'heading':
                $level = isset($node['attrs']['level']) ? (int) $node['attrs']['level'] : 3;
                $level = max(1, min(6, $level));

                return str_repeat('#', $level) . ' ' . trim($this->renderChildren($content, ''));

            case 'bulletList':
            case 'orderedList':
                $lines = array();
                $index = 1;
                foreach ($content as $item) {
                    if (!is_array($item)) {
                        continue;
                    }
                    $prefix = $type === 'orderedList' ? ($index++ . '. ') : '- ';
                    $lines[] = $prefix . ltrim($this->renderNode($item));
                }

                return implode("\n", $lines);

            case 'listItem':
                return $this->renderChildren($content, "\n");

            case 'blockquote':
                return $this->renderChildren($content, "\n");

            case 'codeBlock':
                return "```\n" . $this->renderChildren($content, '') . "\n```";

            case 'rule':
                return '---';

            case 'table':
                return $this->renderTable($node);

            case 'tableRow':
                return $this->renderChildren($content, '');

            case 'tableCell':
            case 'tableHeader':
                return $this->renderCellInline($node);

            case 'mention':
                if (isset($node['attrs']['text'])) {
                    return (string) $node['attrs']['text'];
                }

                return '@mention';

            case 'emoji':
                if (isset($node['attrs']['shortName'])) {
                    return (string) $node['attrs']['shortName'];
                }

                return '';

            case 'inlineCard':
                if (isset($node['attrs']['url'])) {
                    return '<' . $node['attrs']['url'] . '>';
                }

                return '';

            case 'mediaSingle':
            case 'mediaGroup':
            case 'media':
                return '[attachment]';

            default:
                return $this->renderChildren($content, '');
        }
    }

    private function renderTextNode(array $node)
    {
        $text = isset($node['text']) ? (string) $node['text'] : '';
        if ($text === '' || !isset($node['marks']) || !is_array($node['marks'])) {
            return $text;
        }

        foreach ($node['marks'] as $mark) {
            if (!is_array($mark) || !isset($mark['type'])) {
                continue;
            }

            $text = $this->applyMark($text, $mark);
        }

        return $text;
    }

    private function applyMark($text, array $mark)
    {
        switch ($mark['type']) {
            case 'strong':
                return '**' . $text . '**';

            case 'em':
                return '*' . $text . '*';

            case 'code':
                return '`' . $text . '`';

            case 'strike':
                return '~~' . $text . '~~';

            case 'underline':
                return $text;

            case 'link':
                $href = isset($mark['attrs']['href']) ? trim((string) $mark['attrs']['href']) : '';
                if ($href === '') {
                    return $text;
                }
                if ($text === $href || $text === '<' . $href . '>') {
                    return '<' . $href . '>';
                }

                return '[' . $text . '](' . $href . ')';

            default:
                return $text;
        }
    }

    /**
     * Jira often uses *Заголовок* in a lone paragraph instead of heading node.
     */
    private function renderSectionHeadingParagraph($text)
    {
        $trimmed = trim((string) $text);
        if ($trimmed === '') {
            return '';
        }

        if ($this->inTableCell) {
            return $this->cleanMarkdownEmphasis($this->stripBoldAsterisks($trimmed));
        }

        $plain = $this->plainSectionHeading($trimmed);
        if ($plain !== null) {
            return '### ' . $plain;
        }

        return $this->dedupeAutolinkParens($trimmed);
    }

    /**
     * Jira section titles: *Title* with strong/em marks or literal asterisk nodes.
     */
    private function plainSectionHeading($text)
    {
        $plain = $this->cleanMarkdownEmphasis($text);
        if ($plain === '' || mb_strlen($plain) > 80) {
            return null;
        }

        // Не считать заголовком предложение, заканчивающееся на . ! ?
        if (preg_match('/[.!?]$/u', $plain)) {
            return null;
        }

        return $plain;
    }

    private function cleanMarkdownEmphasis($text)
    {
        $text = trim((string) $text);
        if ($text === '') {
            return '';
        }

        if (preg_match('/^\*([^*]+)\*$/u', $text, $matches)) {
            return trim($matches[1]);
        }

        $text = preg_replace('/^\*+/u', '', $text);
        $text = preg_replace('/\*+$/u', '', $text);
        $text = trim($text);

        if (preg_match('/^\*\*(.+)\*\*$/u', $text, $matches)) {
            return trim($matches[1]);
        }

        if (preg_match('/^\*(.+)\*$/u', $text, $matches)) {
            return trim($matches[1]);
        }

        return $text;
    }

    private function dedupeAutolinkParens($text)
    {
        $text = preg_replace('/<(https?:\/\/[^>]+)>\(<\1>\)/u', '<$1>', $text);
        $text = preg_replace('/<(https?:\/\/[^>]+)>\(\1\)/u', '<$1>', $text);
        $text = preg_replace('/\[(https?:\/\/[^\]]+)\]\(\1\)/u', '<$1>', $text);

        return $text;
    }

    private function renderTable(array $node)
    {
        $content = isset($node['content']) && is_array($node['content']) ? $node['content'] : array();
        $rawRows = array();

        foreach ($content as $child) {
            if (!is_array($child) || $child['type'] !== 'tableRow') {
                continue;
            }
            $rawRows[] = $this->extractTableRowCells($child);
        }

        $rawRows = $this->filterSeparatorRows($rawRows);
        if (empty($rawRows)) {
            return '';
        }

        $header = $this->normalizeHeaderCells($rawRows[0]);
        $columnCount = count($header);
        if ($columnCount === 0) {
            return '';
        }

        $lines = array();
        $lines[] = '| ' . implode(' | ', array_map(array($this, 'escapeTableCell'), $header)) . ' |';
        $lines[] = '| ' . implode(' | ', array_fill(0, $columnCount, '---')) . ' |';

        for ($i = 1, $count = count($rawRows); $i < $count; $i++) {
            $row = $this->padRow($this->normalizeBodyCells($rawRows[$i]), $columnCount);
            $lines[] = '| ' . implode(' | ', array_map(array($this, 'escapeTableCell'), $row)) . ' |';
        }

        return implode("\n", $lines);
    }

    private function extractTableRowCells(array $row)
    {
        $cells = array();
        $content = isset($row['content']) && is_array($row['content']) ? $row['content'] : array();

        foreach ($content as $cell) {
            if (!is_array($cell)) {
                continue;
            }
            if ($cell['type'] !== 'tableCell' && $cell['type'] !== 'tableHeader') {
                continue;
            }

            $colspan = 1;
            if (isset($cell['attrs']['colspan'])) {
                $colspan = max(1, (int) $cell['attrs']['colspan']);
            }

            $cells[] = $this->renderCellInline($cell);
            for ($c = 1; $c < $colspan; $c++) {
                $cells[] = '';
            }
        }

        return $cells;
    }

    private function renderCellInline(array $cell)
    {
        $content = isset($cell['content']) && is_array($cell['content']) ? $cell['content'] : array();
        $this->inTableCell = true;
        $text = $this->renderChildren($content, ' ');
        $this->inTableCell = false;

        return trim(preg_replace('/\s+/u', ' ', $this->dedupeAutolinkParens($text)));
    }

    private function filterSeparatorRows(array $rows)
    {
        $filtered = array();
        foreach ($rows as $row) {
            if (!$this->isSeparatorRow($row)) {
                $filtered[] = $row;
            }
        }

        return $filtered;
    }

    private function isSeparatorRow(array $cells)
    {
        if (empty($cells)) {
            return true;
        }

        foreach ($cells as $cell) {
            $normalized = trim(str_replace(' ', '', $this->stripBoldAsterisks($cell)));
            if ($normalized !== '---' && $normalized !== '') {
                return false;
            }
        }

        return true;
    }

    private function normalizeHeaderCells(array $cells)
    {
        $normalized = array();
        foreach ($cells as $cell) {
            $normalized[] = $this->cleanMarkdownEmphasis($this->stripBoldAsterisks($cell));
        }

        return $normalized;
    }

    private function normalizeBodyCells(array $cells)
    {
        $normalized = array();
        foreach ($cells as $cell) {
            $value = $this->stripBoldAsterisks($cell);
            $normalized[] = $value === '' ? '—' : $value;
        }

        return $normalized;
    }

    private function stripBoldAsterisks($text)
    {
        $text = trim((string) $text);
        if (preg_match('/^\*(.+)\*$/u', $text, $matches)) {
            return trim($matches[1]);
        }

        return $text;
    }

    private function escapeTableCell($text)
    {
        return str_replace('|', '\\|', (string) $text);
    }

    private function padRow(array $row, $columnCount)
    {
        while (count($row) < $columnCount) {
            $row[] = '';
        }

        return array_slice($row, 0, $columnCount);
    }

    private function renderChildren(array $nodes, $separator)
    {
        $parts = array();
        foreach ($nodes as $node) {
            if (!is_array($node)) {
                continue;
            }
            $part = $this->renderNode($node);
            if ($part !== '') {
                $parts[] = $part;
            }
        }

        return implode($separator, $parts);
    }
}

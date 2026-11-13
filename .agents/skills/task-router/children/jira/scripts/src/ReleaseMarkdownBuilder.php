<?php

final class ReleaseMarkdownBuilder
{
    /** @var TaskMarkdownBuilder */
    private $taskBuilder;

    public function __construct(TaskMarkdownBuilder $taskBuilder)
    {
        $this->taskBuilder = $taskBuilder;
    }

    /**
     * @param array<int, array<string, mixed>> $activeIssues
     * @param array<int, array<string, mixed>> $excludedIssues
     */
    public function build($version, array $activeIssues, array $excludedIssues, callable $browseUrlResolver)
    {
        $lines = array();
        $total = count($activeIssues) + count($excludedIssues);

        $lines[] = '# Release ' . $version . ' — задачи Jira';
        $lines[] = '';
        $lines[] = '**Fix Version:** ' . $version;
        $lines[] = '**Exported:** ' . gmdate('d.m.Y H:i') . ' UTC';
        $lines[] = '**Активных (как на доске релиза в Jira):** ' . count($activeIssues);
        $lines[] = '**Всего в Fix Version (API):** ' . $total;
        if (!empty($excludedIssues)) {
            $lines[] = '**Скрыты на доске (Done / Отменено):** ' . count($excludedIssues);
        }
        $lines[] = '';
        $lines[] = 'Без описания и комментариев — только метаданные задач.';
        $lines[] = '';
        $lines[] = '## Сводная таблица';
        $lines[] = '';
        $lines[] = $this->buildSummaryTable($activeIssues);
        $lines[] = '';
        $lines[] = '## Задачи';
        $lines[] = '';
        $lines = array_merge($lines, $this->buildIssueSections($activeIssues, $browseUrlResolver));

        if (!empty($excludedIssues)) {
            $lines[] = '';
            $lines[] = '## Исключённые из доски релиза (Done / Отменено)';
            $lines[] = '';
            $lines[] = $this->buildSummaryTable($excludedIssues);
            $lines[] = '';
            $lines = array_merge($lines, $this->buildIssueSections($excludedIssues, $browseUrlResolver));
        }

        return rtrim(implode("\n", $lines)) . "\n";
    }

    /**
     * @param array<int, array<string, mixed>> $issues
     * @return array<int, string>
     */
    private function buildIssueSections(array $issues, callable $browseUrlResolver)
    {
        $lines = array();

        foreach ($issues as $index => $issue) {
            if ($index > 0) {
                $lines[] = '';
                $lines[] = '---';
                $lines[] = '';
            }

            $issueKey = isset($issue['key']) ? (string) $issue['key'] : '';
            $browseUrl = $issueKey !== '' ? call_user_func($browseUrlResolver, $issueKey) : '';
            $lines[] = rtrim($this->taskBuilder->buildMetaOnly($issue, $browseUrl, 3));
        }

        return $lines;
    }

    /**
     * @param array<int, array<string, mixed>> $issues
     */
    private function buildSummaryTable(array $issues)
    {
        $lines = array();
        $lines[] = '| # | Title | State | Kind | Priority | Assignee | Reporter | Component | Updated |';
        $lines[] = '| --- | --- | --- | --- | --- | --- | --- | --- | --- |';

        foreach ($issues as $issue) {
            $meta = $this->taskBuilder->extractMetaRow($issue);
            $lines[] = '| '
                . $this->escapeCell($meta['issue_id']) . ' | '
                . $this->escapeCell($meta['title']) . ' | '
                . $this->escapeCell($meta['state']) . ' | '
                . $this->escapeCell($meta['kind']) . ' | '
                . $this->escapeCell($meta['priority']) . ' | '
                . $this->escapeCell($meta['assignee']) . ' | '
                . $this->escapeCell($meta['reporter']) . ' | '
                . $this->escapeCell($meta['component']) . ' | '
                . $this->escapeCell($meta['updated']) . ' |';
        }

        return implode("\n", $lines);
    }

    private function escapeCell($value)
    {
        return str_replace('|', '\\|', (string) $value);
    }
}

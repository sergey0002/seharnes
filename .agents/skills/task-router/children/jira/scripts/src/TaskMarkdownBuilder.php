<?php

final class TaskMarkdownBuilder
{
    /** @var array<string, string> */
    private static $changeFieldLabels = array(
        'assignee' => 'Assignee',
        'status' => 'State',
        'priority' => 'Priority',
        'issuetype' => 'Kind',
        'summary' => 'Title',
        'Fix Version' => 'Version',
        'fixVersions' => 'Version',
        'components' => 'Component',
        'description' => 'Description',
    );

    /** @var AdfTextConverter */
    private $adfConverter;

    public function __construct(AdfTextConverter $adfConverter = null)
    {
        $this->adfConverter = $adfConverter !== null ? $adfConverter : new AdfTextConverter();
    }

    public function buildMetaOnly($issue, $browseUrl, $headingLevel = 2)
    {
        $lines = $this->buildMetaLines($issue, $browseUrl, $headingLevel);

        return rtrim(implode("\n", $lines)) . "\n";
    }

    /**
     * @return array<int, string>
     */
    public function extractMetaRow($issue)
    {
        $fields = isset($issue['fields']) && is_array($issue['fields']) ? $issue['fields'] : array();
        $issueNumber = $this->issueNumber($issue);
        $title = isset($fields['summary']) ? $fields['summary'] : 'Untitled';

        return array(
            'issue_id' => $issueNumber,
            'issue_key' => isset($issue['key']) ? (string) $issue['key'] : '',
            'title' => $title,
            'state' => $this->fieldName($fields, 'status'),
            'kind' => $this->fieldName($fields, 'issuetype'),
            'priority' => $this->fieldName($fields, 'priority'),
            'reporter' => $this->personName(isset($fields['reporter']) ? $fields['reporter'] : null),
            'assignee' => $this->personName(isset($fields['assignee']) ? $fields['assignee'] : null),
            'created' => $this->formatDate(isset($fields['created']) ? $fields['created'] : null),
            'updated' => $this->formatDate(isset($fields['updated']) ? $fields['updated'] : null),
            'version' => $this->namedList(isset($fields['fixVersions']) ? $fields['fixVersions'] : null),
            'component' => $this->namedList(isset($fields['components']) ? $fields['components'] : null),
            'labels' => $this->stringList(isset($fields['labels']) ? $fields['labels'] : null),
            'resolution' => $this->fieldName($fields, 'resolution'),
            'parent' => $this->parentLabel(isset($fields['parent']) ? $fields['parent'] : null),
        );
    }

    public function build($issue, array $comments, array $histories, $browseUrl)
    {
        $fields = isset($issue['fields']) && is_array($issue['fields']) ? $issue['fields'] : array();

        $description = trim($this->adfConverter->toText(isset($fields['description']) ? $fields['description'] : null));
        $entries = $this->buildEntries($comments, $histories);

        // Bitbucket issues imported into Jira keep their original number in the
        // text ("Imported from .../issues/328"). Legacy git branches use that
        // number, so the export records it as a normal field.
        $bitbucketText = array($description);
        foreach ($entries as $entry) {
            $bitbucketText[] = isset($entry['body']) ? $entry['body'] : '';
        }
        $bitbucketIssues = $this->extractBitbucketIssues(implode("\n", $bitbucketText));

        $lines = $this->buildMetaLines($issue, $browseUrl, 1, $bitbucketIssues);

        if ($description !== '') {
            $lines[] = '';
            $lines[] = '## Description';
            $lines[] = '';
            $lines[] = $description;
        }

        if (!empty($entries)) {
            $lines[] = '';
            $lines[] = '## Comments';
            $lines[] = '';

            foreach ($entries as $index => $entry) {
                if ($index > 0) {
                    $lines[] = '---';
                    $lines[] = '';
                }

                $lines[] = '**' . $entry['author'] . '** · ' . $this->formatDate($entry['created']);
                $lines[] = '';

                $changeText = $this->formatChanges(isset($entry['changes']) ? $entry['changes'] : null);
                if ($changeText !== '') {
                    $lines[] = $changeText;
                    $lines[] = '';
                }

                $body = trim($entry['body']);
                if ($body !== '') {
                    $lines[] = $body;
                    $lines[] = '';
                }
            }
        }

        return rtrim(implode("\n", $lines)) . "\n";
    }

    /**
     * @return array<int, string>
     */
    private function buildMetaLines($issue, $browseUrl, $headingLevel, array $bitbucketIssues = array())
    {
        $lines = array();
        $fields = isset($issue['fields']) && is_array($issue['fields']) ? $issue['fields'] : array();

        $issueNumber = $this->issueNumber($issue);
        $title = isset($fields['summary']) ? $fields['summary'] : 'Untitled';
        $prefix = str_repeat('#', max(1, min(6, (int) $headingLevel)));

        $lines[] = $prefix . ' Issue #' . $issueNumber . ': ' . $title;
        $lines[] = '';

        if ($browseUrl !== null && $browseUrl !== '') {
            $lines[] = '**Jira:** <' . $browseUrl . '>';
            $lines[] = '';
        }

        $lines[] = '| Field | Value |';
        $lines[] = '| --- | --- |';
        $this->appendMetaRow($lines, 'State', $this->fieldName($fields, 'status'));
        $this->appendMetaRow($lines, 'Kind', $this->fieldName($fields, 'issuetype'));
        $this->appendMetaRow($lines, 'Priority', $this->fieldName($fields, 'priority'));
        $this->appendMetaRow($lines, 'Reporter', $this->personName(isset($fields['reporter']) ? $fields['reporter'] : null));
        $this->appendMetaRow($lines, 'Assignee', $this->personName(isset($fields['assignee']) ? $fields['assignee'] : null));
        $this->appendMetaRow($lines, 'Created', $this->formatDate(isset($fields['created']) ? $fields['created'] : null));
        $this->appendMetaRow($lines, 'Updated', $this->formatDate(isset($fields['updated']) ? $fields['updated'] : null));
        $this->appendMetaRow($lines, 'Version', $this->namedList(isset($fields['fixVersions']) ? $fields['fixVersions'] : null));
        $this->appendMetaRow($lines, 'Component', $this->namedList(isset($fields['components']) ? $fields['components'] : null));
        $this->appendMetaRow($lines, 'Labels', $this->stringList(isset($fields['labels']) ? $fields['labels'] : null));
        $this->appendMetaRow($lines, 'Resolution', $this->fieldName($fields, 'resolution'));
        $this->appendMetaRow($lines, 'Parent', $this->parentLabel(isset($fields['parent']) ? $fields['parent'] : null));
        $this->appendMetaRow($lines, 'Bitbucket', implode(', ', $bitbucketIssues));

        return $lines;
    }

    /**
     * Original Bitbucket issue numbers from "Imported from .../issues/N" links.
     *
     * @return array<int, string>
     */
    private function extractBitbucketIssues($text)
    {
        $numbers = array();
        if (!is_string($text) || $text === '') {
            return $numbers;
        }
        if (preg_match_all('#Imported[ \t]+from[ \t]+<?https?://(?:www\.)?bitbucket\.org/[^\s/]+/[^\s/]+/issues/(\d+)#i', $text, $matches)) {
            foreach ($matches[1] as $number) {
                $number = ltrim((string) $number, '0');
                if ($number !== '') {
                    $numbers[$number] = true;
                }
            }
        }
        return array_keys($numbers);
    }

    private function buildEntries(array $comments, array $histories)
    {
        $entries = array();

        foreach ($comments as $comment) {
            $entries[] = array(
                'created' => isset($comment['created']) ? $comment['created'] : '',
                'author' => $this->personName(isset($comment['author']) ? $comment['author'] : null),
                'body' => $this->adfConverter->toText(isset($comment['body']) ? $comment['body'] : null),
                'changes' => null,
            );
        }

        foreach ($histories as $history) {
            $changes = $this->historyToChanges(isset($history['items']) ? $history['items'] : null);
            $body = '';

            $entries[] = array(
                'created' => isset($history['created']) ? $history['created'] : '',
                'author' => $this->personName(isset($history['author']) ? $history['author'] : null),
                'body' => $body,
                'changes' => $changes,
            );
        }

        usort($entries, function ($a, $b) {
            return strcmp($a['created'], $b['created']);
        });

        $filtered = array();
        foreach ($entries as $entry) {
            $body = trim($entry['body']);
            $changeText = $this->formatChanges($entry['changes']);
            if ($body === '' && $changeText === '') {
                continue;
            }
            $filtered[] = $entry;
        }

        return $filtered;
    }

    private function historyToChanges($items)
    {
        if (!is_array($items) || empty($items)) {
            return null;
        }

        $changes = array();
        foreach ($items as $item) {
            if (!is_array($item) || !isset($item['field'])) {
                continue;
            }

            $field = (string) $item['field'];
            $changes[$field] = array(
                'old' => isset($item['fromString']) ? (string) $item['fromString'] : '',
                'new' => isset($item['toString']) ? (string) $item['toString'] : '',
            );
        }

        return empty($changes) ? null : $changes;
    }

    private function formatChanges($changes)
    {
        if (!is_array($changes) || empty($changes)) {
            return '';
        }

        $parts = array();
        foreach ($changes as $field => $delta) {
            if (!is_array($delta)) {
                continue;
            }

            $old = isset($delta['old']) ? (string) $delta['old'] : '';
            $new = isset($delta['new']) ? (string) $delta['new'] : '';
            if ($old === '' && $new === '') {
                continue;
            }

            $label = isset(self::$changeFieldLabels[$field])
                ? self::$changeFieldLabels[$field]
                : ucfirst(str_replace('_', ' ', $field));
            $parts[] = $label . ': `' . $old . '` → `' . $new . '`';
        }

        if (empty($parts)) {
            return '';
        }

        return '*Changed:* ' . implode(', ', $parts);
    }

    private function issueNumber(array $issue)
    {
        if (!isset($issue['key']) || !is_string($issue['key'])) {
            return isset($issue['id']) ? (string) $issue['id'] : '';
        }

        $pos = strrpos($issue['key'], '-');
        if ($pos === false) {
            return $issue['key'];
        }

        return substr($issue['key'], $pos + 1);
    }

    private function appendMetaRow(array &$lines, $label, $value)
    {
        if ($value === null || $value === '') {
            return;
        }

        $lines[] = '| ' . $label . ' | ' . $this->escapeCell($value) . ' |';
    }

    private function escapeCell($value)
    {
        return str_replace('|', '\\|', (string) $value);
    }

    private function personName($person)
    {
        if (!is_array($person)) {
            return 'Unknown';
        }

        if (isset($person['displayName']) && $person['displayName'] !== '') {
            return $person['displayName'];
        }

        if (isset($person['name']) && $person['name'] !== '') {
            return $person['name'];
        }

        return 'Unknown';
    }

    private function fieldName(array $fields, $fieldKey)
    {
        if (!isset($fields[$fieldKey]) || !is_array($fields[$fieldKey])) {
            return '';
        }

        if (isset($fields[$fieldKey]['name']) && $fields[$fieldKey]['name'] !== '') {
            return $fields[$fieldKey]['name'];
        }

        return '';
    }

    private function namedList($items)
    {
        if (!is_array($items) || empty($items)) {
            return '';
        }

        $names = array();
        foreach ($items as $item) {
            if (!is_array($item)) {
                continue;
            }
            if (isset($item['name']) && $item['name'] !== '') {
                $names[] = $item['name'];
            }
        }

        return implode(', ', $names);
    }

    private function stringList($items)
    {
        if (!is_array($items) || empty($items)) {
            return '';
        }

        $values = array();
        foreach ($items as $item) {
            if (is_string($item) && $item !== '') {
                $values[] = $item;
            }
        }

        return implode(', ', $values);
    }

    private function parentLabel($parent)
    {
        if (!is_array($parent)) {
            return '';
        }

        $key = isset($parent['key']) ? (string) $parent['key'] : '';
        $summary = '';
        if (isset($parent['fields']) && is_array($parent['fields']) && isset($parent['fields']['summary'])) {
            $summary = (string) $parent['fields']['summary'];
        }

        if ($key === '' && $summary === '') {
            return '';
        }

        if ($summary === '') {
            return $key;
        }

        return $key . ': ' . $summary;
    }

    private function formatDate($iso)
    {
        if ($iso === null || $iso === '') {
            return '';
        }

        $timestamp = strtotime($iso);
        if ($timestamp === false) {
            return (string) $iso;
        }

        return gmdate('d.m.Y H:i', $timestamp) . ' UTC';
    }
}

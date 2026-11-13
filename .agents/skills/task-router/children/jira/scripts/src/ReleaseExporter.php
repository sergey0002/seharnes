<?php

final class ReleaseExporter
{
    /** @var JiraClient */
    private $client;

    /** @var ReleaseMarkdownBuilder */
    private $builder;

    /** @var TaskMarkdownBuilder */
    private $taskBuilder;

    /** @var string */
    private $outputRoot;

    public function __construct(
        JiraClient $client,
        ReleaseMarkdownBuilder $builder,
        TaskMarkdownBuilder $taskBuilder,
        $outputRoot
    ) {
        $this->client = $client;
        $this->builder = $builder;
        $this->taskBuilder = $taskBuilder;
        $this->outputRoot = rtrim($outputRoot, '/\\');
    }

    public function export($releaseVersion)
    {
        $version = JiraClient::normalizeReleaseVersion($releaseVersion);
        if ($version === '') {
            throw new InvalidArgumentException('release_version is required');
        }

        $issues = $this->client->searchByFixVersion($version);
        $partition = self::partitionIssues($issues);
        $client = $this->client;

        $markdown = $this->builder->build(
            $version,
            $partition['active'],
            $partition['excluded'],
            function ($issueKey) use ($client) {
                return $client->browseUrl($issueKey);
            }
        );

        $docDir = $this->outputRoot . DIRECTORY_SEPARATOR . '.doc';
        if (!is_dir($docDir) && !mkdir($docDir, 0777, true) && !is_dir($docDir)) {
            throw new RuntimeException('Cannot create directory: ' . $docDir);
        }

        $taskFile = $docDir . DIRECTORY_SEPARATOR . $version . '.md';
        if (file_put_contents($taskFile, $markdown) === false) {
            throw new RuntimeException('Cannot write file: ' . $taskFile);
        }

        $rows = array();
        foreach ($partition['active'] as $issue) {
            $rows[] = $this->taskBuilder->extractMetaRow($issue);
        }

        return array(
            'release_version' => $version,
            'path' => $taskFile,
            'issues_count' => count($partition['active']),
            'issues_total' => count($issues),
            'issues_excluded' => count($partition['excluded']),
            'issues' => $rows,
        );
    }

    /**
     * Jira release board usually hides Done and Cancelled issues.
     *
     * @param array<int, array<string, mixed>> $issues
     * @return array{active: array<int, array<string, mixed>>, excluded: array<int, array<string, mixed>>}
     */
    public static function partitionIssues(array $issues)
    {
        $active = array();
        $excluded = array();

        foreach ($issues as $issue) {
            if (self::isExcludedFromReleaseBoard($issue)) {
                $excluded[] = $issue;
            } else {
                $active[] = $issue;
            }
        }

        return array(
            'active' => $active,
            'excluded' => $excluded,
        );
    }

    /**
     * @param array<string, mixed> $issue
     */
    private static function isExcludedFromReleaseBoard(array $issue)
    {
        $fields = isset($issue['fields']) && is_array($issue['fields']) ? $issue['fields'] : array();
        if (!isset($fields['status']) || !is_array($fields['status'])) {
            return false;
        }

        $status = $fields['status'];
        $name = isset($status['name']) ? (string) $status['name'] : '';
        $category = '';
        if (isset($status['statusCategory']) && is_array($status['statusCategory'])) {
            $category = isset($status['statusCategory']['key'])
                ? (string) $status['statusCategory']['key']
                : '';
        }

        if ($category === 'done') {
            return true;
        }

        $cancelledNames = array('Отменено', 'Cancelled', 'Canceled');
        return in_array($name, $cancelledNames, true);
    }
}

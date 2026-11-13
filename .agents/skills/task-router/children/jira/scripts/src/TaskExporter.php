<?php

final class TaskExporter
{
    private $client;
    private $builder;
    private $outputRoot;

    public function __construct(JiraClient $client, TaskMarkdownBuilder $builder, $outputRoot)
    {
        $this->client = $client;
        $this->builder = $builder;
        $this->outputRoot = rtrim($outputRoot, '/\\');
    }

    public function export($issueId)
    {
        $issueId = IssueIdParser::parse($issueId, $this->client->projectKey());

        $issue = $this->client->getIssue($issueId);
        $pages = $this->client->listIssueCommentsPaged($issueId);
        $comments = array();
        foreach ($pages as $page) {
            foreach ($page['comments'] as $comment) {
                $comments[] = $comment;
            }
        }
        $changes = $this->client->listIssueChanges($issue);

        $issueKey = isset($issue['key']) ? $issue['key'] : $this->client->issueKeyFromNumber($issueId);
        $browseUrl = $this->client->browseUrl($issueKey);
        $markdown = $this->builder->build($issue, $comments, $changes, $browseUrl);

        $taskDir = $this->outputRoot . DIRECTORY_SEPARATOR . '.doc' . DIRECTORY_SEPARATOR . 'tasks' . DIRECTORY_SEPARATOR . $issueId;
        if (!is_dir($taskDir) && !mkdir($taskDir, 0777, true) && !is_dir($taskDir)) {
            throw new RuntimeException('Cannot create directory: ' . $taskDir);
        }

        $taskFile = $taskDir . DIRECTORY_SEPARATOR . 'task.md';
        if (file_put_contents($taskFile, $markdown) === false) {
            throw new RuntimeException('Cannot write file: ' . $taskFile);
        }

        $trackerPath = $this->writeTrackerSnapshot($taskDir, $issue, $pages, $changes, $issueKey, $markdown);

        $fields = isset($issue['fields']) && is_array($issue['fields']) ? $issue['fields'] : array();

        $result = array(
            'issue_id' => $issueId,
            'issue_key' => $issueKey,
            'path' => $taskFile,
            'comments_count' => count($comments),
            'changes_count' => count($changes),
            'title' => isset($fields['summary']) ? $fields['summary'] : '',
        );
        if ($trackerPath !== null) {
            $result['tracker_path'] = $trackerPath;
        }

        return $result;
    }

    /**
     * JSONdoc dual output (plan 19.2): normalized tracker snapshot next to the
     * legacy markdown. Failure here must NOT fail the export itself.
     */
    private function writeTrackerSnapshot($taskDir, $issue, $pages, $changes, $issueKey, $markdown)
    {
        try {
            $fields = isset($issue['fields']) && is_array($issue['fields']) ? $issue['fields'] : array();

            $person = function ($value) {
                if (!is_array($value)) {
                    return null;
                }
                return array(
                    'id' => isset($value['accountId']) ? $value['accountId'] : null,
                    'name' => isset($value['displayName']) ? $value['displayName'] : null,
                    'active' => isset($value['active']) ? (bool) $value['active'] : null,
                );
            };

            $fixVersions = array();
            if (isset($fields['fixVersions']) && is_array($fields['fixVersions'])) {
                foreach ($fields['fixVersions'] as $version) {
                    $fixVersions[] = array(
                        'name' => isset($version['name']) ? $version['name'] : null,
                        'released' => isset($version['released']) ? (bool) $version['released'] : null,
                    );
                }
            }

            $status = isset($fields['status']) && is_array($fields['status']) ? $fields['status'] : array();
            $statusOut = array(
                'id' => isset($status['id']) ? $status['id'] : null,
                'name' => isset($status['name']) ? $status['name'] : null,
                'category' => isset($status['statusCategory']) && is_array($status['statusCategory'])
                    ? array(
                        'id' => isset($status['statusCategory']['id']) ? $status['statusCategory']['id'] : null,
                        'key' => isset($status['statusCategory']['key']) ? $status['statusCategory']['key'] : null,
                        'name' => isset($status['statusCategory']['name']) ? $status['statusCategory']['name'] : null,
                    ) : null,
            );

            $adfConverter = new AdfTextConverter();

            $commentsPages = array();
            foreach ($pages as $page) {
                $commentsOut = array();
                foreach ($page['comments'] as $comment) {
                    $rawBody = isset($comment['body']) ? $comment['body'] : null;
                    $cleanText = $adfConverter->toText($rawBody);
                    $commentsOut[] = array(
                        'id' => isset($comment['id']) ? $comment['id'] : null,
                        'author' => $person(isset($comment['author']) ? $comment['author'] : null),
                        'created_at' => isset($comment['created']) ? $comment['created'] : null,
                        'updated_at' => isset($comment['updated']) ? $comment['updated'] : null,
                        'clean_text' => $cleanText,
                        'body' => $rawBody,
                        'visibility' => isset($comment['visibility']) ? $comment['visibility'] : null,
                    );
                }
                $commentsPages[] = array(
                    'start_at' => $page['start_at'],
                    'max_results' => $page['max_results'],
                    'total' => $page['total'],
                    'is_last' => $page['is_last'],
                    'comments' => $commentsOut,
                );
            }

            $issueLinks = array();
            if (isset($fields['issuelinks']) && is_array($fields['issuelinks'])) {
                foreach ($fields['issuelinks'] as $link) {
                    $type = isset($link['type']['name']) ? $link['type']['name'] : 'relates';
                    $direction = isset($link['inwardIssue']) ? 'inward' : 'outward';
                    $linked = isset($link['inwardIssue']) ? $link['inwardIssue'] : (isset($link['outwardIssue']) ? $link['outwardIssue'] : null);
                    if ($linked && is_array($linked)) {
                        $issueLinks[] = array(
                            'id' => isset($link['id']) ? $link['id'] : null,
                            'type' => $type,
                            'direction' => $direction,
                            'key' => isset($linked['key']) ? $linked['key'] : null,
                            'summary' => isset($linked['fields']['summary']) ? $linked['fields']['summary'] : null,
                            'status' => isset($linked['fields']['status']['name']) ? $linked['fields']['status']['name'] : null,
                        );
                    }
                }
            }

            $parent = null;
            if (isset($fields['parent']) && is_array($fields['parent'])) {
                $parent = array(
                    'key' => isset($fields['parent']['key']) ? $fields['parent']['key'] : null,
                    'summary' => isset($fields['parent']['fields']['summary']) ? $fields['parent']['fields']['summary'] : null,
                );
            }

            $subtasks = array();
            if (isset($fields['subtasks']) && is_array($fields['subtasks'])) {
                foreach ($fields['subtasks'] as $sub) {
                    if (is_array($sub) && isset($sub['key'])) {
                        $subtasks[] = array(
                            'key' => $sub['key'],
                            'summary' => isset($sub['fields']['summary']) ? $sub['fields']['summary'] : null,
                            'status' => isset($sub['fields']['status']['name']) ? $sub['fields']['status']['name'] : null,
                        );
                    }
                }
            }

            $payload = array(
                'schema_version' => '1.0',
                'issue' => array(
                    'issue_key' => $issueKey,
                    'summary' => isset($fields['summary']) ? $fields['summary'] : null,
                    'status' => $statusOut,
                    'issuetype' => isset($fields['issuetype']) && is_array($fields['issuetype'])
                        ? array(
                            'id' => isset($fields['issuetype']['id']) ? $fields['issuetype']['id'] : null,
                            'name' => isset($fields['issuetype']['name']) ? $fields['issuetype']['name'] : null,
                        ) : null,
                    'resolution' => isset($fields['resolution']) && is_array($fields['resolution'])
                        ? array(
                            'id' => isset($fields['resolution']['id']) ? $fields['resolution']['id'] : null,
                            'name' => isset($fields['resolution']['name']) ? $fields['resolution']['name'] : null,
                        ) : null,
                    'priority' => isset($fields['priority']) && is_array($fields['priority'])
                        ? array(
                            'id' => isset($fields['priority']['id']) ? $fields['priority']['id'] : null,
                            'name' => isset($fields['priority']['name']) ? $fields['priority']['name'] : null,
                        ) : null,
                    'creator' => $person(isset($fields['creator']) ? $fields['creator'] : null),
                    'reporter' => $person(isset($fields['reporter']) ? $fields['reporter'] : null),
                    'assignee' => $person(isset($fields['assignee']) ? $fields['assignee'] : null),
                    'fix_versions' => $fixVersions,
                    'labels' => isset($fields['labels']) && is_array($fields['labels']) ? $fields['labels'] : array(),
                    'components' => (function ($items) {
                        $out = array();
                        foreach ($items as $item) {
                            if (is_array($item)) {
                                $out[] = array(
                                    'id' => isset($item['id']) ? $item['id'] : null,
                                    'name' => isset($item['name']) ? $item['name'] : null,
                                );
                            }
                        }
                        return $out;
                    })(isset($fields['components']) && is_array($fields['components']) ? $fields['components'] : array()),
                    'issuelinks' => $issueLinks,
                    'parent' => $parent,
                    'subtasks' => $subtasks,
                    'created' => isset($fields['created']) ? $fields['created'] : null,
                    'updated' => isset($fields['updated']) ? $fields['updated'] : null,
                    'resolutiondate' => isset($fields['resolutiondate']) ? $fields['resolutiondate'] : null,
                    'duedate' => isset($fields['duedate']) ? $fields['duedate'] : null,
                ),
                'comments_pages' => $commentsPages,
                'changelog_pages' => array(array(
                    'start_at' => 0,
                    'max_results' => count($changes),
                    'total' => count($changes),
                    'is_last' => true,
                    'histories' => $changes,
                )),
                'exporter' => 'gototask',
                'exported_at' => gmdate('Y-m-d\TH:i:s\Z'),
                'task_md_sha256' => hash('sha256', $markdown),
                'field_availability' => array(),
            );

            $dir = $taskDir . DIRECTORY_SEPARATOR . '_jsondoc' . DIRECTORY_SEPARATOR . 'work';
            if (!is_dir($dir) && !mkdir($dir, 0777, true) && !is_dir($dir)) {
                throw new RuntimeException('Cannot create directory: ' . $dir);
            }
            $path = $dir . DIRECTORY_SEPARATOR . 'tracker.json';
            $json = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
            if ($json === false || file_put_contents($path, $json . "\n") === false) {
                throw new RuntimeException('Cannot write file: ' . $path);
            }

            return $path;
        } catch (Exception $e) {
            fwrite(STDERR, 'tracker snapshot failed: ' . $e->getMessage() . PHP_EOL);

            return null;
        }
    }
}

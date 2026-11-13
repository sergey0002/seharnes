#!/usr/bin/env php
<?php

$baseDir = __DIR__;
$srcDir = $baseDir . DIRECTORY_SEPARATOR . 'src';

require_once $srcDir . DIRECTORY_SEPARATOR . 'EnvConfig.php';
require_once $srcDir . DIRECTORY_SEPARATOR . 'IssueIdParser.php';
require_once $srcDir . DIRECTORY_SEPARATOR . 'AdfTextConverter.php';
require_once $srcDir . DIRECTORY_SEPARATOR . 'JiraClient.php';
require_once $srcDir . DIRECTORY_SEPARATOR . 'TaskMarkdownBuilder.php';
require_once $srcDir . DIRECTORY_SEPARATOR . 'TaskExporter.php';
require_once $srcDir . DIRECTORY_SEPARATOR . 'ReleaseMarkdownBuilder.php';
require_once $srcDir . DIRECTORY_SEPARATOR . 'ReleaseExporter.php';
require_once $srcDir . DIRECTORY_SEPARATOR . 'McpStdioServer.php';

function resolveConfigPath($baseDir)
{
    $configPath = getenv('JIRA_CONFIG_FILE') ?: ($baseDir . DIRECTORY_SEPARATOR . 'config.env');
    if (is_file($configPath)) {
        return $configPath;
    }

    throw new RuntimeException('Create config.env from config.example.env in ' . $baseDir);
}

function resolveOutputRoot(EnvConfig $config, $baseDir)
{
    $configured = $config->get('WORKSPACE_ROOT');
    if ($configured !== null && $configured !== '') {
        return rtrim($configured, '/\\');
    }

    // .doc/skil_data/jira -> repo root
    return dirname(dirname($baseDir));
}

function buildJiraClient($baseDir)
{
    $config = new EnvConfig(resolveConfigPath($baseDir));

    return new JiraClient(
        $config->requireValue('JIRA_BASE_URL'),
        $config->requireValue('JIRA_PROJECT_KEY'),
        $config->requireValue('JIRA_EMAIL'),
        $config->requireValue('JIRA_API_TOKEN')
    );
}

function buildExporter($baseDir)
{
    $config = new EnvConfig(resolveConfigPath($baseDir));
    $client = buildJiraClient($baseDir);

    return new TaskExporter(
        $client,
        new TaskMarkdownBuilder(new AdfTextConverter()),
        resolveOutputRoot($config, $baseDir)
    );
}

function buildReleaseExporter($baseDir)
{
    $config = new EnvConfig(resolveConfigPath($baseDir));
    $client = buildJiraClient($baseDir);
    $taskBuilder = new TaskMarkdownBuilder(new AdfTextConverter());

    return new ReleaseExporter(
        $client,
        new ReleaseMarkdownBuilder($taskBuilder),
        $taskBuilder,
        resolveOutputRoot($config, $baseDir)
    );
}

function mcpTextResult($text, $isError = false)
{
    return array(
        'content' => array(
            array(
                'type' => 'text',
                'text' => $text,
            ),
        ),
        'isError' => $isError,
    );
}

function formatReleaseCliSummary(array $result)
{
    $lines = array();
    $lines[] = 'Saved: ' . $result['path'];
    $lines[] = 'Release: ' . $result['release_version'];
    $lines[] = 'Active: ' . $result['issues_count'] . ' (total API: ' . $result['issues_total'] . ', excluded: ' . $result['issues_excluded'] . ')';

    foreach ($result['issues'] as $row) {
        $lines[] = '#'
            . $row['issue_id']
            . ' | '
            . $row['state']
            . ' | '
            . $row['assignee']
            . ' | '
            . $row['title'];
    }

    return implode(PHP_EOL, $lines);
}

function formatReleaseMcpSummary(array $result)
{
    $lines = array();
    $lines[] = 'Exported release ' . $result['release_version'];
    $lines[] = 'Path: ' . $result['path'];
    $lines[] = 'Active: ' . $result['issues_count'] . ' (total API: ' . $result['issues_total'] . ', excluded: ' . $result['issues_excluded'] . ')';
    $lines[] = '';

    foreach ($result['issues'] as $row) {
        $lines[] = '#'
            . $row['issue_id']
            . ' | '
            . $row['state']
            . ' | '
            . $row['kind']
            . ' | '
            . $row['assignee']
            . ' | '
            . $row['reporter']
            . ' | '
            . $row['title'];
    }

    return implode("\n", $lines);
}

function parseReleaseCliArg(array $argv)
{
    if (!isset($argv[1]) || $argv[1] === '') {
        return null;
    }

    if ($argv[1] === 'release' || $argv[1] === '--release') {
        if (!isset($argv[2]) || trim($argv[2]) === '') {
            throw new InvalidArgumentException('Usage: php server.php release 5.7.2');
        }

        return $argv[2];
    }

    return null;
}

// CLI mode
if (PHP_SAPI === 'cli' && isset($argv[1]) && $argv[1] !== '') {
    try {
        $releaseVersion = parseReleaseCliArg($argv);
        if ($releaseVersion !== null) {
            $exporter = buildReleaseExporter($baseDir);
            $result = $exporter->export($releaseVersion);
            fwrite(STDOUT, formatReleaseCliSummary($result) . PHP_EOL);
            exit(0);
        }

        $exporter = buildExporter($baseDir);
        $result = $exporter->export($argv[1]);
        fwrite(STDOUT, "Saved: " . $result['path'] . PHP_EOL);
        fwrite(STDOUT, "Key: " . $result['issue_key'] . PHP_EOL);
        fwrite(STDOUT, "Title: " . $result['title'] . PHP_EOL);
        fwrite(STDOUT, "Comments: " . $result['comments_count'] . PHP_EOL);
        fwrite(STDOUT, "Changes: " . $result['changes_count'] . PHP_EOL);
        exit(0);
    } catch (Exception $e) {
        fwrite(STDERR, $e->getMessage() . PHP_EOL);
        exit(1);
    }
}

$server = new McpStdioServer();

$server->registerTool(
    'export_task_md',
    array(
        'description' => 'Fetch Jira issue by numeric number and write .doc/tasks/{id}/task.md with full metadata, description, comments and changelog.',
        'inputSchema' => array(
            'type' => 'object',
            'properties' => array(
                'issue_id' => array(
                    'type' => 'string',
                    'description' => 'Jira issue: numeric id (2538), key (CT-2538), or browse URL',
                ),
            ),
            'required' => array('issue_id'),
        ),
    ),
    function (array $arguments) use ($baseDir) {
        try {
            if (!isset($arguments['issue_id'])) {
                throw new InvalidArgumentException('issue_id is required');
            }

            $exporter = buildExporter($baseDir);
            $result = $exporter->export($arguments['issue_id']);

            $text = "Exported issue #" . $result['issue_id'] . "\n"
                . "Key: " . $result['issue_key'] . "\n"
                . "Title: " . $result['title'] . "\n"
                . "Path: " . $result['path'] . "\n"
                . "Comments: " . $result['comments_count'] . "\n"
                . "Changes: " . $result['changes_count'];

            return mcpTextResult($text, false);
        } catch (Exception $e) {
            return mcpTextResult('Error: ' . $e->getMessage(), true);
        }
    }
);

$server->registerTool(
    'list_release_tasks',
    array(
        'description' => 'Fetch all Jira issues for a Fix Version (release) and write .doc/{version}.md with metadata only (no description, no comments).',
        'inputSchema' => array(
            'type' => 'object',
            'properties' => array(
                'release_version' => array(
                    'type' => 'string',
                    'description' => 'Fix Version name, e.g. 5.7.2 or releases/5.7.2',
                ),
            ),
            'required' => array('release_version'),
        ),
    ),
    function (array $arguments) use ($baseDir) {
        try {
            if (!isset($arguments['release_version'])) {
                throw new InvalidArgumentException('release_version is required');
            }

            $exporter = buildReleaseExporter($baseDir);
            $result = $exporter->export($arguments['release_version']);

            return mcpTextResult(formatReleaseMcpSummary($result), false);
        } catch (Exception $e) {
            return mcpTextResult('Error: ' . $e->getMessage(), true);
        }
    }
);

$server->run();

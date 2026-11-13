<?php
/**
 * J13a dual-output test (offline): fake JiraClient transport via subclass,
 * TaskExporter::export into a sandbox dir, assertions on task.md and
 * tracker.json contract. Run: php .doc/skil_data/jira/test-dual-export.php
 */

require_once __DIR__ . '/src/EnvConfig.php';
require_once __DIR__ . '/src/IssueIdParser.php';
require_once __DIR__ . '/src/JiraClient.php';
require_once __DIR__ . '/src/AdfTextConverter.php';
require_once __DIR__ . '/src/TaskMarkdownBuilder.php';
require_once __DIR__ . '/src/TaskExporter.php';

function fixtureIssue()
{
    return array(
        'key' => 'CT-2612',
        'fields' => array(
            'summary' => 'Услуга архивации',
            'status' => array(
                'id' => '3',
                'name' => 'In Progress',
                'statusCategory' => array('id' => '2', 'key' => 'indeterminate',
                                          'name' => 'In Progress'),
            ),
            'assignee' => array('accountId' => 'u1', 'displayName' => 'Dev',
                                'active' => true),
            'fixVersions' => array(array('name' => '5.6.1', 'released' => false)),
            'labels' => array('orders'),
            'components' => array(array('id' => 'c1', 'name' => 'backend')),
            'created' => '2026-08-01T10:00:00.000+0300',
            'updated' => '2026-09-20T12:00:00.000+0300',
            'resolutiondate' => null,
            'duedate' => null,
        ),
        'changelog' => array('histories' => array(array(
            'id' => 'h1',
            'created' => '2026-09-02T11:00:00.000+0300',
            'author' => array('accountId' => 'u1', 'displayName' => 'Dev'),
            'items' => array(array('field' => 'status', 'fromString' => 'Open',
                                   'toString' => 'In Progress')),
        ))),
    );
}

function fixtureComment($id)
{
    return array(
        'id' => 'c-' . $id,
        'author' => array('accountId' => 'u0', 'displayName' => 'QA',
                          'active' => true),
        'created' => '2026-09-01T00:00:00.000+0000',
        'updated' => null,
        'body' => 'comment ' . $id,
    );
}

class FakeJiraClient extends JiraClient
{
    private $issue;

    public function __construct($issue)
    {
        parent::__construct('https://jira.example.test', 'CT', 'qa@example.test', 'token');
        $this->issue = $issue;
    }

    protected function request($path)
    {
        if (strpos($path, '/comment') !== false) {
            $startAt = 0;
            if (preg_match('/startAt=(\d+)/', $path, $m)) {
                $startAt = (int) $m[1];
            }
            if ($startAt === 0) {
                $comments = array();
                for ($i = 0; $i < 100; $i++) {
                    $comments[] = fixtureComment($i);
                }
                return array('startAt' => 0, 'maxResults' => 100, 'total' => 101,
                             'comments' => $comments);
            }
            return array('startAt' => 100, 'maxResults' => 100, 'total' => 101,
                         'comments' => array(fixtureComment(100)));
        }
        if (strpos($path, '/issue/') !== false) {
            return $this->issue;
        }
        throw new RuntimeException('unexpected path ' . $path);
    }
}

function assert_true($condition, $message)
{
    if (!$condition) {
        fwrite(STDERR, 'FAIL: ' . $message . PHP_EOL);
        exit(1);
    }
    echo 'ok - ', $message, PHP_EOL;
}

$sandbox = sys_get_temp_dir() . '/jsondoc-dual-' . getmypid();
if (is_dir($sandbox)) {
    foreach (new RecursiveIteratorIterator(new RecursiveDirectoryIterator($sandbox, FilesystemIterator::SKIP_DOTS)) as $file) {
        unlink($file->getPathname());
    }
    rmdir($sandbox . '/.doc/tasks/2612/_jsondoc/work');
    rmdir($sandbox . '/.doc/tasks/2612/_jsondoc');
    rmdir($sandbox . '/.doc/tasks/2612');
    rmdir($sandbox . '/.doc/tasks');
    rmdir($sandbox . '/.doc');
    rmdir($sandbox);
}
mkdir($sandbox . '/.doc/tasks', 0777, true);

$client = new FakeJiraClient(fixtureIssue());
$builder = new TaskMarkdownBuilder();
$exporter = new TaskExporter($client, $builder, $sandbox);

$result = $exporter->export('2612');

$taskFile = $sandbox . '/.doc/tasks/2612/task.md';
assert_true(is_file($taskFile), 'task.md written');
$markdown1 = file_get_contents($taskFile);
assert_true(strpos($markdown1, 'CT-2612') !== false, 'task.md contains issue key');

assert_true(isset($result['tracker_path']), 'tracker_path in result');
$trackerFile = $result['tracker_path'];
assert_true(is_file($trackerFile), 'tracker.json written');
$payload = json_decode(file_get_contents($trackerFile), true);
assert_true(is_array($payload), 'tracker.json is valid json');
assert_true($payload['schema_version'] === '1.0', 'schema_version');
assert_true($payload['issue']['issue_key'] === 'CT-2612', 'issue_key');
assert_true($payload['issue']['fix_versions'][0]['name'] === '5.6.1', 'fix_version');
assert_true(isset($payload['issue']['issuelinks']), 'issue links present');
assert_true(array_key_exists('parent', $payload['issue']), 'parent field present');
assert_true(isset($payload['issue']['subtasks']), 'subtasks field present');
assert_true($payload['issue']['created'] === '2026-08-01T10:00:00.000+0300', 'created field present');
assert_true($payload['issue']['updated'] === '2026-09-20T12:00:00.000+0300', 'updated field present');
assert_true($payload['issue']['components'][0]['name'] === 'backend', 'components mapped');
assert_true(count($payload['changelog_pages']) === 1, 'changelog page present');
assert_true(count($payload['changelog_pages'][0]['histories']) === 1, 'changelog history present');
assert_true($payload['changelog_pages'][0]['histories'][0]['items'][0]['field'] === 'status', 'changelog item field');
assert_true(count($payload['comments_pages']) === 2, 'two comment pages');
assert_true(isset($payload['comments_pages'][0]['comments'][0]['clean_text']), 'comment clean_text present');
assert_true(count($payload['comments_pages'][0]['comments']) === 100, 'page one size');
assert_true(count($payload['comments_pages'][1]['comments']) === 1, 'page two size');
assert_true($payload['comments_pages'][0]['total'] === 101, 'total reported');
assert_true($payload['exporter'] === 'gototask', 'exporter actor');
assert_true($payload['task_md_sha256'] === hash('sha256', $markdown1), 'task_md hash matches');

sleep(1);
$exporter->export('2612');
$markdown2 = file_get_contents($taskFile);
assert_true($markdown1 === $markdown2, 'task.md byte-identical on rerun');
$payload2 = json_decode(file_get_contents($trackerFile), true);
assert_true($payload2['exported_at'] !== $payload['exported_at'], 'exported_at refreshed');

echo 'PASS dual-export', PHP_EOL;
exit(0);

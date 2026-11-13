<?php
/**
 * Проверка JIRA_EMAIL + JIRA_API_TOKEN (без вывода секрета).
 * Usage: php diag-auth.php [myself|issue] [issue_number]
 */
require __DIR__ . '/src/EnvConfig.php';
require __DIR__ . '/src/IssueIdParser.php';

$config = new EnvConfig(__DIR__ . '/config.env');
$baseUrl = rtrim((string) $config->get('JIRA_BASE_URL', ''), '/');
$projectKey = strtoupper(trim((string) $config->get('JIRA_PROJECT_KEY', 'CT')));
$email = $config->get('JIRA_EMAIL');
$token = $config->get('JIRA_API_TOKEN');

echo "base_url={$baseUrl}\n";
echo "project_key={$projectKey}\n";
echo 'email=' . ($email ?: '(empty)') . "\n";
$t = (string) $token;
echo 'token_length=' . strlen($t) . "\n";
echo 'token_has_wrapping_quotes=' . (preg_match('/^["\'].*["\']$/', $t) ? 'yes' : 'no') . "\n";
echo 'token_has_whitespace=' . (preg_match('/\s/', $t) ? 'yes' : 'no') . "\n";

$test = isset($argv[1]) ? $argv[1] : 'issue';
$issueNumber = isset($argv[2]) && $argv[2] !== '' ? IssueIdParser::parse($argv[2], $projectKey) : '2538';
$issueKey = $projectKey . '-' . $issueNumber;

$url = $test === 'myself'
    ? $baseUrl . '/rest/api/3/myself'
    : $baseUrl . '/rest/api/3/issue/' . rawurlencode($issueKey);

echo "url={$url}\n";

$ch = curl_init($url);
curl_setopt_array($ch, array(
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_USERPWD => $email . ':' . $token,
    CURLOPT_HTTPHEADER => array('Accept: application/json'),
    CURLOPT_TIMEOUT => 30,
));
$body = curl_exec($ch);
$code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

echo "HTTP {$code}\n";
$decoded = json_decode((string) $body, true);
if ($code === 200 && is_array($decoded)) {
    if (isset($decoded['displayName'])) {
        echo 'user=' . $decoded['displayName'] . "\n";
    }
    if (isset($decoded['key'])) {
        echo 'issue_key=' . $decoded['key'] . "\n";
    }
    if (isset($decoded['fields']['summary'])) {
        echo 'issue_summary=' . $decoded['fields']['summary'] . "\n";
    }
    echo "ok\n";
} elseif (is_array($decoded)) {
    if (isset($decoded['errorMessages']) && is_array($decoded['errorMessages'])) {
        echo 'api_message=' . implode('; ', $decoded['errorMessages']) . "\n";
    } elseif (isset($decoded['message'])) {
        echo 'api_message=' . $decoded['message'] . "\n";
    }
} else {
    echo "hint=401 usually means wrong Atlassian email, invalid/expired token, or missing read:jira-work scope\n";
}

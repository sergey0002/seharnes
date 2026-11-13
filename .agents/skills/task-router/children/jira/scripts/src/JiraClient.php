<?php

class JiraClient
{
    private $baseUrl;
    private $email;
    private $apiToken;
    private $projectKey;

    public function __construct($baseUrl, $projectKey, $email, $apiToken)
    {
        $this->baseUrl = rtrim((string) $baseUrl, '/');
        $this->projectKey = strtoupper(trim((string) $projectKey));
        $this->email = $email;
        $this->apiToken = $apiToken;
    }

    public function projectKey()
    {
        return $this->projectKey;
    }

    public function issueKeyFromNumber($issueNumber)
    {
        return $this->projectKey . '-' . (string) $issueNumber;
    }

    public function getIssue($issueNumber)
    {
        $issueKey = $this->issueKeyFromNumber($issueNumber);

        return $this->request(
            '/rest/api/3/issue/' . rawurlencode($issueKey)
            . '?expand=changelog'
        );
    }

    /**
     * Comments with page metadata (for JSONdoc tracker snapshots).
     * Same requests as listIssueComments; returns pages instead of a flat list.
     */
    public function listIssueCommentsPaged($issueNumber)
    {
        $issueKey = $this->issueKeyFromNumber($issueNumber);
        $path = '/rest/api/3/issue/' . rawurlencode($issueKey) . '/comment';

        $pages = array();
        $startAt = 0;
        $maxResults = 100;

        while (true) {
            $query = $path . '?startAt=' . $startAt
                . '&maxResults=' . $maxResults;

            $response = $this->request($query);
            $comments = isset($response['comments']) && is_array($response['comments'])
                ? $response['comments'] : array();
            $total = isset($response['total']) ? (int) $response['total'] : null;

            $pages[] = array(
                'start_at' => $startAt,
                'max_results' => $maxResults,
                'total' => $total,
                'is_last' => (count($comments) === 0)
                    || ($total !== null && $startAt + count($comments) >= $total),
                'comments' => $comments,
            );

            if (count($comments) === 0
                || ($total !== null && $startAt + count($comments) >= $total)) {
                break;
            }

            $startAt += count($comments);
        }

        return $pages;
    }

    public function listIssueComments($issueNumber)
    {
        $issueKey = $this->issueKeyFromNumber($issueNumber);
        $path = '/rest/api/3/issue/' . rawurlencode($issueKey) . '/comment';

        return $this->paginate($path, 'comments');
    }

    public function listIssueChanges($issue)
    {
        if (!isset($issue['changelog']['histories']) || !is_array($issue['changelog']['histories'])) {
            return array();
        }

        return $issue['changelog']['histories'];
    }

    /**
     * @return array<int, array<string, mixed>>
     */
    public function listProjectVersions()
    {
        $response = $this->request(
            '/rest/api/3/project/' . rawurlencode($this->projectKey) . '/versions'
        );

        return is_array($response) ? $response : array();
    }

    /**
     * @param array<int, string>|null $fields
     * @return array<int, array<string, mixed>>
     */
    public function searchByFixVersion($version, array $fields = null)
    {
        $version = self::normalizeReleaseVersion($version);
        if ($version === '') {
            throw new InvalidArgumentException('release version is required');
        }

        $escaped = str_replace('"', '\\"', $version);
        $jql = 'project = ' . $this->projectKey
            . ' AND fixVersion = "' . $escaped . '"'
            . ' ORDER BY key ASC';

        return $this->searchIssuesJql($jql, $fields);
    }

    /**
     * @param array<int, string>|null $fields
     * @return array<int, array<string, mixed>>
     */
    public function searchIssuesJql($jql, array $fields = null)
    {
        if ($fields === null) {
            $fields = self::defaultSearchFields();
        }

        $issues = array();
        $nextPageToken = null;
        $maxResults = 100;

        while (true) {
            $query = '/rest/api/3/search/jql'
                . '?jql=' . rawurlencode($jql)
                . '&maxResults=' . $maxResults
                . '&fields=' . rawurlencode(implode(',', $fields));

            if ($nextPageToken !== null && $nextPageToken !== '') {
                $query .= '&nextPageToken=' . rawurlencode($nextPageToken);
            }

            $response = $this->request($query);
            if (isset($response['issues']) && is_array($response['issues'])) {
                $issues = array_merge($issues, $response['issues']);
            }

            $isLast = !isset($response['isLast']) || (bool) $response['isLast'];
            $nextPageToken = isset($response['nextPageToken']) ? (string) $response['nextPageToken'] : '';

            if ($isLast || $nextPageToken === '') {
                break;
            }
        }

        return $issues;
    }

    public static function normalizeReleaseVersion($version)
    {
        $version = trim((string) $version);
        $version = preg_replace('#^(releases?)/#i', '', $version);

        return trim($version);
    }

    /**
     * @return array<int, string>
     */
    public static function defaultSearchFields()
    {
        return array(
            'summary',
            'status',
            'issuetype',
            'priority',
            'reporter',
            'assignee',
            'created',
            'updated',
            'fixVersions',
            'components',
            'labels',
            'resolution',
            'parent',
        );
    }

    protected function paginate($path, $itemsKey)
    {
        $items = array();
        $startAt = 0;
        $maxResults = 100;

        while (true) {
            $query = $path . (strpos($path, '?') === false ? '?' : '&')
                . 'startAt=' . $startAt
                . '&maxResults=' . $maxResults;

            $response = $this->request($query);
            if (isset($response[$itemsKey]) && is_array($response[$itemsKey])) {
                $items = array_merge($items, $response[$itemsKey]);
            }

            $total = isset($response['total']) ? (int) $response['total'] : count($items);
            $fetched = isset($response[$itemsKey]) && is_array($response[$itemsKey])
                ? count($response[$itemsKey])
                : 0;

            if ($fetched === 0 || count($items) >= $total) {
                break;
            }

            $startAt += $fetched;
        }

        return $items;
    }

    public function browseUrl($issueKey)
    {
        return $this->baseUrl . '/browse/' . rawurlencode($issueKey);
    }

    protected function request($path)
    {
        $url = $this->baseUrl . $path;

        $ch = curl_init($url);
        if ($ch === false) {
            throw new RuntimeException('Failed to init curl');
        }

        curl_setopt_array($ch, array(
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER => array(
                'Accept: application/json',
                'User-Agent: jira-task-mcp/1.0',
            ),
            CURLOPT_USERPWD => $this->email . ':' . $this->apiToken,
            CURLOPT_TIMEOUT => 60,
        ));

        $body = curl_exec($ch);
        $status = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $error = curl_error($ch);
        curl_close($ch);

        if ($body === false) {
            throw new RuntimeException('Jira request failed: ' . $error);
        }

        $decoded = json_decode($body, true);
        if (!is_array($decoded)) {
            if ($status === 401) {
                throw new RuntimeException(
                    'Jira authentication failed (HTTP 401). '
                    . 'Use Atlassian account email and API token with scope read:jira-work. '
                    . 'Run: php diag-auth.php myself'
                );
            }

            throw new RuntimeException('Invalid JSON from Jira (HTTP ' . $status . ')');
        }

        if ($status >= 400) {
            $messages = array();
            if (isset($decoded['errorMessages']) && is_array($decoded['errorMessages'])) {
                $messages = array_merge($messages, $decoded['errorMessages']);
            }
            if (isset($decoded['errors']) && is_array($decoded['errors'])) {
                foreach ($decoded['errors'] as $field => $message) {
                    $messages[] = $field . ': ' . $message;
                }
            }
            if (empty($messages) && isset($decoded['message'])) {
                $messages[] = (string) $decoded['message'];
            }
            if (empty($messages)) {
                $messages[] = 'HTTP ' . $status;
            }

            $message = implode('; ', $messages);
            if ($status === 401) {
                $message .= '. Check JIRA_EMAIL and JIRA_API_TOKEN (scope read:jira-work).';
            }

            throw new RuntimeException('Jira API error: ' . $message);
        }

        return $decoded;
    }
}

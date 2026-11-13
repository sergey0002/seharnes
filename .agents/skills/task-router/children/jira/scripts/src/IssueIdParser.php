<?php

final class IssueIdParser
{
    /**
     * Normalize user input to numeric issue id (folder name / branch number).
     *
     * Accepts: "2538", "CT-2538", full browse URL.
     *
     * @return string digits only, e.g. "2538"
     */
    public static function parse($input, $expectedProjectKey = null)
    {
        $raw = trim((string) $input);
        if ($raw === '') {
            throw new InvalidArgumentException('issue_id is required');
        }

        $token = self::extractToken($raw);
        $number = self::extractNumber($token, $expectedProjectKey);

        if (!preg_match('/^\d+$/', $number)) {
            throw new InvalidArgumentException(
                'issue_id must be a numeric Jira issue number, key (CT-2538), or browse URL'
            );
        }

        return $number;
    }

    private static function extractToken($raw)
    {
        if (preg_match('~/browse/([A-Za-z][A-Za-z0-9_]*-\d+)(?:[/?#]|$)~i', $raw, $matches)) {
            return $matches[1];
        }

        if (preg_match('#^https?://#i', $raw)) {
            throw new InvalidArgumentException('Cannot parse issue id from URL: ' . $raw);
        }

        return $raw;
    }

    private static function extractNumber($token, $expectedProjectKey)
    {
        if (preg_match('/^\d+$/', $token)) {
            return $token;
        }

        if (!preg_match('/^([A-Za-z][A-Za-z0-9_]*)-(\d+)$/i', $token, $matches)) {
            throw new InvalidArgumentException('Invalid Jira issue key: ' . $token);
        }

        $projectKey = strtoupper($matches[1]);
        $number = $matches[2];

        if ($expectedProjectKey !== null && $expectedProjectKey !== '') {
            $expected = strtoupper(trim((string) $expectedProjectKey));
            if ($expected !== '' && $projectKey !== $expected) {
                fwrite(
                    STDERR,
                    'Warning: issue key project ' . $projectKey . ' differs from JIRA_PROJECT_KEY ' . $expected . PHP_EOL
                );
            }
        }

        return $number;
    }
}

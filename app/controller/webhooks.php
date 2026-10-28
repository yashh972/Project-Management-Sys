<?php

namespace Controller;

/**
 * Inbound webhooks from source-control providers.
 *
 * GitHub is the first provider. The endpoint is public by design, so the HMAC
 * signature is mandatory whenever a secret is configured.
 */
class Webhooks extends \Controller
{
    /**
     * POST /webhooks/github
     */
    public function github(\Base $f3): void
    {
        $body = (string) $f3->get('BODY');
        if ($body === '') {
            $body = (string) file_get_contents('php://input');
        }

        $secret = (string) ($f3->get('github.webhook_secret') ?: getenv('GITHUB_WEBHOOK_SECRET') ?: '');
        if ($secret !== '') {
            $signature = (string) ($_SERVER['HTTP_X_HUB_SIGNATURE_256'] ?? '');
            $expected = 'sha256=' . hash_hmac('sha256', $body, $secret);
            if ($signature === '' || !hash_equals($expected, $signature)) {
                http_response_code(401);
                echo json_encode(['error' => 'Invalid webhook signature']);
                return;
            }
        }

        $payload = json_decode($body, true);
        if (!is_array($payload)) {
            http_response_code(400);
            echo json_encode(['error' => 'Invalid JSON payload']);
            return;
        }

        $event = (string) ($_SERVER['HTTP_X_GITHUB_EVENT'] ?? 'unknown');
        $db = $f3->get('db.instance');

        try {
            if ($event === 'pull_request') {
                $this->handlePullRequest($db, $payload);
            } elseif ($event === 'push') {
                $this->handlePush($db, $payload);
            }

            echo json_encode(['ok' => true, 'event' => $event]);
        } catch (\Throwable $e) {
            http_response_code(500);
            echo json_encode(['error' => $e->getMessage()]);
        }
    }

    /**
     * @param array<string,mixed> $payload
     */
    protected function handlePullRequest($db, array $payload): void
    {
        $pr = $payload['pull_request'] ?? null;
        $repo = (string) ($payload['repository']['full_name'] ?? '');
        if (!is_array($pr) || $repo === '') {
            return;
        }

        $number = (int) ($pr['number'] ?? 0);
        $title = (string) ($pr['title'] ?? '');
        $body = (string) ($pr['body'] ?? '');
        $branch = (string) ($pr['head']['ref'] ?? '');
        $url = (string) ($pr['html_url'] ?? '');
        $state = !empty($pr['merged']) ? 'merged' : (string) ($pr['state'] ?? 'open');
        $external = $repo . '#' . $number;
        $occurred = (string) ($pr['updated_at'] ?? $pr['created_at'] ?? date('c'));

        $issueIds = $this->issueIds($title . ' ' . $body . ' ' . $branch);
        foreach ($issueIds as $issueId) {
            $this->linkIssue($db, $issueId, $repo, 'pull_request', $external, $url, $state, [
                'number' => $number,
                'title' => $title,
                'branch' => $branch,
                'merged' => !empty($pr['merged']),
            ]);
        }

        $cycleHours = 0.0;
        if (!empty($pr['merged']) && !empty($pr['merged_at']) && !empty($pr['created_at'])) {
            $cycleHours = max(0.0, (strtotime((string) $pr['merged_at']) - strtotime((string) $pr['created_at'])) / 3600);
        }

        $this->recordDora($db, $repo, 'pull_request', $external . ':' . $state, $occurred, $cycleHours, [
            'number' => $number,
            'title' => $title,
            'state' => $state,
            'created_at' => $pr['created_at'] ?? null,
            'merged_at' => $pr['merged_at'] ?? null,
            'closed_at' => $pr['closed_at'] ?? null,
        ]);

        if (!empty($pr['merged']) && (string) (\Base::instance()->get('github.auto_close') ?: '0') === '1') {
            foreach ($issueIds as $issueId) {
                $issue = new \Model\Issue();
                $issue->load($issueId);
                if ($issue->id && !$issue->closed_date) {
                    $issue->status = 3;
                    $issue->closed_date = date('Y-m-d H:i:s');
                    $issue->save(false);
                }
            }
        }
    }

    /**
     * @param array<string,mixed> $payload
     */
    protected function handlePush($db, array $payload): void
    {
        $repo = (string) ($payload['repository']['full_name'] ?? '');
        if ($repo === '') {
            return;
        }

        foreach (($payload['commits'] ?? []) as $commit) {
            $sha = (string) ($commit['id'] ?? '');
            $message = (string) ($commit['message'] ?? '');
            $url = (string) ($commit['url'] ?? '');
            if ($sha === '') {
                continue;
            }

            $external = $repo . '@' . substr($sha, 0, 12);
            foreach ($this->issueIds($message) as $issueId) {
                $this->linkIssue($db, $issueId, $repo, 'commit', $external, $url, 'pushed', [
                    'sha' => $sha,
                    'message' => $message,
                ]);
            }
            $this->recordDora($db, $repo, 'commit', $external, (string) ($commit['timestamp'] ?? date('c')), 1.0, [
                'message' => $message,
            ]);
        }
    }

    /**
     * @return int[]
     */
    protected function issueIds(string $text): array
    {
        preg_match_all('/#(\d{1,9})/', $text, $matches);
        return array_values(array_unique(array_map('intval', $matches[1] ?? [])));
    }

    /**
     * Upsert an issue link without relying on engine-specific SQL.
     *
     * @param array<string,mixed> $meta
     */
    protected function linkIssue(
        $db,
        int $issueId,
        string $repo,
        string $kind,
        string $externalId,
        string $url,
        string $state,
        array $meta
    ): void {
        $issue = new \Model\Issue();
        $issue->load($issueId);
        if (!$issue->id) {
            return;
        }

        $existing = $db->exec(
            'SELECT id FROM issue_link WHERE provider = ? AND kind = ? AND external_id = ?',
            ['github', $kind, $externalId]
        );
        $metaJson = json_encode($meta, JSON_UNESCAPED_SLASHES);

        if (!empty($existing)) {
            $db->exec(
                'UPDATE issue_link SET issue_id = ?, repo = ?, url = ?, state = ?, meta_json = ? WHERE id = ?',
                [$issueId, $repo, $url, $state, $metaJson, (int) $existing[0]['id']]
            );
            return;
        }

        $db->exec(
            'INSERT INTO issue_link (issue_id, provider, repo, kind, external_id, url, state, meta_json, created_at)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            [$issueId, 'github', $repo, $kind, $externalId, $url, $state, $metaJson, date('Y-m-d H:i:s')]
        );
    }

    /**
     * @param array<string,mixed> $meta
     */
    protected function recordDora(
        $db,
        string $repo,
        string $kind,
        string $externalId,
        string $occurredAt,
        float $value,
        array $meta
    ): void {
        $timestamp = strtotime($occurredAt) ?: time();
        $existing = $db->exec(
            'SELECT id FROM dora_event WHERE repo = ? AND kind = ? AND external_id = ?',
            [$repo, $kind, $externalId]
        );
        $metaJson = json_encode($meta, JSON_UNESCAPED_SLASHES);

        if (!empty($existing)) {
            $db->exec(
                'UPDATE dora_event SET occurred_at = ?, value = ?, meta_json = ? WHERE id = ?',
                [date('Y-m-d H:i:s', $timestamp), $value, $metaJson, (int) $existing[0]['id']]
            );
            return;
        }

        $db->exec(
            'INSERT INTO dora_event (repo, kind, external_id, occurred_at, value, meta_json)
             VALUES (?, ?, ?, ?, ?, ?)',
            [$repo, $kind, $externalId, date('Y-m-d H:i:s', $timestamp), $value, $metaJson]
        );
    }
}

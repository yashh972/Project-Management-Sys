<?php

namespace Controller;

/**
 * Smart assignment: ranks the team for a new or existing task using the ML
 * service (POST /v1/assign/suggest).
 *
 * GET /assign/suggest?type_id=1&hours=6&priority=0&due=2026-10-10&tags=backend,api[&exclude=3,4]
 * GET /assign/suggest?issue_id=123
 */
class Assign extends \Controller
{
    public function __construct()
    {
        $this->_requireLogin();
    }

    public function suggest(\Base $f3): void
    {
        $issueId = (int) $f3->get('GET.issue_id');
        $tags = implode(',', array_filter(array_map(
            fn ($t) => preg_replace('/[^a-z0-9_-]/i', '', ltrim(trim((string) $t), '#')),
            explode(',', (string) $f3->get('GET.tags'))
        )));
        $exclude = array_values(array_filter(array_map('intval', explode(',', (string) $f3->get('GET.exclude')))));

        if ($issueId > 0) {
            $issue = new \Model\Issue();
            $issue->load($issueId);
            if (!$issue->id) {
                $f3->error(404, 'Issue not found');
                return;
            }
            if (!$issue->allowAccess()) {
                $f3->error(403);
                return;
            }

            $payload = [
                'issue_id' => $issueId,
                'top' => 5,
            ];
        } else {
            $due = (string) $f3->get('GET.due');
            $hours = (float) $f3->get('GET.hours');
            $payload = [
                'draft' => [
                    'type_id' => (int) ($f3->get('GET.type_id') ?: 1),
                    'priority' => (int) $f3->get('GET.priority'),
                    'due' => preg_match('/^\d{4}-\d{2}-\d{2}$/', $due) ? $due : null,
                    'hours' => $hours > 0 ? $hours : null,
                    'tags' => $tags === '' ? [] : explode(',', $tags),
                    'exclude' => $exclude,
                ],
                'top' => 5,
            ];
        }

        [$status, $data, $error] = \Helper\Ml::suggest($payload);
        if ($error !== null || $data === null) {
            if (!headers_sent()) {
                http_response_code($status > 0 ? $status : 503);
            }
            $this->_printJson(['error' => $error ?: 'The assignment service is unavailable.']);
            return;
        }

        $this->_printJson($data);
    }
}

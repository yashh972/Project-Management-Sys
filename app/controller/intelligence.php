<?php

namespace Controller;

/**
 * JSON endpoints for the intelligence layer.
 *
 * These are thin proxies: the Python service owns the models, PHP owns
 * authentication and issue-level access control.
 */
class Intelligence extends \Controller
{
    protected bool|int $_userId;

    public function __construct()
    {
        $this->_userId = $this->_requireLogin();
    }

    /**
     * GET /intelligence/risk/@id
     */
    public function risk(\Base $f3, array $params): void
    {
        $issue = $this->_loadIssue((int) $params['id']);
        if (!$issue) {
            return;
        }

        [$status, $data, $error] = \Helper\Ml::predictRisk((int) $issue->id);
        $this->_respond($status, $data, $error);
    }

    /**
     * POST /intelligence/ask
     */
    public function ask(\Base $f3): void
    {
        $this->_requireLogin(\Model\User::RANK_MANAGER);
        $question = trim((string) $f3->get('POST.question'));
        if (mb_strlen($question) < 3) {
            $this->_printJson(['error' => 'Ask a question first.']);
            return;
        }

        $sprintId = (int) $f3->get('POST.sprint_id');
        [$status, $data, $error] = \Helper\Ml::ask([
            'question' => mb_substr($question, 0, 2000),
            'sprint_id' => $sprintId > 0 ? $sprintId : null,
        ]);
        $this->_respond($status, $data, $error);
    }

    /**
     * GET /intelligence/similar/@id
     */
    public function similarIssue(\Base $f3, array $params): void
    {
        $issue = $this->_loadIssue((int) $params['id']);
        if (!$issue) {
            return;
        }

        [$status, $data, $error] = \Helper\Ml::similar([
            'issue_id' => (int) $issue->id,
            'top_k' => 5,
        ]);
        $this->_respond($status, $this->_filterSimilar($data), $error);
    }

    /**
     * POST /intelligence/similar
     *
     * Used by the new-issue form to catch likely duplicates before saving.
     */
    public function similarText(\Base $f3): void
    {
        $text = trim((string) $f3->get('POST.text'));
        if (mb_strlen($text) < 8) {
            $this->_printJson(['results' => []]);
            return;
        }

        [$status, $data, $error] = \Helper\Ml::similar([
            'text' => mb_substr($text, 0, 4000),
            'top_k' => 5,
        ]);
        $this->_respond($status, $this->_filterSimilar($data), $error);
    }

    /**
     * Drop similarity results the current user cannot open.
     *
     * @param array<string,mixed>|null $data
     * @return array<string,mixed>|null
     */
    protected function _filterSimilar(?array $data): ?array
    {
        if (!is_array($data) || empty($data['results'])) {
            return $data;
        }

        $data['results'] = array_values(array_filter(
            $data['results'],
            function (array $result): bool {
                $issue = new \Model\Issue();
                $issue->load((int) ($result['issue_id'] ?? 0));
                return $issue->id && $issue->allowAccess();
            }
        ));

        return $data;
    }

    /**
     * GET /intelligence/risk-batch?ids=1,2,3
     */
    public function batchRisk(\Base $f3): void
    {
        $ids = array_filter(array_map('intval', explode(',', (string) $f3->get('GET.ids'))));
        $ids = array_slice(array_values(array_unique($ids)), 0, 200);
        if ($ids === []) {
            $this->_printJson(['results' => []]);
            return;
        }

        $allowed = [];
        foreach ($ids as $id) {
            $issue = new \Model\Issue();
            $issue->load($id);
            if ($issue->id && $issue->allowAccess()) {
                $allowed[] = $id;
            }
        }

        if ($allowed === []) {
            $this->_printJson(['results' => []]);
            return;
        }

        [$status, $data, $error] = \Helper\Ml::batchRisk($allowed);
        $this->_respond($status, $data, $error);
    }

    /**
     * GET /intelligence/cycle/@id
     */
    public function cycle(\Base $f3, array $params): void
    {
        $issue = $this->_loadIssue((int) $params['id']);
        if (!$issue) {
            return;
        }

        [$status, $data, $error] = \Helper\Ml::predictCycle((int) $issue->id);
        $this->_respond($status, $data, $error);
    }

    /**
     * GET /intelligence/forecast/@id
     */
    public function forecast(\Base $f3, array $params): void
    {
        $simulations = (int) ($f3->get('GET.simulations') ?: 5000);
        $extraDays = (int) ($f3->get('GET.extra_days') ?: 0);
        $capacityMultiplier = (float) ($f3->get('GET.capacity_multiplier') ?: 1.0);
        [$status, $data, $error] = \Helper\Ml::forecastSprint(
            (int) $params['id'],
            $simulations,
            $extraDays,
            $capacityMultiplier
        );
        $this->_respond($status, $data, $error);
    }

    /**
     * GET /intelligence/models
     */
    public function models(\Base $f3): void
    {
        $this->_requireAdmin();
        [$status, $data, $error] = \Helper\Ml::models();
        $this->_respond($status, $data, $error);
    }

    /**
     * GET /intelligence/health
     *
     * A manager/admin command center: sprint forecast, risk distribution,
     * workload, model quality and recent activity in one view.
     */
    public function health(\Base $f3): void
    {
        $this->_requireLogin(\Model\User::RANK_MANAGER);
        $f3->set('title', 'Command center');
        $f3->set('menuitem', 'health');
        $f3->set('health_error', null);
        $db = $f3->get('db.instance');
        $today = date('Y-m-d');

        $sprintRows = $db->exec(
            'SELECT * FROM sprint WHERE ? BETWEEN start_date AND end_date ORDER BY id DESC LIMIT 1',
            [$today]
        );
        if (empty($sprintRows)) {
            $sprintRows = $db->exec('SELECT * FROM sprint ORDER BY end_date DESC LIMIT 1');
        }
        $sprint = $sprintRows[0] ?? null;
        if (!$sprint) {
            $f3->set('health_error', 'Create a sprint to see the command center.');
            $this->_render('intelligence/health.html');
            return;
        }

        $issues = $db->exec(
            "SELECT i.id, i.name, i.status, i.type_id, i.owner_id, i.priority,
                    i.hours_total, i.hours_remaining, i.due_date, i.created_date,
                    i.closed_date, s.closed AS status_closed, u.name AS owner_name
             FROM issue i
             LEFT JOIN issue_status s ON s.id = i.status
             LEFT JOIN user u ON u.id = i.owner_id
             WHERE i.deleted_date IS NULL AND i.sprint_id = ? AND i.type_id <> 2
             ORDER BY i.id",
            [(int) $sprint['id']]
        );

        $open = [];
        $closedCount = 0;
        foreach ($issues as $issue) {
            if ((int) $issue['status_closed'] === 1) {
                $closedCount++;
            } else {
                $open[] = $issue;
            }
        }

        $openIds = array_map(fn ($issue) => (int) $issue['id'], $open);
        $riskById = [];
        $riskError = null;
        if ($openIds !== []) {
            [$riskStatus, $riskData, $riskError] = \Helper\Ml::batchRisk($openIds);
            if ($riskStatus >= 200 && $riskStatus < 300 && is_array($riskData)) {
                foreach ($riskData['results'] ?? [] as $result) {
                    if (($result['error'] ?? null) === null && isset($result['p_late'])) {
                        $riskById[(int) $result['issue_id']] = $result;
                    }
                }
            }
        }

        $riskCounts = ['low' => 0, 'medium' => 0, 'high' => 0, 'unknown' => 0];
        $topRisks = [];
        $overdue = 0;
        $totalOpenHours = 0.0;
        foreach ($open as &$issue) {
            $risk = $riskById[(int) $issue['id']] ?? null;
            $issue['risk'] = $risk;
            $level = $risk['risk'] ?? 'unknown';
            $riskCounts[$level] = ($riskCounts[$level] ?? 0) + 1;
            if ($level === 'high' || $level === 'medium') {
                $topRisks[] = $issue;
            }
            if (!empty($issue['due_date']) && $issue['due_date'] < $today) {
                $overdue++;
            }
            $hours = (float) ($issue['hours_remaining'] ?: $issue['hours_total'] ?: 0);
            $totalOpenHours += $hours;
        }
        unset($issue);

        usort($topRisks, function ($a, $b) {
            return ($b['risk']['p_late'] ?? 0) <=> ($a['risk']['p_late'] ?? 0);
        });
        $topRisks = array_slice($topRisks, 0, 6);

        $workloadRows = $db->exec(
            "SELECT i.owner_id, u.name AS user_name, COUNT(*) AS tasks,
                    SUM(COALESCE(NULLIF(i.hours_remaining, 0), i.hours_total, 4)) AS hours
             FROM issue i
             LEFT JOIN issue_status s ON s.id = i.status
             LEFT JOIN user u ON u.id = i.owner_id
             WHERE i.deleted_date IS NULL AND s.closed = 0 AND i.type_id <> 2
             GROUP BY i.owner_id, u.name
             ORDER BY hours DESC"
        );
        $workload = [];
        $unassigned = 0;
        foreach ($workloadRows as $row) {
            if (empty($row['owner_id'])) {
                $unassigned = (int) $row['tasks'];
                continue;
            }
            $row['hours'] = round((float) $row['hours'], 1);
            $row['utilization'] = min(1.0, $row['hours'] / 40);
            $workload[] = $row;
        }
        $workload = array_slice($workload, 0, 8);

        [$forecastStatus, $forecast, $forecastError] = \Helper\Ml::forecastSprint((int) $sprint['id'], 3000);

        [$modelStatus, $modelData, $modelError] = \Helper\Ml::models();
        $model = null;
        if ($modelStatus >= 200 && $modelStatus < 300 && is_array($modelData)) {
            foreach ($modelData['models'] ?? [] as $candidate) {
                if (($candidate['name'] ?? '') === 'task-late-risk') {
                    $model = $candidate;
                    break;
                }
            }
        }

        $recent = $db->exec(
            'SELECT iu.created_date, i.id, i.name, u.name AS actor_name
             FROM issue_update iu
             JOIN issue i ON i.id = iu.issue_id
             LEFT JOIN user u ON u.id = iu.user_id
             WHERE i.deleted_date IS NULL
             ORDER BY iu.id DESC
             LIMIT 8'
        );

        $git = [
            'commits' => 0,
            'pull_requests' => 0,
            'merged' => 0,
            'pr_cycle_hours' => null,
            'repos' => 0,
            'recent' => [],
        ];
        try {
            $since = date('Y-m-d H:i:s', strtotime('-30 days'));
            $kindRows = $db->exec(
                'SELECT kind, COUNT(*) AS count FROM dora_event WHERE occurred_at >= ? GROUP BY kind',
                [$since]
            );
            foreach ($kindRows as $row) {
                if ($row['kind'] === 'commit') {
                    $git['commits'] = (int) $row['count'];
                }
            }
            $pullRequests = [];
            $pullRows = $db->exec(
                "SELECT external_id FROM dora_event WHERE kind = 'pull_request' AND occurred_at >= ?",
                [$since]
            );
            foreach ($pullRows as $row) {
                $pullRequests[explode(':', (string) $row['external_id'])[0]] = true;
            }
            $git['pull_requests'] = count($pullRequests);
            $merged = $db->exec(
                "SELECT COUNT(*) AS count FROM dora_event
                 WHERE kind = 'pull_request' AND external_id LIKE '%:merged' AND occurred_at >= ?",
                [$since]
            );
            $git['merged'] = (int) ($merged[0]['count'] ?? 0);
            $cycleRows = $db->exec(
                "SELECT value FROM dora_event
                 WHERE kind = 'pull_request' AND external_id LIKE '%:merged'
                   AND occurred_at >= ? AND value > 0",
                [$since]
            );
            if ($cycleRows) {
                $cycles = array_map(fn ($row) => (float) $row['value'], $cycleRows);
                sort($cycles);
                $middle = intdiv(count($cycles), 2);
                $git['pr_cycle_hours'] = count($cycles) % 2
                    ? round($cycles[$middle], 1)
                    : round(($cycles[$middle - 1] + $cycles[$middle]) / 2, 1);
            }
            $repos = $db->exec('SELECT COUNT(DISTINCT repo) AS count FROM dora_event WHERE occurred_at >= ?', [$since]);
            $git['repos'] = (int) ($repos[0]['count'] ?? 0);
            $git['recent'] = $db->exec(
                'SELECT repo, kind, external_id, occurred_at, meta_json
                 FROM dora_event ORDER BY occurred_at DESC LIMIT 4'
            );
        } catch (\Throwable $e) {
            // Git integration is optional.
        }

        $f3->set('health', [
            'sprint' => $sprint,
            'open' => count($open),
            'closed' => $closedCount,
            'total' => count($issues),
            'progress' => count($issues) ? round($closedCount / count($issues) * 100) : 0,
            'overdue' => $overdue,
            'unassigned' => $unassigned,
            'open_hours' => round($totalOpenHours, 1),
            'team_utilization' => $workload ? round(array_sum(array_column($workload, 'hours')) / (count($workload) * 40) * 100) : 0,
            'risk_counts' => $riskCounts,
            'top_risks' => $topRisks,
            'workload' => $workload,
            'forecast' => $forecastStatus >= 200 && $forecastStatus < 300 ? $forecast : null,
            'forecast_error' => $forecastError,
            'risk_error' => $riskError,
            'model' => $model,
            'model_error' => $modelError,
            'recent' => $recent,
            'git' => $git,
        ]);
        $this->_render('intelligence/health.html');
    }

    /**
     * GET /intelligence/timeline/@id
     */
    public function timeline(\Base $f3, array $params): void
    {
        $this->_requireLogin(\Model\User::RANK_MANAGER);
        $sprintId = (int) $params['id'];
        $db = $f3->get('db.instance');
        $sprints = $db->exec('SELECT * FROM sprint WHERE id = ?', [$sprintId]);
        if (empty($sprints)) {
            $f3->error(404, 'Sprint not found');
            return;
        }
        $sprint = $sprints[0];

        $rows = $db->exec(
            "SELECT i.id, i.name, i.status, i.owner_id, i.priority, i.start_date, i.due_date,
                    i.hours_total, i.hours_remaining, s.closed AS status_closed, u.name AS owner_name
             FROM issue i
             LEFT JOIN issue_status s ON s.id = i.status
             LEFT JOIN user u ON u.id = i.owner_id
             WHERE i.deleted_date IS NULL AND i.sprint_id = ? AND i.type_id <> 2
             ORDER BY i.start_date, i.due_date, i.id",
            [$sprintId]
        );

        $openIds = [];
        foreach ($rows as $row) {
            if ((int) $row['status_closed'] === 0) {
                $openIds[] = (int) $row['id'];
            }
        }
        $riskById = [];
        if ($openIds !== []) {
            [$riskStatus, $riskData] = \Helper\Ml::batchRisk($openIds);
            if ($riskStatus >= 200 && $riskStatus < 300 && is_array($riskData)) {
                foreach ($riskData['results'] ?? [] as $result) {
                    if (($result['error'] ?? null) === null) {
                        $riskById[(int) $result['issue_id']] = $result;
                    }
                }
            }
        }

        $deps = [];
        if ($rows !== []) {
            $ids = implode(',', array_map(fn ($row) => (int) $row['id'], $rows));
            foreach ($db->exec("SELECT issue_id, COUNT(*) AS count FROM issue_dependency WHERE issue_id IN ({$ids}) GROUP BY issue_id") as $dep) {
                $deps[(int) $dep['issue_id']] = (int) $dep['count'];
            }
        }

        $rangeStart = strtotime($sprint['start_date']);
        $rangeEnd = strtotime($sprint['end_date']) + 86400;
        foreach ($rows as $row) {
            if (!empty($row['start_date']) && ($ts = strtotime($row['start_date'])) && $ts < $rangeStart) {
                $rangeStart = $ts;
            }
            if (!empty($row['due_date']) && ($ts = strtotime($row['due_date']) + 86400) && $ts > $rangeEnd) {
                $rangeEnd = $ts;
            }
        }
        $rangeStart = strtotime('-1 day', $rangeStart);
        $rangeEnd = strtotime('+1 day', $rangeEnd);
        $span = max(86400, $rangeEnd - $rangeStart);

        $tasks = [];
        foreach ($rows as $row) {
            $taskStart = !empty($row['start_date']) ? strtotime($row['start_date']) : strtotime($sprint['start_date']);
            $taskEnd = !empty($row['due_date']) ? strtotime($row['due_date']) + 86400 : $taskStart + 86400;
            if ($taskEnd <= $taskStart) {
                $taskEnd = $taskStart + 86400;
            }
            $left = max(0, min(100, ($taskStart - $rangeStart) / $span * 100));
            $width = max(1.5, min(100 - $left, ($taskEnd - $taskStart) / $span * 100));
            $risk = $riskById[(int) $row['id']] ?? null;
            $tasks[] = [
                'id' => (int) $row['id'],
                'name' => $row['name'],
                'owner' => $row['owner_name'] ?: 'Unassigned',
                'closed' => (int) $row['status_closed'] === 1,
                'risk' => $risk['risk'] ?? null,
                'p_late' => $risk['p_late'] ?? null,
                'left' => round($left, 2),
                'width' => round($width, 2),
                'start' => date('M j', $taskStart),
                'due' => date('M j', $taskEnd - 86400),
                'hours' => (float) ($row['hours_remaining'] ?: $row['hours_total'] ?: 0),
                'deps' => $deps[(int) $row['id']] ?? 0,
            ];
        }

        $ticks = [];
        for ($tick = $rangeStart; $tick <= $rangeEnd; $tick += 7 * 86400) {
            $ticks[] = [
                'label' => date('M j', $tick),
                'left' => round(max(0, min(100, ($tick - $rangeStart) / $span * 100)), 2),
            ];
        }

        $todayLeft = null;
        $today = strtotime('today');
        if ($today >= $rangeStart && $today <= $rangeEnd) {
            $todayLeft = round(($today - $rangeStart) / $span * 100, 2);
        }

        $f3->set('title', $sprint['name'] . ' timeline');
        $f3->set('menuitem', 'backlog');
        $f3->set('timeline', [
            'sprint' => $sprint,
            'tasks' => $tasks,
            'ticks' => $ticks,
            'today_left' => $todayLeft,
            'range_start' => date('M j, Y', $rangeStart),
            'range_end' => date('M j, Y', $rangeEnd - 86400),
        ]);
        $this->_render('intelligence/timeline.html');
    }

    /**
     * GET /intelligence/quality
     *
     * Admin view of the calibration and walk-forward evaluation report.
     */
    public function quality(\Base $f3): void
    {
        $this->_requireAdmin();
        $f3->set('title', 'Model quality');
        $f3->set('menuitem', 'analytics');
        $f3->set('quality_error', null);
        $f3->set('quality', null);
        $f3->set('models', []);
        $f3->set('model_error', null);

        [$status, $data, $error] = \Helper\Ml::backtest(4, 30);
        if ($error !== null || $data === null || $status >= 400) {
            $f3->set('quality_error', $error ?: 'The ML service is unavailable.');
        } else {
            $data['overall'] = array_merge(
                ['auc' => null, 'brier' => null, 'ece' => null, 'precision_at_10pct' => null],
                $data['overall'] ?? []
            );
            $data['folds'] = $data['folds'] ?? [];
            $data['reliability'] = $data['reliability'] ?? [];
            $data['rows'] = $data['rows'] ?? 0;
            $data['generated_at'] = $data['generated_at'] ?? '';
            $f3->set('quality', $data);
        }

        [$modelStatus, $models, $modelError] = \Helper\Ml::models();
        if ($modelStatus >= 200 && $modelStatus < 300 && is_array($models)) {
            $f3->set('models', $models['models'] ?? []);
        } elseif ($modelError) {
            $f3->set('model_error', $modelError);
        }

        $this->_render('intelligence/quality.html');
    }

    /**
     * POST /intelligence/optimize
     */
    public function optimize(\Base $f3): void
    {
        $this->_requireLogin(\Model\User::RANK_MANAGER);
        $this->validateCsrf();
        $sprintId = (int) $f3->get('POST.sprint_id');
        if ($sprintId <= 0) {
            $this->_printJson(['error' => 'A sprint is required']);
            return;
        }

        $fairness = $f3->get('POST.fairness');
        [$status, $data, $error] = \Helper\Ml::optimize([
            'sprint_id' => $sprintId,
            'capacity_hours' => (float) ($f3->get('POST.capacity_hours') ?: 40),
            'max_wip' => (int) ($f3->get('POST.max_wip') ?: 3),
            'time_limit_seconds' => 5,
            'fairness' => $fairness === null || $fairness === ''
                ? true
                : filter_var($fairness, FILTER_VALIDATE_BOOLEAN),
        ]);
        $this->_respond($status, $data, $error);
    }

    /**
     * POST /intelligence/optimize/apply
     *
     * Apply a reviewed set of optimizer assignments. Managers and admins only;
     * every change goes through Model\Issue::save() so the normal audit trail
     * and notifications still fire.
     */
    public function applyOptimize(\Base $f3): void
    {
        $this->_requireLogin(\Model\User::RANK_MANAGER);
        $this->validateCsrf();

        $sprintId = (int) $f3->get('POST.sprint_id');
        $assignments = json_decode((string) $f3->get('POST.assignments'), true);
        if ($sprintId <= 0 || !is_array($assignments) || $assignments === []) {
            $this->_printJson(['error' => 'No assignments to apply']);
            return;
        }

        $assignments = array_slice($assignments, 0, 200);
        $applied = [];
        $skipped = [];
        $db = $f3->get('db.instance');

        foreach ($assignments as $assignment) {
            $issueId = (int) ($assignment['issue_id'] ?? 0);
            $userId = (int) ($assignment['user_id'] ?? 0);
            if ($issueId <= 0 || $userId <= 0) {
                continue;
            }

            $issue = new \Model\Issue();
            $issue->load($issueId);
            if (!$issue->id || $issue->deleted_date) {
                $skipped[] = ['issue_id' => $issueId, 'reason' => 'not found'];
                continue;
            }
            if ((int) $issue->sprint_id !== $sprintId) {
                $skipped[] = ['issue_id' => $issueId, 'reason' => 'not in sprint'];
                continue;
            }
            if ($issue->closed_date) {
                $skipped[] = ['issue_id' => $issueId, 'reason' => 'closed'];
                continue;
            }
            if (!$issue->allowAccess()) {
                $skipped[] = ['issue_id' => $issueId, 'reason' => 'access denied'];
                continue;
            }

            $user = new \Model\User();
            $user->load($userId);
            if (!$user->id || $user->deleted_date || !in_array($user->role, ['user', 'manager'], true)) {
                $skipped[] = ['issue_id' => $issueId, 'reason' => 'invalid assignee'];
                continue;
            }

            if ((int) $issue->owner_id === $userId) {
                $skipped[] = ['issue_id' => $issueId, 'reason' => 'already assigned'];
                continue;
            }

            $issue->owner_id = $userId;
            // Bulk reassignment should not email every watcher for each task.
            $issue->save(false);
            $applied[] = [
                'issue_id' => $issueId,
                'user_id' => $userId,
                'user_name' => $user->name,
                'score' => $assignment['score'] ?? null,
                'hours' => $assignment['hours'] ?? null,
            ];
        }

        $runId = null;
        if ($applied) {
            $now = date('Y-m-d H:i:s');
            $db->exec(
                'INSERT INTO assignment_run
                    (sprint_id, created_by, created_at, objective, constraints_json, result_json, baseline_json)
                 VALUES (?, ?, ?, ?, ?, ?, ?)',
                [
                    $sprintId,
                    (int) $f3->get('user.id'),
                    $now,
                    'applied',
                    null,
                    json_encode(['applied' => $applied, 'skipped' => $skipped]),
                    null,
                ]
            );
            $runId = (int) $db->lastInsertId();
            foreach ($applied as $item) {
                $db->exec(
                    'INSERT INTO assignment_item (run_id, issue_id, user_id, score, reason_json)
                     VALUES (?, ?, ?, ?, ?)',
                    [
                        $runId,
                        $item['issue_id'],
                        $item['user_id'],
                        $item['score'],
                        json_encode(['hours' => $item['hours'], 'source' => 'optimizer']),
                    ]
                );
            }
        }

        $this->_printJson([
            'ok' => true,
            'run_id' => $runId,
            'applied' => count($applied),
            'skipped' => $skipped,
        ]);
    }

    /**
     * POST /intelligence/suggestions/log
     *
     * Record a suggestion decision so future evaluations can measure acceptance
     * and realized lift instead of only offline accuracy.
     */
    public function logSuggestion(\Base $f3): void
    {
        $this->validateCsrf();

        $kind = (string) $f3->get('POST.kind');
        $action = (string) $f3->get('POST.action');
        $allowedKinds = ['assignment', 'forecast', 'risk'];
        $allowedActions = ['shown', 'accepted', 'rejected', 'overridden', 'ignored'];
        if (!in_array($kind, $allowedKinds, true) || !in_array($action, $allowedActions, true)) {
            $this->_printJson(['error' => 'Invalid suggestion event']);
            return;
        }

        $payload = (string) $f3->get('POST.payload');
        if (strlen($payload) > 20000) {
            $this->_printJson(['error' => 'Suggestion payload is too large']);
            return;
        }

        $issueId = (int) $f3->get('POST.issue_id');
        $now = date('Y-m-d H:i:s');
        $db = $f3->get('db.instance');
        $db->exec(
            'INSERT INTO suggestion_log
                (user_id, issue_id, kind, payload_json, shown_at, action, acted_at)
             VALUES (?, ?, ?, ?, ?, ?, ?)',
            [
                (int) $f3->get('user.id'),
                $issueId > 0 ? $issueId : null,
                $kind,
                $payload !== '' ? $payload : null,
                $now,
                $action,
                $now,
            ]
        );

        $this->_printJson(['ok' => true, 'id' => (int) $db->lastInsertId()]);
    }

    /**
     * Load an issue and enforce its access rules.
     */
    protected function _loadIssue(int $id): ?\Model\Issue
    {
        $issue = new \Model\Issue();
        $issue->load($id);
        if (!$issue->id) {
            \Base::instance()->error(404, 'Issue not found');
            return null;
        }

        if (!$issue->allowAccess()) {
            \Base::instance()->error(403);
            return null;
        }

        return $issue;
    }

    /**
     * Emit a JSON response with the upstream status.
     */
    protected function _respond(int $status, ?array $data, ?string $error): void
    {
        if (!headers_sent()) {
            http_response_code($status > 0 ? $status : 503);
        }

        if ($error !== null || $data === null) {
            $this->_printJson(['error' => $error ?: 'The ML service is unavailable.']);
            return;
        }

        $this->_printJson($data);
    }
}

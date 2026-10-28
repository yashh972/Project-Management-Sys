<?php

namespace Controller;

/**
 * Analytics dashboard. Admins see everything; other users see the same pages scoped to the tasks assigned to them
 * (their projects, alerts and export only; team, performance and comparison data stay admin-only).
 *
 * GET  /analytics          Team, project and per-employee analytics
 * POST /analytics/refresh  Re-runs the ML job (ml/run_analytics.py) and reloads the page
 *
 * Aggregation is done in PHP on plain SELECTs so it works with both SQLite and MySQL.
 * Employee scores, clusters and task late-risk come from the tables written by
 * ml/run_analytics.py (employee_performance, task_risk, ml_run). Without them the page
 * still works and shows a hint to run the job.
 */
class Analytics extends \Controller
{
    /** Open-work capacity per person (hours) used to scale the workload bars */
    private const CAPACITY_HOURS = 40.0;

    private const RANGES = ['week' => 7, 'month' => 30, 'quarter' => 91];

    protected bool|int $_userId;

    /** Null for admins (all data); the user's id for everyone else (only tasks assigned to them) */
    protected ?int $scopeId = null;

    public function __construct()
    {
        $this->_userId = $this->_requireLogin();
        if (\Base::instance()->get('user.role') !== 'admin') {
            $this->scopeId = (int) $this->_userId;
        }

        \Base::instance()->set('menuitem', 'analytics');
    }

    /**
     * GET /analytics
     */
    public function index(\Base $f3): void
    {
        $db = $f3->get('db.instance');
        $f3->set('title', 'Analytics');

        $range = (string) $f3->get('GET.range');
        if (!isset(self::RANGES[$range])) {
            $range = 'month';
        }

        $days = self::RANGES[$range];
        $now = time();
        $today = strtotime('today', $now);
        $start = $today - ($days - 1) * 86400;
        $end = $today + 86400;
        $prevStart = $start - $days * 86400;

        // ---- Load base data
        $statuses = [];
        foreach ($db->exec('SELECT id, name, closed FROM issue_status') as $s) {
            $statuses[$s['id']] = $s;
        }

        $projectTypes = [];
        foreach ($db->exec('SELECT id, role FROM issue_type') as $t) {
            if ($t['role'] === 'project') {
                $projectTypes[] = $t['id'];
            }
        }

        $users = [];
        foreach ($db->exec("SELECT id, username, name, role, task_color FROM user WHERE deleted_date IS NULL AND role != 'group'") as $u) {
            $users[$u['id']] = $u + ['initials' => $this->initials($u['name']), 'color' => $this->color($u)];
        }

        $rows = $db->exec(
            'SELECT i.id, i.name, i.description, i.type_id, i.status, i.owner_id, i.parent_id, i.priority, i.hours_total, i.hours_remaining,
                    i.created_date, i.closed_date, i.due_date, i.sprint_id
             FROM issue i WHERE i.deleted_date IS NULL'
        );
        $tasks = [];
        $projects = [];
        foreach ($rows as $r) {
            $r['closed'] = !empty($statuses[$r['status']]['closed']);
            $r['created_ts'] = strtotime($r['created_date']);
            $r['closed_ts'] = $r['closed_date'] ? strtotime($r['closed_date']) : null;
            $r['due_ts'] = $r['due_date'] ? strtotime($r['due_date'] . ' 23:59:59') : null;
            if (in_array($r['type_id'], $projectTypes)) {
                $projects[] = $r;
            } else {
                $tasks[] = $r;
            }
        }

        if ($this->scopeId !== null) {
            [$tasks, $projects] = $this->scopeIssues($tasks, $projects);
        }

        // ---- ML tables (optional)
        [$performance, $riskById, $mlRun] = $this->loadMl($db);
        if ($this->scopeId !== null) {
            $performance = [];
        }

        // ---- KPI tiles
        $cur = $this->periodStats($tasks, $start, $end);
        $prev = $this->periodStats($tasks, $prevStart, $start);
        $openTasks = array_filter($tasks, fn ($t) => !$t['closed']);
        $activeProjects = array_filter($projects, fn ($p) => !$p['closed']);
        $staff = $this->scopeId === null ? array_filter($users, fn ($u) => $u['role'] !== 'admin') : [];

        $projectRows = $this->projectRows($projects, $tasks, $users, $riskById, $now);
        $atRiskProjects = count(array_filter($projectRows, fn ($p) => $p['status'] === 'risk'));

        $kpis = [
            [
                'href' => $f3->get('BASE') . '/issues?type_id=1', 'label' => 'Total Tasks', 'value' => count($tasks), 'icon' => 'fa-tasks', 'tone' => 'violet',
                'delta' => $this->pctChange($cur['created'], $prev['created']), 'hint' => $cur['created'] . ' created',
            ],
            [
                'href' => '#projects', 'label' => 'Active Projects', 'value' => count($activeProjects), 'icon' => 'fa-cubes', 'tone' => 'blue',
                'delta' => null, 'hint' => $atRiskProjects ? $atRiskProjects . ' at risk' : 'none at risk',
                'hint_bad' => (bool) $atRiskProjects,
            ],
            [
                'href' => $f3->get('BASE') . '/issues?status=closed', 'label' => 'Completed', 'value' => $cur['closed'], 'icon' => 'fa-check-circle', 'tone' => 'green',
                'delta' => $this->pctChange($cur['closed'], $prev['closed']), 'hint' => 'vs ' . $prev['closed'] . ' before',
            ],
            [
                'href' => '#performance', 'label' => 'On-time Rate', 'value' => $cur['on_time_rate'] === null ? '-' : $cur['on_time_rate'] . '%', 'icon' => 'fa-clock-o', 'tone' => 'amber',
                'delta' => ($cur['on_time_rate'] !== null && $prev['on_time_rate'] !== null) ? $cur['on_time_rate'] - $prev['on_time_rate'] : null,
                'delta_unit' => ' pts', 'hint' => 'of completed tasks',
            ],
            [
                'href' => '#team', 'label' => 'Team Members', 'value' => count($staff), 'icon' => 'fa-users', 'tone' => 'pink',
                'delta' => null, 'hint' => count(array_unique(array_filter(array_column($openTasks, 'owner_id')))) . ' with open work',
            ],
        ];

        if ($this->scopeId !== null) {
            $base = $f3->get('BASE') . '/issues?owner_id=' . $this->scopeId;
            $kpis[0]['href'] = $base;
            $kpis[0]['label'] = 'My Tasks';
            $kpis[2]['href'] = $base . '&status=closed';
            $kpis[3]['href'] = $base . '&status=closed';
            $kpis[4] = [
                'href' => $base . '&status=open', 'label' => 'My Open Tasks', 'value' => count($openTasks), 'icon' => 'fa-list-ul', 'tone' => 'pink',
                'delta' => null, 'hint' => count(array_filter($openTasks, fn ($t) => $t['due_ts'] && $t['due_ts'] < $now)) . ' overdue',
            ];
        }

        // ---- Chart series
        $bucket = ['week' => 1, 'month' => 3, 'quarter' => 7][$range];
        $labels = [];
        $created = [];
        $completed = [];
        $ontime = [];
        for ($from = $start; $from < $end; $from += $bucket * 86400) {
            $to = $from + $bucket * 86400;
            $labels[] = date('M j', $from);
            $c = $this->periodStats($tasks, $from, $to);
            $created[] = $c['created'];
            $completed[] = $c['closed'];
            $ontime[] = $c['on_time_rate'];
        }

        // ---- Workload
        $workload = [];
        foreach ($staff as $u) {
            $mine = array_filter($openTasks, fn ($t) => (int) $t['owner_id'] === (int) $u['id']);
            $hours = 0.0;
            $overdue = 0;
            foreach ($mine as $t) {
                $hours += (float) ($t['hours_remaining'] ?: $t['hours_total']);
                if ($t['due_ts'] && $t['due_ts'] < $now) {
                    $overdue++;
                }
            }

            $pct = min(100, (int) round($hours / self::CAPACITY_HOURS * 100));
            $workload[] = [
                'id' => $u['id'], 'name' => $u['name'], 'initials' => $u['initials'], 'color' => $u['color'],
                'tasks' => count($mine), 'hours' => round($hours), 'overdue' => $overdue, 'pct' => $pct,
                'tone' => $pct >= 90 ? 'high' : ($pct >= 60 ? 'mid' : 'low'),
            ];
        }

        usort($workload, fn ($a, $b) => $b['hours'] <=> $a['hours']);

        // ---- Employees (ML)
        $employees = $this->employees($performance, $users);

        // ---- Sidebar lists
        $deadlines = $this->deadlines($openTasks, $users, $projects, $riskById, $today);
        $week = $this->weekStrip($tasks, $today);
        $atRisk = $this->atRiskTasks($openTasks, $riskById, $users, $projects);
        $activity = $this->activity($db, $users, $statuses, $this->scopeId);

        $mlSummary = $this->mlSummary($mlRun);
        $alerts = $this->scopedAlerts(\Helper\TaskAlerts::collect($db, $now));
        $alertLabels = ['overdue' => 'Overdue', 'soon' => 'Due soon', 'risk' => 'Late risk'];
        foreach ($alerts['owners'] as &$o) {
            $o['items'] = [];
            foreach ($alertLabels as $k => $label) {
                foreach ($o[$k] as $t) {
                    $o['items'][] = $t + ['label' => $label];
                }
            }
        }

        unset($o);

        $hour = (int) date('G', $now);
        $first = explode(' ', trim((string) $f3->get('user.name')))[0];
        $growth = $this->pctChange($cur['closed'], $prev['closed']);

        $f3->set('an', [
            'range' => $range,
            'greeting' => $hour < 12 ? 'Good morning' : ($hour < 18 ? 'Good afternoon' : 'Good evening'),
            'first_name' => $first,
            'today_label' => date('D, M j, Y', $now),
            'range_label' => ['week' => 'Last 7 days, daily', 'month' => 'Last 30 days, 3-day totals', 'quarter' => 'Last 13 weeks, weekly totals'][$range],
            'kpis' => $kpis,
            'growth' => $growth,
            'projects' => $projectRows,
            'project_counts' => [
                'track' => count(array_filter($projectRows, fn ($p) => $p['status'] === 'track')),
                'progress' => count(array_filter($projectRows, fn ($p) => $p['status'] === 'progress')),
                'risk' => $atRiskProjects,
                'done' => count(array_filter($projectRows, fn ($p) => $p['status'] === 'done')),
            ],
            'workload' => $workload,
            'employees' => $employees,
            'deadlines' => $deadlines,
            'week' => $week,
            'at_risk' => $atRisk,
            'activity' => $activity,
            'ml' => $mlSummary,
            'has_ml' => $employees !== [],
            'scoped' => $this->scopeId !== null,
            'alerts' => $alerts,
            'alert_count' => array_sum($alerts['totals']),
        ]);

        $projectNames = array_column($projects, 'name', 'id');
        $calendar = [];
        foreach ($tasks as $t) {
            if (!$t['due_date']) {
                continue;
            }

            $o = $users[$t['owner_id']] ?? null;
            $calendar[] = [
                'id' => (int) $t['id'], 'name' => $t['name'], 'project' => $projectNames[$t['parent_id']] ?? '', 'due' => $t['due_date'],
                'closed' => (bool) $t['closed'], 'risk' => isset($riskById[(int) $t['id']]) ? (int) round($riskById[(int) $t['id']] * 100) : null,
                'owner' => $o ? ['name' => $o['name'], 'initials' => $o['initials'], 'color' => $o['color']] : null,
            ];
        }

        $f3->set('an_json', json_encode([
            'chart' => ['labels' => $labels, 'created' => $created, 'completed' => $completed, 'ontime' => $ontime, 'bucket' => $bucket],
            'employees' => $employees,
            'growth' => $growth,
            'calendar' => ['today' => date('Y-m-d', $today), 'base' => (string) $f3->get('BASE'), 'tasks' => $calendar],
        ], JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT | JSON_PARTIAL_OUTPUT_ON_ERROR));

        $this->_render('analytics/index.html');
    }

    /**
     * POST /analytics/refresh
     * Runs the Python ML job synchronously, then renders the dashboard again.
     */
    public function refresh(\Base $f3): void
    {
        $this->_requireAdmin();
        $this->validateCsrf();

        [$status, $data, $error] = \Helper\Ml::trainAnalytics(true);
        if ($status >= 200 && $status < 300 && is_array($data) && !empty($data['ok'])) {
            $f3->set('success', 'Insights and the smart-assignment model were recomputed from the latest task history.');
        } else {
            $message = $error ?: 'The ML job failed.';
            $f3->set('error', 'The ML job failed: ' . htmlspecialchars((string) $message));
        }

        $this->index($f3);
    }

    /**
     * GET /analytics/project/@id
     */
    public function project(\Base $f3, array $params): void
    {
        $data = $this->projectData($f3, (int) $params['id']);
        $f3->set('title', $data['project']['name'] . ' - Analytics');
        $f3->set('pa', $data);
        $this->_render('analytics/project.html');
    }

    /**
     * GET /analytics/export?scope=overview|project&format=csv|pdf[&id=N]
     */
    public function export(\Base $f3): void
    {
        $format = $f3->get('GET.format') === 'pdf' ? 'pdf' : 'csv';
        $scope = $f3->get('GET.scope') === 'project' ? 'project' : 'overview';
        $stamp = date('Ymd');

        if ($scope === 'project') {
            $d = $this->projectData($f3, (int) $f3->get('GET.id'));
            $slug = trim((string) preg_replace('/[^a-z0-9]+/i', '-', $d['project']['name']), '-') ?: 'project';
            $sections = [
                'Summary' => [
                    ['Metric', 'Value'],
                    [
                        ['Project', $d['project']['name']], ['Status', $d['row']['status_label']], ['Progress', $d['row']['progress'] . '%'],
                        ['Due', $d['project']['due_date'] ?: '-'], ['Total tasks', $d['kpi']['total']], ['Completed', $d['kpi']['done']],
                        ['Open', $d['kpi']['open']], ['Overdue', $d['kpi']['overdue']],
                        ['On-time rate', $d['kpi']['on_time'] === null ? '-' : $d['kpi']['on_time'] . '%'],
                        ['Hours planned', $d['kpi']['hours_total']], ['Hours remaining', $d['kpi']['hours_left']],
                    ],
                ],
                'By status' => [['Status', 'Tasks'], array_map(fn ($s) => [$s['name'], $s['count']], $d['by_status'])],
                'Team' => [
                    ['Member', 'Open', 'Done', 'Overdue', 'Hours remaining'],
                    array_map(fn ($m) => [$m['name'], $m['open'], $m['done'], $m['overdue'], $m['hours']], $d['team']),
                ],
                'Tasks' => [
                    ['ID', 'Task', 'Owner', 'Status', 'Due', 'Hours left', 'Late risk %'],
                    array_map(fn ($t) => [$t['id'], $t['name'], $t['owner'], $t['status'], $t['due'], $t['hours'], $t['risk'] ?? ''], $d['tasks']),
                ],
            ];
            $title = 'Project analytics: ' . $d['project']['name'];
            $file = "analytics-$slug-$stamp";
        } else {
            $sections = $this->overviewSections($f3);
            $title = 'Team & project analytics';
            $file = "analytics-overview-$stamp";
        }

        if ($format === 'csv') {
            header('Content-Type: text/csv; charset=utf-8');
            header('Content-Disposition: attachment; filename="' . $file . '.csv"');
            $out = fopen('php://output', 'w');
            fwrite($out, "\xEF\xBB\xBF");
            foreach ($sections as $name => [$head, $rows]) {
                fputcsv($out, [$name], ',', '"', '');
                fputcsv($out, $head, ',', '"', '');
                foreach ($rows as $row) {
                    fputcsv($out, array_map([$this, 'csvSafe'], $row), ',', '"', '');
                }

                fputcsv($out, [], ',', '"', '');
            }

            fclose($out);
            return;
        }

        $pdf = new \Helper\Pdf($title, (string) $f3->get('site.name') . ' - exported by ' . $f3->get('user.name'));
        foreach ($sections as $name => [$head, $rows]) {
            $pdf->heading($name);
            $pdf->table($head, $rows, $this->pdfWeights($head));
        }

        $pdf->output($file . '.pdf');
    }

    /**
     * POST /analytics/alerts/send
     * Emails the current alert digest to task owners, then reloads the dashboard.
     */
    public function alerts_send(\Base $f3): void
    {
        $this->_requireAdmin();
        $this->validateCsrf();
        $data = \Helper\TaskAlerts::collect($f3->get('db.instance'));
        $r = \Helper\TaskAlerts::send($f3, $data);
        if ($r['error']) {
            $f3->set('error', $r['error']);
        } else {
            $f3->set('success', "Alert emails sent to {$r['sent']} people ({$r['skipped']} skipped).");
        }

        $this->index($f3);
    }

    // ------------------------------------------------------------------ export / project helpers

    /**
     * Restrict tasks to those assigned to the current user, and projects to those containing one of them
     * (or owned by the user).
     *
     * @return array{0: array, 1: array}
     */
    private function scopeIssues(array $tasks, array $projects): array
    {
        $tasks = array_values(array_filter($tasks, fn ($t) => (int) $t['owner_id'] === $this->scopeId));
        $projectIds = array_flip(array_filter(array_column($tasks, 'parent_id')));
        $projects = array_values(array_filter(
            $projects,
            fn ($p) => isset($projectIds[$p['id']]) || (int) $p['owner_id'] === $this->scopeId
        ));

        return [$tasks, $projects];
    }

    /** Keep only the current user's alerts when the viewer is not an admin. */
    private function scopedAlerts(array $alerts): array
    {
        if ($this->scopeId === null) {
            return $alerts;
        }

        $mine = isset($alerts['owners'][$this->scopeId]) ? [$this->scopeId => $alerts['owners'][$this->scopeId]] : [];
        $totals = ['overdue' => 0, 'soon' => 0, 'risk' => 0];
        foreach ($mine as $o) {
            foreach ($totals as $k => $_) {
                $totals[$k] = count($o[$k]);
            }
        }

        return ['owners' => $mine, 'unassigned' => [], 'totals' => $totals];
    }


    private function csvSafe(mixed $v): string
    {
        $v = (string) $v;

        // Prevent spreadsheet formula injection from user-entered text
        return $v !== '' && str_contains("=+-@\t\r", $v[0]) && !is_numeric($v) ? "'" . $v : $v;
    }

    private function pdfWeights(array $head): array
    {
        return array_map(fn ($h) => in_array($h, ['Task', 'Project', 'Member', 'Name']) ? 4 : (in_array($h, ['Metric', 'Owner', 'Status']) ? 2 : 1.2), $head);
    }

    /** Sections for the overview export: [name => [headers, rows]] */
    private function overviewSections(\Base $f3): array
    {
        $db = $f3->get('db.instance');
        $now = time();
        $statuses = [];
        foreach ($db->exec('SELECT id, name, closed FROM issue_status') as $s) {
            $statuses[$s['id']] = $s;
        }

        $projectTypes = array_column($db->exec("SELECT id FROM issue_type WHERE role = 'project'"), 'id');
        $users = [];
        foreach ($db->exec("SELECT id, username, name, role, task_color FROM user WHERE deleted_date IS NULL AND role != 'group'") as $u) {
            $users[$u['id']] = $u + ['initials' => $this->initials($u['name']), 'color' => $this->color($u)];
        }

        [$tasks, $projects] = $this->loadIssues($db, $statuses, $projectTypes);
        if ($this->scopeId !== null) {
            [$tasks, $projects] = $this->scopeIssues($tasks, $projects);
        }

        [$performance, $riskById] = $this->loadMl($db);
        if ($this->scopeId !== null) {
            $performance = [];
            $users = array_intersect_key($users, [$this->scopeId => true]);
        }
        $projectRows = $this->projectRows($projects, $tasks, $users, $riskById, $now);
        $open = array_filter($tasks, fn ($t) => !$t['closed']);

        $workload = [];
        foreach ($users as $u) {
            if ($u['role'] === 'admin') {
                continue;
            }

            $mine = array_filter($open, fn ($t) => (int) $t['owner_id'] === (int) $u['id']);
            $workload[] = [
                $u['name'], count($mine),
                round(array_sum(array_map(fn ($t) => (float) ($t['hours_remaining'] ?: $t['hours_total']), $mine))),
                count(array_filter($mine, fn ($t) => $t['due_ts'] && $t['due_ts'] < $now)),
            ];
        }

        $sections = [
            'Projects' => [
                ['Project', 'Status', 'Progress', 'Tasks done', 'Tasks total', 'Due'],
                array_map(fn ($p) => [$p['name'], $p['status_label'], $p['progress'] . '%', $p['done'], $p['total'], $p['due']], $projectRows),
            ],
        ];
        if ($this->scopeId === null) {
            $sections['Team workload'] = [['Member', 'Open tasks', 'Hours remaining', 'Overdue'], $workload];
        }

        $employees = $this->employees($performance, $users);
        if ($employees) {
            $sections['Employee performance (ML)'] = [
                ['Rank', 'Member', 'Score', 'Group', 'Closed tasks', 'On-time %', 'Expected %', 'Reopen %', 'Open', 'Overdue'],
                array_map(fn ($e) => [$e['rank'] ?? '-', $e['name'], $e['score'] ?? '-', $e['cluster'], $e['tasks'], $e['on_time'], $e['expected'], $e['reopen'], $e['open_tasks'], $e['overdue']], $employees),
            ];
        }

        $alerts = $this->scopedAlerts(\Helper\TaskAlerts::collect($db, $now));
        $alertRows = [];
        foreach ($alerts['owners'] as $o) {
            foreach (['overdue' => 'Overdue', 'soon' => 'Due soon', 'risk' => 'Late risk'] as $k => $label) {
                foreach ($o[$k] as $t) {
                    $alertRows[] = [$label, '#' . $t['id'] . ' ' . $t['name'], $o['user']['name'], $t['due'] ?: '-', $t['p'] === null ? '' : $t['p'] . '%'];
                }
            }
        }

        $sections['Task alerts'] = [['Alert', 'Task', 'Owner', 'Due', 'Late risk'], $alertRows];

        return $sections;
    }

    /** @return array{0: array, 1: array} [tasks, projects] with derived timestamps */
    private function loadIssues($db, array $statuses, array $projectTypes): array
    {
        $tasks = [];
        $projects = [];
        $rows = $db->exec(
            'SELECT id, name, description, type_id, status, owner_id, parent_id, priority, hours_total, hours_remaining,
                    created_date, closed_date, due_date, sprint_id FROM issue WHERE deleted_date IS NULL'
        );
        foreach ($rows as $r) {
            $r['closed'] = !empty($statuses[$r['status']]['closed']);
            $r['created_ts'] = strtotime($r['created_date']);
            $r['closed_ts'] = $r['closed_date'] ? strtotime($r['closed_date']) : null;
            $r['due_ts'] = $r['due_date'] ? strtotime($r['due_date'] . ' 23:59:59') : null;
            if (in_array($r['type_id'], $projectTypes)) {
                $projects[] = $r;
            } else {
                $tasks[] = $r;
            }
        }

        return [$tasks, $projects];
    }

    /** Everything the per-project page and its exports need. */
    private function projectData(\Base $f3, int $id): array
    {
        $db = $f3->get('db.instance');
        $now = time();
        $statuses = [];
        foreach ($db->exec('SELECT id, name, closed FROM issue_status') as $s) {
            $statuses[$s['id']] = $s;
        }

        $projectTypes = array_column($db->exec("SELECT id FROM issue_type WHERE role = 'project'"), 'id');
        [$tasks, $projects] = $this->loadIssues($db, $statuses, $projectTypes);
        $allTasks = $tasks;
        if ($this->scopeId !== null) {
            [$tasks, $projects] = $this->scopeIssues($tasks, $projects);
        }

        $project = null;
        foreach ($projects as $p) {
            if ((int) $p['id'] === $id) {
                $project = $p;
            }
        }

        if ($project === null) {
            $f3->error(404);
            exit;
        }

        $users = [];
        foreach ($db->exec("SELECT id, username, name, role, task_color FROM user WHERE deleted_date IS NULL AND role != 'group'") as $u) {
            $users[$u['id']] = $u + ['initials' => $this->initials($u['name']), 'color' => $this->color($u)];
        }

        [, $riskById] = $this->loadMl($db);

        // Tasks under the project, at any depth
        $byParent = [];
        foreach ($allTasks as $t) {
            $byParent[(int) $t['parent_id']][] = $t;
        }

        $mine = [];
        $queue = [$id];
        while ($queue) {
            foreach ($byParent[array_shift($queue)] ?? [] as $t) {
                if ($this->scopeId === null || (int) $t['owner_id'] === $this->scopeId) {
                    $mine[] = $t;
                }

                $queue[] = (int) $t['id'];
            }
        }

        $row = $this->projectRows([$project], $mine, $users, $riskById, $now)[0];
        $open = array_filter($mine, fn ($t) => !$t['closed']);
        $done = array_filter($mine, fn ($t) => $t['closed']);
        $overdue = array_filter($open, fn ($t) => $t['due_ts'] && $t['due_ts'] < $now);
        $withDue = array_filter($done, fn ($t) => $t['due_ts'] && $t['closed_ts']);
        $onTime = array_filter($withDue, fn ($t) => $t['closed_ts'] <= $t['due_ts']);
        $risks = array_filter(array_map(fn ($t) => $riskById[(int) $t['id']] ?? null, $open), fn ($r) => $r !== null);

        $byStatus = [];
        foreach ($mine as $t) {
            $sid = $t['status'];
            $byStatus[$sid] ??= ['name' => $statuses[$sid]['name'] ?? 'Unknown', 'count' => 0, 'closed' => !empty($statuses[$sid]['closed'])];
            $byStatus[$sid]['count']++;
        }

        $max = max([1, ...array_column($byStatus, 'count')]);
        foreach ($byStatus as &$s) {
            $s['pct'] = (int) round($s['count'] / $max * 100);
        }

        unset($s);

        $team = [];
        foreach ($mine as $t) {
            $u = $users[$t['owner_id']] ?? null;
            $key = $u ? $t['owner_id'] : 0;
            $team[$key] ??= [
                'name' => $u['name'] ?? 'Unassigned', 'initials' => $u['initials'] ?? '?', 'color' => $u['color'] ?? '#8a8da2',
                'open' => 0, 'done' => 0, 'overdue' => 0, 'hours' => 0.0,
            ];
            if ($t['closed']) {
                $team[$key]['done']++;
            } else {
                $team[$key]['open']++;
                $team[$key]['hours'] += (float) ($t['hours_remaining'] ?: $t['hours_total']);
                if ($t['due_ts'] && $t['due_ts'] < $now) {
                    $team[$key]['overdue']++;
                }
            }
        }

        foreach ($team as $key => $member) {
            $team[$key]['hours'] = round($member['hours']);
        }

        usort($team, fn ($a, $b) => $b['open'] <=> $a['open']);

        // Weekly flow, last 8 weeks
        $today = strtotime('today', $now);
        $flow = [];
        for ($w = 7; $w >= 0; $w--) {
            $from = $today - ($w * 7 + 6) * 86400;
            $to = $from + 7 * 86400;
            $s = $this->periodStats($mine, $from, $to);
            $flow[] = ['label' => date('M j', $from), 'created' => $s['created'], 'closed' => $s['closed']];
        }

        $fmax = max([1, ...array_column($flow, 'created'), ...array_column($flow, 'closed')]);
        foreach ($flow as &$fw) {
            $fw['created_pct'] = (int) round($fw['created'] / $fmax * 100);
            $fw['closed_pct'] = (int) round($fw['closed'] / $fmax * 100);
        }

        unset($fw);

        usort($mine, fn ($a, $b) => [(int) $a['closed'], $a['due_ts'] ?: PHP_INT_MAX] <=> [(int) $b['closed'], $b['due_ts'] ?: PHP_INT_MAX]);
        $taskRows = array_map(function ($t) use ($users, $statuses, $riskById, $now) {
            $p = $riskById[(int) $t['id']] ?? null;

            return [
                'id' => $t['id'], 'name' => $t['name'], 'owner' => $users[$t['owner_id']]['name'] ?? 'Unassigned',
                'status' => $statuses[$t['status']]['name'] ?? '', 'closed' => $t['closed'],
                'due' => $t['due_date'] ?: '', 'overdue' => !$t['closed'] && $t['due_ts'] && $t['due_ts'] < $now,
                'hours' => (float) ($t['hours_remaining'] ?: 0),
                'risk' => ($p === null || $t['closed']) ? null : (int) round($p * 100),
            ];
        }, $mine);

        return [
            'project' => $project,
            'row' => $row,
            'kpi' => [
                'total' => count($taskRows), 'done' => count($done), 'open' => count($open), 'overdue' => count($overdue),
                'on_time' => $withDue ? (int) round(count($onTime) / count($withDue) * 100) : null,
                'hours_total' => round(array_sum(array_map(fn ($t) => (float) $t['hours_total'], $mine))),
                'hours_left' => round(array_sum(array_map(fn ($t) => (float) $t['hours_remaining'], $open))),
                'risk' => $risks ? (int) round(array_sum($risks) / count($risks) * 100) : null,
            ],
            'by_status' => array_values($byStatus),
            'team' => array_values($team),
            'flow' => $flow,
            'tasks' => $taskRows,
            'scoped' => $this->scopeId !== null,
        ];
    }

    // ------------------------------------------------------------------ helpers

    private function loadMl($db): array
    {
        $performance = [];
        $risk = [];
        $run = null;
        try {
            $performance = $db->exec('SELECT * FROM employee_performance');
            foreach ($db->exec('SELECT issue_id, p_late FROM task_risk') as $r) {
                $risk[(int) $r['issue_id']] = (float) $r['p_late'];
            }

            $runs = $db->exec('SELECT computed_at, metrics FROM ml_run ORDER BY id DESC LIMIT 1');
            $run = $runs ? ['computed_at' => $runs[0]['computed_at']] + (json_decode($runs[0]['metrics'], true) ?: []) : null;
        } catch (\Throwable $e) {
            // ML job has not been run yet
        }

        return [$performance, $risk, $run];
    }

    private function periodStats(array $tasks, int $from, int $to): array
    {
        $created = 0;
        $closed = 0;
        $withDue = 0;
        $onTime = 0;
        foreach ($tasks as $t) {
            if ($t['created_ts'] >= $from && $t['created_ts'] < $to) {
                $created++;
            }

            if ($t['closed'] && $t['closed_ts'] && $t['closed_ts'] >= $from && $t['closed_ts'] < $to) {
                $closed++;
                if ($t['due_ts']) {
                    $withDue++;
                    if ($t['closed_ts'] <= $t['due_ts']) {
                        $onTime++;
                    }
                }
            }
        }

        return [
            'created' => $created, 'closed' => $closed,
            'on_time_rate' => $withDue ? (int) round($onTime / $withDue * 100) : null,
        ];
    }

    private function pctChange(int|float $now, int|float $before): ?float
    {
        if ($before == 0) {
            return $now > 0 ? 100.0 : null;
        }

        return round(($now - $before) / $before * 100, 1);
    }

    private function initials(string $name): string
    {
        $parts = preg_split('/\s+/', trim($name)) ?: [];
        $out = '';
        foreach (array_slice($parts, 0, 2) as $p) {
            $out .= mb_strtoupper(mb_substr($p, 0, 1));
        }

        return $out ?: '?';
    }

    private function color(array $u): string
    {
        if (!empty($u['task_color']) && preg_match('/^[0-9a-fA-F]{6}$/', $u['task_color'])) {
            return '#' . $u['task_color'];
        }

        $palette = ['#6d5df6', '#2f7ff0', '#12a05c', '#d9820b', '#e5484d', '#0ea5a4', '#ec6bd0', '#8b5cf6'];

        return $palette[$u['id'] % count($palette)];
    }

    private function projectRows(array $projects, array $tasks, array $users, array $riskById, int $now): array
    {
        $kids = [];
        foreach ($tasks as $t) {
            if ($t['parent_id']) {
                $kids[$t['parent_id']][] = $t;
            }
        }

        $rows = [];
        foreach ($projects as $p) {
            $mine = $kids[$p['id']] ?? [];
            $total = count($mine);
            $done = count(array_filter($mine, fn ($k) => $k['closed']));
            $progress = $total ? (int) round($done / $total * 100) : ($p['closed'] ? 100 : 0);

            // Team: most frequent owners
            $owners = array_count_values(array_filter(array_column($mine, 'owner_id')));
            arsort($owners);
            $team = [];
            foreach (array_slice(array_keys($owners), 0, 4) as $oid) {
                if (isset($users[$oid])) {
                    $team[] = ['name' => $users[$oid]['name'], 'initials' => $users[$oid]['initials'], 'color' => $users[$oid]['color']];
                }
            }

            $open = array_filter($mine, fn ($k) => !$k['closed']);
            $overdue = count(array_filter($open, fn ($k) => $k['due_ts'] && $k['due_ts'] < $now));
            $risks = array_filter(array_map(fn ($k) => $riskById[(int) $k['id']] ?? null, $open), fn ($r) => $r !== null);
            $avgRisk = $risks ? array_sum($risks) / count($risks) : 0;

            $status = 'progress';
            if ($p['closed']) {
                $status = 'done';
            } else {
                $span = max(1, ($p['due_ts'] ?: $now) - $p['created_ts']);
                $expected = max(0, min(1, ($now - $p['created_ts']) / $span));
                if ($expected - $progress / 100 > 0.15 || $avgRisk > 0.6 || $overdue >= 3) {
                    $status = 'risk';
                } elseif ($progress / 100 >= $expected - 0.05) {
                    $status = 'track';
                }
            }

            $rows[] = [
                'id' => $p['id'], 'name' => $p['name'], 'subtitle' => $this->firstSentence((string) $p['description']),
                'progress' => $progress, 'done' => $done, 'total' => $total, 'team' => $team,
                'status' => $status, 'status_label' => ['done' => 'Completed', 'track' => 'On Track', 'risk' => 'At Risk', 'progress' => 'In Progress'][$status],
                'due' => $p['due_date'] ? date('M j', strtotime($p['due_date'])) : '',
                'sort' => $p['closed'] ? 1 : 0, 'sort_ts' => $p['closed'] ? -($p['closed_ts'] ?: 0) : ($p['due_ts'] ?: PHP_INT_MAX),
            ];
        }

        usort($rows, fn ($a, $b) => [$a['sort'], $a['sort_ts']] <=> [$b['sort'], $b['sort_ts']]);

        return $rows;
    }

    private function firstSentence(string $text): string
    {
        $text = trim(preg_replace('/\s+/', ' ', strip_tags($text)) ?? '');
        if (preg_match('/^(.{10,90}?[.!?])(\s|$)/u', $text, $m)) {
            return $m[1];
        }

        return mb_strlen($text) > 90 ? mb_substr($text, 0, 87) . '...' : $text;
    }

    private function employees(array $performance, array $users): array
    {
        $out = [];
        foreach ($performance as $p) {
            $u = $users[$p['user_id']] ?? null;
            if (!$u) {
                continue;
            }

            $out[] = [
                'id' => (int) $p['user_id'], 'name' => $u['name'], 'initials' => $u['initials'], 'color' => $u['color'],
                'score' => $p['score'] === null ? null : (float) $p['score'],
                'rank' => $p['rank'] === null ? null : (int) $p['rank'],
                'shift' => ($p['rank'] !== null && $p['naive_rank'] !== null) ? (int) $p['naive_rank'] - (int) $p['rank'] : 0,
                'cluster' => $p['cluster'],
                'cluster_key' => strtolower(preg_replace('/[^a-z]+/i', '-', $p['cluster'])),
                'tasks' => (int) $p['tasks_closed'],
                'on_time' => round($p['on_time_rate'] * 100), 'expected' => round($p['expected_on_time'] * 100),
                'speed' => round((float) $p['speed_index'], 2), 'late_days' => round((float) $p['avg_lateness_days'], 1),
                'reopen' => round($p['reopen_rate'] * 100, 1), 'estimate' => round($p['estimate_accuracy'] * 100),
                'throughput' => round((float) $p['weekly_throughput'], 1), 'hours' => round((float) $p['hours_delivered']),
                'trend' => round($p['trend_delta'] * 100), 'open_tasks' => (int) $p['open_tasks'], 'overdue' => (int) $p['overdue_open'],
                'strengths' => json_decode($p['strengths'] ?? '[]', true) ?: [],
                'concerns' => json_decode($p['concerns'] ?? '[]', true) ?: [],
                'components' => json_decode($p['components'] ?? '{}', true) ?: [],
            ];
        }

        usort($out, fn ($a, $b) => ($a['rank'] ?? PHP_INT_MAX) <=> ($b['rank'] ?? PHP_INT_MAX));

        return $out;
    }

    private function deadlines(array $open, array $users, array $projects, array $riskById, int $today): array
    {
        $names = array_column($projects, 'name', 'id');
        $list = array_filter($open, fn ($t) => $t['due_ts'] && $t['due_ts'] < $today + 8 * 86400);
        usort($list, fn ($a, $b) => $a['due_ts'] <=> $b['due_ts']);

        $out = [];
        foreach (array_slice($list, 0, 7) as $t) {
            $risk = $riskById[(int) $t['id']] ?? null;
            $out[] = [
                'id' => $t['id'], 'name' => $t['name'], 'project' => $names[$t['parent_id']] ?? '',
                'when' => $t['due_ts'] < $today ? 'Overdue' : ($t['due_ts'] < $today + 86400 ? 'Today' : date('D, M j', $t['due_ts'])),
                'overdue' => $t['due_ts'] < $today,
                'owner' => $users[$t['owner_id']] ?? null,
                'risk' => $risk === null ? null : (int) round($risk * 100),
            ];
        }

        return $out;
    }

    private function weekStrip(array $tasks, int $today): array
    {
        $monday = strtotime('monday this week', $today);
        $days = [];
        for ($d = 0; $d < 7; $d++) {
            $ts = $monday + $d * 86400;
            $count = 0;
            foreach ($tasks as $t) {
                if ($t['due_ts'] && $t['due_ts'] >= $ts && $t['due_ts'] < $ts + 86400) {
                    $count++;
                }
            }

            $days[] = ['dow' => date('D', $ts), 'day' => date('j', $ts), 'today' => $ts === $today, 'count' => $count];
        }

        return ['month' => date('F Y', $today), 'days' => $days];
    }

    private function atRiskTasks(array $open, array $riskById, array $users, array $projects): array
    {
        $names = array_column($projects, 'name', 'id');
        $list = array_filter($open, fn ($t) => isset($riskById[(int) $t['id']]) && $riskById[(int) $t['id']] >= 0.28);
        usort($list, fn ($a, $b) => $riskById[(int) $b['id']] <=> $riskById[(int) $a['id']]);

        $out = [];
        foreach (array_slice($list, 0, 6) as $t) {
            $p = (int) round($riskById[(int) $t['id']] * 100);
            $out[] = [
                'id' => $t['id'], 'name' => $t['name'], 'project' => $names[$t['parent_id']] ?? '',
                'owner' => $users[$t['owner_id']] ?? null, 'p' => $p, 'tone' => $p >= 40 ? 'high' : 'mid',
                'due' => $t['due_date'] ? date('M j', strtotime($t['due_date'])) : '',
            ];
        }

        return $out;
    }

    private function activity($db, array $users, array $statuses, ?int $ownerId = null): array
    {
        $ups = $db->exec(
            'SELECT u.id, u.issue_id, u.user_id, u.created_date, u.comment_id, i.name AS issue_name
             FROM issue_update u JOIN issue i ON i.id = u.issue_id'
            . ($ownerId !== null ? ' WHERE (i.owner_id = ' . (int) $ownerId . ' OR u.user_id = ' . (int) $ownerId . ')' : '')
            . ' ORDER BY u.created_date DESC, u.id DESC LIMIT 12'
        );

        $fields = [];
        if ($ups) {
            $ids = implode(',', array_map('intval', array_column($ups, 'id')));
            foreach ($db->exec("SELECT issue_update_id, field, old_value, new_value FROM issue_update_field WHERE issue_update_id IN ($ids)") as $f) {
                $fields[$f['issue_update_id']][$f['field']] = $f;
            }
        }

        $out = [];
        foreach ($ups as $u) {
            $f = $fields[$u['id']] ?? [];
            $icon = 'fa-pencil';
            $verb = 'updated';
            if (isset($f['status'])) {
                $to = $statuses[$f['status']['new_value']] ?? null;
                $from = $statuses[$f['status']['old_value']] ?? null;
                if ($to && $to['closed']) {
                    [$verb, $icon] = ['completed', 'fa-check'];
                } elseif ($from && $from['closed']) {
                    [$verb, $icon] = ['reopened', 'fa-repeat'];
                } else {
                    [$verb, $icon] = ['moved to ' . ($to['name'] ?? 'a new status') . ':', 'fa-arrow-right'];
                }
            } elseif (isset($f['sprint_id'])) {
                [$verb, $icon] = ['scheduled into a sprint:', 'fa-bolt'];
            } elseif (isset($f['owner_id'])) {
                [$verb, $icon] = ['reassigned', 'fa-exchange'];
            } elseif ($u['comment_id']) {
                [$verb, $icon] = ['commented on', 'fa-comment-o'];
            } elseif (isset($f['hours_remaining'])) {
                [$verb, $icon] = ['updated the estimate for', 'fa-hourglass-half'];
            }

            $who = $users[$u['user_id']] ?? null;
            $out[] = [
                'who' => $who['name'] ?? 'Someone', 'initials' => $who['initials'] ?? '?', 'color' => $who['color'] ?? '#8a8da2',
                'verb' => $verb, 'icon' => $icon, 'issue_id' => $u['issue_id'], 'issue' => $u['issue_name'],
                'ago' => $this->ago(strtotime($u['created_date'])), 'ts' => strtotime($u['created_date']),
            ];
        }

        // Comments posted through the app have no issue_update row, so read them directly
        $comments = $db->exec(
            'SELECT c.user_id, c.issue_id, c.created_date, i.name AS issue_name
             FROM issue_comment c JOIN issue i ON i.id = c.issue_id
             WHERE NOT EXISTS (SELECT 1 FROM issue_update u WHERE u.comment_id = c.id)'
            . ($ownerId !== null ? ' AND (i.owner_id = ' . (int) $ownerId . ' OR c.user_id = ' . (int) $ownerId . ')' : '')
            . ' ORDER BY c.created_date DESC, c.id DESC LIMIT 12'
        );
        foreach ($comments as $c) {
            $who = $users[$c['user_id']] ?? null;
            $out[] = [
                'who' => $who['name'] ?? 'Someone', 'initials' => $who['initials'] ?? '?', 'color' => $who['color'] ?? '#8a8da2',
                'verb' => 'commented on', 'icon' => 'fa-comment-o', 'issue_id' => $c['issue_id'], 'issue' => $c['issue_name'],
                'ago' => $this->ago(strtotime($c['created_date'])), 'ts' => strtotime($c['created_date']),
            ];
        }

        usort($out, fn ($a, $b) => $b['ts'] <=> $a['ts']);

        return array_slice($out, 0, 8);
    }

    private function ago(int $ts): string
    {
        $d = time() - $ts;
        if ($d < 60) {
            return 'just now';
        }

        foreach ([[86400, 'day'], [3600, 'hour'], [60, 'minute']] as [$size, $label]) {
            if ($d >= $size) {
                $n = intdiv($d, $size);

                return $n . ' ' . $label . ($n > 1 ? 's' : '') . ' ago';
            }
        }

        return 'just now';
    }

    private function mlSummary(?array $run): ?array
    {
        if (!$run) {
            return null;
        }

        $late = $run['late_model'] ?? [];
        $risk = $run['risk_model'] ?? [];
        $cyc = $run['cycle_model'] ?? [];
        $lc = $late['candidates'][$late['chosen'] ?? ''] ?? [];
        $rc = $risk['candidates'][$risk['chosen'] ?? ''] ?? [];
        $cc = $cyc['candidates'][$cyc['chosen'] ?? ''] ?? [];

        return [
            'computed_at' => date('M j, g:ia', strtotime($run['computed_at'])),
            'tasks' => $run['n_closed_tasks'] ?? 0, 'open' => $run['n_open_tasks'] ?? 0,
            'late_model' => str_replace('_', ' ', (string) ($late['chosen'] ?? '')), 'late_auc' => $lc['auc'] ?? null,
            'risk_model' => str_replace('_', ' ', (string) ($risk['chosen'] ?? '')), 'risk_auc' => $rc['auc'] ?? null,
            'cycle_model' => str_replace('_', ' ', (string) ($cyc['chosen'] ?? '')), 'cycle_mae' => $cc['mae_days'] ?? null,
            'cycle_base' => $cyc['candidates']['baseline_median']['mae_days'] ?? null,
            'k' => $run['clustering']['k'] ?? null, 'silhouette' => $run['clustering']['silhouette'] ?? null,
            'rho' => $run['rank_correlation_vs_naive_on_time'] ?? null,
        ];
    }
}

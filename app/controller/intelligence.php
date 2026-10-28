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
        [$status, $data, $error] = \Helper\Ml::forecastSprint((int) $params['id'], $simulations);
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

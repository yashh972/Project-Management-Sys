<?php

namespace Controller;

/**
 * Smart assignment: ranks the team for a new task using ml/assign_model.py.
 *
 * GET /assign/suggest?type_id=1&hours=6&priority=0&due=2026-10-10&tags=backend,api[&exclude=3,4]
 */
class Assign extends \Controller
{
    public function __construct()
    {
        $this->_requireLogin();
    }

    public function suggest(\Base $f3): void
    {
        $type = (int) $f3->get('GET.type_id') ?: 1;
        $hours = (float) $f3->get('GET.hours');
        $priority = (int) $f3->get('GET.priority');
        $due = (string) $f3->get('GET.due');
        $tags = implode(',', array_filter(array_map(
            fn ($t) => preg_replace('/[^a-z0-9_-]/i', '', ltrim(trim($t), '#')),
            explode(',', (string) $f3->get('GET.tags'))
        )));
        $exclude = implode(',', array_filter(array_map('intval', explode(',', (string) $f3->get('GET.exclude')))));

        $args = '--type ' . $type . ' --priority ' . $priority;
        if ($hours > 0) {
            $args .= ' --hours ' . $hours;
        }

        if (preg_match('/^\d{4}-\d{2}-\d{2}$/', $due)) {
            $args .= ' --due ' . $due;
        }

        if ($tags !== '') {
            $args .= ' --tags ' . escapeshellarg($tags);
        }

        if ($exclude !== '') {
            $args .= ' --exclude ' . escapeshellarg($exclude);
        }

        [$code, $lines] = \Helper\Ml::run('assign_model.py', 'suggest ' . $args . ' --top 5', 90);
        $data = $code === 0 ? json_decode(implode('', $lines), true) : null;
        if (!is_array($data)) {
            $this->_printJson(['error' => $code === 127 ? $lines[0] : 'The assignment model could not run. Try again or retrain it from Analytics.']);
            return;
        }

        $this->_printJson($data);
    }
}

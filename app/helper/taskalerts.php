<?php

namespace Helper;

/**
 * Task alerts: overdue tasks, tasks due soon, and open tasks the ML job flags as likely to slip.
 * Used by the /analytics Alerts tab and by cron/task_alerts.php (email digests to owners).
 */
class TaskAlerts
{
    /** Tasks due within this many days count as "due soon" */
    public const SOON_DAYS = 2;

    /** Minimum ML late-probability to flag a task */
    public const RISK_THRESHOLD = 0.4;

    /**
     * Collect alerts grouped by task owner.
     *
     * @return array{owners: array<int, array>, unassigned: array, totals: array<string,int>}
     */
    public static function collect($db, ?int $now = null): array
    {
        $now ??= time();
        $today = gmdate('Y-m-d', $now);
        $soonEnd = gmdate('Y-m-d', $now + self::SOON_DAYS * 86400);

        $risk = [];
        try {
            foreach ($db->exec('SELECT issue_id, p_late FROM task_risk') as $r) {
                $risk[(int) $r['issue_id']] = (float) $r['p_late'];
            }
        } catch (\Throwable $e) {
            // ML job has not been run yet
        }

        $rows = $db->exec(
            "SELECT i.id, i.name, i.due_date, i.owner_id, i.parent_id
             FROM issue i
             JOIN issue_status s ON s.id = i.status
             JOIN issue_type t ON t.id = i.type_id
             WHERE i.deleted_date IS NULL AND s.closed = 0 AND t.role != 'project'"
        );

        $users = [];
        foreach ($db->exec("SELECT id, name, email FROM user WHERE deleted_date IS NULL AND role != 'group'") as $u) {
            $users[(int) $u['id']] = $u;
        }

        $owners = [];
        $unassigned = [];
        $totals = ['overdue' => 0, 'soon' => 0, 'risk' => 0];
        foreach ($rows as $t) {
            $kind = null;
            $due = $t['due_date'];
            $p = $risk[(int) $t['id']] ?? null;
            if ($due && $due < $today) {
                $kind = 'overdue';
            } elseif ($due && $due <= $soonEnd) {
                $kind = 'soon';
            } elseif ($p !== null && $p >= self::RISK_THRESHOLD) {
                $kind = 'risk';
            }

            if ($kind === null) {
                continue;
            }

            $totals[$kind]++;
            $item = [
                'id' => (int) $t['id'], 'name' => $t['name'], 'due' => $due, 'kind' => $kind,
                'p' => $p === null ? null : (int) round($p * 100),
                'days' => $due ? (int) round((strtotime($due) - strtotime($today)) / 86400) : null,
            ];
            $oid = (int) $t['owner_id'];
            if (!isset($users[$oid])) {
                $unassigned[] = $item;
                continue;
            }

            $owners[$oid] ??= ['user' => $users[$oid], 'overdue' => [], 'soon' => [], 'risk' => []];
            $owners[$oid][$kind][] = $item;
        }

        uasort($owners, fn ($a, $b) => (count($b['overdue']) <=> count($a['overdue'])) ?: (count($b['soon']) <=> count($a['soon'])));

        return ['owners' => $owners, 'unassigned' => $unassigned, 'totals' => $totals];
    }

    /**
     * Email each owner a digest of their alerts.
     *
     * @return array{sent: int, skipped: int, error: ?string}
     */
    public static function send(\Base $f3, array $data): array
    {
        if (!$f3->get('mail.from')) {
            return ['sent' => 0, 'skipped' => count($data['owners']), 'error' => 'Email is not configured (mail.from is empty).'];
        }

        $notification = new Notification();
        $site = (string) $f3->get('site.name');
        $url = rtrim((string) $f3->get('site.url'), '/');
        $sent = 0;
        $skipped = 0;
        foreach ($data['owners'] as $uid => $o) {
            $user = new \Model\User();
            $user->load($uid);
            if (!$user->id || !$user->email || $user->option('disable_due_alerts')) {
                $skipped++;
                continue;
            }

            $sections = [
                'overdue' => 'Overdue', 'soon' => 'Due in the next ' . self::SOON_DAYS . ' days', 'risk' => 'Likely to slip (ML forecast)',
            ];
            $text = "$site - task alerts\n";
            $html = '<h2 style="font-family:sans-serif">' . htmlspecialchars($site) . ' - task alerts</h2>';
            foreach ($sections as $k => $label) {
                if (!$o[$k]) {
                    continue;
                }

                $text .= "\n$label:\n";
                $html .= '<h3 style="font-family:sans-serif">' . $label . '</h3><ul style="font-family:sans-serif">';
                foreach ($o[$k] as $t) {
                    $extra = $t['due'] ? ' (due ' . $t['due'] . ')' : '';
                    $extra .= $k === 'risk' ? ' - ' . $t['p'] . '% late risk' : '';
                    $link = $url . '/issues/' . $t['id'];
                    $text .= "  #{$t['id']} {$t['name']}$extra - $link\n";
                    $html .= '<li><a href="' . htmlspecialchars($link) . '">#' . $t['id'] . ' ' . htmlspecialchars($t['name']) . '</a>' . htmlspecialchars($extra) . '</li>';
                }

                $html .= '</ul>';
            }

            $count = count($o['overdue']) + count($o['soon']) + count($o['risk']);
            if ($notification->utf8mail($user->email, "$count task alert" . ($count === 1 ? '' : 's') . " - $site", $html, $text)) {
                $sent++;
            } else {
                $skipped++;
            }
        }

        return ['sent' => $sent, 'skipped' => $skipped, 'error' => null];
    }
}

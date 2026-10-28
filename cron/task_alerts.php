<?php

/**
 *  task_alerts.php
 *  Emails each task owner a digest of overdue tasks, tasks due soon and tasks the ML job flags as likely to slip.
 *  Schedule daily, e.g. after ml/run_analytics.py: php cron/task_alerts.php
 */

require_once __DIR__ . "/base.php";

$data = \Helper\TaskAlerts::collect($f3->get("db.instance"));
$result = \Helper\TaskAlerts::send($f3, $data);

echo sprintf(
    "Alerts: %d overdue, %d due soon, %d at risk. Emails sent: %d, skipped: %d.%s\n",
    $data['totals']['overdue'],
    $data['totals']['soon'],
    $data['totals']['risk'],
    $result['sent'],
    $result['skipped'],
    $result['error'] ? " " . $result['error'] : ""
);

<?php

/**
 * Generate deterministic demo data for local evaluation and demos.
 *
 * Usage: php cron/seed_demo.php
 *
 * Creates four team members, three projects, a year of sprints, ~140 closed
 * tasks with realistic lateness profiles, and open work for the current and
 * next sprint. Safe to run repeatedly: it exits if the marker is present.
 */

require_once __DIR__ . "/base.php";

$db = $f3->get("db.instance");

$seeded = $db->exec("SELECT value FROM config WHERE attribute = 'demo.seeded'");
if (!empty($seeded)) {
    echo "Demo data already seeded. Delete the demo.seeded config row to run again.\n";
    exit(0);
}

$admin = $db->exec("SELECT id FROM user WHERE role = 'admin' ORDER BY id LIMIT 1");
if (empty($admin)) {
    fwrite(STDERR, "No admin user found. Install the application first.\n");
    exit(1);
}
$adminId = (int) $admin[0]['id'];
$security = \Helper\Security::instance();
// Use the legacy SHA1 format so the seed also works on databases that have not
// yet applied the password-width migration; login supports both formats.
$passwordSalt = $security->salt();
$password = [
    'salt' => $passwordSalt,
    'hash' => $security->hash('demo1234', $passwordSalt),
];
$now = time();

mt_srand(20261028);

/**
 * Insert a user if the username does not exist and return its id.
 */
function demo_user($db, string $username, string $name, string $role, array $password, int $now): int
{
    $existing = $db->exec("SELECT id FROM user WHERE username = ?", [$username]);
    if (!empty($existing)) {
        return (int) $existing[0]['id'];
    }

    $db->exec(
        "INSERT INTO user (username, email, name, password, salt, role, `rank`, task_color, created_date)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            $username,
            $username . '@example.com',
            $name,
            $password['hash'],
            $password['salt'],
            $role,
            $role === 'admin' ? 100 : \Model\User::RANK_USER,
            substr(md5($username), 0, 6),
            date('Y-m-d H:i:s', $now - 200 * 86400),
        ]
    );

    return (int) $db->lastInsertId();
}

$team = [
    'demo_alice' => ['name' => 'Alice Sharma', 'reliability' => 0.86],
    'demo_bob' => ['name' => 'Bob Mehta', 'reliability' => 0.62],
    'demo_carol' => ['name' => 'Carol Iyer', 'reliability' => 0.92],
    'demo_dave' => ['name' => 'Dave Nair', 'reliability' => 0.74],
];
$userIds = [];
foreach ($team as $username => $profile) {
    $userIds[$username] = demo_user($db, $username, $profile['name'], 'user', $password, $now);
}

/**
 * Create an issue and return its id.
 */
function demo_issue($db, array $row): int
{
    $fields = array_keys($row);
    $placeholders = implode(', ', array_fill(0, count($fields), '?'));
    $db->exec(
        "INSERT INTO issue (" . implode(', ', $fields) . ") VALUES (" . $placeholders . ")",
        array_values($row)
    );
    return (int) $db->lastInsertId();
}

function demo_tag($db, int $issueId, string $tag): void
{
    $db->exec("INSERT INTO issue_tag (issue_id, tag) VALUES (?, ?)", [$issueId, $tag]);
}

function demo_activate($db, int $issueId, int $userId, string $when): void
{
    $db->exec(
        "INSERT INTO issue_update (issue_id, user_id, created_date, notify) VALUES (?, ?, ?, 0)",
        [$issueId, $userId, $when]
    );
    $updateId = (int) $db->lastInsertId();
    $db->exec(
        "INSERT INTO issue_update_field (issue_update_id, field, old_value, new_value) VALUES (?, 'status', '1', '2')",
        [$updateId]
    );
}

$tags = ['backend', 'frontend', 'api', 'data', 'ui', 'infra'];
$projectNames = ['Customer Portal', 'Payments Platform', 'Internal Tools'];
$projectIds = [];
foreach ($projectNames as $index => $name) {
    $projectIds[] = demo_issue($db, [
        'status' => 1,
        'type_id' => 2,
        'name' => $name,
        'description' => "Demo project: {$name}",
        'author_id' => $adminId,
        'owner_id' => $adminId,
        'priority' => 0,
        'created_date' => date('Y-m-d H:i:s', $now - (200 - $index * 10) * 86400),
    ]);
}

// Twelve past two-week sprints + current + next.
$sprints = [];
for ($i = 12; $i >= 1; $i--) {
    $start = $now - ($i * 14 + 7) * 86400;
    $sprints[] = [
        'name' => 'Sprint ' . (13 - $i),
        'start' => date('Y-m-d', $start),
        'end' => date('Y-m-d', $start + 13 * 86400),
        'start_ts' => $start,
        'kind' => 'past',
    ];
}
$currentStart = $now - 3 * 86400;
$sprints[] = [
    'name' => 'Sprint 13',
    'start' => date('Y-m-d', $currentStart),
    'end' => date('Y-m-d', $currentStart + 13 * 86400),
    'start_ts' => $currentStart,
    'kind' => 'current',
];
$nextStart = $currentStart + 14 * 86400;
$sprints[] = [
    'name' => 'Sprint 14',
    'start' => date('Y-m-d', $nextStart),
    'end' => date('Y-m-d', $nextStart + 13 * 86400),
    'start_ts' => $nextStart,
    'kind' => 'next',
];

$sprintIds = [];
foreach ($sprints as $sprint) {
    $db->exec(
        "INSERT INTO sprint (name, start_date, end_date) VALUES (?, ?, ?)",
        [$sprint['name'], $sprint['start'], $sprint['end']]
    );
    $sprintIds[] = (int) $db->lastInsertId();
}

$sprintIndex = 0;
$taskNumber = 1;
$closedCount = 0;
$usernames = array_keys($team);

foreach ($sprints as $sprint) {
    $sprintId = $sprintIds[$sprintIndex++];
    $isPast = $sprint['kind'] === 'past';
    $isCurrent = $sprint['kind'] === 'current';
    $count = $isPast ? 30 : ($isCurrent ? 5 : 4);

    for ($j = 0; $j < $count; $j++) {
        $username = $usernames[mt_rand(0, count($usernames) - 1)];
        $ownerId = $userIds[$username];
        $reliability = $team[$username]['reliability'];
        $isBug = mt_rand(1, 100) <= 22;

        if ($isPast) {
            $created = $sprint['start_ts'] - mt_rand(0, 3) * 86400 + mt_rand(0, 8) * 3600;
            $start = $created + mt_rand(1, 2) * 86400;
            $due = $start + mt_rand(2, 6) * 86400;
            $late = (mt_rand() / mt_getrandmax()) > $reliability;
            $closed = $due + ($late ? mt_rand(1, 3) : -mt_rand(1, 2)) * 86400;
            $hours = mt_rand(2, 18);
            $tag = $tags[mt_rand(0, count($tags) - 1)];
            $issueId = demo_issue($db, [
                'status' => 3,
                'type_id' => $isBug ? 3 : 1,
                'name' => ($isBug ? 'Fix' : 'Build') . " {$tag} item {$taskNumber}",
                'description' => "Demo work item #{$taskNumber} with #{$tag}.",
                'parent_id' => $projectIds[mt_rand(0, count($projectIds) - 1)],
                'author_id' => $adminId,
                'owner_id' => $ownerId,
                'priority' => mt_rand(0, 4) === 0 ? 1 : 0,
                'hours_total' => $hours,
                'hours_remaining' => 0,
                'hours_spent' => round($hours * (0.8 + mt_rand(0, 40) / 100), 1),
                'created_date' => date('Y-m-d H:i:s', $created),
                'start_date' => date('Y-m-d', $start),
                'due_date' => date('Y-m-d', $due),
                'closed_date' => date('Y-m-d H:i:s', $closed),
                'sprint_id' => $sprintId,
                'version' => 1,
            ]);
            demo_tag($db, $issueId, $tag);
            demo_activate($db, $issueId, $ownerId, date('Y-m-d H:i:s', $start));
            $closedCount++;
        } else {
            $created = $now - mt_rand(2, 12) * 86400;
            $start = $now - mt_rand(0, 4) * 86400;
            $due = $now + mt_rand(1, 12) * 86400;
            $hours = mt_rand(2, 16);
            $tag = $tags[mt_rand(0, count($tags) - 1)];
            $status = $isCurrent ? (mt_rand(0, 1) ? 2 : 1) : 1;
            $owner = $isCurrent ? $ownerId : null;
            $issueId = demo_issue($db, [
                'status' => $status,
                'type_id' => $isBug ? 3 : 1,
                'name' => ($isBug ? 'Fix' : 'Build') . " {$tag} item {$taskNumber}",
                'description' => "Demo work item #{$taskNumber} with #{$tag}.",
                'parent_id' => $projectIds[mt_rand(0, count($projectIds) - 1)],
                'author_id' => $adminId,
                'owner_id' => $owner,
                'priority' => mt_rand(0, 3) === 0 ? 1 : 0,
                'hours_total' => $hours,
                'hours_remaining' => $hours,
                'hours_spent' => 0,
                'created_date' => date('Y-m-d H:i:s', $created),
                'start_date' => date('Y-m-d', $start),
                'due_date' => date('Y-m-d', $due),
                'sprint_id' => $sprintId,
                'version' => 1,
            ]);
            demo_tag($db, $issueId, $tag);
            if ($status === 2) {
                demo_activate($db, $issueId, (int) $owner, date('Y-m-d H:i:s', $start));
            }
            if ($isCurrent && $j === 1) {
                // One dependency inside the current sprint.
                $db->exec(
                    "INSERT INTO issue_dependency (issue_id, dependency_id, dependency_type) VALUES (?, ?, 'FS')",
                    [$issueId, $issueId - 1]
                );
            }
        }

        $taskNumber++;
    }
}

\Model\Config::setVal('demo.seeded', '1');

echo "Seeded " . count($userIds) . " team members, " . count($projectIds) . " projects, "
    . count($sprintIds) . " sprints, {$closedCount} closed tasks and " . ($taskNumber - $closedCount - 1)
    . " open tasks.\n";
echo "Demo login: demo_alice / demo1234\n";

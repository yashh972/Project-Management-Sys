<?php

/**
 * Reset a user's password from the command line.
 *
 *   php reset-password.php            list usernames
 *   php reset-password.php admin      prompts for a new password and saves it
 *
 * CLI only. Uses the same bcrypt hashing as the app (salt column = "bcrypt").
 */

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

$config = is_file(__DIR__ . '/config.php') ? require __DIR__ . '/config.php' : [];
if (($config['db.engine'] ?? 'sqlite') !== 'sqlite') {
    fwrite(STDERR, "This script only supports SQLite. Reset the password from /admin/users instead.\n");
    exit(1);
}

$name = $config['db.name'] ?? 'phproject.db';
$path = preg_match('~^([A-Za-z]:|/|\\\\)~', $name) ? $name : __DIR__ . '/' . $name;
if (!is_file($path)) {
    fwrite(STDERR, "Database not found: $path\n");
    exit(1);
}

$db = new PDO('sqlite:' . $path);
$db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

$username = $argv[1] ?? null;
if ($username === null) {
    echo "Users:\n";
    foreach ($db->query("SELECT username, role FROM user WHERE deleted_date IS NULL AND role != 'group' ORDER BY role, username") as $u) {
        echo "  {$u['username']} ({$u['role']})\n";
    }

    echo "\nUsage: php reset-password.php <username>\n";
    exit(0);
}

$st = $db->prepare('SELECT id FROM user WHERE username = ? AND deleted_date IS NULL');
$st->execute([$username]);
$id = $st->fetchColumn();
if (!$id) {
    fwrite(STDERR, "No active user named '$username'.\n");
    exit(1);
}

echo "New password for $username (at least 8 characters): ";
$password = trim((string) fgets(STDIN));
if (strlen($password) < 8) {
    fwrite(STDERR, "Too short, nothing changed.\n");
    exit(1);
}

$db->prepare("UPDATE user SET password = ?, salt = 'bcrypt', reset_token = NULL WHERE id = ?")
    ->execute([password_hash($password, PASSWORD_BCRYPT), $id]);

echo "Password updated for $username. You can log in now.\n";

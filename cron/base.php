<?php

/**
 * Cron job base initialization
 */

if (PHP_SAPI !== 'cli') {
    throw new Exception("Cron jobs must be run from the command line.");
}

$homedir = dirname(__FILE__, 2) . "/";
set_include_path($homedir);

require_once $homedir . "vendor/autoload.php";

$f3 = Base::instance();
$f3->mset([
    "UI" => $homedir . "app/view/",
    "LOGS" => $homedir . "log/",
    "AUTOLOAD" => $homedir . "app/;" . $homedir . "lib/vendor/",
    "TEMP" => $homedir . "tmp/",
    "TZ" => "UTC",
]);

// Load local configuration
$f3->mset(require_once(is_file(__DIR__ . '/config.php') ? __DIR__ . '/config.php' : $homedir . 'config.php'));

// Connect to database
if ($f3->get("db.engine") === "sqlite") {
    $dbName = (string) $f3->get("db.name");
    if (!preg_match('~^([A-Za-z]:|/|\\\\\\\\)~', $dbName)) {
        $dbName = $homedir . $dbName;
    }

    $f3->set("db.instance", new \Helper\SQL("sqlite:" . $dbName));
} else {
    $f3->set("db.instance", new \Helper\SQL(
        "mysql:host=" . $f3->get("db.host") . ";port=" . ($f3->get("db.port") ?: 3306) . ";dbname=" . $f3->get("db.name"),
        $f3->get("db.user"),
        $f3->get("db.pass")
    ));
}

// Load database-backed config
\Model\Config::loadAll();

// Notification templates expect an imap array even when mailboxes are disabled.
$f3->set('imap', [
    'hostname' => $f3->get('imap.hostname'),
    'username' => $f3->get('imap.username'),
    'password' => $f3->get('imap.password'),
    'truncate_lines' => $f3->get('imap.truncate_lines'),
]);
$f3->set('ml', [
    'url' => $f3->get('ml.url') ?: getenv('ML_URL') ?: 'http://127.0.0.1:8000',
    'token' => $f3->get('ml.token') ?: getenv('ML_INTERNAL_TOKEN') ?: '',
    'timeout' => $f3->get('ml.timeout') ?: '30',
]);
$f3->set('github', [
    'webhook_secret' => $f3->get('github.webhook_secret') ?: getenv('GITHUB_WEBHOOK_SECRET') ?: '',
    'auto_close' => $f3->get('github.auto_close') ?: '0',
]);

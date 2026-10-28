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

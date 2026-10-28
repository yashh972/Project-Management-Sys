<?php

/**
 * Apply pending database migrations from db/.
 *
 * Usage: php cron/migrate.php
 */

require_once __DIR__ . "/base.php";

$security = \Helper\Security::instance();
$applied = 0;

while (($version = $security->checkDatabaseVersion()) !== true) {
    echo "Applying {$version}...\n";
    $security->updateDatabase($version);
    $applied++;
    if ($applied > 50) {
        fwrite(STDERR, "Aborting: too many pending migrations.\n");
        exit(1);
    }
}

echo $applied === 0 ? "Database is already up to date.\n" : "Applied {$applied} migration(s).\n";

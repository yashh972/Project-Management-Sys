<?php

/**
 * Recompute ML insights and the assignment model through the ML service.
 *
 * Usage: php cron/refresh_ml.php
 */

require_once __DIR__ . "/base.php";

[$status, $data, $error] = \Helper\Ml::trainAnalytics(true);

if ($status >= 200 && $status < 300 && is_array($data) && !empty($data['ok'])) {
    echo "ML insights recomputed.\n";
    if (!empty($data['metrics'])) {
        echo json_encode($data['metrics'], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n";
    }
    exit(0);
}

fwrite(STDERR, "ML refresh failed: " . ($error ?: 'unknown error') . "\n");
exit(1);

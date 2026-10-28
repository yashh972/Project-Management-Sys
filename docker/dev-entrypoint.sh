#!/bin/sh
set -eu

# The dev/test image does not run the installer (which would overwrite data).
# Generate a config from the compose environment instead.
if [ ! -f /var/www/html/config.php ]; then
    cat > /var/www/html/config.php <<PHP
<?php
return [
    'db.engine' => 'mysql',
    'db.host' => getenv('DB_HOST') ?: 'db',
    'db.port' => getenv('DB_PORT') ?: '3306',
    'db.user' => getenv('DB_USER') ?: 'phproject',
    'db.pass' => getenv('DB_PASSWORD') ?: 'phproject',
    'db.name' => getenv('DB_NAME') ?: 'phproject',
    'site.url' => getenv('SITE_URL') ?: 'http://localhost:9090/',
];
PHP
fi

exec "$@"

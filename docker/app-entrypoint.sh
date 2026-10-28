#!/bin/sh
set -eu

CONFIG_STORAGE=/var/www/html/storage/config.php
mkdir -p /var/www/html/storage /var/www/html/tmp/cache /var/www/html/log /var/www/html/uploads

if [ ! -f "$CONFIG_STORAGE" ]; then
    if [ -f /var/www/html/config.php ] && [ ! -L /var/www/html/config.php ]; then
        # Preserve a config written by an older image before the storage volume existed.
        mv /var/www/html/config.php "$CONFIG_STORAGE"
    else
        echo "Waiting for the database..."
        i=0
        until php -r '
            try {
                new PDO(
                    "mysql:host=" . getenv("DB_HOST") . ";port=" . (getenv("DB_PORT") ?: "3306"),
                    getenv("DB_USER"),
                    getenv("DB_PASSWORD")
                );
                exit(0);
            } catch (Throwable $e) {
                exit(1);
            }
        '; do
            i=$((i + 1))
            if [ "$i" -ge 60 ]; then
                echo "Database did not become ready in time." >&2
                exit 1
            fi
            sleep 2
        done

        echo "Installing Agile CodeBoard..."
        php /var/www/html/install.php \
            --site-name="${SITE_NAME:-Agile CodeBoard}" \
            --site-url="${SITE_URL:-http://localhost:9090/}" \
            --timezone="${SITE_TIMEZONE:-UTC}" \
            --from-email="${MAIL_FROM:-noreply@example.com}" \
            --db-engine=mysql \
            --db-host="${DB_HOST:-db}" \
            --db-port="${DB_PORT:-3306}" \
            --db-user="${DB_USER:-phproject}" \
            --db-password="${DB_PASSWORD:-phproject}" \
            --db-name="${DB_NAME:-phproject}" \
            --admin-username="${ADMIN_USERNAME:-admin}" \
            --admin-email="${ADMIN_EMAIL:-admin@example.com}" \
            --admin-password="${ADMIN_PASSWORD:-admin}"

        mv /var/www/html/config.php "$CONFIG_STORAGE"
    fi
fi

ln -sf "$CONFIG_STORAGE" /var/www/html/config.php
chown -h 33:33 /var/www/html/config.php
chmod 755 /var/www/html
chown -R 33:33 /var/www/html/storage /var/www/html/tmp /var/www/html/log /var/www/html/uploads 2>/dev/null || true

exec "$@"

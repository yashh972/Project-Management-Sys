# syntax=docker/dockerfile:1

FROM composer:2 AS vendor
WORKDIR /app
COPY composer.json composer.lock ./
RUN composer install --no-dev --no-interaction --no-progress --prefer-dist --optimize-autoloader

FROM composer:2 AS vendor-dev
WORKDIR /app
COPY composer.json composer.lock ./
RUN composer install --no-interaction --no-progress --prefer-dist

FROM php:8.5.12-apache AS app

COPY --from=ghcr.io/mlocati/php-extension-installer /usr/bin/install-php-extensions /usr/local/bin/
RUN install-php-extensions exif gd zip pdo_mysql intl curl opcache
RUN a2enmod rewrite

COPY --chown=33:33 . /var/www/html/
COPY --from=vendor /app/vendor /var/www/html/vendor
COPY docker/app-entrypoint.sh /usr/local/bin/app-entrypoint
COPY docker/dev-entrypoint.sh /usr/local/bin/dev-entrypoint
RUN chmod +x /usr/local/bin/app-entrypoint /usr/local/bin/dev-entrypoint \
    && chmod 755 /var/www/html \
    && mkdir -p /var/www/html/storage \
    && chown 33:33 /var/www/html/storage \
    && printf 'upload_max_filesize = 1024M\npost_max_size = 1024M\n' > /usr/local/etc/php/conf.d/limits.ini \
    && mv "$PHP_INI_DIR/php.ini-production" "$PHP_INI_DIR/php.ini"

WORKDIR /var/www/html

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -fsS http://127.0.0.1/ >/dev/null || exit 1

ENTRYPOINT ["app-entrypoint"]
CMD ["apache2-foreground"]

FROM app AS dev
COPY --from=vendor-dev /app/vendor /var/www/html/vendor

<?php
// Dev-only router for `php -S`: serve real files directly, send everything else to index.php
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$file = __DIR__ . $path;
if ($path !== '/' && is_file($file) && pathinfo($file, PATHINFO_EXTENSION) !== 'php') {
    return false;
}
if ($path === '/install.php') {
    return false;
}
require __DIR__ . '/index.php';

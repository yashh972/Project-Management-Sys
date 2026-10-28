<?php

namespace Helper;

/**
 * Runs the Python ML scripts in ml/ (analytics job and smart-assignment model).
 */
class Ml
{
    /**
     * Path to the project's Python virtualenv interpreter, or null if it has not been set up.
     */
    public static function python(): ?string
    {
        $root = dirname(__DIR__, 2);
        foreach (["$root/ml/.venv/Scripts/python.exe", "$root/ml/.venv/bin/python"] as $candidate) {
            if (is_file($candidate)) {
                return $candidate;
            }
        }

        return null;
    }

    /**
     * Run ml/<script> with already-escaped arguments.
     *
     * @return array{0: int, 1: string[]} [exit code, output lines]
     */
    public static function run(string $script, string $args = '', int $timeout = 120): array
    {
        $python = self::python();
        if ($python === null || !function_exists('exec')) {
            return [127, ['ML environment not found. Create it with: python -m venv ml/.venv && ml/.venv/Scripts/pip install -r ml/requirements.txt']];
        }

        $output = [];
        $code = 1;
        @set_time_limit($timeout);
        exec(escapeshellarg($python) . ' ' . escapeshellarg(dirname(__DIR__, 2) . "/ml/$script") . ' ' . $args . ' 2>&1', $output, $code);

        return [$code, $output];
    }
}

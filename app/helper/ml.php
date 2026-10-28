<?php

namespace Helper;

/**
 * HTTP client for the Python ML service.
 *
 * The PHP application never shells out. All inference and training requests go
 * through the FastAPI sidecar, with a short timeout and an explicit fallback so
 * the core task board keeps working when the service is unavailable.
 */
class Ml
{
    /**
     * Resolve the service base URL.
     */
    public static function url(): string
    {
        $f3 = \Base::instance();
        $url = (string) $f3->get('ml.url');
        if ($url === '') {
            $url = (string) (getenv('ML_URL') ?: 'http://127.0.0.1:8000');
        }

        return rtrim($url, '/');
    }

    /**
     * Whether a service URL is configured.
     */
    public static function enabled(): bool
    {
        return self::url() !== '';
    }

    /**
     * Make a JSON request to the ML service.
     *
     * @return array{0:int,1:array|null,2:string|null} [status, data, error]
     */
    public static function request(string $method, string $path, ?array $payload = null, int $timeout = 10): array
    {
        $f3 = \Base::instance();
        $base = self::url();
        if ($base === '') {
            return [0, null, 'ML service is not configured'];
        }

        $headers = [
            'Content-Type: application/json',
            'Accept: application/json',
        ];
        $token = (string) $f3->get('ml.token');
        if ($token === '') {
            $token = (string) (getenv('ML_INTERNAL_TOKEN') ?: '');
        }
        if ($token !== '') {
            $headers[] = 'X-Internal-Token: ' . $token;
        }

        $options = [
            'method' => strtoupper($method),
            'header' => $headers,
            'timeout' => max(1, $timeout),
            'ignore_errors' => true,
        ];
        if ($payload !== null) {
            $options['content'] = json_encode($payload, JSON_THROW_ON_ERROR);
        }

        $result = \Web::instance()->request($base . $path, $options);
        if (!empty($result['error'])) {
            return [0, null, (string) $result['error']];
        }

        $status = self::parseStatus($result['headers'] ?? []);
        $body = (string) ($result['body'] ?? '');
        $decoded = json_decode($body, true);

        if ($status >= 200 && $status < 300) {
            if (!is_array($decoded)) {
                return [$status, null, 'Invalid JSON returned by the ML service'];
            }

            return [$status, $decoded, null];
        }

        $detail = is_array($decoded)
            ? ($decoded['detail'] ?? $decoded['error'] ?? null)
            : null;
        if (!is_string($detail) || $detail === '') {
            $detail = $body !== '' ? $body : 'ML request failed with HTTP ' . $status;
        }

        return [$status ?: 502, null, $detail];
    }

    /**
     * Extract the final HTTP status from F3's header list.
     *
     * @param array<int|string,mixed> $headers
     */
    protected static function parseStatus(array $headers): int
    {
        $status = 0;
        foreach ($headers as $line) {
            if (is_string($line) && preg_match('~^HTTP/\S+\s+(\d{3})~i', $line, $match)) {
                $status = (int) $match[1];
            }
        }

        return $status;
    }

    /**
     * @return array{0:int,1:array|null,2:string|null}
     */
    public static function predictRisk(int $issueId): array
    {
        return self::request('POST', '/v1/predict/risk', ['issue_id' => $issueId]);
    }

    /**
     * @return array{0:int,1:array|null,2:string|null}
     */
    public static function predictCycle(int $issueId): array
    {
        return self::request('POST', '/v1/predict/cycle', ['issue_id' => $issueId]);
    }

    /**
     * @return array{0:int,1:array|null,2:string|null}
     */
    public static function forecastSprint(int $sprintId, int $simulations = 5000): array
    {
        return self::request('POST', '/v1/forecast/sprint', [
            'sprint_id' => $sprintId,
            'simulations' => max(200, min(50000, $simulations)),
        ], 30);
    }

    /**
     * @param array<string,mixed> $payload
     * @return array{0:int,1:array|null,2:string|null}
     */
    public static function suggest(array $payload): array
    {
        return self::request('POST', '/v1/assign/suggest', $payload, 20);
    }

    /**
     * @param array<string,mixed> $payload
     * @return array{0:int,1:array|null,2:string|null}
     */
    public static function optimize(array $payload): array
    {
        return self::request('POST', '/v1/assign/optimize', $payload, 30);
    }

    /**
     * @return array{0:int,1:array|null,2:string|null}
     */
    public static function models(): array
    {
        return self::request('GET', '/v1/models', null, 10);
    }

    /**
     * @return array{0:int,1:array|null,2:string|null}
     */
    public static function refreshRisk(): array
    {
        return self::request('POST', '/v1/models/risk/refresh', null, 60);
    }

    /**
     * @return array{0:int,1:array|null,2:string|null}
     */
    public static function backtest(int $folds = 4, int $minTrain = 30): array
    {
        return self::request('POST', '/v1/models/risk/backtest', [
            'folds' => max(2, min(12, $folds)),
            'min_train' => max(10, $minTrain),
        ], 60);
    }

    /**
     * Run the legacy batch analytics/assignment scripts inside the ML service.
     *
     * @return array{0:int,1:array|null,2:string|null}
     */
    public static function trainAnalytics(bool $includeAssignment = true): array
    {
        return self::request('POST', '/v1/train/analytics', [
            'include_assignment' => $includeAssignment,
        ], 300);
    }

    /**
     * @return array{0:int,1:array|null,2:string|null}
     */
    public static function health(): array
    {
        return self::request('GET', '/healthz', null, 3);
    }
}

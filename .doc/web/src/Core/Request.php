<?php
declare(strict_types=1);

namespace Seharnes\Panel\Core;

/**
 * Неизменяемый снимок HTTP-запроса.
 *
 * Контроллеры не читают суперглобальные массивы напрямую: единственный источник
 * правды — этот объект, поэтому любой запрос можно собрать в тесте.
 */
final class Request
{
    /**
     * @param array<string, string> $query
     * @param array<string, mixed>  $body
     * @param array<string, string> $cookies
     * @param array<string, string> $headers
     */
    private function __construct(
        private readonly string $method,
        private readonly string $path,
        private readonly array $query,
        private readonly array $body,
        private readonly array $cookies,
        private readonly array $headers,
    ) {
    }

    public static function capture(): self
    {
        $method = strtoupper((string) ($_SERVER['REQUEST_METHOD'] ?? 'GET'));
        $path = (string) parse_url((string) ($_SERVER['REQUEST_URI'] ?? '/'), PHP_URL_PATH);
        $headers = self::captureHeaders();
        $body = [];
        if (in_array($method, ['POST', 'PUT', 'PATCH', 'DELETE'], true)) {
            $raw = (string) file_get_contents('php://input');
            $decoded = $raw === '' ? null : json_decode($raw, true);
            $body = is_array($decoded) ? $decoded : [];
        }
        $query = [];
        foreach ($_GET as $key => $value) {
            $query[(string) $key] = is_scalar($value) ? (string) $value : '';
        }
        $cookies = [];
        foreach ($_COOKIE as $key => $value) {
            $cookies[(string) $key] = is_scalar($value) ? (string) $value : '';
        }
        return new self($method, $path === '' ? '/' : $path, $query, $body, $cookies, $headers);
    }

    /**
     * @param array<string, string> $query
     * @param array<string, mixed>  $body
     * @param array<string, string> $cookies
     * @param array<string, string> $headers
     */
    public static function create(string $method, string $path, array $query = [], array $body = [], array $cookies = [], array $headers = []): self
    {
        return new self(strtoupper($method), $path, $query, $body, $cookies, $headers);
    }

    public function method(): string
    {
        return $this->method;
    }

    public function path(): string
    {
        return $this->path;
    }

    public function isPost(): bool
    {
        return $this->method === 'POST';
    }

    public function query(string $key, ?string $default = null): ?string
    {
        return $this->query[$key] ?? $default;
    }

    /** @return array<string, string> */
    public function allQuery(): array
    {
        return $this->query;
    }

    public function input(string $key, mixed $default = null): mixed
    {
        return $this->body[$key] ?? $default;
    }

    public function cookie(string $key, ?string $default = null): ?string
    {
        return $this->cookies[$key] ?? $default;
    }

    public function header(string $name): ?string
    {
        return $this->headers[strtolower($name)] ?? null;
    }

    /** XHR/fetch-запрос из панели: нужен для изменяющих вызовов и CSRF-фильтра. */
    public function isAjax(): bool
    {
        return strtoupper((string) $this->header('x-requested-with')) === 'XMLHTTPREQUEST';
    }

    public function wantsJson(): bool
    {
        $accept = (string) $this->header('accept');
        return $this->isAjax() || str_contains($accept, 'application/json');
    }

    public function host(): string
    {
        $host = (string) $this->header('host');
        return $host !== '' ? (string) parse_url('http://' . $host, PHP_URL_HOST) : '';
    }

    public function origin(): string
    {
        $origin = (string) $this->header('origin');
        return $origin !== '' ? (string) parse_url($origin, PHP_URL_HOST) : '';
    }

    /** @return array<string, string> */
    private static function captureHeaders(): array
    {
        $headers = [];
        foreach ($_SERVER as $key => $value) {
            if (!is_string($value)) {
                continue;
            }
            if (str_starts_with($key, 'HTTP_')) {
                $name = strtolower(str_replace('_', '-', substr($key, 5)));
                $headers[$name] = $value;
            } elseif (in_array($key, ['CONTENT_TYPE', 'CONTENT_LENGTH'], true)) {
                $headers[strtolower(str_replace('_', '-', $key))] = $value;
            }
        }
        return $headers;
    }
}

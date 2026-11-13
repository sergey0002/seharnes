<?php
declare(strict_types=1);

namespace Seharnes\Panel\Core;

/**
 * Неизменяемый HTTP-ответ. Контроллер возвращает Response, отправляет его фронт-контроллер.
 */
final class Response
{
    /** @param array<string, string> $headers */
    private function __construct(
        private readonly int $status,
        private readonly string $body,
        private readonly array $headers,
    ) {
    }

    /** @param array<string, mixed> $payload */
    public static function json(array $payload, int $status = 200): self
    {
        return new self($status, self::encode($payload), [
            'Content-Type' => 'application/json; charset=utf-8',
            'Cache-Control' => 'no-store',
            'X-Content-Type-Options' => 'nosniff',
        ]);
    }

    public static function html(string $html, int $status = 200): self
    {
        return new self($status, $html, [
            'Content-Type' => 'text/html; charset=utf-8',
            'Cache-Control' => 'no-store',
            'X-Content-Type-Options' => 'nosniff',
        ]);
    }

    public static function text(string $text, int $status = 200, string $type = 'text/plain; charset=utf-8'): self
    {
        return new self($status, $text, [
            'Content-Type' => $type,
            'Cache-Control' => 'no-store',
            'X-Content-Type-Options' => 'nosniff',
        ]);
    }

    public static function redirect(string $location, int $status = 302): self
    {
        return new self($status, '', ['Location' => $location, 'Cache-Control' => 'no-store']);
    }

    public static function notFound(string $message = 'not found'): self
    {
        return self::json(['status' => 'failed', 'error' => $message], 404);
    }

    public static function forbidden(string $message = 'forbidden'): self
    {
        return self::json(['status' => 'failed', 'error' => $message], 403);
    }

    public function status(): int
    {
        return $this->status;
    }

    public function body(): string
    {
        return $this->body;
    }

    /** @return array<string, string> */
    public function headers(): array
    {
        return $this->headers;
    }

    public function header(string $name): ?string
    {
        foreach ($this->headers as $key => $value) {
            if (strcasecmp($key, $name) === 0) {
                return $value;
            }
        }
        return null;
    }

    public function send(): void
    {
        if (!headers_sent()) {
            http_response_code($this->status);
            foreach ($this->headers as $name => $value) {
                header($name . ': ' . $value, true);
            }
        }
        echo $this->body;
    }

    /** @param array<string, mixed> $payload */
    private static function encode(array $payload): string
    {
        return (string) json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    }
}

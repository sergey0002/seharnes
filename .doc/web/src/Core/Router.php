<?php
declare(strict_types=1);

namespace Seharnes\Panel\Core;

/**
 * Роутер нового каркаса панели.
 *
 * Маршрут = метод + шаблон вида /panel/docs/{id} + обработчик.
 * Шаблон компилируется в регулярное выражение один раз, параметры приходят массивом.
 */
final class Router
{
    /** @var list<array{method: string, regex: string, handler: callable}> */
    private array $routes = [];
    /** @var null|callable(Request): Response */
    private $fallback = null;

    public function get(string $pattern, callable $handler): void
    {
        $this->add('GET', $pattern, $handler);
    }

    public function post(string $pattern, callable $handler): void
    {
        $this->add('POST', $pattern, $handler);
    }

    /** @param callable(Request): Response $fallback */
    public function fallback(callable $fallback): void
    {
        $this->fallback = $fallback;
    }

    public function add(string $method, string $pattern, callable $handler): void
    {
        $this->routes[] = [
            'method' => strtoupper($method),
            'regex' => $this->compile($pattern),
            'handler' => $handler,
        ];
    }

    /** @param array<string, string> $params */
    public function dispatch(Request $request, array $params = []): Response
    {
        $path = $request->path();
        foreach ($this->routes as $route) {
            if ($route['method'] !== $request->method()) {
                continue;
            }
            if (preg_match($route['regex'], $path, $matches) !== 1) {
                continue;
            }
            $arguments = $params;
            foreach ($matches as $key => $value) {
                if (is_string($key) && $value !== '') {
                    $arguments[$key] = rawurldecode($value);
                }
            }
            $response = ($route['handler'])($request, $arguments);
            return $response instanceof Response
                ? $response
                : Response::json(['status' => 'failed', 'error' => 'handler returned ' . get_debug_type($response)], 500);
        }
        if ($this->fallback !== null) {
            return ($this->fallback)($request);
        }
        return Response::notFound('route not found: ' . $path);
    }

    /**
     * Шаблон маршрута: {name} — сегмент без слэшей, {name:regex} — свой шаблон.
     * Пример: /panel/docs/{id:.+} ловит вложенные идентификаторы документов.
     */
    private function compile(string $pattern): string
    {
        $quoted = preg_replace_callback(
            '/\{([a-zA-Z_][a-zA-Z0-9_]*)(?::([^}]+))?\}/',
            static fn (array $m): string => '(?P<' . $m[1] . '>' . (isset($m[2]) && $m[2] !== '' ? $m[2] : '[^/]+') . ')',
            $pattern,
        );
        return '~^' . rtrim((string) $quoted, '/') . '/?$~';
    }
}

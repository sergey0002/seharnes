<?php
declare(strict_types=1);

use Seharnes\Panel\Core\Container;
use Seharnes\Panel\Core\Request;
use Seharnes\Panel\Core\Response;
use Seharnes\Panel\Core\Router;
use Seharnes\Panel\Http\OriginGuard;
use Seharnes\Panel\Support\PathGuard;

return [
    'container builds lazily and caches' => static function (): void {
        $container = new Container();
        $calls = 0;
        $container->set('service', static function () use (&$calls): object {
            $calls++;
            return new stdClass();
        });
        $first = $container->get('service');
        $second = $container->get('service');
        Assert::same(1, $calls);
        Assert::true($first === $second);
    },

    'container can be replaced for tests' => static function (): void {
        $container = new Container();
        $container->set('service', static fn (): string => 'real');
        $container->replace('service', 'fake');
        Assert::same('fake', $container->get('service'));
    },

    'router matches static and dynamic routes' => static function (): void {
        $router = new Router();
        $router->get('/panel/docs', static fn (): Response => Response::text('list'));
        $router->get('/panel/docs/{id:.+}', static fn (Request $r, array $p): Response => Response::text('doc:' . $p['id']));
        $router->fallback(static fn (): Response => Response::notFound('nope'));

        Assert::same('list', $router->dispatch(Request::create('GET', '/panel/docs'))->body());
        Assert::same('doc:harnes/state/01', $router->dispatch(Request::create('GET', '/panel/docs/harnes/state/01'))->body());
        Assert::same(404, $router->dispatch(Request::create('GET', '/panel/other'))->status());
    },

    'router respects http method' => static function (): void {
        $router = new Router();
        $router->post('/panel/api/jobs', static fn (): Response => Response::text('posted'));
        $router->fallback(static fn (): Response => Response::notFound());
        Assert::same(404, $router->dispatch(Request::create('GET', '/panel/api/jobs'))->status());
        Assert::same('posted', $router->dispatch(Request::create('POST', '/panel/api/jobs'))->body());
    },

    'response json encodes without escaping unicode' => static function (): void {
        $response = Response::json(['status' => 'ok', 'value' => 'граф']);
        Assert::contains('граф', $response->body());
        Assert::same('application/json; charset=utf-8', $response->header('content-type'));
    },

    'origin guard requires same origin and xhr header' => static function (): void {
        $guard = new OriginGuard();
        $sameOrigin = Request::create('POST', '/panel/api/jobs', [], [], [], [
            'host' => 'localhost:8077', 'origin' => 'http://localhost:8077', 'x-requested-with' => 'XMLHttpRequest',
        ]);
        $crossOrigin = Request::create('POST', '/panel/api/jobs', [], [], [], [
            'host' => 'localhost:8077', 'origin' => 'https://evil.example', 'x-requested-with' => 'XMLHttpRequest',
        ]);
        $noHeader = Request::create('POST', '/panel/api/jobs', [], [], [], ['host' => 'localhost:8077']);
        $get = Request::create('GET', '/panel/api/jobs', [], [], [], ['host' => 'localhost:8077']);

        Assert::true($guard->allows($sameOrigin), 'same origin must pass');
        Assert::false($guard->allows($crossOrigin), 'cross origin must fail');
        Assert::false($guard->allows($noHeader), 'missing X-Requested-With must fail');
        Assert::true($guard->allows($get), 'GET must pass');
    },

    'path guard keeps ids inside the tree' => static function (): void {
        Assert::true(PathGuard::safeId('harnes/state/01-canon'));
        Assert::true(PathGuard::safeId('harnes/plan/субагенты'));
        Assert::false(PathGuard::safeId('../secrets'));
        Assert::false(PathGuard::safeId('harnes/../../etc/passwd'));
        Assert::false(PathGuard::safeId('/etc/passwd'));
        Assert::false(PathGuard::safeId(''));
    },

    'path guard resolves files only inside base' => static function (): void {
        withTempDir(static function (string $dir): void {
            writeFile($dir . '/inside.txt', 'ok');
            writeFile(dirname($dir) . '/outside-panel-test.txt', 'no');

            $inside = PathGuard::fileWithin($dir, 'inside.txt');
            Assert::notNull($inside);
            Assert::false(PathGuard::fileWithin($dir, '../outside-panel-test.txt') !== null, 'escape must fail');
            @unlink(dirname($dir) . '/outside-panel-test.txt');
        });
    },
];

<?php
declare(strict_types=1);

namespace Seharnes\Panel;

use Seharnes\Panel\Core\Config;
use Seharnes\Panel\Core\Container;
use Seharnes\Panel\Core\Request;
use Seharnes\Panel\Core\Response;
use Seharnes\Panel\Core\Router;
use Seharnes\Panel\Core\View;
use Seharnes\Panel\Domain\Doc\DocRepository;
use Seharnes\Panel\Domain\Graph\GraphRepository;
use Seharnes\Panel\Domain\Graph\NodeWriter;
use Seharnes\Panel\Domain\Harness\HarnessAudit;
use Seharnes\Panel\Domain\Harness\HarnessStatus;
use Seharnes\Panel\Domain\Job\JobRepository;
use Seharnes\Panel\Domain\Job\JobStarter;
use Seharnes\Panel\Domain\Tasks\TasksRepository;
use Seharnes\Panel\Http\Controller\AnalyticsController;
use Seharnes\Panel\Http\Controller\ApiController;
use Seharnes\Panel\Http\Controller\DocsController;
use Seharnes\Panel\Http\Controller\GraphController;
use Seharnes\Panel\Http\Controller\HarnessController;
use Seharnes\Panel\Http\Controller\TasksController;
use Seharnes\Panel\Http\OriginGuard;
use Seharnes\Panel\Support\I18n;
use Throwable;

/**
 * Точка сборки нового каркаса панели.
 *
 * Здесь и только здесь создаются зависимости, регистрируются маршруты и решается,
 * какой контроллер отвечает. Всё остальное получает зависимости через конструктор.
 */
final class App
{
    public const BASE = '/panel';

    private function __construct(
        private readonly Container $container,
        private readonly Router $router,
        private readonly Config $config,
    ) {
    }

    public static function boot(string $webDir): self
    {
        $config = Config::fromWebDir($webDir);
        $container = new Container();

        $container->set('config', static fn (): Config => $config);
        $container->set('view', static function (Container $c): View {
            $view = new View($c->get('config')->webDir() . '/src/View');
            $view->addShared([
                'config' => $c->get('config'),
                'i18n' => $c->get('i18n'),
                'lang' => $c->get('i18n')->lang(),
                'base' => self::BASE,
            ]);
            return $view;
        });
        $container->set('i18n', static fn (Container $c): I18n => new I18n(
            $c->get('config')->langDir(),
            I18n::negotiate(Request::capture()),
        ));
        $container->set('docs', static fn (Container $c): DocRepository => new DocRepository($c->get('config')->docDir()));
        $container->set('graph', static fn (Container $c): GraphRepository => new GraphRepository(
            $c->get('config')->dataDir(),
            $c->get('config')->rootDir(),
        ));
        $container->set('graphWriter', static fn (Container $c): NodeWriter => new NodeWriter(
            $c->get('config'),
            $c->get('graph'),
        ));
        $container->set('harnessStatus', static fn (Container $c): HarnessStatus => new HarnessStatus($c->get('config')->rootDir()));
        $container->set('harnessAudit', static fn (Container $c): HarnessAudit => new HarnessAudit($c->get('config')->rootDir()));
        $container->set('tasks', static fn (): TasksRepository => new TasksRepository());
        $container->set('jobs', static fn (Container $c): JobRepository => new JobRepository($c->get('config')->stateDir()));
        $container->set('jobStarter', static fn (Container $c): JobStarter => new JobStarter($c->get('config')));
        $container->set('guard', static fn (): OriginGuard => new OriginGuard());

        $container->set('controller.docs', static fn (Container $c): DocsController => new DocsController(
            $c->get('view'),
            $c->get('config'),
            $c->get('docs'),
            $c->get('i18n'),
        ));
        $container->set('controller.graph', static fn (Container $c): GraphController => new GraphController(
            $c->get('view'),
            $c->get('graph'),
            $c->get('i18n'),
            $c->get('graphWriter'),
            $c->get('guard'),
        ));
        $container->set('controller.harness', static fn (Container $c): HarnessController => new HarnessController(
            $c->get('view'),
            $c->get('i18n'),
            $c->get('harnessStatus'),
            $c->get('harnessAudit'),
            $c->get('jobs'),
        ));
        $container->set('controller.tasks', static fn (Container $c): TasksController => new TasksController(
            $c->get('view'),
            $c->get('i18n'),
            $c->get('tasks'),
        ));
        $container->set('controller.analytics', static fn (Container $c): AnalyticsController => new AnalyticsController(
            $c->get('view'),
            $c->get('i18n'),
            $c->get('tasks'),
        ));
        $container->set('controller.api', static fn (Container $c): ApiController => new ApiController(
            $c->get('config'),
            $c->get('jobs'),
            $c->get('jobStarter'),
            $c->get('i18n'),
            $c->get('guard'),
        ));

        $router = new Router();
        $app = new self($container, $router, $config);
        $app->routes();
        return $app;
    }

    public function handle(Request $request): Response
    {
        try {
            return $this->router->dispatch($request);
        } catch (Throwable $error) {
            $payload = ['status' => 'failed', 'error' => 'internal error'];
            if (getenv('PANEL_DEBUG') === '1') {
                $payload['detail'] = $error->getMessage();
                $payload['trace'] = $error->getTraceAsString();
            }
            return Response::json($payload, 500);
        }
    }

    public function container(): Container
    {
        return $this->container;
    }

    public function config(): Config
    {
        return $this->config;
    }

    private function routes(): void
    {
        $base = self::BASE;

        $this->router->get($base, fn (Request $r): Response => Response::redirect($base . '/graph'));
        $this->router->get($base . '/graph', fn (Request $r, array $p): Response => $this->container->get('controller.graph')->page($r, $p));
        $this->router->get($base . '/docs', fn (Request $r, array $p): Response => $this->container->get('controller.docs')->page($r, $p));
        $this->router->get($base . '/docs/{id:.+}', fn (Request $r, array $p): Response => $this->container->get('controller.docs')->page($r, $p));
        $this->router->get($base . '/tasks', fn (Request $r, array $p): Response => $this->container->get('controller.tasks')->page($r, $p));
        $this->router->get($base . '/analytics', fn (Request $r, array $p): Response => $this->container->get('controller.analytics')->page($r, $p));
        $this->router->get($base . '/harness', fn (Request $r, array $p): Response => $this->container->get('controller.harness')->page($r, $p));

        $this->router->get($base . '/api/health', fn (): Response => $this->container->get('controller.api')->health());
        $this->router->get($base . '/api/actions', fn (): Response => $this->container->get('controller.api')->actions());
        $this->router->get($base . '/api/i18n', fn (Request $r): Response => $this->container->get('controller.api')->dictionary($r));

        $this->router->get($base . '/api/docs', fn (Request $r): Response => $this->container->get('controller.docs')->list($r));
        $this->router->get($base . '/api/docs/item', fn (Request $r): Response => $this->container->get('controller.docs')->item($r));

        $this->router->get($base . '/api/tasks', fn (Request $r): Response => $this->container->get('controller.tasks')->list($r));
        $this->router->get($base . '/api/tasks/item', fn (Request $r): Response => $this->container->get('controller.tasks')->item($r));
        $this->router->get($base . '/api/analytics', fn (Request $r): Response => $this->container->get('controller.analytics')->data($r));

        $this->router->get($base . '/api/harness/status', fn (): Response => $this->container->get('controller.harness')->status());
        $this->router->get($base . '/api/harness/audit', fn (Request $r): Response => $this->container->get('controller.harness')->audit($r));

        $this->router->get($base . '/api/graph/summary', fn (): Response => $this->container->get('controller.graph')->summary());
        $this->router->get($base . '/api/graph/view', fn (Request $r): Response => $this->container->get('controller.graph')->view($r));
        $this->router->get($base . '/api/graph/node', fn (Request $r): Response => $this->container->get('controller.graph')->node($r));
        $this->router->post($base . '/api/graph/node', fn (Request $r): Response => $this->container->get('controller.graph')->save($r));

        $this->router->get($base . '/api/jobs', fn (): Response => $this->container->get('controller.api')->jobs());
        $this->router->get($base . '/api/jobs/status', fn (Request $r): Response => $this->container->get('controller.api')->jobStatus($r));
        $this->router->post($base . '/api/jobs', fn (Request $r): Response => $this->container->get('controller.api')->run($r));

        $this->router->fallback(static fn (Request $r): Response => Response::json([
            'status' => 'failed',
            'error' => 'route not found: ' . $r->path(),
        ], 404));
    }
}

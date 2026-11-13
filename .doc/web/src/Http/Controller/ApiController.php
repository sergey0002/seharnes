<?php
declare(strict_types=1);

namespace Seharnes\Panel\Http\Controller;

use Seharnes\Panel\Core\Config;
use Seharnes\Panel\Core\Request;
use Seharnes\Panel\Core\Response;
use Seharnes\Panel\Domain\Job\JobRepository;
use Seharnes\Panel\Domain\Job\JobStarter;
use Seharnes\Panel\Http\OriginGuard;
use Seharnes\Panel\Support\I18n;

/**
 * Служебный API нового каркаса: здоровье сервиса, реестр действий, задания, словари.
 *
 * Отдельный контроллер, потому что это не данные раздела, а общая инфраструктура дока.
 */
final class ApiController
{
    public function __construct(
        private readonly Config $config,
        private readonly JobRepository $jobs,
        private readonly JobStarter $starter,
        private readonly I18n $i18n,
        private readonly OriginGuard $guard,
    ) {
    }

    public function health(): Response
    {
        return Response::json([
            'status' => 'ok',
            'service' => [
                'profile' => $this->config->profile(),
                'writable' => $this->config->isWritable(),
                'lang' => $this->i18n->lang(),
                'php' => PHP_VERSION,
            ],
            'data' => ['graph' => is_dir($this->config->dataDir())],
        ]);
    }

    public function actions(): Response
    {
        $actions = [];
        foreach ($this->config->actions() as $action) {
            if (empty($action['enabled'])) {
                continue;
            }
            $actions[] = [
                'id' => (string) ($action['id'] ?? ''),
                'label' => (string) ($action['label'] ?? ''),
                'group' => (string) ($action['group'] ?? ''),
                'confirm' => (bool) ($action['confirm'] ?? false),
                'timeout' => (int) ($action['timeout'] ?? 0),
            ];
        }
        return Response::json(['status' => 'ok', 'data' => $actions]);
    }

    public function jobs(): Response
    {
        return Response::json(['status' => 'ok', 'data' => $this->jobs->recent(20)]);
    }

    public function jobStatus(Request $request): Response
    {
        $id = (string) $request->query('id', '');
        $status = $this->jobs->status($id);
        return $status === null
            ? Response::notFound('job not found')
            : Response::json(['status' => 'ok', 'data' => $status]);
    }

    public function run(Request $request): Response
    {
        if (!$this->guard->allows($request)) {
            return Response::forbidden('origin not allowed');
        }
        $actionId = (string) $request->input('action', '');
        $params = $request->input('params', []);
        if ($actionId === '') {
            return Response::json(['status' => 'failed', 'error' => 'action is required'], 400);
        }
        $result = $this->starter->start($actionId, is_array($params) ? $params : []);
        $code = ($result['status'] ?? '') === 'failed' ? 400 : 202;
        if (isset($result['error']) && in_array($result['error'], ['origin not allowed', 'action unavailable for profile'], true)) {
            $code = 403;
        }
        return Response::json($result, $code);
    }

    public function dictionary(Request $request): Response
    {
        $lang = (string) $request->query('lang', $this->i18n->lang());
        $i18n = new I18n($this->config->langDir(), in_array($lang, $this->i18n->available(), true) ? $lang : $this->i18n->lang());
        return Response::json([
            'status' => 'ok',
            'data' => [
                'lang' => $i18n->lang(),
                'available' => $i18n->available(),
                'dictionary' => $i18n->dictionary(),
            ],
        ]);
    }
}

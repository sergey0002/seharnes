<?php
declare(strict_types=1);

namespace Seharnes\Panel\Http\Controller;

use Seharnes\Panel\Core\Request;
use Seharnes\Panel\Core\Response;
use Seharnes\Panel\Core\View;
use Seharnes\Panel\Domain\Graph\GraphRepository;
use Seharnes\Panel\Domain\Graph\NodeWriter;
use Seharnes\Panel\Http\OriginGuard;
use Seharnes\Panel\Support\I18n;

/**
 * Раздел «Граф харнеса»: левая панель (дерево/фильтры), центр (канвас),
 * правая панель (карточка выбранного элемента из API), нижний док (действия и лог).
 */
final class GraphController
{
    public function __construct(
        private readonly View $view,
        private readonly GraphRepository $graph,
        private readonly I18n $i18n,
        private readonly NodeWriter $writer,
        private readonly OriginGuard $guard,
    ) {
    }

    /** @param array<string, string> $params */
    public function page(Request $request, array $params): Response
    {
        $summary = $this->graph->summary();
        $html = $this->view->render('pages/graph', [
            'section' => 'graph',
            'title' => $this->i18n->t('nav.graph'),
            'toolbar' => $this->view->renderFile('partials/graph-toolbar', [
                'summary' => $summary,
            ]),
            'sidebar' => $this->view->renderFile('partials/graph-sidebar', [
                'summary' => $summary,
                'kinds' => $summary['kinds'],
            ]),
            'contentHtml' => $this->view->renderFile('partials/graph-canvas', ['summary' => $summary]),
            'right' => $this->view->renderFile('partials/graph-node-right', ['detail' => null]),
            'rightApiTitle' => $this->i18n->t('graph.apiTitle'),
            'rightApiHint' => $this->i18n->t('graph.apiHint'),
            'rightApiHtml' => $this->view->renderFile('partials/graph-api', []),
            'boot' => [
                'section' => 'graph',
                'selected' => null,
                'summary' => $summary,
            ],
        ], 'app');
        return Response::html($html);
    }

    public function summary(): Response
    {
        return Response::json(['status' => 'ok', 'data' => $this->graph->summary()]);
    }

    public function view(Request $request): Response
    {
        $kind = $request->query('kind', '');
        $linkedOnly = $request->query('linked', '') === '1';
        return Response::json([
            'status' => 'ok',
            'data' => $this->graph->view($kind !== '' ? $kind : null, $linkedOnly),
        ]);
    }

    public function node(Request $request): Response
    {
        $id = (string) $request->query('id', '');
        if ($id === '') {
            return Response::json(['status' => 'failed', 'error' => 'id is required'], 400);
        }
        $detail = $this->graph->detail($id);
        if (($detail['status'] ?? '') === 'failed') {
            return Response::json(['status' => 'failed', 'error' => (string) ($detail['error'] ?? 'not found')], 404);
        }
        return Response::json([
            'status' => 'ok',
            'html' => ['right' => $this->view->renderFile('partials/graph-node-right', ['detail' => $detail])],
            'data' => $detail,
        ]);
    }

    /**
     * Сохранение канонического файла узла.
     *
     * Тот же контракт, что у старых изменяющих запросов: Origin совпадает с хостом
     * и обязателен заголовок X-Requested-With — иначе 403, как у /jobs.
     */
    public function save(Request $request): Response
    {
        if (!$this->guard->allows($request)) {
            return Response::json(['status' => 'failed', 'error' => 'origin not allowed'], 403);
        }
        $id = (string) $request->input('id', '');
        $content = $request->input('content', null);
        if ($id === '' || !is_string($content)) {
            return Response::json(['status' => 'failed', 'error' => 'id and content are required'], 400);
        }
        $result = $this->writer->save($id, $content);
        if ($result['status'] !== 'ok') {
            $error = (string) ($result['error'] ?? 'save failed');
            $code = match (true) {
                $error === 'origin not allowed' => 403,
                str_starts_with($error, 'not editable'), $error === 'write disabled' => 403,
                $error === 'node not found' => 404,
                $error === 'file too large' => 413,
                $error === 'busy' => 409,
                default => 400,
            };
            return Response::json(['status' => 'failed', 'error' => $error], $code);
        }
        $detail = $this->graph->detail($id);
        return Response::json([
            'status' => 'ok',
            'message' => 'saved',
            'html' => ['right' => $this->view->renderFile('partials/graph-node-right', ['detail' => $detail])],
            'data' => [
                'id' => $id,
                'stats' => $result['stats'] ?? null,
                'detail' => $detail,
            ],
        ]);
    }
}

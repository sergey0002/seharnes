<?php
declare(strict_types=1);

namespace Seharnes\Panel\Http\Controller;

use Seharnes\Panel\Core\Config;
use Seharnes\Panel\Core\Request;
use Seharnes\Panel\Core\Response;
use Seharnes\Panel\Core\View;
use Seharnes\Panel\Domain\Doc\DocRepository;
use Seharnes\Panel\Support\I18n;

/**
 * Страницы раздела «Документация».
 *
 * Сервер отдаёт готовую страницу (первый экран без ожидания JS), а переходы внутри
 * раздела идут через фрагменты API — поэтому переключение документа не перезагружает страницу.
 */
final class DocsController
{
    public function __construct(
        private readonly View $view,
        private readonly Config $config,
        private readonly DocRepository $docs,
        private readonly I18n $i18n,
    ) {
    }

    /** @param array<string, string> $params */
    public function page(Request $request, array $params): Response
    {
        $selectedId = (string) ($params['id'] ?? $request->query('doc', ''));
        $query = (string) $request->query('q', '');
        $source = (string) $request->query('source', '');
        $selected = $selectedId !== '' ? $this->docs->find($selectedId) : null;

        $html = $this->view->render('pages/docs', [
            'section' => 'docs',
            'title' => $this->i18n->t('nav.docs'),
            'toolbar' => $this->view->renderFile('partials/docs-toolbar', [
                'query' => $query,
                'source' => $source,
                'sources' => $this->docs->sources(),
                'total' => count($this->docs->filter($query, $source)),
            ]),
            'sidebar' => $this->sidebar($query, $source, $selected?->id),
            'contentHtml' => $this->contentHtml($selected),
            'right' => $this->rightHtml($selected),
            // Правая нижняя панель показывает ту же нагрузку, что отдаёт API при клике.
            'rightApi' => $selected === null ? [] : ['status' => 'ok', 'data' => $selected->toArray()],
            'rightApiHint' => $selected === null ? '' : 'GET /panel/api/docs/item · ' . $selected->id,
            'boot' => [
                'section' => 'docs',
                'selected' => $selected?->id,
                'query' => $query,
                'source' => $source,
                'counts' => ['total' => count($this->docs->all())],
            ],
        ], 'app');

        return Response::html($html);
    }

    public function list(Request $request): Response
    {
        $query = (string) $request->query('q', '');
        $source = (string) $request->query('source', '');
        return Response::json([
            'status' => 'ok',
            'html' => ['sidebar' => $this->sidebar($query, $source, null)],
            'data' => ['total' => count($this->docs->filter($query, $source))],
        ]);
    }

    public function item(Request $request): Response
    {
        $id = (string) $request->query('id', '');
        $doc = $this->docs->find($id);
        if ($doc === null) {
            return Response::notFound('document not found');
        }
        return Response::json([
            'status' => 'ok',
            'html' => [
                'content' => $this->contentHtml($doc),
                'right' => $this->rightHtml($doc),
            ],
            'data' => ['id' => $doc->id] + $doc->toArray(),
        ]);
    }

    private function sidebar(string $query, string $source, ?string $selectedId): string
    {
        return $this->view->renderFile('partials/docs-sidebar', [
            'groups' => $this->docs->grouped($query, $source),
            'selected' => $selectedId,
            'total' => count($this->docs->filter($query, $source)),
        ]);
    }

    private function contentHtml(?\Seharnes\Panel\Domain\Doc\DocItem $doc): string
    {
        return $this->view->renderFile('partials/docs-content', ['doc' => $doc]);
    }

    private function rightHtml(?\Seharnes\Panel\Domain\Doc\DocItem $doc): string
    {
        return $this->view->renderFile('partials/docs-right', ['doc' => $doc]);
    }
}

<?php
declare(strict_types=1);

namespace Seharnes\Panel\Http\Controller;

use Seharnes\Panel\Core\Request;
use Seharnes\Panel\Core\Response;
use Seharnes\Panel\Core\View;
use Seharnes\Panel\Domain\Tasks\TasksRepository;
use Seharnes\Panel\Support\I18n;

/**
 * Раздел «Аналитика».
 *
 * Раньше аналитика была вкладкой внутри «Задач» старой панели. Теперь это отдельный
 * раздел нового каркаса: те же цифры (сессии, токены, стоимость, разрезы по моделям,
 * инструментам, MCP и ролям) и тот же срез фильтров, что у «Задач».
 */
final class AnalyticsController
{
    public function __construct(
        private readonly View $view,
        private readonly I18n $i18n,
        private readonly TasksRepository $tasks,
    ) {
    }

    /** @param array<string, string> $params */
    public function page(Request $request, array $params): Response
    {
        $filters = $this->filters($request);
        $data = $this->tasks->analytics($filters);

        $html = $this->view->render('pages/analytics', [
            'section' => 'analytics',
            'title' => $this->i18n->t('nav.analytics'),
            'toolbar' => $this->view->renderFile('partials/analytics-toolbar', [
                'filters' => $data['filters'],
                'options' => $this->tasks->filters(),
            ]),
            'sidebar' => $this->view->renderFile('partials/analytics-sidebar', ['data' => $data]),
            'contentHtml' => $this->view->renderFile('partials/analytics-content', ['data' => $data]),
            'right' => $this->view->renderFile('partials/analytics-right', ['data' => $data]),
            'rightTitle' => $this->i18n->t('analytics.rightTitle'),
            'rightApiTitle' => $this->i18n->t('analytics.rightApiTitle'),
            'rightApiHint' => $this->i18n->t('analytics.rightApiHint'),
            'rightApi' => ['totals' => $data['totals'], 'filters' => $data['filters']],
            'boot' => [
                'section' => 'analytics',
                'filters' => $data['filters'],
                'data' => $data,
            ],
        ], 'app');

        return Response::html($html);
    }

    public function data(Request $request): Response
    {
        return Response::json(['status' => 'ok', 'data' => $this->tasks->analytics($this->filters($request))]);
    }

    /** @return array<string, mixed> */
    private function filters(Request $request): array
    {
        return [
            'q' => trim((string) $request->query('q', '')),
            'release' => trim((string) $request->query('release', '')),
            'assignee' => trim((string) $request->query('assignee', '')),
            'project' => trim((string) $request->query('project', '')),
            'unassigned' => true,
        ];
    }
}

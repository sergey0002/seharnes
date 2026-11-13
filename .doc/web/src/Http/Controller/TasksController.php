<?php
declare(strict_types=1);

namespace Seharnes\Panel\Http\Controller;

use Seharnes\Panel\Core\Request;
use Seharnes\Panel\Core\Response;
use Seharnes\Panel\Core\View;
use Seharnes\Panel\Domain\Tasks\TasksRepository;
use Seharnes\Panel\Support\I18n;

/**
 * Раздел «Задачи».
 *
 * Данные те же, что у старой панели (список задач, фильтры, детали и диалоги),
 * раскладка — нового каркаса: тулбар, три колонки, док. Фильтры живут в строке
 * запроса, поэтому состояние раздела воспроизводится ссылкой.
 */
final class TasksController
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
        $list = $this->tasks->list($filters);
        $selected = (string) $request->query('id', '');
        $detail = $selected !== '' ? $this->tasks->detail($selected, (string) $list['filters']['project']) : null;

        $html = $this->view->render('pages/tasks', [
            'section' => 'tasks',
            'title' => $this->i18n->t('nav.tasks'),
            'toolbar' => $this->view->renderFile('partials/tasks-toolbar', [
                'filters' => $list['filters'],
                'options' => $this->tasks->filters(),
                'totals' => $list['totals'],
            ]),
            'sidebar' => $this->view->renderFile('partials/tasks-sidebar', ['list' => $list]),
            'contentHtml' => $this->view->renderFile('partials/tasks-content', [
                'list' => $list,
                'selected' => $selected,
            ]),
            'right' => $detail !== null
                ? $this->view->renderFile('partials/tasks-right', ['detail' => $detail, 'id' => $selected])
                : $this->view->renderFile('partials/tasks-right-empty'),
            'rightTitle' => $this->i18n->t('tasks.rightTitle'),
            'rightApiTitle' => $this->i18n->t('tasks.rightApiTitle'),
            'rightApiHint' => $selected !== ''
                ? $this->i18n->t('tasks.rightApiHint', ['id' => $selected])
                : $this->i18n->t('tasks.rightApiIdle'),
            'rightApi' => $detail ?? ['idle' => true],
            'boot' => [
                'section' => 'tasks',
                'filters' => $list['filters'],
                'selected' => $selected,
                'list' => $list,
            ],
        ], 'app');

        return Response::html($html);
    }

    public function list(Request $request): Response
    {
        return Response::json(['status' => 'ok', 'data' => $this->tasks->list($this->filters($request))]);
    }

    public function item(Request $request): Response
    {
        $id = trim((string) $request->query('id', ''));
        if ($id === '' || !preg_match('/^[0-9]{1,12}$/', $id)) {
            return Response::json(['status' => 'failed', 'error' => 'bad id'], 400);
        }
        $detail = $this->tasks->detail($id, trim((string) $request->query('project', '')));
        if ($detail === null) {
            return Response::json(['status' => 'failed', 'error' => 'task not found', 'id' => $id], 404);
        }

        return Response::json(['status' => 'ok', 'data' => $detail]);
    }

    /** @return array<string, mixed> */
    private function filters(Request $request): array
    {
        return [
            'q' => trim((string) $request->query('q', '')),
            'release' => trim((string) $request->query('release', '')),
            'assignee' => trim((string) $request->query('assignee', '')),
            'project' => trim((string) $request->query('project', '')),
            'unassigned' => (string) $request->query('unassigned', '') === '1',
        ];
    }
}

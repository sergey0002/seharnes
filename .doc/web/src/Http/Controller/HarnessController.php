<?php
declare(strict_types=1);

namespace Seharnes\Panel\Http\Controller;

use Seharnes\Panel\Core\Request;
use Seharnes\Panel\Core\Response;
use Seharnes\Panel\Core\View;
use Seharnes\Panel\Domain\Harness\HarnessAudit;
use Seharnes\Panel\Domain\Harness\HarnessStatus;
use Seharnes\Panel\Domain\Job\JobRepository;
use Seharnes\Panel\Support\I18n;

/**
 * Раздел «Контроль харнеса»: источник обновления, квитанция, задания и сканы.
 *
 * Повторяет старую админку по смыслу и данным, но живёт в новом каркасе:
 * раскладка та же (тулбар, три колонки, док), действия — те же задания.
 */
final class HarnessController
{
    public function __construct(
        private readonly View $view,
        private readonly I18n $i18n,
        private readonly HarnessStatus $status,
        private readonly HarnessAudit $audit,
        private readonly JobRepository $jobs,
    ) {
    }

    /** @param array<string, string> $params */
    public function page(Request $request, array $params): Response
    {
        $status = $this->status->snapshot();
        $history = $this->jobs->recent(12);
        $html = $this->view->render('pages/harness', [
            'section' => 'harness',
            'title' => $this->i18n->t('nav.admin'),
            'toolbar' => $this->view->renderFile('partials/harness-toolbar', [
                'status' => $status,
            ]),
            'sidebar' => $this->view->renderFile('partials/harness-sidebar', [
                'status' => $status,
                'history' => $history,
            ]),
            'contentHtml' => $this->view->renderFile('partials/harness-content', [
                'status' => $status,
                'history' => $history,
            ]),
            'right' => $this->view->renderFile('partials/harness-right', [
                'status' => $status,
            ]),
            'rightTitle' => $this->i18n->t('harness.rightTitle'),
            'rightApiTitle' => $this->i18n->t('harness.rightApiTitle'),
            'rightApiHint' => $this->i18n->t('harness.rightApiHint'),
            'rightApi' => ['status' => $status],
            'boot' => [
                'section' => 'harness',
                'status' => $status,
            ],
        ], 'app');
        return Response::html($html);
    }

    public function status(): Response
    {
        return Response::json(['status' => 'ok', 'data' => $this->status->snapshot()]);
    }

    /**
     * Сканы: read-only, поэтому GET без проверки Origin.
     *
     * Список проверок приходит из строки запроса; неизвестные значения отбрасываются,
     * пустой список означает «все».
     */
    public function audit(Request $request): Response
    {
        $checks = (string) $request->query('checks', '');
        $report = $this->audit->run($checks);
        // Ненулевой код выхода у audit_harness.py означает «найдены проблемы», а не сбой
        // запуска: отчёт с проверками всегда отдаём как 200, чтобы UI показал находки.
        $broken = isset($report['error']) || !isset($report['checks']);
        return Response::json($report, $broken ? 500 : 200);
    }
}

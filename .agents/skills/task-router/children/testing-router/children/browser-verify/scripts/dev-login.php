<?php

/**
 * Служебный вход без формы/капчи для dev/test-стендов (см. .doc/tests2.md
 * «Решение 3»). Физически не существует в git и в проде: `.doc/` не
 * отслеживается git (.git/info/exclude), а на dev/test-стенды попадает
 * автоматически через уже существующий bind-mount всего репо
 * (`../../:/var/www/html` в tools/docker-dev|docker-test/compose.yaml) —
 * доступен по прямому пути `/.agents/skills/task-router/children/testing-router/children/browser-verify/scripts/dev-login.php`,
 * без отдельного дополнительного volume.
 *
 * Ставит те же cookie/сессию, что обычный логин через UI — не отдельный
 * механизм, использует тот же SessionManagerService::startClientSession()
 * и тот же auth_check()-совместимый набор admin-cookie.
 *
 * ?as=client&id={clientId}  — сессия клиента (как AccountController после
 *                              формы /account/signin)
 * ?as=admin[&login=...&pass=...] — cookie login/pass (как admin/index.php
 *                              после формы /admin/, но без капчи — она
 *                              проверяется только в POST-обработчике формы)
 */

declare(strict_types=1);

// Скрипт лежит в .tools/codeception/scripts/ — корень приложения на три уровня выше.
define('PATH', dirname(__DIR__, 3) . '/');

require_once PATH . 'vendor/autoload.php';
require_once PATH . 'lib/System.php';
define('DJT_PATH', System::getBasePath());
define('DJT_REAL_PATH', PATH);
require_once PATH . 'constants.php';

$appEnv = $_ENV['APP_ENV'] ?? getenv('APP_ENV') ?? '';
if ($appEnv === 'production') {
    http_response_code(404);
    exit;
}

require_once PATH . 'lib/Objects/SfInjector.php';
require_once PATH . 'lib/Objects/Client/ClientService.php';

header('Content-Type: text/plain; charset=utf-8');

$as = $_GET['as'] ?? '';

if ($as === 'client') {
    $clientId = isset($_GET['id']) ? (int) $_GET['id'] : 0;
    if ($clientId <= 0) {
        http_response_code(400);
        echo 'FAIL: id required';
        exit;
    }

    $client = ClientService::getClientById($clientId);
    if (!$client) {
        http_response_code(404);
        echo 'FAIL: client not found';
        exit;
    }

    /** @var \App\SessionManagerService\SessionManagerService $sessionManagerService */
    $sessionManagerService = SfInjector::Get()->getService(\App\SessionManagerService\SessionManagerService::class);
    $sessionManagerService->startClientSession($client);

    echo 'OK: client session started, id=' . $clientId;
    exit;
}

if ($as === 'admin') {
    $login = $_GET['login'] ?? 'realant';
    $pass = $_GET['pass'] ?? 'realant2020';

    // path=/ обязателен: иначе cookie остаётся на /.tools/codeception/scripts/
    // и /admin/ их не видит.
    setcookie('login', $login, time() + 3600 * 24 * 7, '/');
    setcookie('pass', md5($pass), time() + 3600 * 24 * 7, '/');

    echo 'OK: admin cookies set, login=' . $login;
    exit;
}

http_response_code(400);
echo 'FAIL: unknown "as" (use as=client&id=N or as=admin)';

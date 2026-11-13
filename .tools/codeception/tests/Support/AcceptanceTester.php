<?php

declare(strict_types=1);

namespace Tests\Support;

/**
 * Inherited Methods
 * @method void wantTo($text)
 * @method void wantToTest($text)
 * @method void execute($callable)
 * @method void expectTo($prediction)
 * @method void expect($prediction)
 * @method void amGoingTo($argumentation)
 * @method void am($role)
 * @method void lookForwardTo($achieveValue)
 * @method void comment($description)
 * @method void pause($vars = [])
 *
 * @SuppressWarnings(PHPMD)
*/
class AcceptanceTester extends \Codeception\Actor
{
    use _generated\AcceptanceTesterActions;

    /** Путь к dev-входу без формы и капчи (см. scripts/dev-login.php). */
    private const DEV_LOGIN = '/.tools/codeception/scripts/dev-login.php';

    /** Снимок DOM предыдущего checkpoint для расчёта дельты. */
    private ?string $lastDomSnapshot = null;

    /** Порядковый номер checkpoint в рамках теста (для имён скриншотов). */
    private int $checkpointIndex = 0;

    // =====================================================================
    // Консоль браузера
    // =====================================================================

    /**
     * Ставит перехват console.error / window.onerror / unhandledrejection.
     * Идемпотентен: повторный вызов не сбрасывает уже собранные ошибки.
     * Вызывается автоматически из checkpoint(), но можно и явно в _before.
     */
    public function initConsoleCapture(): void
    {
        $this->executeJS(
            'if (!window.__testConsoleHooked) {'
            . '  window.__testConsoleHooked = true;'
            . '  window.__testConsoleErrors = window.__testConsoleErrors || [];'
            . '  var origError = console.error;'
            . '  console.error = function () {'
            . '    try {'
            . '      window.__testConsoleErrors.push("console.error: " +'
            . '        Array.prototype.map.call(arguments, function (a) {'
            . '          try { return typeof a === "string" ? a : JSON.stringify(a); }'
            . '          catch (e) { return String(a); }'
            . '        }).join(" "));'
            . '    } catch (e) {}'
            . '    if (origError) { origError.apply(console, arguments); }'
            . '  };'
            . '  window.addEventListener("error", function (e) {'
            . '    window.__testConsoleErrors.push("onerror: " + (e && e.message ? e.message : "unknown")'
            . '      + " @ " + (e && e.filename ? e.filename : "?") + ":" + (e && e.lineno ? e.lineno : "?"));'
            . '  });'
            . '  window.addEventListener("unhandledrejection", function (e) {'
            . '    var r = e && e.reason;'
            . '    window.__testConsoleErrors.push("unhandledrejection: " +'
            . '      (r && r.message ? r.message : String(r)));'
            . '  });'
            . '}'
        );
    }

    /**
     * Накопленные ошибки консоли с момента initConsoleCapture().
     *
     * @return array<int, string>
     */
    public function grabConsoleErrors(): array
    {
        $errors = $this->executeJS('return window.__testConsoleErrors || [];');

        if (is_object($errors)) {
            $errors = json_decode((string) json_encode($errors), true);
        }

        return is_array($errors) ? array_values(array_map('strval', $errors)) : [];
    }

    /**
     * Очищает накопленные ошибки (например, когда шаг заведомо шумит).
     */
    public function resetConsoleErrors(): void
    {
        $this->executeJS('window.__testConsoleErrors = [];');
    }

    /**
     * Строгая проверка: падает тест, если в консоли есть ошибки.
     * В отличие от checkpoint(), который только фиксирует их в отчёт.
     */
    public function seeNoConsoleErrors(): void
    {
        $errors = $this->grabConsoleErrors();

        $this->assertSame(
            [],
            $errors,
            "Ошибки в консоли браузера:\n  - " . implode("\n  - ", $errors)
        );
    }

    // =====================================================================
    // Checkpoint — скрин + консоль + DOM-дельта + error-modal / toasted
    // =====================================================================

    /**
     * Снимок качества шага. Вызывать после каждого значимого действия
     * (клик, сабмит, переход шага wizard), не только в конце теста.
     *
     * Собирает: скриншот, ошибки консоли, дельту DOM к предыдущему checkpoint,
     * видимые error-modal и toasted-сообщения. Пишет строку в
     * `_output/checkpoints.jsonl` — оттуда её забирает отчёт прогона.
     *
     * Сам по себе тест не валит: это диагностика. Для жёсткой проверки
     * консоли есть seeNoConsoleErrors(), для сообщений — dontSeeErrorModal().
     *
     * @return array{label: string, console: array<int, string>, errorModal: string,
     *     toasted: array<int, string>, domAdded: int, domRemoved: int}
     */
    public function checkpoint(string $label): array
    {
        $this->initConsoleCapture();
        $this->checkpointIndex++;

        $slug = preg_replace('/[^a-zA-Z0-9_.-]+/', '-', $label) ?? 'step';
        $this->makeScreenshot(sprintf('%02d-%s', $this->checkpointIndex, $slug));

        $console = $this->grabConsoleErrors();
        $messages = $this->grabPageMessages();

        [$added, $removed] = $this->domDelta();

        $entry = [
            'label'      => $label,
            'index'      => $this->checkpointIndex,
            'url'        => $this->grabCurrentUrlSafe(),
            'console'    => $console,
            'errorModal' => $messages['errorModal'],
            'toasted'    => $messages['toasted'],
            'domAdded'   => $added,
            'domRemoved' => $removed,
        ];

        $this->writeCheckpointLog($entry);

        $summary = sprintf(
            'checkpoint "%s": консоль %d, toasted %d, error-modal %s, DOM +%d/-%d',
            $label,
            count($console),
            count($messages['toasted']),
            $messages['errorModal'] === '' ? 'нет' : 'ЕСТЬ',
            $added,
            $removed
        );
        $this->comment($summary);

        if ($messages['errorModal'] !== '') {
            $this->comment('  error-modal: ' . $messages['errorModal']);
        }
        foreach ($console as $line) {
            $this->comment('  console: ' . $line);
        }

        return $entry;
    }

    /**
     * Жёсткая проверка отсутствия модалки ошибки на текущем экране.
     */
    public function dontSeeErrorModal(): void
    {
        $messages = $this->grabPageMessages();

        $this->assertSame(
            '',
            $messages['errorModal'],
            'На экране показана модалка ошибки: ' . $messages['errorModal']
        );
    }

    /**
     * Видимые сообщения страницы: модалка ошибки и тосты.
     *
     * `.toasted` — осознанное исключение из конвенции data-test:
     * вендорная vue-toasted не умеет произвольные атрибуты
     * (см. .doc/qa/fragments.md П-3).
     *
     * @return array{errorModal: string, toasted: array<int, string>}
     */
    public function grabPageMessages(): array
    {
        $raw = $this->executeJS(
            'return (function () {'
            . '  function visible(el) {'
            . '    if (!el) { return false; }'
            . '    var s = window.getComputedStyle(el);'
            . '    if (s.display === "none" || s.visibility === "hidden") { return false; }'
            . '    return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);'
            . '  }'
            . '  function text(el) { return (el.innerText || el.textContent || "").trim(); }'
            . '  var modal = "";'
            . '  var titles = document.querySelectorAll("h2.modal-header__title");'
            . '  for (var i = 0; i < titles.length; i++) {'
            . '    if (!visible(titles[i])) { continue; }'
            . '    var t = text(titles[i]);'
            . '    if (/^Ошибк/.test(t)) { modal = t; break; }'
            . '  }'
            . '  var toasted = [];'
            . '  var toasts = document.querySelectorAll(".toasted");'
            . '  for (var j = 0; j < toasts.length; j++) {'
            . '    if (visible(toasts[j])) { toasted.push(text(toasts[j])); }'
            . '  }'
            . '  return {errorModal: modal, toasted: toasted};'
            . '})();'
        );

        if (is_object($raw)) {
            $raw = json_decode((string) json_encode($raw), true);
        }

        return [
            'errorModal' => is_array($raw) ? (string) ($raw['errorModal'] ?? '') : '',
            'toasted'    => is_array($raw) && is_array($raw['toasted'] ?? null)
                ? array_values(array_map('strval', $raw['toasted']))
                : [],
        ];
    }

    /**
     * Дельта DOM к предыдущему checkpoint: [добавлено строк, убрано строк].
     *
     * @return array{0: int, 1: int}
     */
    private function domDelta(): array
    {
        $current = (string) $this->grabPageSource();

        if ($this->lastDomSnapshot === null) {
            $this->lastDomSnapshot = $current;

            return [0, 0];
        }

        $before = array_filter(array_map('trim', explode("\n", $this->lastDomSnapshot)), 'strlen');
        $after  = array_filter(array_map('trim', explode("\n", $current)), 'strlen');

        $added   = count(array_diff($after, $before));
        $removed = count(array_diff($before, $after));

        $this->lastDomSnapshot = $current;

        return [$added, $removed];
    }

    private function grabCurrentUrlSafe(): string
    {
        try {
            return (string) $this->executeJS('return window.location.href;');
        } catch (\Throwable $e) {
            return '';
        }
    }

    /**
     * @param array<string, mixed> $entry
     */
    private function writeCheckpointLog(array $entry): void
    {
        $dir = codecept_output_dir();

        if (!is_dir($dir)) {
            return;
        }

        @file_put_contents(
            $dir . 'checkpoints.jsonl',
            json_encode($entry, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n",
            FILE_APPEND
        );
    }

    // =====================================================================
    // Вход без формы (dev/test стенд)
    // =====================================================================

    /**
     * Сессия клиента без формы и капчи. Тот же startClientSession(),
     * что и обычный вход, только без UI. Только dev/test стенд.
     */
    public function devLoginAsClient(int $clientId): void
    {
        $this->amOnPage(self::DEV_LOGIN . '?as=client&id=' . $clientId);
        $this->see('OK: client session started');
    }

    /**
     * Cookie админа без формы и капчи. Только dev/test стенд.
     */
    public function devLoginAsAdmin(string $login = 'realant', string $pass = 'realant2020'): void
    {
        $this->haveInDbDefaultAdmin($login, $pass);
        $this->amOnPage(self::DEV_LOGIN . '?as=admin&login=' . urlencode($login) . '&pass=' . urlencode($pass));
        $this->see('OK: admin cookies set');
    }

    /**
     * Вход под произвольным клиентом через админский имперсонейт
     * (`client/login-by-client`), а не через пароль клиента.
     * Клиент с таким id должен уже существовать в БД.
     *
     * См. скил login-as-user и .doc/tests.md §2.
     */
    public function loginAsClientById(int $clientId): void
    {
        $this->assertGreaterThan(0, $this->grabNumRecords('ct_client', ['id' => $clientId]), sprintf(
            'Клиента id=%d нет в БД: loginAsClientById не создаёт клиента',
            $clientId
        ));

        $this->devLoginAsAdmin();

        $this->amOnPage('/admin/');
        $this->executeJS(
            'var xhr = new XMLHttpRequest();'
            . 'xhr.open("POST", "/client/login-by-client", false);'
            . 'xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");'
            . 'xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");'
            . 'xhr.send("id=" + arguments[0]);'
            . 'return xhr.status;',
            [$clientId]
        );

        $this->amOnPage('/account/edit');
        $this->waitForElement('//body', 10);
    }

    /**
     * Upsert админа и минимальных прав. Вынесено из loginAsAdmin(),
     * чтобы dev-вход тоже мог гарантировать пользователя.
     */
    public function haveInDbDefaultAdmin(string $login = 'realant', string $pass = 'realant2020'): void
    {
        $userData = [
            'name'  => 'Admin',
            'login' => $login,
            'pass'  => md5($pass),
        ];

        if ($this->grabNumRecords('ct_user', ['id' => 1]) > 0) {
            $this->updateInDatabase('ct_user', $userData, ['id' => 1]);
        } else {
            $this->haveInDatabase('ct_user', array_merge(['id' => 1], $userData));
        }

        if ($this->grabNumRecords('ct_right', ['slug' => 'tariffs']) === 0) {
            $this->haveInDatabase('ct_right', [
                'id'       => 6,
                'name'     => 'Тарифы',
                'slug'     => 'tariffs',
                'priority' => 1005,
            ]);
        }
        $rightId = (int) $this->grabFromDatabase('ct_right', 'id', ['slug' => 'tariffs']);

        if ($this->grabNumRecords('ct_role', ['id' => 1]) === 0) {
            $this->haveInDatabase('ct_role', ['id' => 1, 'name' => 'Admin']);
        }

        if ($this->grabNumRecords('ct_role2right', ['roleId' => 1, 'rightId' => $rightId]) === 0) {
            $this->haveInDatabase('ct_role2right', ['roleId' => 1, 'rightId' => $rightId]);
        }

        if ($this->grabNumRecords('ct_user2role', ['userId' => 1, 'roleId' => 1]) === 0) {
            $this->haveInDatabase('ct_user2role', ['userId' => 1, 'roleId' => 1]);
        }
    }

    /**
     * Второй клиент (id=2) для тестов прав доступа.
     * Переиспользует ct_country / ct_tariff из haveInDbDefaultClient() —
     * вызывать после него.
     */
    public function haveInDbSecondClient(): void
    {
        $client = [
            'id'                   => 2,
            'email'                => 'test+local-client2@seyfer.pro',
            'emailStatus'          => 'SUCCESS',
            'pass'                 => md5('Qwert123'),
            'name'                 => '',
            'approved'             => '',
            'theDate'              => '2009-04-19',
            'state'                => 1,
            'phone'                => '1234555',
            'phoneCode'            => 994,
            'phoneCountryId'       => 268,
            'phoneId'              => 0,
            'phoneVerified'        => 0,
            'tariffId'             => 7,
            'attempts'             => 0,
            'level'                => 0,
            'disk_quota'           => 250,
            'item_max_data'        => 50,
            'items_limit'          => 5,
            'maxRegisterPeriod'    => 11,
            'pinCode'              => 0,
            'closedRegistration'   => 1,
            'underPseud'           => 1,
            'receiveMailings'      => 0,
            'sendClientLetters'    => 1,
            'receiveClientLetters' => 1,
            'fee'                  => 0,
            'dayLimit'             => 75000,
            'identificationStatus' => 0,
            'resident'             => 1,
            'hash'                 => sha1('local-client2'),
            'offerConfirmed'       => 1,
        ];

        if ($this->grabNumRecords('ct_client', ['id' => 2]) > 0) {
            $this->updateInDatabase('ct_client', $client, ['id' => 2]);
        } else {
            $this->haveInDatabase('ct_client', $client);
        }
    }

    // =====================================================================
    // Делегаты в Page-объекты (селекторы живут там, не в акторе и не в Cest)
    // =====================================================================

    /** Заказ проверки качества ОИС: /order/check. */
    public function orderCheckPage(): Page\OrderCheckPage
    {
        return new Page\OrderCheckPage($this);
    }

    /** Многошаговая форма депонирования: /item/start. */
    public function wizardPage(): Page\WizardPage
    {
        return new Page\WizardPage($this);
    }

    /** Webpack-редактирование профиля: /profile/edit. */
    public function profileEditPage(): Page\ProfileEditPage
    {
        return new Page\ProfileEditPage($this);
    }

    public function signinPage(): Page\SigninPage
    {
        return new Page\SigninPage($this);
    }

    public function sessionEndModalPage(): Page\SessionEndModalPage
    {
        return new Page\SessionEndModalPage($this);
    }

    public function signupPage(): Page\SignupPage
    {
        return new Page\SignupPage($this);
    }

    public function oauthIdAccessPage(): Page\OauthIdAccessPage
    {
        return new Page\OauthIdAccessPage($this);
    }

    public function orderMainPage(): Page\OrderMainPage
    {
        return new Page\OrderMainPage($this);
    }


    /** Админка: профиль клиента, логин/email. */
    public function adminClientProfilePage(): Page\AdminClientProfilePage
    {
        return new Page\AdminClientProfilePage($this);
    }

    public function amOnOrderCheckPage(): void
    {
        $this->orderCheckPage()->open();
    }

    /**
     * @param array<int, array{uin: string, name: string, issetCover: bool, issetDataBlocks: bool}> $items
     */
    public function seedOrderCheckQualitySubjects(array $items): void
    {
        $this->orderCheckPage()->seedSubjects($items);
    }

    public function seeOrderQualityWarning(): void
    {
        $this->orderCheckPage()->seeWarning();
    }

    public function dontSeeOrderQualityWarning(): void
    {
        $this->orderCheckPage()->dontSeeWarning();
    }

    public function seeOrderQualityWarningContains(string $uin): void
    {
        $this->orderCheckPage()->seeWarningContains($uin);
    }


    public function loginAsClient(): void
    {
        $I = $this;
        $I->haveInDbDefaultClient();

        if ($I->loadSessionSnapshot('login')) {
            return;
        }

        $I->amOnPage('/account/signin');
        $I->fillField(
            '//*[@data-test="login-form"]//*[@data-test="login-form__email"]',
            'test+local-client1@seyfer.pro'
        );
        $I->fillField(
            '//*[@data-test="login-form"]//*[@data-test="login-form__pass"]',
            'Qwert123'
        );
        $I->click('//*[@data-test="login-form"]//*[@data-test="login-form__submit"]');
        $I->waitForElement('//*[@data-test="item-main"]', 10);


        $I->see('Мои регистрации', '//*[@data-test="item-main__title"]');

        $I->saveSessionSnapshot('login');

    }

    public function loginAsAdmin(): void
    {
        $userData = [
            'name' => 'Admin',
            'login' => 'realant',
            'pass' => md5('realant2020'),
        ];
        if ($this->grabNumRecords('ct_user', ['id' => 1]) > 0) {
            $this->updateInDatabase('ct_user', $userData, ['id' => 1]);
        } else {
            $this->haveInDatabase('ct_user', array_merge(['id' => 1], $userData));
        }

        if ($this->grabNumRecords('ct_right', ['slug' => 'tariffs']) === 0) {
            $this->haveInDatabase('ct_right', [
                'id' => 6,
                'name' => 'Тарифы',
                'slug' => 'tariffs',
                'priority' => 1005,
            ]);
        }
        $rightId = (int) $this->grabFromDatabase('ct_right', 'id', ['slug' => 'tariffs']);

        if ($this->grabNumRecords('ct_role', ['id' => 1]) === 0) {
            $this->haveInDatabase('ct_role', [
                'id' => 1,
                'name' => 'Admin',
            ]);
        }

        if ($this->grabNumRecords('ct_role2right', ['roleId' => 1, 'rightId' => $rightId]) === 0) {
            $this->haveInDatabase('ct_role2right', [
                'roleId' => 1,
                'rightId' => $rightId,
            ]);
        }

        if ($this->grabNumRecords('ct_user2role', ['userId' => 1, 'roleId' => 1]) === 0) {
            $this->haveInDatabase('ct_user2role', [
                'userId' => 1,
                'roleId' => 1,
            ]);
        }

        $this->amOnPage('/.tools/codeception/scripts/dev-login.php?as=admin');
        $this->amOnPage('/admin/');
        $this->waitForText('Admin Mode', 10, '//*[@data-test="title"]');
    }

    public function haveInDbTariff(int $id, array $overrides = []): void
    {
        $defaults = [
            'id' => $id,
            'name' => 'Test tariff ' . $id,
            'isDefault' => 0,
            'isSelectable' => 1,
            'isOverdraft' => 0,
            'visible' => 0,
            'description' => 'test',
            'fullDescription' => 'test',
            'subscriptionFee' => 0.00,
            'settlementPeriod' => 0,
            'minBalanceAllow' => 0,
            'isDeleted' => 0,
            'isAvailableForFizik' => 1,
            'isAvailableForJurik' => 1,
            'isAvailableForIp' => 1,
        ];
        $row = array_merge($defaults, $overrides);

        if ($this->grabNumRecords('ct_tariff', ['id' => $id]) > 0) {
            $this->updateInDatabase('ct_tariff', $row, ['id' => $id]);
        } else {
            $this->haveInDatabase('ct_tariff', $row);
        }

        $uacDefaults = [
            'tariffId' => $id,
            'disk_quota' => 250,
            'item_max_data' => 25,
            'items_limit' => 1,
            'maxRegisterPeriod' => 1,
            'pinCode' => 0,
            'closedRegistration' => 0,
            'underPseud' => 0,
            'sendClientLetters' => 0,
            'receiveClientLetters' => 0,
        ];

        if ($this->grabNumRecords('ct_tariff_uac_parameters', ['tariffId' => $id]) > 0) {
            $this->updateInDatabase('ct_tariff_uac_parameters', $uacDefaults, ['tariffId' => $id]);
        } else {
            $this->haveInDatabase('ct_tariff_uac_parameters', $uacDefaults);
        }
    }

    public function haveInDbPromo(int $tariffId, array $overrides = []): void
    {
        $defaults = [
            'theDate' => date('Y-m-d H:i:s'),
            'series' => 'TST24',
            'description' => 'test promo',
            'md5code' => md5('promo-' . $tariffId . '-' . microtime(true)),
            'sum' => 0,
            'tariff_id' => $tariffId,
            'profile_type_id' => '0#1#2',
            'status' => 0,
            'client_id' => null,
        ];

        $this->haveInDatabase('ct_promo', array_merge($defaults, $overrides));
    }

    public function deleteTariffViaAdmin(int $tariffId): void
    {
        $this->amOnPage('/admin/m_tariff.php');
        $this->waitForElement('//*[@data-test="tariff-delete-btn-' . $tariffId . '"]', 10);
        $this->click('//*[@data-test="tariff-delete-btn-' . $tariffId . '"]');
        $this->waitForElement('//*[@data-test="tariff-delete-confirm"]', 10);
        $this->click('//*[@data-test="tariff-delete-confirm"]');
    }

    /**
     * DEFAULT колонки ct_paymentChannel.kurs (SHOW COLUMNS). CT-2602 stage2.
     */
    public function grabPaymentChannelKursColumnDefault(): string
    {
        $modules = $this->getScenario()->current('modules');
        if (!is_array($modules) || !isset($modules['Db']) || !is_object($modules['Db'])) {
            $this->fail('Db module is not available');
        }
        /** @var \Codeception\Module\Db $db */
        $db = $modules['Db'];
        $col = $db->_getDbh()->query("SHOW COLUMNS FROM ct_paymentChannel LIKE 'kurs'")->fetch(\PDO::FETCH_ASSOC);
        if (!is_array($col) || !array_key_exists('Default', $col)) {
            $this->fail('SHOW COLUMNS kurs empty');
        }

        return (string) $col['Default'];
    }

    public function haveInDbDefaultClient(): void
    {
        $country = [
            'id'            => 268,
            'code'          => 'AZE',
            'country'       => 'Азербайджан',
            'name_rus'      => 'Азербайджан',
            'name_en'       => 'Azerbaijan',
            'phone_code'    => 994,
            'state_type'    => 1,
            'forced_order'  => 0,
            'code2'         => 'AZ',
        ];
        if ($this->grabNumRecords('ct_country', ['id' => 268]) > 0) {
            $this->updateInDatabase('ct_country', $country, ['id' => 268]);
        } else {
            $this->haveInDatabase('ct_country', $country);
        }

        $tariff = [
            'id'               => 7,
            'name'             => 'Простой',
            'isDefault'        => 1,
            'isSelectable'     => 1,
            'isOverdraft'      => 0,
            'visible'          => 1,
            'description'      => 'Базовый тариф',
            'fullDescription'  => 'Базовый тариф без абонентской платы',
            'subscriptionFee'  => 0.00,
            'settlementPeriod' => 0,
            'minBalanceAllow'  => -50000,
            'isDeleted'        => 0,
            'updatedAt'        => '2025-08-13 15:03:51',
        ];
        if ($this->grabNumRecords('ct_tariff', ['id' => 7]) > 0) {
            $this->updateInDatabase('ct_tariff', $tariff, ['id' => 7]);
        } else {
            $this->haveInDatabase('ct_tariff', $tariff);
        }

        $uac = [
            'id'                   => 6,
            'tariffId'             => 7,
            'disk_quota'           => 250,
            'item_max_data'        => 25,
            'items_limit'          => 1,
            'maxRegisterPeriod'    => 1,
            'pinCode'              => 0,
            'closedRegistration'   => 0,
            'underPseud'           => 0,
            'sendClientLetters'    => 0,
            'receiveClientLetters' => 0,
        ];
        if ($this->grabNumRecords('ct_tariff_uac_parameters', ['tariffId' => 7]) > 0) {
            $this->updateInDatabase('ct_tariff_uac_parameters', $uac, ['tariffId' => 7]);
        } else {
            $this->haveInDatabase('ct_tariff_uac_parameters', $uac);
        }

        $client = [
            'id'                       => 1,
            'email'                    => 'test+local-client1@seyfer.pro',
            'emailStatus'              => 'SUCCESS',
            'pass'                     => md5('Qwert123'),
            'name'                     => '',
            'approved'                 => '',
            'theDate'                  => '2009-04-19',
            'state'                    => 1,
            'phone'                    => '1234554',
            'phoneCode'                => 994,
            'phoneCountryId'           => 268,
            'phoneId'                  => 0,
            'phoneVerified'            => 0,
            'tariffId'                 => 7,
            'gatewayAccount'           => null,
            'parentId'                 => null,
            'dealerSiteId'             => 0,
            'dealerParentId'           => null,
            'attempts'                 => 0,
            'admincomment'             => '',
            'level'                    => 0,
            'disk_quota'               => 250,
            'item_max_data'            => 50,
            'items_limit'              => 5,
            'adminmessage'             => '',
            'transitionDate'           => '2025-08-13 00:00:00',
            'endDate'                  => null,
            'maxRegisterPeriod'        => 11,
            'contractType'             => null,
            'pinCode'                  => 0,
            'closedRegistration'       => 1,
            'underPseud'               => 1,
            'receiveMailings'          => 0,
            'sendClientLetters'        => 1,
            'copytrustContractNumber'  => null,
            'copytrustContractDate'    => null,
            'receiveClientLetters'     => 1,
            'fee'                      => 0,
            'dayLimit'                 => 75000,
            'identificationStatus'     => 0,
            'identificationDate'       => null,
            'lastLogin'                => '2025-01-22',
            'resident'                 => 1,
            'reasonChangeStatus'       => '',
            'lastDateChangeStatus'     => null,
            'descriptionChangeStatus'  => '',
            'hash'                     => '16e30ebd3b93ac1c6981a184260906efe78569bc',
            'offerConfirmed'           => 1,
            'dateNextNotification'     => '2025-08-12',
            'renewalDate'              => null,
        ];
        if ($this->grabNumRecords('ct_client', ['id' => 1]) > 0) {
            $this->updateInDatabase('ct_client', $client, ['id' => 1]);
        } else {
            $this->haveInDatabase('ct_client', $client);
        }
    }

    public function haveInDbProgramLang(): void
    {
        $this->haveInDatabase('ct_program_language',[
            'name' => 'PHP',
        ]);
        $this->haveInDatabase('ct_program_language',[
            'name' => 'Смесь языков',
        ]);
    }

    public function haveInDbIdentityType(): void
    {
        $this->haveInDatabase('ct_doc', [
            'code' => 14,
            'name' => 'Паспорт гражданина РФ',
        ]);
    }

    public function haveInDbItemSection(): void
    {
        $this->haveInDatabase('ct_itemSection', [
            'id' => 100,
            'name' => 'Достижения, факты и прогнозы',
            'Position' => 1,
            'visible' => 1,
            'hasChildren' => 1,
        ]);
        $this->haveInDatabase('ct_itemSection', [
            'id' => 101,
            'name' => 'Спорт/Экстрим/Конкурсы',
            'Position' => 1,
            'visible' => 1,
            'parentId' => 100,
            'hasChildren' => 0,
            'path' => '_100'
        ]);
    }

    public function haveInDbItemDraft(): void
    {
        $this->haveInDatabase('ct_item', [
            'id' => 1,
            'isDraft' => 1,
            'clientId' => 1,
            'strategy' => 'programm',
            'CreatedDate' => '2020-01-01',
            'name' => 'Наименование',
            'draftName' => 'Наименование',
            'description' => 'Описание программы',
            'place_creation' => 'Место создания',
            'number_version' => '1.0.0',
            'destination' => 'Назначение программы',
            'scope' => 'Область применения',
            'functionality' => 'Функциональные возможности',
            'technical_requirements' => 'Технические требования',
            'term' => 5,
            'itemSectionId' => 101,
            'regtype' => 2,
            'itemtype' => 1,
            'ispublic' => 2,
            'prolongate' => 1,
            'mainType' => 'Software',
            'subType' => 'Independed',
            'theDate' => '2025-01-01 00:00:00',
        ]);

        $this->haveInDatabase('ct_author', [
            'id' => 1,
            'draftId' => 1,
            'surname' => 'Фамилия',
            'firstName' => 'Имя',
            'secondName' => 'Отчество',
            'birthDate' => '01.01.2010',
            'identitySeria' => '1122',
            'identityNumber' => '112233',
            'identityDate' => '2020-01-01 00:00:00',
            'identityResponcible' => 'МВД',
        ]);

        $this->haveInDatabase('ct_rightsHolder', [
            'type' => 'Authors',
            'rightType' => 'Copyrights',
            'authorRole' => 'автор',
            'partsDescription' => 'Музыка',
            'subjectId' => 1,
            'itemId' => 1,
        ]);
        $this->haveInDatabase('ct_rightsHolder', [
            'type' => 'ExclusiveRightsHolders',
            'rightType' => 'ExceptionalRights',
            "exceptType" => 'AllAsAuthorAndOwner',
            'subjectId' => 1,
            'itemId' => 1,
        ]);
        $this->haveInDatabase('ct_rightsHolder', [
            'type' => 'DatabaseCreators',
            'rightType' => 'RelatedRights',
            'subjectId' => 1,
            'itemId' => 1,
        ]);
    }

    public function adminTariffListPage(): Page\AdminTariffListPage
    {
        return new Page\AdminTariffListPage($this);
    }

    public function adminTariffEditPage(): Page\AdminTariffEditPage
    {
        return new Page\AdminTariffEditPage($this);
    }

    public function tariffListPage(): Page\TariffListPage
    {
        return new Page\TariffListPage($this);
    }

    public function tariffFullListPage(): Page\TariffFullListPage
    {
        return new Page\TariffFullListPage($this);
    }

    /** Пополнение: /payments/main (CT-2602). */
    public function paymentsMainPage(): Page\PaymentsMainPage
    {
        return new Page\PaymentsMainPage($this);
    }

    public function orderViewPage(): Page\OrderViewPage
    {
        return new Page\OrderViewPage($this);
    }

    public function orderRemovePage(): Page\OrderRemovePage
    {
        return new Page\OrderRemovePage($this);
    }

    public function ensureClientBalance(int $clientId, float $amount): void
    {
        $this->haveInDatabase('ct_payment', [
            'clientId'    => $clientId,
            'serviceId'   => 22,
            'name'        => 'AT ensure balance',
            'sum'         => $amount,
            'volume'      => 0,
            'free_volume' => 0,
            'committed'   => 1,
            'theDate'     => date('Y-m-d H:i:s'),
            'is_virtual'  => 0,
            'channel'     => 3,
        ]);
    }

    public function seedClientMessageFlags(int $recv, int $send, int $tRecv, int $tSend): void
    {
        $this->updateInDatabase('ct_client', [
            'receiveClientLetters' => $recv,
            'sendClientLetters' => $send,
        ], ['id' => 1]);
        $this->updateInDatabase('ct_tariff_uac_parameters', [
            'receiveClientLetters' => $tRecv,
            'sendClientLetters' => $tSend,
        ], ['tariffId' => 7]);
    }

    public function amOnOrderPrintForm(string $url, string $title): void
    {
        $this->amOnPage($url);
        $this->waitForText($title, 20);
        $this->waitForElement('//div[contains(@class,"order-cert-country")]', 15);
        $this->waitForJS(
            'return !!(window.storeVue && window.storeVue.getters'
            . ' && window.storeVue.getters["country/allGeographic"]'
            . ' && window.storeVue.getters["country/allGeographic"].length > 0);',
            15
        );
    }

    public function seeOrderCountryListWithoutSpecialCodes(): void
    {
        $probe = $this->executeJS(
            'return (function () {'
            . 'var geo = (window.storeVue && window.storeVue.getters)'
            . ' ? window.storeVue.getters["country/allGeographic"] : [];'
            . 'var all = (window.storeVue && window.storeVue.state && window.storeVue.state.country)'
            . ' ? window.storeVue.state.country.all : [];'
            . 'var special = [];'
            . 'for (var i = 0; i < (geo || []).length; i++) {'
            . '  var c = geo[i] || {};'
            . '  var code = String(c.code || "");'
            . '  var name = String(c.country || "");'
            . '  if (code === "NONE" || code === "NOT_EXIST"'
            . '    || name === "Без гражданства"'
            . '    || name.indexOf("несуществующих") !== -1) {'
            . '    special.push(name || code);'
            . '  }'
            . '}'
            . 'return {geoLen: (geo || []).length, allLen: (all || []).length, special: special};'
            . '})();'
        );
        if (is_object($probe)) {
            $probe = json_decode((string) json_encode($probe), true);
        }
        $this->assertGreaterThan(10, (int) ($probe['geoLen'] ?? 0), 'geographic country list must be loaded');
        $this->assertSame([], $probe['special'] ?? ['missing'], 'allGeographic must not contain citizenship specials');
        $this->click('//div[contains(@class,"order-cert-country")]//div[contains(@class,"vs__dropdown-toggle")]');
        $this->waitForElement(
            '//div[contains(@class,"order-cert-country")]//*[contains(@class,"vs__dropdown-menu")]',
            10
        );
        $menu = '//div[contains(@class,"order-cert-country")]//*[contains(@class,"vs__dropdown-menu")]';
        $this->see('Россия', $menu);
        $this->dontSee('Без гражданства', $menu);
        $this->dontSee('Гражданство несуществующих юрисдикций', $menu);
    }

    public function seeOrderCountrySearchRejectsStateless(): void
    {
        $this->fillField(
            '//div[contains(@class,"order-cert-country")]//input[contains(@class,"vs__search")]',
            'Без гражданства'
        );
        $this->waitForText('Ничего не найдено', 10);
        $this->dontSee('Без гражданства', '//ul[contains(@class,"vs__dropdown-menu")]//li');
    }

    public function amOnAccountEditMessages(): void
    {
        (new Page\AccountEditPage($this))->openMessagesAccordion();
    }

    public function amOnAccountEditOisParams(): void
    {
        (new Page\AccountEditPage($this))->openOisAccordion();
    }

    public function seeAccountMessageCheckbox(string $labelPart, bool $checked, bool $disabled): void
    {
        (new Page\AccountEditPage($this))->seeCheckbox($labelPart, $checked, $disabled);
    }

    public function openAccountMessagePurchase(string $labelPart): void
    {
        (new Page\AccountEditPage($this))->clickCheckbox($labelPart);
    }

    public function seeAccountMessagePayConfirm(): void
    {
        (new Page\AccountEditPage($this))->seePayConfirm();
    }

    public function cancelAccountMessagePayConfirm(): void
    {
        (new Page\AccountEditPage($this))->cancelPayConfirm();
    }

    public function accountEditPage(): Page\AccountEditPage
    {
        return new Page\AccountEditPage($this);
    }

    public function seedClientOisFlags(int $pin, int $closed, int $pseud): void
    {
        $this->updateInDatabase('ct_client', [
            'pinCode'            => $pin,
            'closedRegistration' => $closed,
            'underPseud'         => $pseud,
        ], ['id' => 1]);
        $this->updateInDatabase('ct_tariff_uac_parameters', [
            'pinCode'            => 0,
            'closedRegistration' => 0,
            'underPseud'         => 0,
        ], ['tariffId' => 7]);
    }

    public function setTariffServiceActive(int $tariffId, string $serviceCode, int $active): void
    {
        $serviceId = (int) $this->grabFromDatabase('ct_service', 'id', ['code' => $serviceCode]);
        $this->updateInDatabase(
            'ct_tariff2Service',
            ['active' => $active],
            ['tariffId' => $tariffId, 'serviceId' => $serviceId]
        );
    }

    public function bookingSteps(): \Tests\Support\Step\BookingSteps
    {
        return new \Tests\Support\Step\BookingSteps($this);
    }

    public function depositionSteps(): \Tests\Support\Step\DepositionSteps
    {
        return new \Tests\Support\Step\DepositionSteps($this);
    }

    public function authRequiredFieldsSteps(): \Tests\Support\Step\AuthRequiredFieldsSteps
    {
        return new \Tests\Support\Step\AuthRequiredFieldsSteps($this);
    }

    public function adminClientProfileSteps(): \Tests\Support\Step\AdminClientProfileSteps
    {
        return new \Tests\Support\Step\AdminClientProfileSteps($this);
    }

    public function accountRemindRestorePage(): Page\AccountRemindRestorePage
    {
        return new Page\AccountRemindRestorePage($this);
    }

    public function adminDbLogPage(): Page\AdminDbLogPage
    {
        return new Page\AdminDbLogPage($this);
    }

    public function adminOrderBookingPage(): Page\AdminOrderBookingPage
    {
        return new Page\AdminOrderBookingPage($this);
    }

    public function adminOrdersPage(): Page\AdminOrdersPage
    {
        return new Page\AdminOrdersPage($this);
    }

    public function bookingCalendarPage(): Page\BookingCalendarPage
    {
        return new Page\BookingCalendarPage($this);
    }

    public function consultationMakePage(): Page\ConsultationMakePage
    {
        return new Page\ConsultationMakePage($this);
    }

    public function itemViewPage(): Page\ItemViewPage
    {
        return new Page\ItemViewPage($this);
    }

    public function orderNeighborPage(): Page\OrderNeighborPage
    {
        return new Page\OrderNeighborPage($this);
    }

    public function orderViewBookingPage(): Page\OrderViewBookingPage
    {
        return new Page\OrderViewBookingPage($this);
    }

    public function registrationHelpMakePage(): Page\RegistrationHelpMakePage
    {
        return new Page\RegistrationHelpMakePage($this);
    }

    public function tariffChangePage(): Page\TariffChangePage
    {
        return new Page\TariffChangePage($this);
    }

    public function cabinetBalancePage(): Page\CabinetBalancePage
    {
        return new Page\CabinetBalancePage($this);
    }

    public function tariffShowcasePage(): Page\TariffShowcasePage
    {
        return new Page\TariffShowcasePage($this);
    }

    public function tariffViewPage(): Page\TariffViewPage
    {
        return new Page\TariffViewPage($this);
    }

    /**
     * Same-origin GET from the already opened app page (WebDriver).
     */
    public function grabSameOriginGet(string $path): string
    {
        return (string) $this->executeJS(
            'var xhr = new XMLHttpRequest();'
            . 'xhr.open("GET", arguments[0], false);'
            . 'xhr.send("");'
            . 'return String(xhr.status) + "\\n" + String(xhr.responseText || "");',
            [$path]
        );
    }

    /**
     * Record executable evidence for one acceptance criterion.
     */
    public function recordAcceptanceCriterion(string $id, bool $passed, string $evidence): void
    {
        $file = getenv('QA_AC_RESULTS_FILE');
        if ($file === false || $file === '') {
            throw new \RuntimeException('QA_AC_RESULTS_FILE is not configured');
        }

        $payload = ['results' => []];
        if (is_file($file)) {
            $decoded = json_decode((string) file_get_contents($file), true);
            if (is_array($decoded) && is_array($decoded['results'] ?? null)) {
                $payload = $decoded;
            }
        }
        $payload['results'][] = [
            'id' => $id,
            'status' => $passed ? 'passed' : 'failed',
            'evidence' => $evidence,
        ];
        file_put_contents($file, json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT) . PHP_EOL, LOCK_EX);

        if (!$passed) {
            $this->fail(sprintf('Acceptance criterion %s failed: %s', $id, $evidence));
        }
    }

    /**
     * Удаление строк из БД через PDO модуля Db (Actor::getModule в этой сборке нет).
     *
     * @param array<string, scalar|null> $criteria
     */
    public function deleteFromDatabase(string $table, array $criteria): void
    {
        $modules = $this->getScenario()->current('modules');
        if (!is_array($modules) || !isset($modules['Db']) || !is_object($modules['Db'])) {
            throw new \RuntimeException('Db module is not available');
        }
        /** @var \Codeception\Module\Db $db */
        $db = $modules['Db'];
        $dbh = $db->_getDbh();
        if ($criteria === []) {
            throw new \InvalidArgumentException('deleteFromDatabase: criteria пустой');
        }
        $parts = [];
        $params = [];
        $i = 0;
        foreach ($criteria as $col => $val) {
            $key = ':p' . $i;
            if ($val === null) {
                $parts[] = '`' . str_replace('`', '``', (string) $col) . '` IS NULL';
            } else {
                $parts[] = '`' . str_replace('`', '``', (string) $col) . '` = ' . $key;
                $params[$key] = $val;
            }
            $i++;
        }
        $sql = 'DELETE FROM `' . str_replace('`', '``', $table) . '` WHERE ' . implode(' AND ', $parts);
        $stmt = $dbh->prepare($sql);
        $stmt->execute($params);
    }

    public function grabLatestSecLogData(string $action): string
    {
        $modules = $this->getScenario()->current('modules');
        if (!is_array($modules) || !isset($modules['Db']) || !is_object($modules['Db'])) {
            throw new \RuntimeException('Db module is not available');
        }
        /** @var \Codeception\Module\Db $db */
        $db = $modules['Db'];
        $stmt = $db->_getDbh()->prepare(
            'SELECT data FROM ct_sec_log WHERE action = :action ORDER BY id DESC LIMIT 1'
        );
        $stmt->execute([':action' => $action]);
        $value = $stmt->fetchColumn();

        return $value === false ? '' : (string) $value;
    }
}

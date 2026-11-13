<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Гостевые экраны восстановления пароля: /account/remind и /account/remind/{hash}.
 *
 * Контракт: .doc/qa/flows/account-restore-password.md
 * Задача: CT-2601 (runSend / спиннер до сообщения).
 *
 * data-test на форме нет. Селекторы: id контейнера Vue, BEM form-forgot,
 * класс ajaxloaded. Шаблоны не правим.
 */
final class AccountRemindRestorePage extends BasePage
{
    public const URL_REMIND = '/account/remind';

    public const TITLE_REMIND = 'Восстановление пароля';
    public const TITLE_RESTORE = 'Изменение пароля';
    public const BTN_SEND = 'Отправить';
    public const BTN_NEXT = 'Дальше';

    public const MSG_INVALID_EMAIL = 'Поле должно быть электронным адресом';
    public const MSG_UNKNOWN_EMAIL = 'Пользователь с таким e-mail не зарегистрирован!';
    public const MSG_PASSWORDS_MISMATCH = 'Пароли не совпадают';
    public const MSG_LETTER_SENT = 'Письмо с ссылкой для восстановления пароля отправлено на вашу почту';
    public const MSG_RESTORE_OK = 'Смена пароля прошла успешно';
    public const MSG_404 = 'Извините, страница не найдена';

    public const TABLE_RESTORE = 'ct_restorePassword';

    private const REMIND_ROOT = '//*[@id="vue-remind-container"]';
    private const RESTORE_ROOT = '//*[@id="vue-restore-container"]';
    private const EMAIL_INPUT = '//input[@name="email"]';
    private const PASS1 = '//input[@name="newpass1"]';
    private const PASS2 = '//input[@name="newpass2"]';
    private const SEND_REMIND = self::REMIND_ROOT
        . '//button[contains(@class,"form-forgot__btn") and contains(normalize-space(.),"Отправить")]';
    private const SEND_RESTORE = self::RESTORE_ROOT
        . '//button[contains(@class,"form-forgot__btn") and contains(normalize-space(.),"Отправить")]';
    private const SPINNER_REMIND = self::REMIND_ROOT . '//*[contains(@class,"ajaxloaded")]';
    private const SPINNER_RESTORE = self::RESTORE_ROOT . '//*[contains(@class,"ajaxloaded")]';
    private const SIGNIN_FORM = 'login-form';
    private const NOTFOUND = '//*[contains(@class,"notfound")]';

    public function openRemind(): void
    {
        $this->I->amOnPage(self::URL_REMIND);
        $this->waitRemindVue();
        $this->I->see(self::TITLE_REMIND);
        $this->seeOnRemindUrl();
    }

    public function openRestore(string $hash): void
    {
        $this->I->amOnPage(self::URL_REMIND . '/' . $hash);
        $this->waitRestoreVue();
        $this->I->see(self::TITLE_RESTORE);
        $this->seeOnRestoreUrl($hash);
    }

    public function openUnknownHashExpect404(string $hash): void
    {
        $this->I->amOnPage(self::URL_REMIND . '/' . $hash);
        $this->I->waitForElement(self::NOTFOUND, 20);
        $this->I->see(self::MSG_404);
        $this->I->dontSee(self::TITLE_RESTORE);
        $this->I->dontSee(self::TITLE_REMIND);
    }

    public function openSigninNeighbor(): void
    {
        $this->I->amOnPage('/account/signin');
        $this->I->waitForElement(self::test(self::SIGNIN_FORM), 20);
    }

    public function openRemindWhileLoggedInExpectItemMain(): void
    {
        $this->I->amOnPage(self::URL_REMIND);
        $this->I->waitForElement(self::test('item-main'), 20);
        $this->I->seeInCurrentUrl('/item/main');
        $this->I->dontSee(self::TITLE_REMIND);
    }

    public function reloadRemind(): void
    {
        $this->I->reloadPage();
        $this->waitRemindVue();
        $this->I->see(self::TITLE_REMIND);
        $this->seeOnRemindUrl();
    }

    public function bypassCaptchaRemind(): void
    {
        $this->setVueFlags('#vue-remind-container');
    }

    public function bypassCaptchaRestore(): void
    {
        $this->setVueFlags('#vue-restore-container');
    }

    public function fillEmail(string $email): void
    {
        $this->I->waitForElement(self::EMAIL_INPUT, 10);
        $this->I->fillField(self::EMAIL_INPUT, $email);
    }

    public function fillNewPasswords(string $pass1, string $pass2): void
    {
        $this->I->waitForElement(self::PASS1, 10);
        $this->I->fillField(self::PASS1, $pass1);
        $this->I->fillField(self::PASS2, $pass2);
    }

    public function submitRemind(): void
    {
        $this->I->click(self::SEND_REMIND);
    }

    public function submitRestore(): void
    {
        $this->I->click(self::SEND_RESTORE);
    }

    public function seeRemindSubmit(): void
    {
        $this->I->waitForElement(self::SEND_REMIND, 10);
    }

    public function seeRestoreSubmit(): void
    {
        $this->I->waitForElement(self::SEND_RESTORE, 10);
    }

    public function seeRemindSpinner(): void
    {
        $this->I->waitForElement(self::SPINNER_REMIND, 10);
        $this->I->dontSeeElement(self::SEND_REMIND);
    }

    public function seeRestoreSpinner(): void
    {
        $this->I->waitForElement(self::SPINNER_RESTORE, 10);
        $this->I->dontSeeElement(self::SEND_RESTORE);
    }

    public function seeOnRemindUrl(): void
    {
        $this->I->seeInCurrentUrl(self::URL_REMIND);
        $this->I->dontSeeInCurrentUrl('/item/main');
        $this->I->dontSeeElement(self::NOTFOUND);
    }

    public function seeOnRestoreUrl(string $hash): void
    {
        $this->I->seeInCurrentUrl(self::URL_REMIND . '/' . $hash);
        $this->I->dontSeeElement(self::NOTFOUND);
    }

    public function seeInvalidEmailMessage(): void
    {
        $this->I->waitForText(self::MSG_INVALID_EMAIL, 10);
        $this->I->dontSeeElement(self::SPINNER_REMIND);
        $this->seeRemindSubmit();
        $this->seeOnRemindUrl();
    }

    public function seeUnknownEmailError(): void
    {
        $this->I->waitForText(self::MSG_UNKNOWN_EMAIL, 20);
        $this->seeOnRemindUrl();
        $this->seeRemindSubmit();
        $this->I->dontSeeElement(self::SPINNER_REMIND);
    }

    public function seePasswordMismatch(): void
    {
        $this->I->waitForText(self::MSG_PASSWORDS_MISMATCH, 10);
        $this->I->dontSeeElement(self::SPINNER_RESTORE);
        $this->seeRestoreSubmit();
    }

    public function seeLetterSentStayingOnRemind(): void
    {
        $this->I->waitForText(self::MSG_LETTER_SENT, 20);
        $this->I->see(self::BTN_NEXT);
        $this->I->dontSeeElement(self::SPINNER_REMIND);
        $this->I->dontSeeElement(self::SEND_REMIND);
        $this->seeOnRemindUrl();
    }

    public function seeRestoreOkStayingOnHash(string $hash): void
    {
        $this->I->waitForText(self::MSG_RESTORE_OK, 20);
        $this->I->see(self::BTN_NEXT);
        $this->I->dontSeeElement(self::SPINNER_RESTORE);
        $this->seeOnRestoreUrl($hash);
    }

    public function seeEnvTimeoutExposed(): void
    {
        $timeout = $this->I->executeJS(
            'return window.emailVerificationSettings && window.emailVerificationSettings.timeout;'
        );
        $this->I->assertTrue(
            is_numeric($timeout) && (int) $timeout > 0,
            'CLIENT_EMAIL_VERIFICATION_TIMEOUT must be on the page'
        );
    }

    public function mockForgotThenPollSuccess(int $ajaxMs, int $pollMs): void
    {
        $this->I->executeJS(
            'var ajaxMs = arguments[0]; var pollMs = arguments[1];'
            . 'window.Services.Account.forgot_password = function (data) {'
            . '  var d = window.jQuery.Deferred();'
            . '  window.setTimeout(function () {'
            . '    d.resolve({ status: 1, data: { clientId: "1", email: data.email } });'
            . '  }, ajaxMs);'
            . '  return d;'
            . '};'
            . 'window.AccountEmailStatusPoll.callWithIntervalAndTimeout = function () {'
            . '  return new Promise(function (resolve) {'
            . '    window.setTimeout(function () { resolve(true); }, pollMs);'
            . '  });'
            . '};'
            . 'return true;',
            [$ajaxMs, $pollMs]
        );
    }

    public function mockChangePasswordThenPollSuccess(int $ajaxMs, int $pollMs): void
    {
        $this->I->executeJS(
            'var ajaxMs = arguments[0]; var pollMs = arguments[1];'
            . 'window.Services.Account.remind_change_password = function () {'
            . '  var d = window.jQuery.Deferred();'
            . '  window.setTimeout(function () {'
            . '    d.resolve({ status: 1, data: { clientId: "1", email: "test+local-client1@seyfer.pro" } });'
            . '  }, ajaxMs);'
            . '  return d;'
            . '};'
            . 'window.AccountEmailStatusPoll.callWithIntervalAndTimeout = function () {'
            . '  return new Promise(function (resolve) {'
            . '    window.setTimeout(function () { resolve(true); }, pollMs);'
            . '  });'
            . '};'
            . 'return true;',
            [$ajaxMs, $pollMs]
        );
    }

    public function wrapRealForgotPassword(): void
    {
        $this->I->executeJS(
            'window.__ct2601Forgot = { called: false, failed: false, status: null };'
            . 'var orig = window.Services.Account.forgot_password;'
            . 'window.Services.Account.forgot_password = function (data) {'
            . '  window.__ct2601Forgot.called = true;'
            . '  var req = orig.call(window.Services.Account, data);'
            . '  req.fail(function () {'
            . '    window.__ct2601Forgot.failed = true;'
            . '    window.__ct2601Forgot.status = req.status;'
            . '  });'
            . '  return req;'
            . '};'
            . 'return true;'
        );
    }

    public function seeForgotPasswordWasCalledAndFailed(): void
    {
        $this->I->waitForJS(
            'return !!(window.__ct2601Forgot && window.__ct2601Forgot.called && window.__ct2601Forgot.failed);',
            20
        );
    }

    public function seeRunSendTrueRemind(): void
    {
        $flag = $this->I->executeJS(
            'var el = document.querySelector("#vue-remind-container");'
            . 'return !!(el && el.__vue__ && el.__vue__.runSend);'
        );
        $this->I->assertTrue((bool) $flag, 'runSend must stay true while waiting');
    }

    public function seedRestoreHash(string $hash, int $clientId = 1, int $ttlSeconds = 600): void
    {
        $expires = date('Y-m-d H:i:s', time() + $ttlSeconds);
        $this->I->haveInDatabase(self::TABLE_RESTORE, [
            'clientId' => $clientId,
            'hash'     => $hash,
            'expires'  => $expires,
        ]);
        $this->I->seeInDatabase(self::TABLE_RESTORE, [
            'clientId' => $clientId,
            'hash'     => $hash,
        ]);
    }

    /**
     * Реальный POST account/change_password (не mock).
     * Poll статуса письма подменяется, иначе UI ждёт почтовый канал.
     */
    public function restorePasswordViaRealApi(string $hash, string $newPassword): void
    {
        $this->openRestore($hash);
        $this->bypassCaptchaRestore();
        $this->I->executeJS(
            'window.AccountEmailStatusPoll.callWithIntervalAndTimeout = function () {'
            . '  return Promise.resolve(true);'
            . '};'
            . 'return true;'
        );
        $this->fillNewPasswords($newPassword, $newPassword);
        $this->submitRestore();
        $this->seeRestoreOkStayingOnHash($hash);
    }

    private function waitRemindVue(): void
    {
        $this->I->waitForJS(
            'var el = document.querySelector("#vue-remind-container");'
            . 'return !!(el && el.__vue__);',
            20
        );
        $this->I->waitForElement(self::SEND_REMIND, 10);
    }

    private function waitRestoreVue(): void
    {
        $this->I->waitForJS(
            'var el = document.querySelector("#vue-restore-container");'
            . 'return !!(el && el.__vue__);',
            20
        );
        $this->I->waitForElement(self::SEND_RESTORE, 10);
    }

    private function setVueFlags(string $cssId): void
    {
        $ok = $this->I->executeJS(
            'var el = document.querySelector(arguments[0]);'
            . 'if (!el || !el.__vue__) { return "no-vue"; }'
            . 'el.__vue__.disableCaptcha = true;'
            . 'el.__vue__.captcha = el.__vue__.captcha || {};'
            . 'el.__vue__.captcha.response = "qa-captcha";'
            . 'return "ok";',
            [$cssId]
        );
        $this->I->assertSame('ok', $ok, 'Vue root not ready for captcha bypass');
    }
}

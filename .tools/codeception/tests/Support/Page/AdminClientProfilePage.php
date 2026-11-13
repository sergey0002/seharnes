<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Админка: профиль клиента, блок "Основные параметры" (логин = email).
 *
 * Контракт: .doc/qa/flows/admin-client-login.md
 * Задача: CT-2597.
 *
 * data-test на поле логина нет. Селекторы: id контейнера Vue, name=email,
 * текст спойлера и кнопки Сохранить. Шаблоны не правим.
 */
final class AdminClientProfilePage extends BasePage
{
    public const TITLE_ACCOUNT = 'Параметры учетной записи';
    public const SPOILER_GENERAL = 'Основные параметры';
    public const LABEL_LOGIN = 'Логин:';
    public const BTN_SAVE = 'Сохранить';
    public const TOAST_ACCOUNT = 'Изменены параметры учетной записи';
    public const TOAST_NONE = 'Нет изменений';
    public const ERR_EXISTING_EMAIL = 'Пользователь с таким e-mail уже существует!';
    public const ERR_UNEXPECTED = 'Произошла непредвиденная ошибка, пожалуйста обратитесь в службу техподдержки';
    public const ERR_MODAL_TITLE = 'Ошибка';

    private const ROOT_ID = 'vue-profile-edit-container';
    private const SPOILER = '//div[contains(@class,"old-spoiler") and contains(normalize-space(.),"Основные параметры")]';
    private const SAVE = '//div[@id="vue-profile-edit-container"]//div[contains(@class,"spoiler-container")]/button[@type="button" and contains(normalize-space(.),"Сохранить")]';
    private const EMAIL_INPUT = '//div[@id="vue-profile-edit-container"]//input[@name="email"]';

    public function open(int $clientId): void
    {
        $this->I->amOnPage('/admin/m_router.php?q=client/edit/' . $clientId);
        $this->I->waitForText(self::TITLE_ACCOUNT, 25);
        $this->waitFormReady();
        $this->installXhrProbe();
    }

    public function openGeneralParams(): void
    {
        $this->I->waitForElement(self::SPOILER, 15);
        $this->I->click(self::SPOILER);
        $this->I->waitForText(self::LABEL_LOGIN, 10);
        $this->I->waitForElementVisible(self::EMAIL_INPUT, 10);
    }

    public function setLogin(string $email): void
    {
        $ok = $this->I->executeJS(
            'var root = document.getElementById("' . self::ROOT_ID . '");'
            . 'var vm = root && root.__vue__ ? root.__vue__ : null;'
            . 'if (!vm || !vm.form || !vm.form.client) { return false; }'
            . 'if (vm.$set) { vm.$set(vm.form.client, "email", arguments[0]); }'
            . 'else { vm.form.client.email = arguments[0]; }'
            . 'var input = document.evaluate('
            . '\'//*[@id="' . self::ROOT_ID . '"]//input[@name="email"]\','
            . ' document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null'
            . ').singleNodeValue;'
            . 'if (input) {'
            . '  input.value = arguments[0];'
            . '  input.dispatchEvent(new Event("input", { bubbles: true }));'
            . '  input.dispatchEvent(new Event("change", { bubbles: true }));'
            . '}'
            . 'return true;',
            [$email]
        );
        $this->I->assertTrue((bool) $ok, 'Vue form.client.email не найден');
    }

    public function grabLogin(): string
    {
        $value = $this->I->executeJS(
            'var root = document.getElementById("' . self::ROOT_ID . '");'
            . 'var vm = root && root.__vue__ ? root.__vue__ : null;'
            . 'if (!vm || !vm.form || !vm.form.client) { return ""; }'
            . 'return String(vm.form.client.email || "");'
        );

        return is_string($value) ? $value : '';
    }

    public function save(): void
    {
        $this->resetXhrLog();
        $this->I->click(self::SAVE);
        $this->I->waitForJS(
            'var root = document.getElementById("' . self::ROOT_ID . '");'
            . 'var vm = root && root.__vue__ ? root.__vue__ : null;'
            . 'return !!(vm && vm.runAjax === false);',
            20
        );
    }

    public function seeAccountSavedToast(): void
    {
        $this->I->waitForText(self::TOAST_ACCOUNT, 15);
        $this->I->see(self::TOAST_ACCOUNT);
    }

    public function seeNoChangesToast(): void
    {
        $this->I->waitForText(self::TOAST_NONE, 15);
        $this->I->see(self::TOAST_NONE);
    }

    public function seeExistingEmailError(): void
    {
        $this->I->waitForText(self::ERR_MODAL_TITLE, 15);
        $this->I->see(self::ERR_EXISTING_EMAIL);
    }

    public function dontSeeUnexpectedSuccess(): void
    {
        $this->I->dontSee(self::TOAST_ACCOUNT);
        $this->I->dontSee(self::ERR_UNEXPECTED);
    }

    public function seeEmailClientValidate(): void
    {
        $has = $this->I->executeJS(
            'var root = document.getElementById("' . self::ROOT_ID . '");'
            . 'var vm = root && root.__vue__ ? root.__vue__ : null;'
            . 'if (!vm || !vm.validateErrors) { return false; }'
            . 'return !!vm.validateErrors.has("email");'
        );
        $this->I->assertTrue((bool) $has, 'vee-validate по полю email не сработал');
    }

    public function seeAdminSaveProfileRequest(): void
    {
        $this->I->waitForJS(
            'var log = window.__ctAdminXhrLog || [];'
            . 'for (var i = 0; i < log.length; i++) {'
            . '  if (String(log[i].url || "").indexOf("AdminSaveProfile") !== -1) { return true; }'
            . '}'
            . 'return false;',
            15
        );
    }

    public function dontSeeAdminSaveProfileRequest(): void
    {
        $hit = $this->I->executeJS(
            'var log = window.__ctAdminXhrLog || [];'
            . 'for (var i = 0; i < log.length; i++) {'
            . '  if (String(log[i].url || "").indexOf("AdminSaveProfile") !== -1) { return true; }'
            . '}'
            . 'return false;'
        );
        $this->I->assertFalse((bool) $hit, 'POST profile/AdminSaveProfile не должен уходить');
    }

    public function seeGuestBlocked(): void
    {
        $this->I->dontSee(self::TITLE_ACCOUNT);
        $this->I->seeElement(self::test('login-form'));
    }

    private function waitFormReady(): void
    {
        $this->I->waitForJS(
            'var root = document.getElementById("' . self::ROOT_ID . '");'
            . 'var vm = root && root.__vue__ ? root.__vue__ : null;'
            . 'return !!(vm && vm.init && vm.init_form && vm.form && vm.form.client);',
            25
        );
    }

    private function installXhrProbe(): void
    {
        $this->I->executeJS(
            'if (window.__ctAdminXhrProbeInstalled) { window.__ctAdminXhrLog = []; return; }'
            . 'window.__ctAdminXhrLog = [];'
            . 'window.__ctAdminXhrProbeInstalled = true;'
            . 'var open = XMLHttpRequest.prototype.open;'
            . 'XMLHttpRequest.prototype.open = function(method, url) {'
            . '  this.__ctUrl = url;'
            . '  return open.apply(this, arguments);'
            . '};'
            . 'var send = XMLHttpRequest.prototype.send;'
            . 'XMLHttpRequest.prototype.send = function() {'
            . '  var xhr = this;'
            . '  xhr.addEventListener("loadend", function() {'
            . '    window.__ctAdminXhrLog.push({url: xhr.__ctUrl || "", status: xhr.status});'
            . '  });'
            . '  return send.apply(this, arguments);'
            . '};'
        );
    }

    private function resetXhrLog(): void
    {
        $this->I->executeJS('window.__ctAdminXhrLog = [];');
    }
}

<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * /account/signin. Селекторы data-test login-form* уже в шаблоне
 * (qa/flows/account-signin.md). Новые data-test не добавляем.
 */
final class SigninPage extends AccountGuestFormPage
{
    public const URL = '/account/signin';

    private const FORM = 'login-form';
    private const EMAIL = 'login-form__email';
    private const PASS = 'login-form__pass';
    private const SUBMIT = 'login-form__submit';
    private const ID_TOGGLE = '.signin-btn-id-toggle';
    private const ID_MENU = '#signin-mobile-id-list';
    private const ID_SIDEBAR = '.signin-sidebar-id-col';

    public function open(): void
    {
        $this->ensureGuest();
        $this->I->wait(1);
        $this->I->amOnPage(self::URL);
        $this->I->waitForElement(self::test(self::FORM), 20);
        $this->I->waitForElementVisible(self::test(self::FORM), 20);
        $this->I->see('Вход');
        $this->installXhrProbe();
        $this->dropCaptchaConsoleNoise();
    }

    public function submitCredentials(string $email, string $password): void
    {
        $this->open();
        $this->I->fillField(self::testIn(self::FORM, self::EMAIL), $email);
        $this->I->fillField(self::testIn(self::FORM, self::PASS), $password);
        $this->I->click(self::test(self::SUBMIT));
        $this->I->wait(2);
    }

    public function loginWithPassword(string $email, string $password): void
    {
        $this->submitCredentials($email, $password);
        $this->I->waitForElement(self::test('item-main'), 25);
        $this->I->see('Мои регистрации', self::test('item-main__title'));
    }

    /**
     * Чекбокс "Запомнить" без data-test: класс form-signin-remember и модель Vue form.memento.
     * Шаблоны не правим.
     */
    public function loginRemembering(string $email, string $password, bool $remember): void
    {
        $this->open();
        $this->I->fillField(self::testIn(self::FORM, self::EMAIL), $email);
        $this->I->fillField(self::testIn(self::FORM, self::PASS), $password);
        $set = $this->I->executeJS(
            'var box = document.querySelector(".form-signin-remember input[type=checkbox]");'
            . 'if (!box) { return false; }'
            . 'var root = document.getElementById("vue-signin-container");'
            . 'var vm = root && root.__vue__ ? root.__vue__ : null;'
            . 'if (vm && vm.form) { vm.form.memento = arguments[0] ? 1 : ""; }'
            . 'box.checked = !!arguments[0];'
            . 'return true;',
            [$remember]
        );
        $this->I->assertTrue((bool) $set, 'чекбокс Запомнить не найден');
        $this->I->click(self::test(self::SUBMIT));
        $this->I->waitForElement(self::test('item-main'), 25);
        $this->I->see('Мои регистрации', self::test('item-main__title'));
    }

    public function seeCabinet(): void
    {
        $this->I->waitForElement(self::test('item-main'), 25);
        $this->I->see('Мои регистрации', self::test('item-main__title'));
    }

    public function seeLoginRejected(): void
    {
        $this->I->seeInCurrentUrl('/account/signin');
        $this->I->seeElement(self::test(self::FORM));
        $this->I->dontSeeElement(self::test('item-main'));
    }

    public function seeLoginFormContract(): void
    {
        $this->I->seeElement(self::testIn(self::FORM, self::EMAIL));
        $this->I->seeElement(self::testIn(self::FORM, self::PASS));
        $this->I->seeElement(self::testIn(self::FORM, self::SUBMIT));
        $this->I->see('E-mail');
        $this->I->see('Пароль');
        $this->I->see('Войти');
    }

    public function seeRequiredStars(): void
    {
        $this->seeRequiredStar('E-mail');
        $this->seeRequiredStar('Пароль');
        $this->seeRequiredStar('Защитный код');
    }

    public function seeVueNotHtml5Required(): void
    {
        $this->seeNoNativeHtml5Required('[data-test="login-form"]');
        $hasRules = $this->I->executeJS(
            'var root = document.getElementById("vue-signin-container");'
            . 'var vm = root && root.__vue__ ? root.__vue__ : null;'
            . 'if (!vm || !vm.$validator) { return false; }'
            . 'var bag = vm.$validator;'
            . 'return !!(bag.fields && (bag.fields.items || bag.fields).length !== 0 || bag.errors);'
        );
        $this->I->assertTrue((bool) $hasRules, 'Vue $validator на signin не найден');
    }

    public function submitEmpty(): void
    {
        $this->I->click(self::test(self::SUBMIT));
        $this->I->wait(1);
    }

    public function seeEmptySubmitBlocked(): void
    {
        $this->submitEmpty();
        $this->I->seeInCurrentUrl('/account/signin');
        $this->I->seeElement(self::test(self::FORM));
        $this->I->see(self::REQUIRED_MESSAGE);
        $this->dontSeeXhrUrlPart('oauth/login');
        $this->dontSeeXhrUrlPart('account/registration');
    }

    public function seeDesktopIdLayout(): void
    {
        $this->I->resizeWindow(1425, 900);
        $this->openForLayoutTest();
        $this->assertIdButtonsMatchClients(self::ID_SIDEBAR);
        $this->I->dontSeeElement(self::ID_TOGGLE);
    }

    public function seeMobileIdMenuToggle(): void
    {
        $this->I->resizeWindow(320, 800);
        $this->openForLayoutTest();
        $this->I->waitForElementVisible(self::ID_TOGGLE, 20);
        $this->I->dontSeeElement(self::ID_MENU);
        $this->I->click(self::ID_TOGGLE);
        $this->I->waitForElementVisible(self::ID_MENU, 5);
        $this->assertIdButtonsMatchClients(self::ID_MENU);
        $this->I->click(self::ID_TOGGLE);
        $this->I->waitForElementNotVisible(self::ID_MENU, 5);
    }

    private function openForLayoutTest(): void
    {
        $this->I->amOnPage(self::URL);
        $this->I->waitForElement(self::test(self::FORM), 20);
        $this->I->waitForElementVisible(self::test(self::FORM), 20);
    }

    private function assertIdButtonsMatchClients(string $container): void
    {
        $actual = $this->I->executeJS(
            'return Array.prototype.map.call(document.querySelectorAll(arguments[0] + " .signin-id-btn"), function (node) {'
            . ' return (node.textContent || "").replace(/\s+/g, " ").trim();'
            . '});',
            [$container]
        );
        $expected = $this->I->executeJS(
            'var root = document.getElementById("vue-signin-container");'
            . 'var vm = root && root.__vue__ ? root.__vue__ : null;'
            . 'var labels = {sber:"СБЕР ID", tbank:"Т-БАНК ID", yandex:"ЯНДЕКС ID", mts:"МТС ID", vk:"ВК ID"};'
            . 'return vm ? vm.idClients.map(function (client) { return labels[client.name]; }) : [];'
        );
        if (is_object($actual)) {
            $actual = json_decode((string) json_encode($actual), true);
        }
        if (is_object($expected)) {
            $expected = json_decode((string) json_encode($expected), true);
        }
        $this->I->assertSame($expected, $actual, 'ID-кнопки должны совпадать с активными window.clients');
    }
}

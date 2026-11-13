<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * /account/signup. data-test на форме нет (шаблоны не правим).
 * Селекторы: BEM form-signup / form-signup__btn и текст лейблов.
 * Контракт: .doc/qa/flows/account-signup.md
 */
final class SignupPage extends AccountGuestFormPage
{
    public const URL = '/account/signup';

    private const FORM = '//form[contains(@class,"form-signup")]';
    private const SUBMIT = '//button[contains(@class,"form-signup__btn")]';
    private const EMAIL_INPUT = '//form[contains(@class,"form-signup")]//input[@name="email"]';
    private const PASS_INPUT = '//form[contains(@class,"form-signup")]//input[@name="pass"]';
    private const PASS2_INPUT = '//form[contains(@class,"form-signup")]//input[@name="pass2"]';

    public function open(): void
    {
        $this->ensureGuest();
        $this->I->amOnPage(self::URL);
        $this->I->waitForElement(self::FORM, 20);
        $this->I->waitForElementVisible(self::FORM, 20);
        $this->I->see('Регистрация');
        $this->installXhrProbe();
        $this->dropCaptchaConsoleNoise();
    }

    public function seeSignupFormContract(): void
    {
        $this->I->seeElement(self::EMAIL_INPUT);
        $this->I->seeElement(self::PASS_INPUT);
        $this->I->seeElement(self::PASS2_INPUT);
        $this->I->see('E-mail');
        $this->I->see('Пароль');
        $this->I->see('Повторите пароль');
        $this->I->see('ПРОМО-код');
    }

    public function seeRequiredStars(): void
    {
        $this->seeRequiredStar('E-mail');
        $this->seeRequiredStar('Пароль');
        $this->seeRequiredStar('Повторите пароль');
        $this->seeRequiredStar('Защитный код');
    }

    public function seeOptionalFieldsHaveNoStar(): void
    {
        $this->dontSeeRequiredStar('ПРОМО-код');
        $info = $this->grabLabelStar('Я принимаю условия');
        $this->I->assertTrue(is_array($info), 'чекбокс соглашения не найден');
        $this->I->assertTrue(
            strpos((string) $info['className'], 'require-lable') === false,
            'require-lable не должен висеть на соглашении'
        );
    }

    public function seeVueNotHtml5Required(): void
    {
        $this->seeNoNativeHtml5Required('form.form-signup');
        $ok = $this->I->executeJS(
            'var root = document.querySelector("#vue-signup-container");'
            . 'var vm = root && root.__vue__ ? root.__vue__ : null;'
            . 'if (!vm) {'
            . '  var all = document.querySelectorAll("*");'
            . '  for (var i = 0; i < all.length; i++) {'
            . '    if (all[i].__vue__ && all[i].__vue__.submitForm) { vm = all[i].__vue__; break; }'
            . '  }'
            . '}'
            . 'return !!(vm && vm.$validator);'
        );
        $this->I->assertTrue((bool) $ok, 'Vue $validator на signup не найден');
    }

    public function seeSubmitDisabledWhilePristine(): void
    {
        $disabled = $this->I->executeJS(
            'var btn = document.querySelector("button.form-signup__btn");'
            . 'return !!(btn && btn.disabled);'
        );
        $this->I->assertTrue((bool) $disabled, 'кнопка Отправить должна быть disabled на пустой форме');
    }

    public function forceSubmitClick(): void
    {
        $this->I->executeJS(
            'var btn = document.querySelector("button.form-signup__btn");'
            . 'if (btn) { btn.click(); }'
        );
        $this->I->wait(1);
    }

    public function seeEmptySubmitBlocked(): void
    {
        $this->seeSubmitDisabledWhilePristine();
        $this->forceSubmitClick();
        $this->I->seeInCurrentUrl('/account/signup');
        $this->I->seeElement(self::FORM);
        $this->dontSeeXhrUrlPart('account/registration');
        $this->dontSeeXhrUrlPart('oauth/login');
    }

    public function touchEmptyFieldsAndSeeVueErrors(): void
    {
        foreach (['email', 'pass', 'pass2'] as $name) {
            $this->I->executeJS(
                'var el = document.querySelector("form.form-signup input[name=\\"" + arguments[0] + "\\"]");'
                . 'if (!el) { return; }'
                . 'el.focus();'
                . 'el.dispatchEvent(new Event("input", {bubbles:true}));'
                . 'el.dispatchEvent(new Event("blur", {bubbles:true}));',
                [$name]
            );
        }
        $this->I->wait(1);
        $this->I->see(self::REQUIRED_MESSAGE);
        $this->seeEmptySubmitBlocked();
    }
}

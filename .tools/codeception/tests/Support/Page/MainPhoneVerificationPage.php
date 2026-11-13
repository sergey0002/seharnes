<?php

declare(strict_types=1);

namespace Tests\Support\Page;

final class MainPhoneVerificationPage extends BasePage
{
    private const SPOILER = '//div[contains(@class,"spoiler") and contains(.,"телефонного номера")]';
    private const CONFIRM = '//button[contains(@class,"btn-confirm-phone")]';
    private const CHANGE = '//button[contains(@class,"btn-change-phone")]';
    private const CODE = 'input.code-input';
    private const CANCEL = 'a.btn-cancel-verify';

    public function scrollToSpoiler(): void
    {
        $this->I->executeJS('var el = document.evaluate(\'//div[contains(@class,"spoiler") and contains(.,"телефонного номера")]\', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue; if (el) el.scrollIntoView({behavior: "instant", block: "start"});');
    }

    public function open(): void
    {
        $this->I->amOnPage('/account/edit');
        $this->scrollToSpoiler();
        $this->I->click(self::SPOILER);
        $this->I->waitForText('Основной телефон', 20);
        $this->scrollToSpoiler();
    }

    public function seeIdle(string $instruction): void
    {
        $this->I->waitForElement(self::CONFIRM, 15);
        $this->scrollToSpoiler();
        $this->I->see('Не подтвержден');
        $this->I->see($instruction);
    }

    public function installTelegramFixture(): void
    {
        $this->I->executeJS(
            'var nodes = document.querySelectorAll("*");'
            . 'for (var i = 0; i < nodes.length; i++) {'
            . ' var component = nodes[i].__vue__;'
            . ' if (component && component.$options && component.$options._componentTag === "account-change-main-phone") {'
            . '  component.provider = 2; component.scheme = 0;'
            . '  component.$emit = function () {};'
            . '  break;'
            . ' }'
            . '}'
            . 'window.Services.Account.sendMainPhoneCode = function () {'
            . ' return $.Deferred().resolve({success:true, verificationId:2078, provider:2, scheme:null, callTimeoutSec:60}).promise();'
            . '};'
            . 'window.Services.Account.verifyMainPhone = function (data) {'
            . ' window.__ct2078VerifyCalls = (window.__ct2078VerifyCalls || 0) + 1;'
            . ' return $.Deferred().resolve({success:true}).promise();'
            . '};'
            . 'window.Services.Account.getPhoneVerificationDeliveryStatus = function () {'
            . ' return $.Deferred().reject({status:500}).promise();'
            . '};'
        );
    }

    public function start(): void
    {
        $this->I->click(self::CONFIRM);
    }

    public function seeActive(bool $call): void
    {
        $this->I->waitForElementVisible(self::CODE, 15);
        $this->scrollToSpoiler();
        $this->I->seeElement(self::CANCEL);
        if ($call) {
            $this->I->see('Осталось');
        } else {
            $this->I->dontSee('Осталось');
        }
    }

    public function enterCode(string $code): void
    {
        $this->I->fillField(self::CODE, $code);
    }

    public function cancel(): void
    {
        $this->I->click(self::CANCEL);
    }

    public function seeVerified(): void
    {
        $this->I->waitForElementVisible('.screen-verified', 15);
        $this->scrollToSpoiler();
        $this->I->seeElement('.account-phone-verified-text');
        $this->I->see('Ваш телефонный номер успешно подтверждён.');
        $this->I->seeElement(self::CHANGE);
    }

    public function seeVerifyRequestCount(int $expected): void
    {
        $actual = $this->I->executeJS('return window.__ct2078VerifyCalls || 0;');
        $this->I->assertSame($expected, (int)$actual);
    }
}

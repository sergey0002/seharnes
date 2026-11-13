<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * /order/registration_help: тип 2035, BookSlotStep > 0.
 *
 * Контракт: .doc/qa/flows/order-booking.md
 */
final class RegistrationHelpMakePage extends BasePage
{
    public const URL = '/order/registration_help';

    private BookingCalendarPage $calendar;

    public function __construct(\Tests\Support\AcceptanceTester $I)
    {
        parent::__construct($I);
        $this->calendar = new BookingCalendarPage($I);
    }

    public function calendar(): BookingCalendarPage
    {
        return $this->calendar;
    }

    public function open(): void
    {
        $this->I->amOnPage(self::URL);
        $this->I->waitForJS(
            'var find = ' . self::jsFindVueComponent() . ';'
            . 'return !!find("registration-help-form");',
            20
        );
    }

    public function selectDraft(int $draftId): void
    {
        $ok = $this->I->executeJS(
            'var find = ' . self::jsFindVueComponent() . ';'
            . 'var c = find("registration-help-form");'
            . 'if (!c) { return "no-form"; }'
            . 'if (!c.params) { c.params = {}; }'
            . 'var draft = {id: arguments[0], draftName: "AT draft " + arguments[0]};'
            . 'c.params.drafts = [draft];'
            . 'var list = find("order-draft-list");'
            . 'if (!list) { return "no-list"; }'
            . 'list.values = [draft];'
            . 'c.form.drafts = [arguments[0]];'
            . 'return "ok";',
            [$draftId]
        );
        $this->I->assertSame('ok', $ok, 'registration-help-form / order-draft-list не найден');
        $this->I->waitForJS(
            'var find = ' . self::jsFindVueComponent() . ';'
            . 'var list = find("order-draft-list");'
            . 'return !!(list && list.values && list.values.length > 0);',
            5
        );
    }

    public function acceptPrivacy(): void
    {
        $this->I->executeJS(
            'var find = ' . self::jsFindVueComponent() . ';'
            . 'var c = find("registration-help-form");'
            . 'if (c) { c.isCheckedPersonData = true; }'
        );
    }

    public function seeSubmitDisabled(): void
    {
        $disabled = $this->I->executeJS(
            'var el = document.evaluate(arguments[0], document, null,'
            . ' XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;'
            . 'return !!(el && el.disabled);',
            [self::test('registration-help-form__submit')]
        );
        $this->I->assertTrue((bool) $disabled, 'ЗАКАЗАТЬ 2035 должна быть недоступна');
    }

    public function seeSubmitEnabled(): void
    {
        $disabled = $this->I->executeJS(
            'var el = document.evaluate(arguments[0], document, null,'
            . ' XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;'
            . 'return !!(el && el.disabled);',
            [self::test('registration-help-form__submit')]
        );
        $this->I->assertFalse((bool) $disabled, 'ЗАКАЗАТЬ 2035 должна быть доступна');
    }

    public function submit(): void
    {
        $this->I->click(self::test('registration-help-form__submit'));
    }

    public function waitRedirectToOrderView(): int
    {
        $this->I->waitForJS(
            'return location.pathname.indexOf("/order/view/") !== -1;',
            25
        );
        $path = (string) $this->I->executeJS('return location.pathname;');
        if (!preg_match('#/order/view/(\d+)#', $path, $m)) {
            $this->I->fail('нет redirect на /order/view/{id} после 2035, path=' . $path);
        }

        return (int) $m[1];
    }
}

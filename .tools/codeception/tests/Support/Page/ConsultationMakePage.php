<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * /order/consultation: устная (4000) / письменная (4001).
 *
 * Контракт: .doc/qa/flows/order-booking.md
 */
final class ConsultationMakePage extends BasePage
{
    public const URL = '/order/consultation';

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
        $this->I->waitForText('Заказ консультации', 20);
        $this->I->waitForJS(
            'var find = ' . self::jsFindVueComponent() . ';'
            . 'return !!find("consultation-form");',
            20
        );
    }

    public function setType(string $type): void
    {
        $this->I->assertTrue(in_array($type, ['spoken', 'written'], true));
        $this->I->executeJS(
            'var find = ' . self::jsFindVueComponent() . ';'
            . 'var c = find("consultation-form");'
            . 'if (!c) { return; }'
            . 'c.form.type = arguments[0];',
            [$type]
        );
        $this->I->waitForJS('return true;', 2);
    }

    public function acceptPrivacy(): void
    {
        $this->I->executeJS(
            'var find = ' . self::jsFindVueComponent() . ';'
            . 'var c = find("consultation-form");'
            . 'if (c) { c.isCheckedPersonData = true; }'
        );
    }

    /**
     * Обязательный вопрос (v-validate required на questions).
     * Без него validateAll() молча блокирует submit, redirect нет.
     */
    public function seedQuestion(string $text = 'AT2548 вопрос консультации'): void
    {
        $this->I->executeJS(
            'if (!window.storeVue || !window.storeVue.state || !window.storeVue.state.Order) { return; }'
            . 'var form = window.storeVue.state.Order.order_form;'
            . 'if (!form) { return; }'
            . 'if (!Array.isArray(form.questions)) { form.questions = []; }'
            . 'if (form.questions.length === 0) { form.questions.push(arguments[0]); }',
            [$text]
        );
        $this->I->waitForJS(
            'return !!(window.storeVue && window.storeVue.state.Order'
            . ' && window.storeVue.state.Order.order_form'
            . ' && window.storeVue.state.Order.order_form.questions'
            . ' && window.storeVue.state.Order.order_form.questions.length > 0);',
            5
        );
    }

    public function seeSubmitDisabled(): void
    {
        $disabled = $this->I->executeJS(
            'var el = document.evaluate(arguments[0], document, null,'
            . ' XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;'
            . 'return !!(el && el.disabled);',
            [self::test('consultation-form__submit')]
        );
        $this->I->assertTrue((bool) $disabled, 'ЗАКАЗАТЬ должна быть недоступна');
    }

    public function seeSubmitEnabled(): void
    {
        $this->I->waitForElement(self::test('consultation-form__submit'), 10);
        $disabled = $this->I->executeJS(
            'var el = document.evaluate(arguments[0], document, null,'
            . ' XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;'
            . 'return !!(el && el.disabled);',
            [self::test('consultation-form__submit')]
        );
        $this->I->assertFalse((bool) $disabled, 'ЗАКАЗАТЬ должна быть доступна');
    }

    public function submit(): void
    {
        $this->I->click(self::test('consultation-form__submit'));
    }

    public function waitRedirectToOrderView(): int
    {
        $this->I->waitForJS(
            'return location.pathname.indexOf("/order/view/") !== -1;',
            25
        );
        $path = (string) $this->I->executeJS('return location.pathname;');
        if (!preg_match('#/order/view/(\d+)#', $path, $m)) {
            $this->I->fail('нет redirect на /order/view/{id}, path=' . $path);
        }

        return (int) $m[1];
    }

    /**
     * Occupied-slot: Vuex Errors/showError. Закрыть модалку и сбросить хук консоли до checkpoint.
     */
    public function dismissErrorModalAndResetConsole(): void
    {
        $this->I->executeJS(
            'if (window.storeVue) { window.storeVue.dispatch("Errors/clearErrors"); }'
        );
        $this->I->waitForJS(
            'return !(window.storeVue && window.storeVue.state'
            . ' && window.storeVue.state.Errors'
            . ' && window.storeVue.state.Errors.showErrorModal);',
            5
        );
        $this->I->resetConsoleErrors();
    }
}

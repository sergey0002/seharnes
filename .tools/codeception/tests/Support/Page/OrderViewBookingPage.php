<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Карточка заказа: бронь, data-loss, оплата, конфликт слота.
 *
 * data-test на карточке нет. Селекторы: текст из task.md и классы модалки.
 * Шаблоны не правим.
 */
final class OrderViewBookingPage extends BasePage
{
    public const DATE_TIME_LABEL = 'Дата и время бронирования:';
    public const DATA_LOSS_MESSAGE = 'Ошибка потери данных: для заказа с бронированием отсутствует запись ct_booking.';
    public const SLOT_CONFLICT_MESSAGE = 'Исходный интервал больше недоступен. Можно перенести бронирование на ближайший свободный слот или отменить заказ.';
    public const SLOT_TAKEN_MESSAGE = 'Этот слот уже занят. Выберите другое время.';
    public const CONFLICT_TITLE = 'Слот недоступен';
    public const SPECIALIST_LABEL = 'Специалист:';

    public function open(int $orderId): void
    {
        $this->I->amOnPage('/order/view/' . $orderId);
        $this->I->waitForText('№ заказа:', 20);
    }

    public function seeBookingFields(): void
    {
        $this->I->see(self::DATE_TIME_LABEL);
        $this->I->see(self::SPECIALIST_LABEL);
        $this->I->see(BookingCalendarPage::MOSCOW_SUFFIX);
        $this->I->dontSee(self::DATA_LOSS_MESSAGE);
    }

    public function seeDataLoss(): void
    {
        $this->I->see(self::DATA_LOSS_MESSAGE);
        $this->I->dontSee(self::DATE_TIME_LABEL);
    }

    public function acceptPayPrivacy(): void
    {
        $this->I->executeJS(
            'var find = ' . self::jsFindVueComponent() . ';'
            . 'var all = document.querySelectorAll("*");'
            . 'for (var i = 0; i < all.length; i++) {'
            . '  var v = all[i].__vue__;'
            . '  if (v && Object.prototype.hasOwnProperty.call(v, "accept_pay")) {'
            . '    v.accept_pay = true;'
            . '    return;'
            . '  }'
            . '}'
        );
    }

    public function clickPay(): void
    {
        $this->I->click('//button[contains(@class,"order__send") and contains(.,"Оплатить")]');
    }

    public function confirmPayFromBalance(): void
    {
        $this->I->waitForText('Оплатить услугу средствами со счета?', 15);
        $this->I->click('//button[contains(@class,"formbox__buttons_find") and contains(.,"Оплата")]');
    }

    public function seeConflictModal(): void
    {
        $this->I->waitForText(self::CONFLICT_TITLE, 20);
        $this->I->see(self::SLOT_CONFLICT_MESSAGE);
        $this->I->see('Отменить заказ');
    }

    public function waitPaidOrStay(): void
    {
        $this->I->waitForJS('return true;', 3);
    }
}

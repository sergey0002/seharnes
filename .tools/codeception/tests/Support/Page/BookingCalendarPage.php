<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Календарь слотов специалиста на формах make (4000 / 2035).
 *
 * Контракт: .doc/qa/flows/order-booking.md
 * data-test уже в booking-calendar.tpl, шаблоны не правим.
 */
final class BookingCalendarPage extends BasePage
{
    public const EMPTY_SLOTS_MESSAGE = 'К сожалению, на ближайшие 28 дней нет доступного времени для бронирования. Попробуйте позднее.';
    public const CURRENT_TIME_PREFIX = 'Текущее время бронирования:';
    public const MOSCOW_SUFFIX = 'Время московское';

    private const TAG = 'booking-calendar';

    public function waitReady(): void
    {
        $this->I->waitForElement(self::test('booking-calendar'), 20);
        $this->I->waitForJS(
            'var find = ' . self::jsFindVueComponent() . ';'
            . 'var c = find("' . self::TAG . '");'
            . 'return !!(c && c.loading === false);',
            20
        );
    }

    public function seeHasSlots(): void
    {
        $this->waitReady();
        $this->I->waitForElement(self::test('booking-slots'), 15);
        $this->I->seeElement(self::test('booking-slot'));
        $this->I->seeElement(self::test('booking-datepicker'));
        $this->I->dontSee(self::EMPTY_SLOTS_MESSAGE, self::test('booking-empty'));
    }

    public function seeEmptyMessage(): void
    {
        $this->waitReady();
        $this->I->waitForElement(self::test('booking-empty'), 15);
        $this->I->see(self::EMPTY_SLOTS_MESSAGE, self::test('booking-empty'));
        $this->I->dontSeeElement(self::test('booking-slots'));
    }

    public function dontSeeCalendar(): void
    {
        $this->I->dontSeeElement(self::test('booking-calendar'));
    }

    public function seeCurrentCaption(): void
    {
        $this->I->waitForElement(self::test('booking-current-time'), 15);
        $this->I->see(self::CURRENT_TIME_PREFIX, self::test('booking-current-time'));
        $this->I->see(self::MOSCOW_SUFFIX, self::test('booking-current-time'));
    }

    public function dontSeeCurrentCaption(): void
    {
        $this->I->dontSeeElement(self::test('booking-current-time'));
    }

    public function grabSelectedStart(): string
    {
        $start = $this->I->executeJS(
            'var find = ' . self::jsFindVueComponent() . ';'
            . 'var c = find("' . self::TAG . '");'
            . 'return c && c.selectedStart ? String(c.selectedStart) : "";'
        );

        $this->I->assertNotSame('', (string) $start, 'слот по умолчанию не выбран');

        return (string) $start;
    }

    public function seeFirstSlotSelectedByDefault(): void
    {
        $ok = $this->I->executeJS(
            'var find = ' . self::jsFindVueComponent() . ';'
            . 'var c = find("' . self::TAG . '");'
            . 'if (!c || !c.dayKeys || !c.dayKeys.length) { return false; }'
            . 'var date = c.dayKeys[0];'
            . 'var slots = c.dayMap[date] || [];'
            . 'if (!slots.length) { return false; }'
            . 'return c.selectedStart === slots[0].start && c.selectedDate === date;'
        );
        $this->I->assertTrue((bool) $ok, 'первый доступный слот должен быть выбран по умолчанию');
    }

    public function seeAvailableDaysMarkedGreen(): void
    {
        $this->I->seeElement('//td[contains(@class,"booking-slot-available")]');
    }

    public function seeFirstAvailableDayIsWeekday(): void
    {
        $iso = $this->I->executeJS(
            'var find = ' . self::jsFindVueComponent() . ';'
            . 'var c = find("' . self::TAG . '");'
            . 'if (!c || !c.dayKeys || !c.dayKeys.length) { return 0; }'
            . 'var parts = String(c.dayKeys[0]).split("-");'
            . 'var d = new Date(parseInt(parts[0],10), parseInt(parts[1],10)-1, parseInt(parts[2],10));'
            . 'var n = d.getDay();'
            . 'return n === 0 ? 7 : n;'
        );
        $n = (int) $iso;
        $this->I->assertGreaterThanOrEqual(1, $n);
        $this->I->assertLessThanOrEqual(5, $n, 'первый день сетки не должен быть сб/вс');
    }
}

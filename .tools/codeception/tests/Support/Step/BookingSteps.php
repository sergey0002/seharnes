<?php

declare(strict_types=1);

namespace Tests\Support\Step;

use Tests\Support\AcceptanceTester;
use Tests\Support\Page\AdminOrderBookingPage;
use Tests\Support\Page\BookingCalendarPage;
use Tests\Support\Page\ConsultationMakePage;
use Tests\Support\Page\OrderViewBookingPage;
use Tests\Support\Page\RegistrationHelpMakePage;

/**
 * Сценарии бронирования специалиста (CT-2548).
 * Селекторы только в Page.
 */
final class BookingSteps
{
    private AcceptanceTester $I;
    private ConsultationMakePage $consultation;
    private RegistrationHelpMakePage $help;
    private OrderViewBookingPage $view;
    private AdminOrderBookingPage $admin;

    public function __construct(AcceptanceTester $I)
    {
        $this->I = $I;
        $this->consultation = new ConsultationMakePage($I);
        $this->help = new RegistrationHelpMakePage($I);
        $this->view = new OrderViewBookingPage($I);
        $this->admin = new AdminOrderBookingPage($I);
    }

    public function consultation(): ConsultationMakePage
    {
        return $this->consultation;
    }

    public function help(): RegistrationHelpMakePage
    {
        return $this->help;
    }

    public function view(): OrderViewBookingPage
    {
        return $this->view;
    }

    public function admin(): AdminOrderBookingPage
    {
        return $this->admin;
    }

    public function calendar(): BookingCalendarPage
    {
        return $this->consultation->calendar();
    }

    /**
     * @return array{orderId: int, start: string, staffId: int}
     */
    public function createSpokenConsultation(): array
    {
        $page = $this->consultation;
        $page->open();
        $page->calendar()->seeHasSlots();
        $start = $page->calendar()->grabSelectedStart();
        $page->seedQuestion();
        $page->acceptPrivacy();
        $page->seeSubmitEnabled();
        $page->submit();
        $orderId = $page->waitRedirectToOrderView();
        $this->I->seeInDatabase('ct_booking', ['OrderId' => $orderId]);
        $staffId = (int) $this->I->grabFromDatabase('ct_booking', 'StaffId', ['OrderId' => $orderId]);
        $stored = (string) $this->I->grabFromDatabase('ct_booking', 'BookedDateTime', ['OrderId' => $orderId]);
        $this->I->assertNotSame('', $stored);

        return ['orderId' => $orderId, 'start' => $start, 'staffId' => $staffId];
    }

    public function occupyStaffInterval(int $staffId, string $start, int $durationMinutes = 30): int
    {
        $fakeOrderId = 925480000 + random_int(1, 99999);
        while ($this->I->grabNumRecords('ct_booking', ['OrderId' => $fakeOrderId]) > 0
            || $this->I->grabNumRecords('ct_order', ['id' => $fakeOrderId]) > 0) {
            $fakeOrderId++;
        }
        $dt = $start;
        if (strlen($dt) === 16) {
            $dt .= ':00';
        }
        // findActiveInWindow JOIN ct_order: без заказа бронь не считается активной.
        $serviceId = (int) $this->I->grabFromDatabase('ct_service', 'id', ['code' => '4000']);
        if ($serviceId < 1) {
            $serviceId = 1;
        }
        $this->I->haveInDatabase('ct_order', [
            'id' => $fakeOrderId,
            'theDate' => date('Y-m-d H:i:s'),
            'clientId' => 1,
            'serviceId' => $serviceId,
            'orderStatusId' => 2,
            'userId' => null,
            'title' => 'AT2548 occupy slot',
            'description' => 'fixture',
            'comment' => '',
        ]);
        $this->I->haveInDatabase('ct_booking', [
            'OrderId' => $fakeOrderId,
            'StaffId' => $staffId,
            'BookedDateTime' => $dt,
            'DurationMinutes' => $durationMinutes,
            'ConnectionDetails' => null,
        ]);

        return $fakeOrderId;
    }

    public function ensureSecondStaffForType(string $type = '4000'): int
    {
        $name = 'AT2548 Staff B';
        if ($this->I->grabNumRecords('ct_staff', ['Name' => $name]) === 0) {
            $this->I->haveInDatabase('ct_staff', [
                'Name' => $name,
                'Timezone' => 3,
                'AbsenceDays' => '',
                'Active' => 1,
            ]);
        } else {
            $this->I->updateInDatabase('ct_staff', ['Active' => 1, 'Timezone' => 3, 'AbsenceDays' => ''], ['Name' => $name]);
        }
        $staffId = (int) $this->I->grabFromDatabase('ct_staff', 'ID', ['Name' => $name]);
        $typeId = (int) $this->I->grabFromDatabase('ct_orderType', 'ID', ['Type' => $type]);
        $this->I->assertGreaterThan(0, $typeId, 'нет ct_orderType ' . $type);
        if ($this->I->grabNumRecords('ct_staff2OrderType', ['StaffId' => $staffId, 'OrderTypeId' => $typeId]) === 0) {
            $this->I->haveInDatabase('ct_staff2OrderType', [
                'StaffId' => $staffId,
                'OrderTypeId' => $typeId,
            ]);
        }

        return $staffId;
    }

    public function deactivateNamedStaff(string $name): void
    {
        $this->I->updateInDatabase('ct_staff', ['Active' => 0], ['Name' => $name]);
    }

    public function activateNamedStaff(string $name): void
    {
        $this->I->updateInDatabase('ct_staff', ['Active' => 1], ['Name' => $name]);
    }

    /**
     * CT-2548 stage 4: runtime больше не фильтрует специалистов по
     * ct_staff2OrderType, поэтому пустая сетка требует деактивации всех
     * Active=1, а не только связанных с типом заказа.
     *
     * @return string[] имена деактивированных специалистов для восстановления
     */
    public function deactivateAllActiveStaff(): array
    {
        $names = $this->I->grabColumnFromDatabase('ct_staff', 'Name', ['Active' => 1]);
        $names = array_map('strval', $names);
        foreach ($names as $name) {
            $this->deactivateNamedStaff($name);
        }

        return $names;
    }
}

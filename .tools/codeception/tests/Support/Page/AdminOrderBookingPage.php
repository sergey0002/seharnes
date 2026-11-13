<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Админ: save-booking, datatable/details с бронью (CT-2548 / сценарий Германа).
 * UI CRUD справочников нет. data-test на полях брони нет (класс order-booking__input).
 */
final class AdminOrderBookingPage extends BasePage
{
    public const URL = '/admin/m_order.php';
    public const OVERLAP_WARNING = 'Выбранные дата, время и специалист пересекаются с другим активным бронированием.';
    public const DATA_LOSS_MESSAGE = 'Ошибка потери данных: для заказа с бронированием отсутствует запись ct_booking.';

    public function open(): void
    {
        $this->I->amOnPage(self::URL);
        $this->I->waitForJS('return document.readyState === "complete";', 15);
    }

    public function openPending(): void
    {
        $this->I->amOnPage(self::URL . '?pending=1');
        $this->I->waitForJS('return document.readyState === "complete";', 15);
    }

    /**
     * POST как list.js fetchData / Services.Order.MainDatatable (admin order/datatable).
     *
     * @return array<string, mixed>|null строка заказа или null
     */
    public function grabOrderFromDatatable(int $orderId, int $pending = 1): ?array
    {
        $raw = $this->I->executeJS(
            'var payload = "page=1&pageSize=20&pending=" + encodeURIComponent(arguments[1])'
            . ' + "&filter[id]=" + encodeURIComponent(arguments[0])'
            . ' + "&filter[title]=&filter[theDate]=&filter[clientId]=&filter[clientEmail]=&filter[orderStatusId]=";'
            . 'var xhr = new XMLHttpRequest();'
            . 'xhr.open("POST", "/admin/m_router.php?q=order/datatable", false);'
            . 'xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");'
            . 'xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");'
            . 'xhr.send(payload);'
            . 'return {status: xhr.status, body: xhr.responseText};',
            [$orderId, $pending]
        );
        if (is_object($raw)) {
            $raw = json_decode(json_encode($raw), true);
        }
        $this->I->assertTrue(is_array($raw), 'order/datatable не ответил');
        $this->I->assertSame(200, (int) ($raw['status'] ?? 0), 'HTTP order/datatable');
        $body = json_decode((string) ($raw['body'] ?? ''), true);
        $this->I->assertTrue(is_array($body), 'order/datatable JSON: ' . (string) ($raw['body'] ?? ''));
        $this->I->assertTrue(empty($body['success']) || $body['success'] !== false, (string) ($body['message'] ?? 'datatable fail'));
        $rows = isset($body['data']) && is_array($body['data']) ? $body['data'] : [];
        foreach ($rows as $row) {
            if ((int) ($row['id'] ?? 0) === $orderId) {
                return is_array($row) ? $row : null;
            }
        }

        return null;
    }

    /**
     * @param array<string, mixed> $row
     */
    public function seeBookingFilledInDatatableRow(array $row, string $expectedBookedDateTime): void
    {
        $this->I->assertTrue(!empty($row['canBook']), 'canBook для типа с BookSlotStep>0');
        $booking = isset($row['booking']) && is_array($row['booking']) ? $row['booking'] : null;
        $this->I->assertNotNull($booking, 'booking в datatable сразу после создания (без задержки)');
        $stored = (string) ($booking['BookedDateTime'] ?? '');
        $this->I->assertNotSame('', $stored, 'BookedDateTime в админ-списке');
        $normExpected = strlen($expectedBookedDateTime) === 16
            ? $expectedBookedDateTime . ':00'
            : $expectedBookedDateTime;
        $this->I->assertSame($normExpected, $stored, 'дата/время брони в админке = ct_booking');
        $this->I->assertGreaterThan(0, (int) ($booking['StaffId'] ?? 0), 'StaffId в админ-списке');
    }

    public function grabDetailsHtml(int $orderId): string
    {
        $raw = $this->I->executeJS(
            'var xhr = new XMLHttpRequest();'
            . 'xhr.open("GET", "/admin/m_router.php?q=order/details/" + arguments[0], false);'
            . 'xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");'
            . 'xhr.send("");'
            . 'return {status: xhr.status, body: xhr.responseText};',
            [$orderId]
        );
        if (is_object($raw)) {
            $raw = json_decode(json_encode($raw), true);
        }
        $this->I->assertTrue(is_array($raw), 'order/details не ответил');
        $this->I->assertSame(200, (int) ($raw['status'] ?? 0), 'HTTP order/details');

        return (string) ($raw['body'] ?? '');
    }

    public function seeDataLossInDetailsHtml(string $html): void
    {
        $this->I->assertTrue(
            strpos($html, self::DATA_LOSS_MESSAGE) !== false,
            'в деталях админки литерал потери ct_booking'
        );
        $this->I->assertFalse(
            strpos($html, 'Дата и время бронирования') !== false,
            'при data-loss нет строки с датой бронирования'
        );
    }

    public function seeBookingInDetailsHtml(string $html): void
    {
        $this->I->assertTrue(
            strpos($html, 'Дата и время бронирования') !== false,
            'в деталях админки есть дата бронирования'
        );
        $this->I->assertTrue(
            strpos($html, self::DATA_LOSS_MESSAGE) === false,
            'при наличии ct_booking нет ошибки потери данных'
        );
    }

    /**
     * POST как list.js postBooking. alert перехватывается, сохранение не блокируется.
     *
     * @return array{success: bool, warning: bool, warningMessage: string, message: string}
     */
    public function saveDateTime(int $orderId, string $bookedDateTime, int $staffId): array
    {
        $raw = $this->I->executeJS(
            'window.__bookingSave = null;'
            . 'var data = "order_id=" + encodeURIComponent(arguments[0])'
            . ' + "&bookedDateTime=" + encodeURIComponent(arguments[1])'
            . ' + "&staffId=" + encodeURIComponent(arguments[2]);'
            . 'var xhr = new XMLHttpRequest();'
            . 'xhr.open("POST", "/admin/m_router.php?q=order/save-booking", false);'
            . 'xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");'
            . 'xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");'
            . 'xhr.send(data);'
            . 'window.__bookingSave = {status: xhr.status, body: xhr.responseText};'
            . 'return window.__bookingSave;',
            [$orderId, $bookedDateTime, $staffId]
        );
        if (is_object($raw)) {
            $raw = json_decode(json_encode($raw), true);
        }
        $this->I->assertTrue(is_array($raw), 'save-booking не ответил');
        $this->I->assertSame(200, (int) ($raw['status'] ?? 0), 'HTTP save-booking');
        $body = json_decode((string) ($raw['body'] ?? ''), true);
        $this->I->assertTrue(is_array($body), 'save-booking JSON: ' . (string) ($raw['body'] ?? ''));

        return [
            'success' => !empty($body['success']),
            'warning' => !empty($body['warning']),
            'warningMessage' => (string) ($body['warningMessage'] ?? ''),
            'message' => (string) ($body['message'] ?? ''),
        ];
    }
}

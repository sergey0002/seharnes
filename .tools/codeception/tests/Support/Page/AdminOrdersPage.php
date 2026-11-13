<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Админ-список заказов: /admin/m_order.php
 * Pending = статусы 3,4,5 (без 9). JSON статусов: POST admin m_router order/statuses.
 */
final class AdminOrdersPage extends BasePage
{
    public function ensureOrdersRight(): void
    {
        $this->ensureRight('orders', 'Заказы', 9207702);
        $this->ensureRight('dblog', 'DbLog', 9207703);
    }

    public function openAll(): void
    {
        $this->ensureOrdersRight();
        $this->I->amOnPage('/admin/m_order.php');
        $this->I->waitForElement('//body', 20);
    }

    public function changeStatusJs(int $orderId, int $statusId): string
    {
        $this->ensureOrdersRight();
        $this->I->amOnPage('/admin/m_order.php');
        $this->I->waitForElement('//body', 20);
        return (string) $this->I->executeJS(
            'var xhr = new XMLHttpRequest();'
            . 'xhr.open("GET", "/admin/m_order.php?js=1&id=" + arguments[0] + "&statusId=" + arguments[1], false);'
            . 'xhr.send("");'
            . 'return String(xhr.responseText || "");',
            [$orderId, $statusId]
        );
    }

    public function seeJsonResultTrue(string $raw): void
    {
        $ok = strpos($raw, '"result":true') !== false || strpos($raw, '"result": true') !== false;
        $this->I->assertTrue($ok, 'admin m_order.js JSON result=true, got: ' . substr($raw, 0, 300));
    }

    public function openPending(): void
    {
        $this->I->amOnPage('/admin/m_order.php?pending=1');
        $this->I->waitForElement('//body', 20);
    }

    public function openVue(): void
    {
        $this->I->amOnPage('/admin/m_order.php?vue=1');
        $this->I->waitForElement('//body', 20);
    }

    public function seeOrderId(int $orderId): void
    {
        $this->I->see((string) $orderId);
    }

    public function dontSeeOrderId(int $orderId): void
    {
        $this->I->dontSee((string) $orderId);
    }

    /**
     * @return array<string, mixed>
     */
    public function grabStatusesJson(int $pending): array
    {
        $raw = $this->I->executeJS(
            'var xhr = new XMLHttpRequest();'
            . 'xhr.open("POST", "/admin/m_router.php?q=order/statuses", false);'
            . 'xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");'
            . 'xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");'
            . 'xhr.send("pending=" + arguments[0]);'
            . 'return xhr.responseText || "";',
            [$pending]
        );
        $data = json_decode((string) $raw, true);
        $this->I->assertTrue(is_array($data), 'admin order statuses JSON');

        return $data;
    }

    private function ensureRight(string $slug, string $name, int $hintId): void
    {
        if ($this->I->grabNumRecords('ct_right', ['slug' => $slug]) === 0) {
            $this->I->haveInDatabase('ct_right', [
                'id' => $hintId,
                'name' => $name,
                'slug' => $slug,
                'priority' => 1000 + $hintId,
            ]);
        }
        $rightId = (int) $this->I->grabFromDatabase('ct_right', 'id', ['slug' => $slug]);
        if ($this->I->grabNumRecords('ct_role2right', ['roleId' => 1, 'rightId' => $rightId]) === 0) {
            $this->I->haveInDatabase('ct_role2right', [
                'roleId' => 1,
                'rightId' => $rightId,
            ]);
        }
    }
}

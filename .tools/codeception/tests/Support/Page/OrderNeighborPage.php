<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Соседний флоу без BookSlotStep: /order/pksr не показывает календарь брони.
 */
final class OrderNeighborPage extends BasePage
{
    public function openPksr(): void
    {
        $this->I->amOnPage('/order/pksr');
        $this->I->waitForElement('//body', 15);
    }
}

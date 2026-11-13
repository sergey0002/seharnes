<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Админ DbLog: /admin/m_dblog.php
 */
final class AdminDbLogPage extends BasePage
{
    public function openWithoutTimes(): void
    {
        $this->I->amOnPage('/admin/m_dblog.php?notimes=1');
        $this->I->waitForText('Description', 20);
    }

    public function openErrorsAndNotices(): void
    {
        $this->I->amOnPage('/admin/m_dblog.php?errnb=1');
        $this->I->waitForText('Description', 20);
    }

    public function seeDescription(string $fragment): void
    {
        $this->I->waitForText($fragment, 20);
        $this->I->see($fragment);
    }

    public function dontSeeDescription(string $fragment): void
    {
        $this->I->dontSee($fragment);
    }
}

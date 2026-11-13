<?php

declare(strict_types=1);

namespace Tests\Support\Step;

use Tests\Support\AcceptanceTester;
use Tests\Support\Page\AdminClientProfilePage;
use Tests\Support\Page\SigninPage;

/**
 * Смена логина клиента в админке (email / hash).
 *
 * Селекторы в Page. Контракт: .doc/qa/flows/admin-client-login.md
 */
final class AdminClientProfileSteps
{
    private AcceptanceTester $I;
    private AdminClientProfilePage $profile;

    public function __construct(AcceptanceTester $I)
    {
        $this->I = $I;
        $this->profile = new AdminClientProfilePage($I);
    }

    public function profile(): AdminClientProfilePage
    {
        return $this->profile;
    }

    public function signin(): SigninPage
    {
        return new SigninPage($this->I);
    }

    public function openAsAdmin(int $clientId): AdminClientProfilePage
    {
        $this->I->loginAsAdmin();
        $this->profile->open($clientId);
        $this->profile->openGeneralParams();

        return $this->profile;
    }

    public function changeLoginAndSave(int $clientId, string $email): AdminClientProfilePage
    {
        $page = $this->openAsAdmin($clientId);
        $page->setLogin($email);
        $page->save();

        return $page;
    }
}

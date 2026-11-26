<?php

declare(strict_types=1);

namespace Tests\Acceptance;

use Tests\Support\AcceptanceTester;

final class FirstCest
{
    public function frontpageWorks(AcceptanceTester $I)
    {
        $I->amOnPage('/');
        $I->see('Как это работает?', '//*[@data-test="mainpage"]//*[@data-test="mainpage__roadmap"]');
    }

    public function iCanLoginAsAdmin(AcceptanceTester $I)
    {
        $I->haveInDatabase('ct_user', [
            'id' => 1,
            'name' => 'Admin',
            'login' => 'realant',
            'pass' => md5('realant2020'),
        ]);


        $I->amOnPage('/admin/');
        $I->fillField('//*[@data-test="login-form"]//*[@data-test="login-form__user"]', 'realant');
        $I->fillField('//*[@data-test="login-form"]//*[@data-test="login-form__pass"]', 'realant2020');
        $I->click('//*[@data-test="login-form"]//*[@data-test="login-form__submit"]');
        $I->waitForText('Admin Mode', 10, '//*[@data-test="title"]');


        $I->see('Основные правила работы с администраторским интерфейсом', '//*[@data-test="subtitle"]');
    }
}

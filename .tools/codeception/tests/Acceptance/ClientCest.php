<?php

declare(strict_types=1);

namespace Tests\Acceptance;

use Tests\Support\AcceptanceTester;

final class ClientCest
{
    /**
     * @group account-signin
     */
    public function iCanLoginAsClient(AcceptanceTester $I): void
    {
        $I->haveInDbDefaultClient();


        $I->amOnPage('/account/signin');
        $I->fillField(
            '//*[@data-test="login-form"]//*[@data-test="login-form__email"]',
            'test+local-client1@seyfer.pro'
        );
        $I->fillField(
            '//*[@data-test="login-form"]//*[@data-test="login-form__pass"]',
            'Qwert123'
        );
        $I->click('//*[@data-test="login-form"]//*[@data-test="login-form__submit"]');
        $I->waitForElement('//*[@data-test="item-main"]', 10);


        $I->see('Мои регистрации', '//*[@data-test="item-main__title"]');
    }

    /**
     * Тест прав доступа (чек-лист категория 11): черновик клиента №1 не должен
     * быть виден клиенту №2 в списке «Черновики» — список фильтруется по
     * clientId на сервере (ItemMVC::GetDraftByUserId, см. .doc/qa/fragments.md).
     *
     * @group access-rights
     */
    public function clientCannotSeeAnotherClientsDraft(AcceptanceTester $I): void
    {
        $I->haveInDbDefaultClient();
        $I->haveInDbItemDraft();
        $I->haveInDbSecondClient();

        $I->loginAsClientById(2);
        $I->amOnPage('/item/drafts');
        $I->waitForElement('//h1[contains(text(), "Черновики")]', 10);

        $I->wait(3);
        $I->checkpoint('client2-drafts-list');

        $I->dontSee('Наименование');
        $I->dontSeeInSource('Описание программы');

        $I->seeInDatabase('ct_item', [
            'id' => 1,
            'clientId' => 1,
            'name' => 'Наименование',
        ]);
    }
}

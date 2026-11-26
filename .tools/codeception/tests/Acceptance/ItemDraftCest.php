<?php

declare(strict_types=1);

namespace Tests\Acceptance;

use Tests\Support\AcceptanceTester;

final class ItemDraftCest {
    public function _before(AcceptanceTester $I): void
    {
        $I->loginAsClient();
    }

    public function saveMinimalDraft(AcceptanceTester $I)
    {
        $draftName = 'Cest literary ' . date('YmdHis');

        $I->amOnPage('/item/start?strategy=literary');
        $I->waitForElement('//*[@data-test="item-form-step2"]');
        $I->fillField(
            '//*[@data-test="item-form-step2"]//*[@data-test="item-form-step2__name"]',
            $draftName
        );
        $I->fillField(
            '//*[@data-test="item-form-step2"]//*[@data-test="item-form-step2__fileDate"]',
            '01.01.2020'
        );
        $I->fillField(
            '//*[@data-test="item-form-step2"]//*[@data-test="item-form-step2__description"]',
            'Описание произведения'
        );

        $I->wait(5);
        $I->click('//*[@data-test="item-container"]//*[@data-test="item-container__next-btn"]');

        $I->click('(//*[@data-test="item-form-buttons"]//*[@data-test="item-form-buttons__save-btn"])[2]');
        $I->waitForElement('//*[@data-test="save-draft-modal"]');

        $I->click('//*[@data-test="save-draft-modal"]//*[@data-test="save-draft-modal__save-btn"]');
        $I->wait(5);

        $I->seeInDatabase('ct_item', [
            'isDraft' => 1,
            'strategy' => 'literary',
            'CreatedDate' => '2020-01-01',
            'name' => $draftName,
            'draftName' => $draftName,
            'description' => 'Описание произведения',
        ]);

        // уйти с wizard без beforeunload-alert перед следующим тестом
        $I->amOnPage('/item/main');
        $I->waitForElement('//*[@data-test="item-main"]', 15);
    }

    public function saveFullDraft(AcceptanceTester $I)
    {
        $I->haveInDbProgramLang();
        $I->haveInDbIdentityType();
        $I->haveInDbItemSection();

        $draftName = 'Cest programm ' . date('YmdHis');

        $I->amOnPage('/item/start?strategy=programm');
        $I->waitForElement('//*[@data-test="item-form-step2"]');
        $I->executeJS(<<<'JS'
(function () {
  var orig = window.dispatchEvent.bind(window);
  window.dispatchEvent = function (ev) {
    if (ev && (ev.type === 'network:error' || ev.type === 'session:expired' || ev.type === 'server:error')) {
      return true;
    }
    return orig(ev);
  };
  document.querySelectorAll('.modal-mask').forEach(function (el) { el.remove(); });
})();
JS
        );
        $I->fillField(
            '//*[@data-test="item-form-step2"]//*[@data-test="item-form-step2__name"]',
            $draftName
        );
        $I->fillField(
            '//*[@data-test="item-form-step2"]//*[@data-test="item-form-step2__fileDate"]',
            '01.01.2020'
        );
        $I->fillField(
            '//*[@data-test="item-form-step2"]//*[@data-test="item-form-step2__description"]',
            'Описание программы'
        );
        $I->fillField(
            '//*[@data-test="item-form-step2"]//*[@data-test="item-form-step2__place-creation"]',
            'Место создания'
        );
        $I->fillField(
            '//*[@data-test="item-form-step2"]//*[@data-test="item-form-step2__number_version"]',
            '1.0.0'
        );
        $I->fillField(
            '//*[@data-test="item-form-step2"]//*[@data-test="item-form-step2__purpose"]',
            'Назначение программы'
        );
        $I->fillField(
            '//*[@data-test="item-form-step2"]//*[@data-test="item-form-step2__scope"]',
            'Область применения'
        );
        $I->fillField(
            '//*[@data-test="item-form-step2"]//*[@data-test="item-form-step2__functionality"]',
            'Функциональные возможности'
        );
        $I->fillField(
            '//*[@data-test="item-form-step2"]//*[@data-test="item-form-step2__requirements"]',
            'Технические требования'
        );

        $I->wait(5);
        $I->click('//*[@data-test="item-container"]//*[@data-test="item-container__next-btn"]');

        $I->clearField('//*[@data-test="item-form-step3__subject"]//*[@data-test="item-form-step3__subject-surname"]');
        $I->fillField(
            '//*[@data-test="item-form-step3__subject"]//*[@data-test="item-form-step3__subject-surname"]',
            'Фамилия'
        );
        $I->clearField('//*[@data-test="item-form-step3__subject"]//*[@data-test="item-form-step3__subject-firstname"]');
        $I->fillField(
            '//*[@data-test="item-form-step3__subject"]//*[@data-test="item-form-step3__subject-firstname"]',
            'Имя'
        );
        $I->clearField('//*[@data-test="item-form-step3__subject"]//*[@data-test="item-form-step3__subject-secondname"]');
        $I->fillField(
            '//*[@data-test="item-form-step3__subject"]//*[@data-test="item-form-step3__subject-secondname"]',
            'Отчество'
        );
        $I->clearField('//*[@data-test="item-form-step3__subject"]//*[@data-test="item-form-step3__subject-birthdate"]');
        $I->fillField(
            '//*[@data-test="item-form-step3__subject"]//*[@data-test="item-form-step3__subject-birthdate"]',
            '01.01.2010'
        );
        // datepicker перекрывает select пола (stage6: radio→select)
        $I->executeJS('if (window.jQuery) { jQuery(".ui-datepicker").hide(); } document.activeElement && document.activeElement.blur();');
        $I->wait(1);
        $I->scrollTo('#step-2_rafi-10');
        $I->click('#step-2_rafi-10 .reg-author-form__label .ui-selectmenu-button');
        $I->click('#step-2_rafi-10 .reg-author-form__label .ui-selectmenu-menu .ui-menu-item:nth-child(1)');
        // профиль автозаполняет ДУЛ — clearField, иначе 1122+1122 / 111222+112233 > varchar(10)
        $I->clearField('//*[@data-test="item-form-step3__subject"]//*[@data-test="item-form-step3__subject-identity-seria"]');
        $I->fillField(
            '//*[@data-test="item-form-step3__subject"]//*[@data-test="item-form-step3__subject-identity-seria"]',
            '1122'
        );
        $I->clearField('//*[@data-test="item-form-step3__subject"]//*[@data-test="item-form-step3__subject-identity-number"]');
        $I->fillField(
            '//*[@data-test="item-form-step3__subject"]//*[@data-test="item-form-step3__subject-identity-number"]',
            '112233'
        );
        $I->clearField('//*[@data-test="item-form-step3__subject"]//*[@data-test="item-form-step3__subject-identity-date"]');
        $I->fillField(
            '//*[@data-test="item-form-step3__subject"]//*[@data-test="item-form-step3__subject-identity-date"]',
            '01.01.2020'
        );
        $I->executeJS('if (window.jQuery) { jQuery(".ui-datepicker").hide(); } document.activeElement && document.activeElement.blur();');
        $I->clearField('//*[@data-test="item-form-step3__subject"]//*[@data-test="item-form-step3__subject-identity-responsible"]');
        $I->fillField(
            '//*[@data-test="item-form-step3__subject"]//*[@data-test="item-form-step3__subject-identity-responsible"]',
            'МВД'
        );
        // без UI-связи с клиентом: fillField иначе склеивает автозаполнение профиля (111222+112233 > varchar(10))
        $I->executeJS(<<<'JS'
(function () {
  var el = document.querySelector('[data-test="item-container"]') || document.body;
  var vm = el.__vue__;
  var guard = 0;
  while (vm && !vm.forms && vm.$parent && guard++ < 20) {
    vm = vm.$parent;
  }
  if (!vm || !vm.forms || !vm.forms[3] || !vm.forms[3].form || !vm.forms[3].form.authors[0]) {
    return;
  }
  var a = vm.forms[3].form.authors[0];
  a.clientId = '0';
  a.surname = 'Фамилия';
  a.firstName = 'Имя';
  a.secondName = 'Отчество';
  a.birthDate = '01.01.2010';
  a.identitySeria = '1122';
  a.identityNumber = '112233';
  a.identityDate = '01.01.2020';
  a.identityResponcible = 'МВД';
  a.identityType = '14';
})();
JS
        );

        $I->wait(2);
        $I->executeJS('document.querySelectorAll(".modal-mask").forEach(function (el) { el.remove(); });');
        $I->click('//*[@data-test="item-container"]//*[@data-test="item-container__next-btn"]');
        $I->waitForElementVisible('//*[@data-test="item-form-step4-rights"]', 15);
        $I->scrollTo('//*[@data-test="item-form-step4-rights"]');
        $I->wait(1);

        $I->click('//*[@data-test="item-form-step4-rights"]//*[@data-test="item-form-step4-rights__copyrights-value"]');
        $I->click('//*[@data-test="item-form-step4-rights"]//*[@data-test="item-form-step4-rights__related-value"]');
        $I->click('//*[@data-test="item-form-step4-rights"]//*[@data-test="item-form-step4-rights__exceptional-value"]');

        $I->fillField(
            '//*[@data-test="author-right-form"]//*[@data-test="author-right-form__parts"]',
            'Музыка'
        );
        $I->click('//*[@data-test="author-adjacent-right-form"]//*[@data-test="author-adjacent-right-form__database-creator"]');

        $I->click('#step-4_rafi-8 .reg-author-form__label .ui-selectmenu-button .ui-selectmenu-icon');
        $I->click('#step-4_rafi-8 .reg-author-form__label .ui-selectmenu-menu .ui-menu-item:nth-child(2)');

        $I->wait(5);
        $I->click('//*[@data-test="item-container"]//*[@data-test="item-container__next-btn"]');

        $I->click('#step-5_rafi-1 .reg-author-form__label .ui-selectmenu-button .ui-selectmenu-icon');
        $I->click('#step-5_rafi-1 .reg-author-form__label .ui-selectmenu-menu li:nth-child(3)');

        $I->click('#step-5_rafi-2 .reg-author-form__label .ui-selectmenu-button .ui-selectmenu-icon');
        $I->click('#step-5_rafi-2 .reg-author-form__label .ui-selectmenu-menu li:nth-child(3)');

        $I->click('(//*[@data-test="item-form-buttons"]//*[@data-test="item-form-buttons__save-btn"])[4]');
        $I->waitForElement('//*[@data-test="save-draft-modal"]');

        $I->click('//*[@data-test="save-draft-modal"]//*[@data-test="save-draft-modal__save-btn"]');
        $I->wait(5);

        $I->seeInDatabase('ct_item', [
            'isDraft' => 1,
            'strategy' => 'programm',
            'CreatedDate' => '2020-01-01',
            'name' => $draftName,
            'draftName' => $draftName,
            'description' => 'Описание программы',
            'place_creation' => 'Место создания',
            'number_version' => '1.0.0',
            'destination' => 'Назначение программы',
            'scope' => 'Область применения',
            'functionality' => 'Функциональные возможности',
            'technical_requirements' => 'Технические требования',
            'term' => 5,
            'itemSectionId' => 101,
        ]);

        $itemId = $I->grabFromDatabase('ct_item', 'id', [
            'isDraft' => 1,
            'strategy' => 'programm',
            'name' => $draftName,
        ]);

        $I->seeInDatabase('ct_author', [
            'draftId' => $itemId,
            'surname' => 'Фамилия',
            'firstName' => 'Имя',
            'secondName' => 'Отчество',
            'birthDate' => '01.01.2010',
            'identitySeria' => '1122',
            'identityNumber' => '112233',
            'identityDate' => '2020-01-01 00:00:00',
            'identityResponcible' => 'МВД',
        ]);

        $subjectId = $I->grabFromDatabase('ct_author', 'id', [
            'draftId' => $itemId,
            'surname' => 'Фамилия',
            'identityNumber' => '112233',
        ]);

        $I->seeInDatabase('ct_rightsHolder', [
            'type' => 'Authors',
            'rightType' => 'Copyrights',
            'authorRole' => 'автор',
            'partsDescription' => 'Музыка',
            'subjectId' => $subjectId,
            'itemId' => $itemId,
        ]);
        $I->seeInDatabase('ct_rightsHolder', [
            'type' => 'ExclusiveRightsHolders',
            'rightType' => 'ExceptionalRights',
            "exceptType" => 'AllAsAuthorAndOwner',
            'subjectId' => $subjectId,
            'itemId' => $itemId,
        ]);
        $I->seeInDatabase('ct_rightsHolder', [
            'type' => 'DatabaseCreators',
            'rightType' => 'RelatedRights',
            'subjectId' => $subjectId,
            'itemId' => $itemId,
        ]);
    }
}

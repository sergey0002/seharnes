<?php

declare(strict_types=1);

namespace Tests\Acceptance;

use Tests\Support\AcceptanceTester;

final class TariffDeleteCest
{
    public function _before(AcceptanceTester $I): void
    {
        $I->loginAsAdmin();
    }

    public function _after(AcceptanceTester $I): void
    {
        $I->updateInDatabase('ct_client', ['tariffId' => 7], ['id' => 1]);
    }

    public function cannotDeleteTariffWithConnectedUsers(AcceptanceTester $I): void
    {
        $tariffId = 9001;
        $I->haveInDbDefaultClient();
        $I->haveInDbTariff($tariffId);
        $I->updateInDatabase('ct_client', ['tariffId' => $tariffId], ['id' => 1]);

        $I->deleteTariffViaAdmin($tariffId);

        $I->waitForText('В системе есть пользователи, подключенные к этому тарифу', 10);
        $I->seeInDatabase('ct_tariff', ['id' => $tariffId, 'isDeleted' => 0]);
    }

    public function cannotDeleteTariffWithUnusedPromo(AcceptanceTester $I): void
    {
        $tariffId = 9002;
        $I->haveInDbTariff($tariffId, [
            'subscriptionFee' => 100.00,
            'settlementPeriod' => 12,
        ]);
        $I->haveInDbPromo($tariffId, [
            'status' => 0,
            'client_id' => null,
        ]);

        $I->deleteTariffViaAdmin($tariffId);

        $I->waitForText('В системе есть незавершённые промо-коды, связанные с этим тарифом', 10);
        $I->seeInDatabase('ct_tariff', ['id' => $tariffId, 'isDeleted' => 0]);
    }

    public function cannotDeleteTariffWithActiveActivatedPromo(AcceptanceTester $I): void
    {
        $tariffId = 9003;
        $I->haveInDbTariff($tariffId, [
            'subscriptionFee' => 100.00,
            'settlementPeriod' => 12,
        ]);
        $I->haveInDbPromo($tariffId, [
            'status' => 1,
            'client_id' => 1,
            'theDateOpened' => date('Y-m-d H:i:s', strtotime('-1 day')),
            'day_period' => 30,
        ]);

        $I->deleteTariffViaAdmin($tariffId);

        $I->waitForText('В системе есть незавершённые промо-коды, связанные с этим тарифом', 10);
        $I->seeInDatabase('ct_tariff', ['id' => $tariffId, 'isDeleted' => 0]);
    }

    public function canDeleteTariffWithOnlyUsedPromo(AcceptanceTester $I): void
    {
        $tariffId = 9004;
        $I->haveInDbTariff($tariffId, [
            'subscriptionFee' => 100.00,
            'settlementPeriod' => 12,
        ]);
        $I->haveInDbPromo($tariffId, [
            'status' => 2,
            'client_id' => 1,
            'theDateOpened' => date('Y-m-d H:i:s', strtotime('-60 days')),
            'day_period' => 30,
        ]);

        $I->deleteTariffViaAdmin($tariffId);

        $I->wait(2);
        $I->dontSee('В системе есть незавершённые промо-коды, связанные с этим тарифом');
        $I->seeInDatabase('ct_tariff', ['id' => $tariffId, 'isDeleted' => 1]);
    }

    public function cannotDeleteTariffUsedAsAlternative(AcceptanceTester $I): void
    {
        $targetTariffId = 9005;
        $parentTariffId = 9006;

        $I->haveInDbTariff($targetTariffId, [
            'subscriptionFee' => 100.00,
            'settlementPeriod' => 12,
        ]);
        $I->haveInDbTariff($parentTariffId, [
            'subscriptionFee' => 200.00,
            'settlementPeriod' => 12,
            'alternativeTariffId' => $targetTariffId,
        ]);

        $I->deleteTariffViaAdmin($targetTariffId);

        $I->waitForText('Тариф указан как альтернативный у другого тарифа и не может быть удалён', 10);
        $I->seeInDatabase('ct_tariff', ['id' => $targetTariffId, 'isDeleted' => 0]);
    }
}

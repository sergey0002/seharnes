<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Сайдбар баланса кабинета (/item/main и соседние страницы с right-column).
 *
 * Контракт: CT-2610 plan.md Patches 2-3 (Display-поля).
 * data-test нет — селекторы по BEM detailed-balance + текст.
 */
final class CabinetBalancePage extends BasePage
{
    public const TEXT_BALANCE = 'Баланс';
    public const TEXT_BONUSES = 'Бонусы';
    public const TEXT_OWN_FUNDS = 'Свои средства';
    public const TEXT_CREDIT_LIMIT = 'Кредитный лимит';
    public const TEXT_AVAILABLE = 'Доступно';

    private const DETAILED = '//*[contains(@class,"detailed-balance")]';

    public function openMain(): void
    {
        $this->I->amOnPage('/item/main');
        $this->I->waitForElementVisible('body', 15);
    }

    public function waitBalanceVisible(): void
    {
        $this->I->waitForText(self::TEXT_BALANCE, 20);
    }

    /**
     * @return array{
     *   realMoney:?int,virtualMoney:?int,realMoneyDisplay:?int,virtualMoneyDisplay:?int,
     *   creditLimit:?int,totalMoney:?int
     * }
     */
    public function grabClientBalanceFromApi(): array
    {
        $this->I->amOnPage('/item/main');
        $this->I->waitForJS(
            'if (typeof window.__ct2610Bal === "undefined" && !window.__ct2610BalStarted) {'
            . '  window.__ct2610BalStarted = true;'
            . '  fetch("/account/current", {credentials:"same-origin"})'
            . '  .then(function(r){return r.json();})'
            . '  .then(function(j){ window.__ct2610Bal = j.clientBalance || j.balance || j.data || j; })'
            . '  .catch(function(e){ window.__ct2610Bal = {error:String(e)}; });'
            . '}'
            . 'return typeof window.__ct2610Bal !== "undefined";',
            30
        );
        $bal = $this->I->executeJS('return window.__ct2610Bal;');
        if (is_object($bal)) {
            $bal = json_decode((string) json_encode($bal), true);
        }
        $this->I->assertTrue(is_array($bal), 'account/current clientBalance not array');

        return [
            'realMoney' => isset($bal['realMoney']) ? (int) $bal['realMoney'] : null,
            'virtualMoney' => isset($bal['virtualMoney']) ? (int) $bal['virtualMoney'] : null,
            'realMoneyDisplay' => isset($bal['realMoneyDisplay']) ? (int) $bal['realMoneyDisplay'] : null,
            'virtualMoneyDisplay' => isset($bal['virtualMoneyDisplay']) ? (int) $bal['virtualMoneyDisplay'] : null,
            'creditLimit' => isset($bal['creditLimit']) ? (int) $bal['creditLimit'] : null,
            'totalMoney' => isset($bal['totalMoney']) ? (int) $bal['totalMoney'] : null,
        ];
    }

    public function seeOwnFundsDisplay(int $expected): void
    {
        $this->waitBalanceVisible();
        $this->I->see(self::TEXT_OWN_FUNDS);
        $this->I->see((string) $expected, self::DETAILED);
    }

    public function seeBonusesDisplay(int $expected): void
    {
        $this->waitBalanceVisible();
        $this->I->see(self::TEXT_BONUSES);
        $this->I->see((string) $expected, self::DETAILED);
    }

    public function dontSeeRawNegativeOwnFunds(int $rawNegative): void
    {
        $this->waitBalanceVisible();
        $this->I->dontSee((string) $rawNegative, self::DETAILED);
    }

    public function seeCreditLimitBlock(): void
    {
        $this->I->see(self::TEXT_CREDIT_LIMIT);
        $this->I->see(self::TEXT_AVAILABLE);
    }

    public function dontSeeCreditLimitBlock(): void
    {
        $this->I->dontSee(self::TEXT_CREDIT_LIMIT);
    }

    /**
     * Открыть модалку "Недостаточно средств" через Vuex store (AC-3 Patch 4).
     */
    public function openAccountEdit(): void
    {
        $this->I->amOnPage('/account/edit');
        $this->I->waitForText(self::TEXT_BALANCE, 20);
    }

    public function openInsufficientFundsModalFromStore(array $balance, int $cost): void
    {
        $this->openAccountEdit();
        $payload = json_encode([
            'balance' => $balance,
            'cost' => $cost,
            'enough' => false,
        ], JSON_UNESCAPED_UNICODE);
        $this->I->executeJS(
            'var data = ' . $payload . ';'
            . 'var vue = null;'
            . 'var all = document.querySelectorAll("*");'
            . 'for (var i = 0; i < all.length; i++) {'
            . '  if (all[i].__vue__ && all[i].__vue__.$store) { vue = all[i].__vue__; break; }'
            . '}'
            . 'if (!vue || !vue.$store) { throw new Error("Vuex store not found"); }'
            . 'return vue.$store.dispatch("InsufficientFundsError/showError", data);'
        );
        $this->I->waitForText('Недостаточно средств', 10);
    }

    public function seeInsufficientFundsDisplay(int $bonuses, int $ownFunds): void
    {
        $this->I->see('Недостаточно средств');
        $this->I->see('Бонусы: ' . $bonuses);
        $this->I->see('Свои средства: ' . $ownFunds);
        $this->I->dontSee('Свои средства: -4000');
    }
}

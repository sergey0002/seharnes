<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Админка: редактирование тарифа, вкладка абонплаты.
 *
 * Контракт: .doc/qa/flows/tariff-showcase-discount.md (CT-2429),
 * .doc/qa/flows/tariff-alternative.md (CT-2427).
 * data-test на полях вкладки нет. Селекторы: id + window.tariffEdit + текст.
 */
final class AdminTariffEditPage extends BasePage
{
    public const TAB_SUBSCRIPTION = 'Абонентская плата и Кредиты';
    public const TAB_SFEE = self::TAB_SUBSCRIPTION;
    public const LABEL_WITHOUT_DISCOUNT = 'Стоимость без скидки';
    public const LABEL_ALT = 'Альтернативный тариф';
    public const OPTION_NONE = 'Нет';
    public const VALIDATION_WITHOUT = 'Стоимость без скидки должна быть больше текущей абонентской платы и больше нуля';
    public const MSG_SELF = 'Альтернативный тариф не может совпадать с текущим';
    public const MSG_UNAVAILABLE = 'Выбранный альтернативный тариф недоступен (базовый / без аб. платы / с ограничением профилей)';
    public const MSG_PROFILE_NARROW = 'Нельзя изменить доступность по профилям: тариф выбран в качестве альтернативного.';

    private const INPUT_WITHOUT = '#subscriptionFeeWithoutDiscount';
    private const INPUT_FEE = '#subscriptionFee';

    public function open(int $tariffId): void
    {
        $this->I->amOnPage('/admin/m_router.php?q=tariffs/edit/' . $tariffId);
        $this->I->waitForText('Редактирование тарифа', 20);
        $this->I->waitForJS(
            'return !!(window.tariffEdit && window.tariffEdit.tariff && window.tariffEdit.tariff.id);',
            20
        );
    }

    public function openSubscriptionTab(): void
    {
        $this->I->click(self::TAB_SUBSCRIPTION);
        $this->I->waitForText(self::LABEL_WITHOUT_DISCOUNT, 10);
        $this->I->waitForElementVisible(self::INPUT_WITHOUT, 10);
    }

    public function openSfeeTab(): void
    {
        $this->openSubscriptionTab();
        $this->I->waitForElement('#alternativeTariffId', 10);
        $this->I->see(self::LABEL_ALT);
    }

    public function seeMainParamsTab(): void
    {
        $this->I->see('Доступен для:');
    }

    public function seeNoneSelected(): void
    {
        $this->I->see(self::OPTION_NONE);
        $selected = $this->grabSelectedAlternativeId();
        $this->I->assertTrue(
            $selected === null || $selected === 0,
            'ожидали Нет, получили: ' . var_export($selected, true)
        );
    }

    public function seeSelectEnabled(): void
    {
        $this->I->assertFalse($this->isAltSelectDisabled(), 'селект альтернативы должен быть доступен');
    }

    public function seeSelectDisabled(): void
    {
        $this->I->assertTrue($this->isAltSelectDisabled(), 'селект альтернативы должен быть disabled');
    }

    /** @return list<int> */
    public function grabOptionIds(): array
    {
        $raw = $this->I->executeJS(
            'return (window.tariffEdit.alternativeTariffOptions || []).map(function (o) { return parseInt(o.id, 10); });'
        );
        if (is_object($raw)) {
            $raw = json_decode((string) json_encode($raw), true);
        }
        if (!is_array($raw)) {
            return [];
        }
        $ids = [];
        foreach ($raw as $id) {
            $ids[] = (int) $id;
        }
        return $ids;
    }

    public function selectAlternative(int $altId): void
    {
        $this->I->executeJS('window.tariffEdit.tariff.alternativeTariffId = arguments[0];', [$altId]);
        $this->I->assertSame($altId, $this->grabSelectedAlternativeId());
    }

    public function forceAlternativeId($value): void
    {
        $this->I->executeJS('window.tariffEdit.tariff.alternativeTariffId = arguments[0];', [$value]);
    }

    public function grabSelectedAlternativeId(): ?int
    {
        $raw = $this->I->executeJS('return window.tariffEdit.tariff.alternativeTariffId;');
        if ($raw === null || $raw === '' || $raw === false) {
            return null;
        }
        return (int) $raw;
    }

    public function saveViaVue(): void
    {
        $this->I->executeJS('window.tariffEdit.save();');
    }

    public function saveAndSeeStored(): void
    {
        $this->saveViaVue();
        $this->seeSaved();
    }

    public function uncheckFizikAvailability(): void
    {
        $this->I->executeJS('window.tariffEdit.tariff.isAvailableForFizik = "0";');
    }

    public function seeDiscountField(): void
    {
        $this->I->see(self::TAB_SUBSCRIPTION);
        $this->I->see(self::LABEL_WITHOUT_DISCOUNT);
        $this->I->seeElement(self::INPUT_WITHOUT);
    }

    public function fillWithoutDiscount(string $value): void
    {
        $this->I->fillField(self::INPUT_WITHOUT, $value);
        $this->dispatchInput(self::INPUT_WITHOUT);
    }

    public function fillSubscriptionFee(string $value): void
    {
        $this->I->fillField(self::INPUT_FEE, $value);
        $this->dispatchInput(self::INPUT_FEE);
    }

    public function save(): void
    {
        $this->I->click('Сохранить');
    }

    public function seeSaved(): void
    {
        $this->I->waitForText('Сохранено', 15);
        $this->I->see('Сохранено');
    }

    public function seeWithoutDiscountValidation(): void
    {
        $this->I->waitForText(self::VALIDATION_WITHOUT, 15);
        $this->I->see(self::VALIDATION_WITHOUT);
    }

    public function dontSeeDiscountEditor(): void
    {
        $this->I->dontSee(self::LABEL_WITHOUT_DISCOUNT);
    }

    private function isAltSelectDisabled(): bool
    {
        return (bool) $this->I->executeJS(
            'var el = document.getElementById("alternativeTariffId");'
            . 'return !!(el && el.disabled);'
        );
    }

    private function dispatchInput(string $css): void
    {
        $this->I->executeJS(
            'var el = document.querySelector(arguments[0]);'
            . 'if (el) { el.dispatchEvent(new Event("input", { bubbles: true })); }',
            [$css]
        );
    }
}

<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Витрина тарифов: главная, /tariffs (panel/carousel), /tariffs/view, /tariffs/change.
 *
 * Контракт: .doc/qa/flows/tariff-showcase-discount.md
 * data-test на цене скидки нет (шаблоны не правим). Селекторы: BEM-классы
 * .tariff-price-old / .tariff-price-current / .tarif-circle__price-old
 * и текст из task.md.
 */
final class TariffShowcasePage extends BasePage
{
    public const URL_INDEX = '/tariffs';
    public const URL_HOME = '/';

    public const CLASS_PRICE_OLD = 'tariff-price-old';
    public const CLASS_PRICE_CURRENT = 'tariff-price-current';
    public const CLASS_CIRCLE_OLD = 'tarif-circle__price-old';
    public const CLASS_CIRCLE_DISCOUNT = 'tarif-circle__discount';

    private const PRICE_OLD = '//*[contains(@class,"tariff-price-old")]';
    private const PRICE_CURRENT = '//*[contains(@class,"tariff-price-current")]';
    private const CIRCLE_OLD = '//*[contains(@class,"tarif-circle__price-old")]';
    private const TOGGLE_CAROUSEL = '//*[contains(@class,"toggle-switch__item--left")]';
    private const TOGGLE_PANEL = '//*[contains(@class,"toggle-switch__item--right")]';

    public function openHome(): void
    {
        $this->I->amOnPage(self::URL_HOME);
        $this->I->waitForText('Наши тарифы', 20);
        $this->I->waitForElementVisible('//*[contains(@class,"tarif-circle")]', 20);
    }

    public function openIndex(): void
    {
        $this->I->amOnPage(self::URL_INDEX);
        $this->I->waitForElementVisible('//h1[contains(@class,"all-tariffs-page__title")]', 20);
        $this->I->waitForText('Наши тарифы', 20);
    }

    public function openView(int $tariffId): void
    {
        $this->I->amOnPage('/tariffs/view/' . $tariffId);
        $this->I->waitForText('Абонентская плата', 20);
    }

    public function openChange(int $tariffId): void
    {
        $this->I->amOnPage('/tariffs/change?id=' . $tariffId);
        $this->I->waitForText('Смена тарифа', 20);
    }

    public function switchToCarousel(): void
    {
        $this->I->click(self::TOGGLE_CAROUSEL);
        $this->I->waitForElementVisible(self::PRICE_OLD, 15);
    }

    public function switchToPanel(): void
    {
        $this->I->click(self::TOGGLE_PANEL);
        $this->I->waitForElementVisible(self::PRICE_OLD, 15);
    }

    public function seeTariffName(string $name): void
    {
        $this->I->see($name);
    }

    public function seeStrikeOldAndCurrentPercent(string $oldAmount, string $fee, string $percentLiteral): void
    {
        $this->I->waitForElementVisible(self::PRICE_OLD, 15);
        $this->I->see($oldAmount, self::PRICE_OLD);
        $this->I->see($fee);
        $this->I->see($percentLiteral);
        $this->seeOldPriceLineThrough(self::CLASS_PRICE_OLD);
        $this->seeCurrentDiscountColor(self::CLASS_PRICE_CURRENT);
    }

    public function seeViewDiscount(string $oldAmount, string $fee, string $percentLiteral): void
    {
        $this->I->see('Абонентская плата');
        $this->seeStrikeOldAndCurrentPercent($oldAmount, $fee, $percentLiteral);
    }

    public function dontSeeDiscountMarkup(): void
    {
        $this->I->dontSeeElement(self::PRICE_OLD);
        $this->I->dontSeeElement(self::PRICE_CURRENT);
        $this->I->dontSeeElement(self::CIRCLE_OLD);
    }

    public function seeMainpageCircleDiscount(string $tariffName, string $oldAmount, string $percentLiteral): void
    {
        $this->I->waitForText($tariffName, 20);
        $found = $this->I->executeJS(
            'var name = arguments[0];'
            . 'var titles = document.querySelectorAll("h3.tarif-item__title");'
            . 'for (var i = 0; i < titles.length; i++) {'
            . '  if ((titles[i].textContent || "").indexOf(name) === -1) { continue; }'
            . '  var root = titles[i].parentElement;'
            . '  if (!root) { return "no-root"; }'
            . '  var oldEl = root.querySelector(".' . self::CLASS_CIRCLE_OLD . '");'
            . '  var disc = root.querySelector(".' . self::CLASS_CIRCLE_DISCOUNT . '");'
            . '  if (!oldEl) { return "no-old"; }'
            . '  if (!disc) { return "no-percent"; }'
            . '  return (oldEl.textContent || "") + "|" + (disc.textContent || "");'
            . '}'
            . 'return "no-title";',
            [$tariffName]
        );
        $this->I->assertTrue(is_string($found) && str_contains($found, $oldAmount), 'circle old price: ' . (string) $found);
        $this->I->assertTrue(is_string($found) && str_contains($found, $percentLiteral), 'circle percent: ' . (string) $found);
        $this->seeOldPriceLineThrough(self::CLASS_CIRCLE_OLD);
    }

    public function seeAvailableProfilesNeighbor(): void
    {
        $this->I->see('Доступные профили:');
    }

    public function seeOldPriceLineThrough(string $className): void
    {
        $deco = $this->I->executeJS(
            'var cls = arguments[0];'
            . 'var el = document.querySelector("." + cls);'
            . 'if (!el) { return ""; }'
            . 'var s = window.getComputedStyle(el);'
            . 'return (s.textDecorationLine || s.textDecoration || "").toLowerCase();',
            [$className]
        );
        $this->I->assertTrue(
            is_string($deco) && str_contains($deco, 'line-through'),
            'expected line-through on .' . $className . ', got: ' . (string) $deco
        );
    }

    public function seeCurrentDiscountColor(string $className): void
    {
        $color = $this->I->executeJS(
            'var cls = arguments[0];'
            . 'var el = document.querySelector("." + cls);'
            . 'if (!el) { return ""; }'
            . 'return window.getComputedStyle(el).color || "";',
            [$className]
        );
        $ok = is_string($color) && (
            str_contains($color, '230, 126, 34')
            || str_contains($color, '255, 224, 130')
            || str_contains($color, '255, 179, 71')
        );
        $this->I->assertTrue($ok, 'expected discount color on .' . $className . ', got: ' . (string) $color);
    }
}

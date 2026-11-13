<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Витрина тарифов: /tariffs (panel), главная /, полный список /tariffs/showall.
 *
 * Контракт: .doc/qa/flows/tariff-showcase-markers.md (CT-2467).
 * data-test маркера ограничения: tariff-plate-restricted (уже в шаблоне).
 * Рамка базового: класс --default (tariff-plate-default в JS, в реестре data-test нет).
 * Шаблоны не правим.
 */
final class TariffListPage extends BasePage
{
    public const URL = '/tariffs';
    public const URL_SHOWALL = '/tariffs/showall';
    public const URL_HOME = '/';

    public const TOOLTIP_PREFIX = 'Тариф не доступен для ';
    public const LABEL_FIZIK = 'Физ. лица';
    public const LABEL_JURIK = 'Юр. лица';
    public const LABEL_IP = 'ИП';
    public const STATUS_RESTRICTED = 'С ограничениями';
    public const STATUS_ARCHIVE = 'Архивный';

    private const RESTRICTED = 'tariff-plate-restricted';
    private const PANEL_CARD = '//div[contains(@class,"tariffs-desktop-panel-card") or contains(@class,"tariffs-mobile-panel-card")]';
    private const DEFAULT_CARD = '//div[contains(@class,"tariffs-desktop-panel-card--default") or contains(@class,"tariffs-mobile-panel-card--default")]';
    private const HOME_RESTRICTED = '//div[contains(@class,"tarif-item--restricted")]';
    private const HOME_DEFAULT = '//div[contains(@class,"tarif-item--default")]';
    private const TOGGLE_CAROUSEL = '//*[contains(@class,"toggle-switch__item--left")]';
    private const CAROUSEL_ITEM = '//div[contains(@class,"tariffs-desktop-carousel-item") or contains(@class,"tariffs-mobile-carousel-slide")]';
    private const CAROUSEL_DEFAULT = '//div[(contains(@class,"tariffs-desktop-carousel-item__content") or contains(@class,"tariffs-mobile-carousel-slide")) and @data-default="1"]';

    public function open(): void
    {
        $this->I->amOnPage(self::URL);
        $this->I->waitForJS('return Array.isArray(window.tariffs);', 15);
        $this->I->waitForText('Наши тарифы', 15);
        $this->I->waitForElement(self::PANEL_CARD, 15);
    }

    public function openHome(): void
    {
        $this->I->amOnPage(self::URL_HOME);
        $this->I->waitForJS('return Array.isArray(window.tariffs);', 15);
        $this->I->waitForElement('//div[contains(@class,"tarif-item")]', 20);
    }

    public function openShowall(): void
    {
        $this->I->amOnPage(self::URL_SHOWALL);
        $this->I->waitForText('Полный список тарифов', 15);
    }

    public function logoutThenOpen(): void
    {
        $this->I->amOnPage('/account/logout');
        $this->open();
    }

    public function dontSeeTariffName(string $name): void
    {
        $this->I->dontSee($name);
    }

    public function seeTariffName(string $name): void
    {
        $this->I->see($name);
    }

    public function seeRestrictedBadgeOnCard(string $name): void
    {
        $this->I->waitForElement($this->restrictedBadgeOnCard($name), 10);
        $this->I->seeElement($this->restrictedBadgeOnCard($name) . '//*[local-name()="svg"]');
    }

    public function dontSeeRestrictedBadgeOnCard(string $name): void
    {
        $this->I->seeElement($this->cardByName($name));
        $this->I->dontSeeElement($this->restrictedBadgeOnCard($name));
    }

    public function seeRestrictedTooltipOnCard(string $name, string $unavailableLabel): void
    {
        $this->I->moveMouseOver($this->restrictedBadgeOnCard($name));
        $this->I->waitForText(self::TOOLTIP_PREFIX . $unavailableLabel, 10);
        $this->I->see(self::TOOLTIP_PREFIX . $unavailableLabel);
    }

    public function seeDefaultCardOnShowcase(): void
    {
        $this->I->waitForElement(self::DEFAULT_CARD, 10);
    }

    public function seeHomeRestrictedAndDefaultMarkers(): void
    {
        $ids = $this->grabWindowTariffIds();
        $this->I->assertNotEmpty($ids, 'window.tariffs on home is empty');
        $this->I->seeElement(self::HOME_RESTRICTED);
        $this->I->dontSeeElement(self::HOME_DEFAULT);
    }

    public function switchToCarousel(): void
    {
        $this->I->click(self::TOGGLE_CAROUSEL);
        $this->I->waitForElementVisible(self::CAROUSEL_ITEM, 15);
    }

    public function seeCarouselRestrictedBadge(string $name): void
    {
        $safe = $this->safe($name);
        $xpath = self::CAROUSEL_ITEM
            . '[contains(normalize-space(.),"' . $safe . '")]'
            . self::test(self::RESTRICTED);
        $this->I->waitForElement($xpath, 10);
        $this->I->seeElement($xpath . '//*[local-name()="svg"]');
    }

    public function seeCarouselDefaultBorder(): void
    {
        $this->I->waitForElement(self::CAROUSEL_DEFAULT, 10);
        $raw = $this->I->executeJS(
            'var el = document.querySelector(".tariffs-desktop-carousel-item__content[data-default=\'1\'], .tariffs-mobile-carousel-slide[data-default=\'1\']");'
            . 'if (!el) { return "missing"; }'
            . 'var s = window.getComputedStyle(el);'
            . 'var frame = window.getComputedStyle(el, ":after");'
            . 'var header = el.querySelector(".tariffs-desktop-carousel-item__header");'
            . 'var layoutW = parseFloat(s.borderTopWidth) || 0;'
            . 'var frameW = parseFloat(frame.borderTopWidth) || 0;'
            . 'var frameR = parseFloat(frame.borderTopLeftRadius) || 0;'
            . 'if (!header) { return layoutW + "|" + frameW + "px|" + frame.borderTopColor + "|no-header"; }'
            . 'var headerR = parseFloat(window.getComputedStyle(header).borderTopLeftRadius) || 0;'
            . 'var match = Math.abs(frameR - headerR) < 0.6;'
            . 'var buttons = Array.prototype.slice.call(document.querySelectorAll(".tariffs-desktop-carousel-item__button"));'
            . 'var align = "skip";'
            . 'if (buttons.length > 1) {'
            . '  var tops = buttons.map(function (b) { return Math.round(b.getBoundingClientRect().top); });'
            . '  align = String(Math.max.apply(null, tops) - Math.min.apply(null, tops));'
            . '}'
            . 'return layoutW + "|" + frameW + "px|" + frame.borderTopColor + "|"'
            . '+ (match ? "match" : "mismatch") + "|align:" + align;'
        );
        $this->I->assertTrue(is_string($raw) && strpos($raw, '0|2px|') === 0, 'carousel default uses overlay 2px, no layout border, got: ' . (string) $raw);
        $this->I->assertTrue(is_string($raw) && strpos($raw, '55, 62, 83') !== false, 'carousel default navy #373e53, got: ' . (string) $raw);
        $this->I->assertTrue(
            is_string($raw) && (strpos($raw, '|match|') !== false || strpos($raw, '|no-header') !== false),
            'carousel frame radius must match header 5px, got: ' . (string) $raw
        );
        if (is_string($raw) && strpos($raw, '|align:skip') === false) {
            $this->I->assertTrue(preg_match('/\\|align:([0-9]+)/', $raw, $m) === 1 && (int) $m[1] <= 1, 'Подключить buttons must share one baseline, got: ' . (string) $raw);
        }
    }

    public function seeCarouselRestrictedTooltip(string $name, string $unavailableLabel): void
    {
        $safe = $this->safe($name);
        $xpath = self::CAROUSEL_ITEM
            . '[contains(normalize-space(.),"' . $safe . '")]'
            . self::test(self::RESTRICTED);
        $this->I->moveMouseOver($xpath);
        $content = $this->I->executeJS(
            'var el = document.evaluate(arguments[0], document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;'
            . 'if (!el) { return ""; }'
            . 'return el.getAttribute("data-tooltip") || "";',
            [$xpath]
        );
        $this->I->assertSame(self::TOOLTIP_PREFIX . $unavailableLabel, (string) $content);
    }

    public function seeDefaultPanelBorderNavy2px(): void
    {
        $raw = $this->I->executeJS(
            'var el = document.querySelector(".tariffs-desktop-panel-card--default, .tariffs-mobile-panel-card--default");'
            . 'if (!el) { return "missing"; }'
            . 'var s = window.getComputedStyle(el);'
            . 'return s.borderTopWidth + "|" + s.borderTopColor;'
        );
        $this->I->assertTrue(is_string($raw) && strpos($raw, '2px|') === 0, 'default border width: ' . (string) $raw);
        $this->I->assertTrue(is_string($raw) && strpos($raw, '55, 62, 83') !== false, 'default border navy #373e53, got: ' . (string) $raw);
    }

    public function dontSeeRestrictedCorner(): void
    {
        $raw = $this->I->executeJS(
            'var el = document.querySelector(".tariffs-desktop-panel-card--restricted, .tariffs-mobile-panel-card--restricted, .tarif-item--restricted");'
            . 'if (!el) { return "no-restricted"; }'
            . 'var s = window.getComputedStyle(el, ":before");'
            . 'return (s.content || "") + "|" + (s.borderLeftWidth || "");'
        );
        $ok = is_string($raw) && (
            $raw === 'no-restricted'
            || strpos($raw, 'none') !== false
            || strpos($raw, 'normal') !== false
        );
        $this->I->assertTrue($ok, 'restricted ::before must not be a red triangle, got: ' . (string) $raw);
    }

    /**
     * @return list<int>
     */
    public function grabWindowTariffIds(): array
    {
        $raw = $this->I->executeJS(
            'return (window.tariffs || []).map(function (t) { return parseInt(t.id, 10); });'
        );

        return $this->intList($raw);
    }

    /**
     * @return array<string, mixed>
     */
    public function grabWindowTariffByName(string $name): array
    {
        $raw = $this->I->executeJS(
            'var name = arguments[0];'
            . 'var list = window.tariffs || [];'
            . 'for (var i = 0; i < list.length; i++) {'
            . '  var label = list[i].label || list[i].name || "";'
            . '  if (label === name) { return list[i]; }'
            . '}'
            . 'return null;',
            [$name]
        );
        if (is_object($raw)) {
            $raw = json_decode((string) json_encode($raw), true);
        }
        $this->I->assertTrue(is_array($raw), 'window.tariffs has no item named ' . $name);

        return $raw;
    }

    public function seeWindowTariffLabels(
        string $name,
        string $availableLabel,
        string $unavailableLabel
    ): void {
        $row = $this->grabWindowTariffByName($name);
        $this->I->assertSame(1, (int) ($row['visible'] ?? 0), 'visible on showcase DTO');
        $this->I->assertSame(1, (int) ($row['isSelectable'] ?? 0), 'isSelectable on showcase DTO');
        $this->I->assertNotEmpty($row['hasProfileRestrictions'] ?? false, 'hasProfileRestrictions');
        $this->I->assertSame($availableLabel, (string) ($row['availableProfileTypesLabel'] ?? ''));
        $this->I->assertSame($unavailableLabel, (string) ($row['unavailableProfileTypesLabel'] ?? ''));
    }

    public function seeWindowHasTariffId(int $id): void
    {
        $this->I->assertTrue(
            in_array($id, $this->grabWindowTariffIds(), true),
            'window.tariffs must contain id ' . $id
        );
    }

    public function dontSeeWindowHasTariffId(int $id): void
    {
        $this->I->assertFalse(
            in_array($id, $this->grabWindowTariffIds(), true),
            'window.tariffs must not contain id ' . $id
        );
    }

    public function seeShowallStatus(string $name, string $status): void
    {
        $this->I->waitForText($name, 10);
        $xpath = '//tr[.//a[normalize-space()="' . $this->safe($name) . '"]]'
            . '//span[contains(@class,"tariffs-full-list-page__badge") and contains(normalize-space(.),"'
            . $this->safe($status) . '")]';
        $this->I->seeElement($xpath);
    }

    /**
     * POST /tariff/all без фильтра витрины (CT-2467: JSON all не режем).
     *
     * @return list<int>
     */
    public function grabJsonAllTariffIds(): array
    {
        $this->I->executeJS(
            'window.__ct2467All = null;'
            . 'fetch("/tariff/all", {'
            . '  method: "POST",'
            . '  credentials: "same-origin",'
            . '  headers: {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8", "X-Requested-With": "XMLHttpRequest"},'
            . '  body: ""'
            . '}).then(function (r) { return r.json(); }).then(function (j) {'
            . '  window.__ct2467All = j;'
            . '}).catch(function (e) {'
            . '  window.__ct2467All = {error: String(e)};'
            . '});'
        );
        $this->I->waitForJS('return window.__ct2467All !== null;', 15);
        $raw = $this->I->executeJS('return window.__ct2467All;');
        if (is_object($raw)) {
            $raw = json_decode((string) json_encode($raw), true);
        }
        $this->I->assertTrue(is_array($raw), 'POST /tariff/all did not return JSON');
        $this->I->assertArrayNotHasKey('error', $raw, (string) ($raw['error'] ?? ''));

        $list = $raw['data'] ?? null;
        if (is_object($list)) {
            $list = json_decode((string) json_encode($list), true);
        }
        $this->I->assertTrue(is_array($list), 'POST /tariff/all has no data[]');

        $ids = [];
        foreach ($list as $item) {
            if (is_object($item)) {
                $item = json_decode((string) json_encode($item), true);
            }
            if (is_array($item) && isset($item['id'])) {
                $ids[] = (int) $item['id'];
            }
        }

        return $ids;
    }

    public function seeJsonAllContains(int $id): void
    {
        $this->I->assertTrue(
            in_array($id, $this->grabJsonAllTariffIds(), true),
            'POST /tariff/all must still contain id ' . $id
        );
    }

    public function grabDefaultShowcaseId(): int
    {
        $raw = $this->I->executeJS(
            'var list = window.tariffs || [];'
            . 'for (var i = 0; i < list.length; i++) {'
            . '  if (parseInt(list[i].isDefault, 10) === 1) { return parseInt(list[i].id, 10); }'
            . '}'
            . 'return 0;'
        );

        return (int) $raw;
    }

    private function cardByName(string $name): string
    {
        $safe = $this->safe($name);

        return self::PANEL_CARD
            . '[.//*[contains(@class,"__name") and normalize-space()="' . $safe . '"]]';
    }

    private function restrictedBadgeOnCard(string $name): string
    {
        return $this->cardByName($name) . self::test(self::RESTRICTED);
    }

    private function safe(string $value): string
    {
        return str_replace(['"', "'"], '', $value);
    }

    /**
     * @param mixed $raw
     * @return list<int>
     */
    private function intList($raw): array
    {
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
}

<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Полный список тарифов: /tariffs/showall и ссылка с витрины /tariffs.
 *
 * Контракт: .doc/qa/flows/tariff-full-list.md
 * Задача: CT-2520. data-test на таблице нет, шаблоны не правим.
 * Селекторы: BEM tariffs-full-list-page / tariffs-full-list-link.
 */
final class TariffFullListPage extends BasePage
{
    public const URL = '/tariffs/showall';
    public const URL_LEGACY_ALL = '/tariffs/all';
    public const URL_VITRINE = '/tariffs';

    public const TITLE = 'Полный список тарифов';
    public const COL_ID = 'ID';
    public const COL_NAME = 'Название';
    public const COL_DESC = 'Краткое описание';
    public const COL_FEE = 'Аб. плата';
    public const COL_STATUS = 'Статус';
    public const FEE_YES = 'Аб. плата';
    public const STATUS_DEFAULT = 'Базовый';
    public const STATUS_ACTIVE = 'Активный';
    public const STATUS_RESTRICTED = 'С ограничениями';
    public const STATUS_SERVICE = 'Служебный';
    public const STATUS_ARCHIVE = 'Архивный';

    private const PAGE = '//section[contains(@class,"tariffs-full-list-page")]';
    private const TITLE_EL = '//h1[contains(@class,"tariffs-full-list-page__title")]';
    private const TABLE = '//table[contains(@class,"tariffs-full-list-page__table")]';
    private const FULL_LIST_LINK = '//div[contains(@class,"tariffs-full-list-link")]//a[normalize-space()="Полный список тарифов"]';
    private const TOGGLE_CAROUSEL = '//*[contains(@class,"toggle-switch__item--left")]';
    private const TOGGLE_PANEL = '//*[contains(@class,"toggle-switch__item--right")]';
    private const VITRINE_TITLE = 'Наши тарифы';

    public function open(): void
    {
        $this->I->amOnPage(self::URL);
        $this->I->waitForElement(self::PAGE, 15);
        $this->I->waitForText(self::TITLE, 10, self::TITLE_EL);
    }

    public function seeHeadingAndColumns(): void
    {
        $this->I->see(self::TITLE, self::TITLE_EL);
        $this->I->see(self::COL_ID, self::TABLE);
        $this->I->see(self::COL_NAME, self::TABLE);
        $this->I->see(self::COL_DESC, self::TABLE);
        $this->I->see(self::COL_FEE, self::TABLE);
        $this->I->see(self::COL_STATUS, self::TABLE);
        $this->I->see('Тарифные планы');
    }

    public function seeRow(int $id, string $name, string $description): void
    {
        $this->I->see($name, $this->row($id));
        $this->I->see($description, $this->row($id));
        $this->I->see((string) $id, $this->row($id) . '//td[contains(@class,"tariffs-full-list-page__col-id")]');
        $href = $this->row($id) . '//a[contains(@class,"tariffs-full-list-page__link") and contains(@href,"/tariffs/view/' . $id . '")]';
        $this->I->seeElement($href);
    }

    public function dontSeeRow(int $id): void
    {
        $this->I->dontSeeElement($this->row($id));
    }

    public function seeFeeYes(int $id): void
    {
        $this->I->see(
            self::FEE_YES,
            $this->row($id) . '//span[contains(@class,"tariffs-full-list-page__fee--yes")]'
        );
    }

    public function seeFeeNo(int $id): void
    {
        $this->I->seeElement(
            $this->row($id) . '//span[contains(@class,"tariffs-full-list-page__fee--no")]'
        );
    }

    public function seeBadge(int $id, string $code, string $label): void
    {
        $xpath = $this->row($id)
            . '//span[contains(@class,"tariffs-full-list-page__badge--' . $code . '")'
            . ' and contains(normalize-space(.),"' . $this->safe($label) . '")]';
        $this->I->seeElement($xpath);
    }

    public function dontSeeBadge(int $id, string $code): void
    {
        $this->I->dontSeeElement(
            $this->row($id) . '//span[contains(@class,"tariffs-full-list-page__badge--' . $code . '")]'
        );
    }

    public function clickName(int $id): void
    {
        $this->I->click(
            $this->row($id) . '//a[contains(@class,"tariffs-full-list-page__link")]'
        );
        $this->I->waitForJS(
            'return window.location.pathname.indexOf("/tariffs/view/' . $id . '") !== -1;',
            15
        );
    }

    public function openVitrine(): void
    {
        $this->I->amOnPage(self::URL_VITRINE);
        $this->I->waitForText(self::VITRINE_TITLE, 20);
        $this->I->waitForElementVisible(self::FULL_LIST_LINK, 15);
    }

    public function seeVitrineFullListLink(): void
    {
        $this->I->see(self::TITLE, self::FULL_LIST_LINK);
        $this->I->seeElement(self::FULL_LIST_LINK . '[contains(@href,"/tariffs/showall")]');
    }

    public function clickVitrineFullListLink(): void
    {
        $this->I->click(self::FULL_LIST_LINK);
        $this->I->waitForElement(self::PAGE, 15);
        $this->I->seeInCurrentUrl('/tariffs/showall');
    }

    public function switchVitrineToCarouselAndSeeLink(): void
    {
        $this->I->click(self::TOGGLE_CAROUSEL);
        $this->I->waitForElementVisible(self::FULL_LIST_LINK, 15);
        $this->seeVitrineFullListLink();
        $this->I->click(self::TOGGLE_PANEL);
        $this->I->waitForElementVisible(self::FULL_LIST_LINK, 15);
        $this->seeVitrineFullListLink();
    }

    public function openLegacyAllAndDontSeeFullList(): void
    {
        $this->I->amOnPage(self::URL_LEGACY_ALL);
        $this->I->dontSeeElement(self::PAGE);
        $this->I->dontSeeElement(self::TABLE);
    }

    public function reloadAndSeeTitle(): void
    {
        $this->I->reloadPage();
        $this->I->waitForElement(self::PAGE, 15);
        $this->I->see(self::TITLE, self::TITLE_EL);
    }

    /**
     * @return list<int>
     */
    public function grabListedIds(): array
    {
        $raw = $this->I->executeJS(
            'var links = document.querySelectorAll("a.tariffs-full-list-page__link");'
            . 'var ids = [];'
            . 'for (var i = 0; i < links.length; i++) {'
            . '  var m = (links[i].getAttribute("href") || "").match(/\\/tariffs\\/view\\/(\\d+)/);'
            . '  if (m) { ids.push(parseInt(m[1], 10)); }'
            . '}'
            . 'return ids;'
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

    private function row(int $id): string
    {
        return '//tr[.//a[contains(@href,"/tariffs/view/' . $id . '")]]';
    }

    private function safe(string $value): string
    {
        return str_replace(['"', "'"], '', $value);
    }
}

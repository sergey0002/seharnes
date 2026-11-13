<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Клиентская страница тарифа: /tariffs/view/{id}.
 *
 * Контракт: .doc/qa/flows/tariff-hidden-archive.md
 * Задача: CT-2511. data-test на H1 и кнопке нет, шаблоны не правим.
 */
final class TariffViewPage extends BasePage
{
    private const TITLE = '//h1[contains(@class,"tariff-more-header-left__title")]';
    private const TITLE_ARCHIVE = '//h1[contains(@class,"tariff-more-header-left__title") and contains(.,"(Архивный)")]';
    private const CONNECT = '//a[contains(@class,"tariff-more-btn")]';
    private const CONNECT_TEXT = '//div[contains(@class,"tariff-more-btn__text") and contains(normalize-space(.),"Подключить")]';
    private const BREADCRUMBS = '//section[contains(@class,"breadcrumbs")]';
    private const SHOWCASE_CORNER = '//*[contains(@class,"tariff-showcase-marker") or contains(@class,"showcase-marker")]';

    public static function url(int $id): string
    {
        return '/tariffs/view/' . $id;
    }

    public function open(int $id): void
    {
        $this->I->amOnPage(self::url($id));
        $this->I->waitForElementVisible(self::TITLE, 15);
    }

    public function seeArchiveLabel(): void
    {
        $this->I->waitForElementVisible(self::TITLE_ARCHIVE, 10);
        $this->I->see('(Архивный)', self::TITLE);
    }

    public function dontSeeArchiveLabel(): void
    {
        $this->I->waitForElementVisible(self::TITLE, 10);
        $this->I->dontSeeElement(self::TITLE_ARCHIVE);
        $this->I->dontSee('(Архивный)', self::TITLE);
    }

    public function seeConnectButton(): void
    {
        $this->I->waitForElementVisible(self::CONNECT, 10);
        $this->I->see('Подключить', self::CONNECT_TEXT);
    }

    public function dontSeeConnectButton(): void
    {
        $this->I->dontSeeElement(self::CONNECT);
        $this->I->dontSeeElement(self::CONNECT_TEXT);
    }

    public function dontSeeArchiveInBreadcrumbs(): void
    {
        $this->I->seeElement(self::BREADCRUMBS);
        $this->I->dontSee('(Архивный)', self::BREADCRUMBS);
    }

    public function seeAvailableProfilesRow(): void
    {
        $this->I->see('Доступные профили:');
    }

    public function dontSeeShowcaseMarkers(): void
    {
        $this->I->dontSeeElement(self::SHOWCASE_CORNER);
    }
}

<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Админский список тарифов: /admin/m_tariff.php
 *
 * Контракт: .doc/qa/flows/tariff-delete.md
 * Задача: CT-2428 (блокеры Remove + soft-delete).
 */
final class AdminTariffListPage extends BasePage
{
    public const URL = '/admin/m_tariff.php';

    public const MSG_DEFAULT = 'Невозможно удалить базовый тариф';
    public const MSG_USERS = 'Нельзя удалить тариф: к нему подключены пользователи';
    public const MSG_PROMO = 'Нельзя удалить тариф: есть неактивированные промо-коды со сроком активации, который ещё не истек';
    public const MSG_ALTERNATIVE = 'Нельзя удалить тариф: он указан как альтернативный у другого тарифа';
    public const ERR_MODAL_TITLE = 'Ошибка';

    private const DELETE_BTN_PREFIX = 'tariff-delete-btn-';
    private const CONFIRM = 'tariff-delete-confirm';

    public function open(): void
    {
        $this->I->amOnPage(self::URL);
        $this->I->waitForElement('#vue-tariffs-container', 15);
    }

    public function deleteTariff(int $tariffId): void
    {
        $this->open();
        $btn = $this->deleteBtn($tariffId);
        $this->I->waitForElement($btn, 10);
        $this->I->click($btn);
        $this->I->waitForElement(self::test(self::CONFIRM), 10);
        $this->I->click(self::test(self::CONFIRM));
    }

    public function waitForErrorModal(string $message): void
    {
        $this->I->waitForText(self::ERR_MODAL_TITLE, 15);
        $this->I->waitForText($message, 15);
        $this->I->see($message);
    }

    public function dismissErrorModal(): void
    {
        $this->I->executeJS(
            'if (window.storeVue) { window.storeVue.dispatch("Errors/clearErrors"); }'
        );
        $this->I->waitForJS(
            'return !(window.storeVue && window.storeVue.state'
            . ' && window.storeVue.state.Errors'
            . ' && window.storeVue.state.Errors.showErrorModal);',
            5
        );
    }

    public function waitTariffGoneFromList(int $tariffId): void
    {
        $this->I->waitForElementNotVisible($this->deleteBtn($tariffId), 15);
    }

    public function seeDeleteButton(int $tariffId): void
    {
        $this->I->seeElement($this->deleteBtn($tariffId));
    }

    public function dontSeeDeleteButton(int $tariffId): void
    {
        $this->I->dontSeeElement($this->deleteBtn($tariffId));
    }

    private function deleteBtn(int $tariffId): string
    {
        return self::test(self::DELETE_BTN_PREFIX . $tariffId);
    }
}

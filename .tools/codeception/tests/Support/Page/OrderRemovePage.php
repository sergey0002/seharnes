<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Форма заказа архивации / удаления ОИС: /order/remove (услуги 2030/2031).
 *
 * Контракт: .doc/qa/flows/order-remove.md
 * Задача-источник: CT-2070.
 *
 * data-test на форме нет. Селекторы: BEM order-cert / delete-form и Vue-теги.
 */
final class OrderRemovePage extends BasePage
{
    public const URL = '/order/remove';

    private const TITLE = '//h1[contains(@class,"order-cert__title")]';
    private const FORM = '//*[contains(@class,"order-cert")]';
    private const PIN_INPUT = '//input[contains(@class,"delete-form__input")]';
    private const SUBMIT = '//button[contains(@class,"order-cert-send__btn")]';
    private const TECH_TAB = '//*[contains(@class,"item-tab__text") and normalize-space()="Технические услуги"]';
    private const TILE_REMOVE = '//p[contains(@class,"creation__item_text") and normalize-space()="Удаление ОИС"]/ancestor::a[1]';
    private const SUBJECT_LIST_TAG = 'order-subject-list2';
    private const REMOVE_FORM_TAG = 'remove-form';

    public function open(?string $rid = null): void
    {
        $url = self::URL;
        if ($rid !== null && $rid !== '') {
            $url .= '?rid=' . rawurlencode($rid);
        }
        $this->I->amOnPage($url);
        $this->I->waitForElement(self::FORM, 20);
        $this->I->waitForJS(
            'return !!(window.Vue && document.getElementById("vue-remove-order-container"));',
            15
        );
    }

    public function openFromTechnicalServicesTile(): void
    {
        $this->I->amOnPage('/item/main');
        $this->I->waitForElement(self::test('item-main'), 20);
        $this->I->click(self::TECH_TAB);
        $this->I->waitForElement(self::TILE_REMOVE, 15);
        $this->I->click(self::TILE_REMOVE);
        $this->I->waitForElement(self::FORM, 20);
    }

    public function seeTitle(): void
    {
        $this->I->see('Заказ архивации / удаления ОИС', self::TITLE);
    }

    public function seeArchiveTitle(): void
    {
        $this->I->see('Заказ архивации / удаления ОИС', self::TITLE);
    }

    public function seeArchiveCheckboxChecked(): void
    {
        $checked = $this->I->executeJS(
            'var root = document.getElementById("vue-remove-order-container");'
            . 'var vue = root && root.__vue__;'
            . 'var form = vue && vue.$children && vue.$children.find(function(child) {'
            . '  return child.form && Object.prototype.hasOwnProperty.call(child.form, "archive");'
            . '});'
            . 'return form && form.form && form.form.archive === true;'
        );
        $this->I->assertTrue((bool) $checked, 'Флаг Архивации ОИС должен быть включён по умолчанию');
    }

    public function seePinFieldIsText(): void
    {
        $this->I->seeElement(self::PIN_INPUT);
        $type = $this->I->executeJS(
            'var nodes = document.getElementsByClassName("delete-form__input");'
            . 'return nodes.length ? nodes[0].getAttribute("type") : "";'
        );
        $this->I->assertSame('text', (string) $type, 'PIN должен быть type=text, не password');
    }

    public function seeTaskLiterals(): void
    {
        $this->I->see('PIN-код запрашивается при добавлении объекта');
        $this->I->see('Будьте внимательны! При архивации сохраняется запись об объекте в реестре');
        $this->I->see('В обоих случаях ранее выданные справки и свидетельства утрачивают юридическую силу');
        $this->I->see('ЗАКАЗАТЬ');
    }

    public function seeArchiveTaskLiterals(): void
    {
        $this->I->see('PIN-код запрашивается при добавлении объекта');
        $this->I->see('Будьте внимательны! При архивации сохраняется запись об объекте в реестре');
        $this->I->see('В обоих случаях ранее выданные справки и свидетельства утрачивают юридическую силу');
        $this->I->see('ЗАКАЗАТЬ');
    }

    public function seeSubmitDisabled(): void
    {
        $this->I->seeElement(self::SUBMIT);
        $disabled = $this->I->executeJS(
            'var nodes = document.getElementsByClassName("order-cert-send__btn");'
            . 'if (!nodes.length) { return "missing"; }'
            . 'return nodes[0].disabled ? "1" : "0";'
        );
        $this->I->assertSame('1', (string) $disabled, 'Кнопка ЗАКАЗАТЬ должна быть disabled');
    }

    /**
     * Подставляет один ОИС в Vue без SOAP-списка, чтобы нажать ЗАКАЗАТЬ.
     * Создание заказа всё равно уйдёт в TryExtractReginfo/checkPin.
     */
    public function seedSubjectAndConsent(string $uin, string $pin = ''): void
    {
        $result = $this->I->executeJS(
            'var uin = arguments[0];'
            . 'var pin = arguments[1];'
            . 'var item = {UIN: uin, name: uin};'
            . 'var find = ' . self::jsFindVueComponent() . ';'
            . 'if (!window.params) { return "no-params"; }'
            . 'window.params.allowedRids = [item];'
            . 'var form = find("' . self::REMOVE_FORM_TAG . '");'
            . 'if (!form) { return "no-form"; }'
            . 'form.form.pins = {};'
            . 'if (pin !== "") { form.form.pins[uin] = pin; }'
            . 'form.form.rids = [uin];'
            . 'form.isCheckedPersonData = true;'
            . 'var list = find("' . self::SUBJECT_LIST_TAG . '");'
            . 'if (list) {'
            . '  list.values = [item];'
            . '  list.$emit("input", [uin]);'
            . '}'
            . 'return "ok";',
            [$uin, $pin]
        );

        $this->I->assertSame('ok', $result, 'remove-form не найден на ' . self::URL);
        $this->I->waitForJS('return true;', 2);
    }

    public function clickSubmit(): void
    {
        $this->I->click(self::SUBMIT);
    }

    public function countToasts(): int
    {
        return (int) $this->I->executeJS('return document.querySelectorAll(".toasted-container").length;');
    }

    /** Ожидаемая ошибка MakeRemove (fake UIN / SOAP). */
    public function seeDataNotFoundError(): void
    {
        $this->I->waitForText('Данные не найдены', 15);
        $this->I->see('Данные не найдены');
    }

    /** Закрыть error-modal через storeVue или крестик .modal-mask. */
    public function dismissErrorModal(): void
    {
        $this->I->executeJS(
            'if (window.storeVue && window.storeVue.dispatch) {'
            . '  window.storeVue.dispatch("Errors/clearErrors");'
            . '  return "store";'
            . '}'
            . 'var btn = document.querySelector(".modal-mask button.modal-close__button");'
            . 'if (btn) { btn.click(); return "click"; }'
            . 'return "none";'
        );
        $this->I->waitForElementNotVisible(
            '//div[contains(@class,"modal-mask")]//h2[contains(@class,"modal-header__title")]',
            10
        );
    }

    public function postMakeRemove(string $uin, string $pin = ''): string
    {
        $body = json_encode(['rids' => [$uin], 'keyword' => $pin], JSON_UNESCAPED_UNICODE);
        $response = $this->I->executeJS(
            'var payload = arguments[0];'
            . 'var xhr = new XMLHttpRequest();'
            . 'xhr.open("POST", "/order/make_remove", false);'
            . 'xhr.setRequestHeader("Content-Type", "application/json");'
            . 'xhr.send(payload);'
            . 'return String(xhr.status) + " " + xhr.responseText;',
            [$body]
        );

        return (string) $response;
    }
}

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
    private const SUBJECT_TOGGLE = '//*[contains(@class,"order-cert")]//*[contains(@class,"vs__dropdown-toggle")]';

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

    /**
     * Подставляет в форму произвольный список доступных ОИС без SOAP-реестра.
     * Нужен, когда проверяется поведение компонента, а не состав реестра.
     *
     * @param string[] $uins
     */
    public function seedAllowedSubjects(array $uins): void
    {
        $items = [];
        foreach ($uins as $uin) {
            $items[] = ['UIN' => $uin, 'Name' => $uin];
        }

        $result = $this->I->executeJS(
            'var items = arguments[0];'
            . 'if (!window.params) { return "no-params"; }'
            . 'window.params.allowedRids = items;'
            . 'var root = document.getElementById("vue-remove-order-container");'
            . 'if (root && root.__vue__) { root.__vue__.$forceUpdate(); }'
            . 'var find = ' . self::jsFindVueComponent() . ';'
            . 'var list = find("' . self::SUBJECT_LIST_TAG . '");'
            . 'if (!list) { return "no-list"; }'
            . 'list.values = [];'
            . 'list.$emit("input", []);'
            . 'var form = find("' . self::REMOVE_FORM_TAG . '");'
            . 'if (form) {'
            . '  form.form.rids = [];'
            . '  var pins = {};'
            . '  items.forEach(function (item) { pins[item.UIN] = ""; });'
            . '  form.form.pins = pins;'
            . '}'
            . 'return "ok";',
            [$items]
        );
        $this->I->assertSame('ok', $result, 'Список ОИС не подготовлен на ' . self::URL);
        $this->I->waitForJS(
            'var find = ' . self::jsFindVueComponent() . ';'
            . 'var list = find("' . self::SUBJECT_LIST_TAG . '");'
            . 'return !!list && Array.isArray(list.rids) && list.rids.length === ' . count($uins) . ';',
            10
        );
    }

    /** Снимает выбор объекта кликом по крестику на теге v-select. */
    public function deselectSubjectByClick(string $uin): void
    {
        $tag = '//span[contains(@class,"vs__selected") and contains(normalize-space(),"' . $uin . '")]';
        $this->I->click($tag . '//button[contains(@class,"vs__deselect")]');
    }

    /** Выбирает объект кликом по варианту в v-select, как это делает клиент. */
    public function selectSubjectByClick(string $uin): void
    {
        $this->I->click(self::TITLE);
        $this->I->click(self::SUBJECT_TOGGLE);
        $option = self::subjectOption($uin);
        $this->I->waitForElementVisible($option, 10);
        $this->I->click($option);
    }

    private static function subjectOption(string $uin): string
    {
        return '//li[contains(@class,"vs__dropdown-option") and contains(normalize-space(),"' . $uin . '")]';
    }

    /** @return string[] */
    public function grabSelectedRids(): array
    {
        $json = (string) $this->I->executeJS(
            'var find = ' . self::jsFindVueComponent() . ';'
            . 'var form = find("' . self::REMOVE_FORM_TAG . '");'
            . 'if (form && form.form && Array.isArray(form.form.rids)) {'
            . '  return JSON.stringify(form.form.rids);'
            . '}'
            . 'var list = find("' . self::SUBJECT_LIST_TAG . '");'
            . 'if (!list) { return "[]"; }'
            . 'return JSON.stringify(list.values.map(function (item) { return item.UIN; }));'
        );
        $decoded = json_decode($json, true);

        return is_array($decoded) ? $decoded : [];
    }

    /** @return array<string,int|bool|null> */
    public function grabLimitState(): array
    {
        $json = (string) $this->I->executeJS(
            'var find = ' . self::jsFindVueComponent() . ';'
            . 'var list = find("' . self::SUBJECT_LIST_TAG . '");'
            . 'var form = find("' . self::REMOVE_FORM_TAG . '");'
            . 'return JSON.stringify({'
            . '  values: list ? list.values.length : -1,'
            . '  error: list ? !!list.maxCountError : null,'
            . '  propRids: list ? list.rids.length : -1,'
            . '  formRids: form && form.form ? form.form.rids.length : -1'
            . '});'
        );
        $decoded = json_decode($json, true);

        return is_array($decoded) ? $decoded : [];
    }

    public function seeLimitValidation(): void
    {
        $this->I->waitForText('Количество объектов в заказе не должно превышать 5 шт.', 5);
        $this->I->see('Количество объектов в заказе не должно превышать 5 шт.');
    }

    public function dontSeeLimitValidation(): void
    {
        $this->I->waitForElementNotVisible(
            '//*[contains(@class,"red") and contains(normalize-space(),"Количество объектов в заказе не должно превышать")]',
            5
        );
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

    public function postCheckRemovePin(string $uin, string $pin): string
    {
        $body = json_encode(['uin' => $uin, 'keyword' => $pin], JSON_UNESCAPED_UNICODE);
        $response = $this->I->executeJS(
            'var payload = arguments[0];'
            . 'var xhr = new XMLHttpRequest();'
            . 'xhr.open("POST", window.base_path + "order/check_remove_pin", false);'
            . 'xhr.setRequestHeader("Content-Type", "application/json");'
            . 'xhr.send(payload);'
            . 'return String(xhr.status) + " " + xhr.responseText;',
            [$body]
        );

        return (string) $response;
    }
}

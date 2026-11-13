<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Список заказов клиента: /order/main.
 * Фильтр статусов: window.statuses + Vue form.status (templates/Order/main.tpl).
 */
final class OrderMainPage extends BasePage
{
    private const ROOT = '//*[@id="vue-order-container"]';
    private const FIND = '//button[contains(@class,"formbox__buttons_find") and contains(.,"Найти")]';

    public function open(): void
    {
        $this->I->amOnPage('/order/main');
        $this->I->waitForElement(self::ROOT, 20);
        $this->I->waitForJS(
            'var el = document.getElementById("vue-order-container");'
            . 'return !!(el && el.__vue__ && Array.isArray(window.statuses));',
            20
        );
        // created() сразу зовёт fetchData; стартовый loading=false нельзя считать idle.
        $this->waitDatatableIdle();
    }

    /**
     * @return list<array{id:int, name:string}>
     */
    public function grabStatuses(): array
    {
        $raw = $this->I->executeJS(
            'return JSON.stringify(window.statuses || []);'
        );
        $rows = json_decode((string) $raw, true);
        $this->I->assertTrue(is_array($rows), 'window.statuses');
        $out = [];
        foreach ($rows as $row) {
            $out[] = [
                'id' => (int) ($row['id'] ?? 0),
                'name' => (string) ($row['name'] ?? ''),
            ];
        }

        return $out;
    }

    public function seeStatusInFilter(int $statusId, string $name): void
    {
        $found = false;
        foreach ($this->grabStatuses() as $row) {
            if ($row['id'] === $statusId && $row['name'] === $name) {
                $found = true;
                break;
            }
        }
        $this->I->assertTrue($found, 'фильтр статусов: id=' . $statusId . ' ' . $name);
    }

    public function filterByStatusId(string $statusId): void
    {
        $started = $this->I->executeJS(
            'var el = document.getElementById("vue-order-container");'
            . 'var vue = el && el.__vue__;'
            . 'if (!vue) { return false; }'
            . 'vue.form.status = String(arguments[0]);'
            . 'vue.filter();'
            . 'return !!(vue.datatable && vue.datatable.loading === true);',
            [$statusId]
        );
        $this->I->assertTrue((bool) $started, 'filter() должен стартовать MainDatatable (loading=true)');
        $this->waitDatatableIdle();
        $this->I->waitForElement(self::FIND, 10);
    }

    public function seeOrderInTable(string $titleFragment): void
    {
        $this->I->waitForText($titleFragment, 20);
        $this->I->see($titleFragment);
    }

    public function dontSeeOrderTitle(string $titleFragment): void
    {
        $this->I->dontSee($titleFragment);
    }

    public const LITERAL_TOTAL = 'Всего заказов';
    public const LITERAL_UNPAID = 'Не оплачено';
    public const LITERAL_PAY = 'Оплатить';
    public const LITERAL_AGREEMENT = 'Я принимаю условия';
    public const LITERAL_OFFER = 'Пользовательского соглашения';
    public const LITERAL_CONFIRM_BATCH = 'Оплатить заказы средствами со счета?';
    public const LITERAL_MODAL_TITLE = 'Оплата заказов';
    public const LITERAL_SKIP = 'не удалось оплатить';
    public const LITERAL_BANNER_SUM = 'Сумма неоплаченных заказов';
    public const LITERAL_ONE_CLICK = 'Выберите способ оплаты';

    private const BANNER = '//*[contains(@class,"unpaid-orders-banner")]';
    private const PAY_BANNER = '//button[contains(@class,"unpaid-orders-banner__pay")]';
    private const AGREEMENT_BOX = '//*[@id="accept-privacy-unpaid"]';
    private const AGREEMENT_MARK = '//*[@id="accept-privacy-unpaid"]//span[contains(@class,"checkmark")]';
    private const ONE_CLICK_PRICE = '//input[@name="price" and contains(@class,"formbox-paymethod__input")]';

    public function waitDatatableIdle(): void
    {
        // init=true ставится только в then() MainDatatable (main.js fetchData).
        $this->I->waitForJS(
            'var el = document.getElementById("vue-order-container");'
            . 'if (!el || !el.__vue__) { return false; }'
            . 'var v = el.__vue__;'
            . 'var d = v.datatable;'
            . 'return !!(v.init === true && d && d.loading === false);',
            25
        );
    }

    public function waitPayUnpaidIdle(): void
    {
        $this->I->waitForJS(
            'var el = document.getElementById("vue-order-container");'
            . 'if (!el || !el.__vue__) { return false; }'
            . 'var v = el.__vue__;'
            . 'var st = v.$store && v.$store.state && v.$store.state.Order'
            . '  && v.$store.state.Order.payunpaidfromaccount;'
            . 'var loading = !!(st && st.loading) || !!v.checkUnpaidLoading;'
            . 'return loading === false;',
            40
        );
        $this->waitDatatableIdle();
    }

    public function seeCounterLiterals(): void
    {
        $this->I->see(self::LITERAL_TOTAL);
        $this->I->see(self::LITERAL_UNPAID);
    }

    /**
     * Заголовок: "Всего заказов (N) / Не оплачено (M)" после первого fetch.
     */
    public function seeUnpaidCountInHeader(int $unpaidCount): void
    {
        $this->waitDatatableIdle();
        $text = (string) $this->I->executeJS(
            'var el = document.querySelector("#vue-order-container .h1_inner");'
            . 'return el ? String(el.innerText || "").replace(/\\s+/g, " ").trim() : "";'
        );
        $needle = self::LITERAL_UNPAID . ' (' . $unpaidCount . ')';
        $this->I->assertTrue(
            strpos($text, self::LITERAL_TOTAL) !== false && strpos($text, $needle) !== false,
            'ожидали "' . $needle . '" в заголовке, получили: ' . $text
        );
    }

    public function seeBanner(): void
    {
        $this->I->waitForElement(self::BANNER, 10);
        $this->I->see(self::LITERAL_BANNER_SUM);
        $this->I->see(self::LITERAL_PAY, self::PAY_BANNER);
    }

    public function seeBannerSum(int $sum): void
    {
        $this->seeBanner();
        $this->I->see((string) $sum, self::BANNER);
    }

    /**
     * Модалка соглашения показывает payableCount / payableSum (не raw unpaid*).
     */
    public function seeModalPayable(int $count, int $sum): void
    {
        $this->I->waitForText(self::LITERAL_MODAL_TITLE, 10);
        $body = (string) $this->I->executeJS(
            'var titles = document.querySelectorAll("h2.modal-header__title");'
            . 'for (var i = 0; i < titles.length; i++) {'
            . '  if ((titles[i].innerText || "").indexOf("Оплата заказов") === -1) { continue; }'
            . '  var root = titles[i];'
            . '  for (var k = 0; k < 14 && root; k++) {'
            . '    var slot = root.querySelector ? root.querySelector("[slot=body], .modal-body, p") : null;'
            . '    if (slot && (slot.innerText || "").indexOf("Будет оплачено") !== -1) {'
            . '      return String(slot.innerText || "").replace(/\\s+/g, " ").trim();'
            . '    }'
            . '    root = root.parentElement;'
            . '  }'
            . '}'
            . 'return "";'
        );
        $this->I->assertTrue(
            strpos($body, 'Будет оплачено заказов') !== false
            && strpos($body, (string) $count) !== false
            && strpos($body, (string) $sum) !== false,
            'модалка payable count/sum: ожидали ' . $count . '/' . $sum . ', получили: ' . $body
        );
    }

    /**
     * @return array{unpaidCount:int,unpaidSum:int,payableCount:int,payableSum:int,autoPaymentPrice:int,autoPaymentMinimum:int,objectId:mixed}
     */
    public function grabUnpaidState(): array
    {
        $this->waitDatatableIdle();
        $raw = $this->I->executeJS(
            'var el = document.getElementById("vue-order-container");'
            . 'if (!el || !el.__vue__) { return null; }'
            . 'var v = el.__vue__;'
            . 'return {'
            . '  unpaidCount: Number(v.unpaidCount || 0),'
            . '  unpaidSum: Number(v.unpaidSum || 0),'
            . '  payableCount: Number(v.payableCount || 0),'
            . '  payableSum: Number(v.payableSum || 0),'
            . '  autoPaymentPrice: Number(v.autoPaymentPrice || 0),'
            . '  autoPaymentMinimum: Number(v.autoPaymentMinimum || 0),'
            . '  objectId: v.autoPaymentObjectId'
            . '};'
        );
        if (is_object($raw)) {
            $raw = json_decode((string) json_encode($raw), true);
        }
        $this->I->assertTrue(is_array($raw), 'Vue /order/main не готов');

        return [
            'unpaidCount' => (int) ($raw['unpaidCount'] ?? 0),
            'unpaidSum' => (int) ($raw['unpaidSum'] ?? 0),
            'payableCount' => (int) ($raw['payableCount'] ?? 0),
            'payableSum' => (int) ($raw['payableSum'] ?? 0),
            'autoPaymentPrice' => (int) ($raw['autoPaymentPrice'] ?? 0),
            'autoPaymentMinimum' => (int) ($raw['autoPaymentMinimum'] ?? 0),
            'objectId' => $raw['objectId'] ?? null,
        ];
    }

    public function seePayBannerEnabled(bool $enabled): void
    {
        $this->I->waitForElement(self::PAY_BANNER, 10);
        $disabled = $this->I->executeJS(
            'var el = document.querySelector(".unpaid-orders-banner__pay");'
            . 'return el ? !!el.disabled : true;'
        );
        $this->I->assertSame($enabled, !$disabled, 'состояние кнопки Оплатить на плашке');
    }

    public function openPayModal(): void
    {
        $this->waitDatatableIdle();
        $this->I->waitForJS(
            'var el = document.getElementById("vue-order-container");'
            . 'var v = el && el.__vue__;'
            . 'var btn = document.querySelector(".unpaid-orders-banner__pay");'
            . 'return !!(v && v.unpaidCount > 0 && btn && !btn.disabled);',
            15
        );
        $this->I->click(self::PAY_BANNER);
        $this->I->waitForText(self::LITERAL_MODAL_TITLE, 10);
        $this->I->see(self::LITERAL_AGREEMENT);
        $this->I->see(self::LITERAL_OFFER);
        $this->I->seeElement(self::AGREEMENT_BOX);
    }

    public function seeModalPayDisabled(bool $disabled): void
    {
        // Footer модалки - sibling body (.trust-modal-footer), не потомок #accept-privacy-unpaid.
        // Ищем только внутри .modal-container соглашения, не «Найти» в фильтре страницы.
        $state = $this->I->executeJS(
            'var box = document.getElementById("accept-privacy-unpaid");'
            . 'if (!box) { return null; }'
            . 'var root = box.closest ? box.closest(".modal-container") : null;'
            . 'if (!root) { return null; }'
            . 'var btn = root.querySelector("button.formbox__buttons_find");'
            . 'return btn ? !!btn.disabled : null;'
        );
        $this->I->assertTrue($state !== null, 'кнопка Оплатить в модалке соглашения не найдена');
        $this->I->assertSame($disabled, (bool) $state, 'Оплатить в модалке соглашения');
    }

    public function acceptAgreement(): void
    {
        $this->I->click(self::AGREEMENT_MARK);
        $this->I->waitForJS(
            'var el = document.querySelector("#accept-privacy-unpaid input[type=checkbox]");'
            . 'return !!(el && el.checked);',
            5
        );
    }

    public function clickModalPay(): void
    {
        $clicked = $this->I->executeJS(
            'var box = document.getElementById("accept-privacy-unpaid");'
            . 'if (!box) { return false; }'
            . 'var root = box.closest ? box.closest(".modal-container") : null;'
            . 'if (!root) { return false; }'
            . 'var btn = root.querySelector("button.formbox__buttons_find");'
            . 'if (!btn || btn.disabled) { return false; }'
            . 'btn.click();'
            . 'return true;'
        );
        $this->I->assertTrue((bool) $clicked, 'клик Оплатить в модалке соглашения');
    }

    public function clickModalCancel(): void
    {
        $this->I->click(
            '//div[contains(@class,"modal-container")]'
            . '//button[contains(@class,"formbox__buttons_reset") and normalize-space()="Отменить"]'
        );
        $this->I->waitForJS(
            'var el = document.getElementById("vue-order-container");'
            . 'return !!(el && el.__vue__ && el.__vue__.showPayUnpaidModal === false);',
            8
        );
    }

    public function dontSeeAgreementModal(): void
    {
        $this->I->dontSeeElement(self::AGREEMENT_BOX);
    }

    public function waitConfirmFromAccount(): void
    {
        $this->I->waitForText(self::LITERAL_CONFIRM_BATCH, 15);
        $this->I->see(self::LITERAL_CONFIRM_BATCH);
    }

    public function confirmPayYes(): void
    {
        // Не contains(.,"Оплата"): это ловит кнопку "Оплатить" в соглашении.
        $this->I->waitForElementClickable(
            '//div[contains(@class,"modal-container")]'
            . '//button[contains(@class,"formbox__buttons_find") and normalize-space()="Оплата"]',
            10
        );
        $this->I->click(
            '//div[contains(@class,"modal-container")]'
            . '//button[contains(@class,"formbox__buttons_find") and normalize-space()="Оплата"]'
        );
        $this->waitPayUnpaidIdle();
    }

    public function confirmPayNo(): void
    {
        $this->I->click(
            '//div[contains(@class,"modal-container")]'
            . '//button[contains(@class,"formbox__buttons_reset") and normalize-space()="Отмена"]'
        );
    }

    public function waitOneClick(): void
    {
        $this->I->waitForText(self::LITERAL_ONE_CLICK, 15);
        $this->I->seeElement(self::ONE_CLICK_PRICE);
    }

    public function grabOneClickInputPrice(): string
    {
        $this->waitOneClick();
        $val = $this->I->executeJS(
            'var el = document.querySelector("input.formbox-paymethod__input[name=price]");'
            . 'return el ? String(el.value) : "";'
        );

        return (string) $val;
    }

    public function seeOneClickPriceNotZero(): void
    {
        $price = $this->grabOneClickInputPrice();
        $this->I->assertTrue($price !== '' && $price !== '0', 'one-click сумма не должна быть 0, got ' . $price);
    }

    public function waitCheckMoneyNetwork(): void
    {
        $this->I->waitForJS(
            'return performance.getEntriesByType("resource").some(function (e) {'
            . '  return String(e.name).indexOf("check_money") !== -1;'
            . '});',
            15
        );
    }

    public function applyStatusFilterAll(): void
    {
        $this->filterByStatusId('');
    }

    public function seeSkipLabel(): void
    {
        $this->I->waitForText(self::LITERAL_SKIP, 10);
        $this->I->see(self::LITERAL_SKIP);
    }
}

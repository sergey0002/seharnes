<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Смена тарифа: /tariffs/change?id={id}.
 *
 * Контракт: .doc/qa/flows/tariff-hidden-archive.md (CT-2511),
 * .doc/qa/flows/tariff-unpaid-recalc.md (CT-2379).
 * Модалки без data-test (fragments.md П-6). Шаблоны не правим.
 */
final class TariffChangePage extends BasePage
{
    public const TEXT_UNAVAILABLE = 'Данный тариф не доступен для вашей учетной записи';
    public const TEXT_ASK_ADMIN = 'Для подключения обратитесь';
    public const TEXT_ADMIN_LINK = 'администратору';
    public const TEXT_TITLE = 'Смена тарифа';
    public const TEXT_CONNECT = 'Подключить';
    public const TEXT_OPEN_UNPAID = 'У вас открыты неоплаченные заказы';
    public const TEXT_WILL_RECALC = 'После смены тарифа их стоимость будет пересчитана';
    public const TEXT_CONFIRM_SWITCH = 'Действительно хотите перейти на новый тариф';
    public const TEXT_SUCCESS_RECALC = 'Стоимости неоплаченных заказов пересчитаны';
    public const TEXT_SUCCESS_CONNECTED = 'Вы успешно подключены к тарифу';
    public const TEXT_OLD_WARN = 'их стоимость не изменится';
    public const TEXT_TASK_RECALC_QUESTION = 'Пересчитать стоимости заказов после переключения на новый тариф';

    private const MODAL_BODY = '//div[contains(@class,"modal-body--with-link")]';
    private const FEEDBACK = '//a[@href="/feedback"]';
    private const BANNER = '//strong[contains(normalize-space(.),"Внимание!")]';
    private const CHANGE_ROOT = '//*[@id="vue-tariff-change-container"]';
    private const CONNECT_BTN = '//button[contains(@class,"tariff-change__action")]';
    private const ORDERS_TABLE = '//table[contains(@class,"tariff-change-orders-table")]';
    private const MODAL_YES = '//button[contains(@class,"formbox__buttons_find") and contains(normalize-space(.),"Да")]';
    private const MODAL_NO = '//button[contains(@class,"formbox__buttons_reset") and contains(normalize-space(.),"Нет")]';
    private const PAYMENT_YES = '//button[contains(@class,"formbox__buttons_find") and contains(normalize-space(.),"Оплата")]';
    private const SUCCESS_OK = '//button[contains(@class,"formbox__buttons_find") and contains(normalize-space(.),"OK")]';

    public static function url(int $id): string
    {
        return '/tariffs/change?id=' . $id;
    }

    public function open(int $id): void
    {
        $this->I->amOnPage(self::url($id));
    }

    public function seeRedirectedToTariffList(): void
    {
        $this->I->waitForElementVisible('body', 10);
        $this->I->seeInCurrentUrl('/tariffs');
        $this->I->dontSeeInCurrentUrl('/tariffs/change');
        $this->I->dontSeeInCurrentUrl('/tariffs/view');
        $this->I->dontSeeElement(self::CHANGE_ROOT);
    }

    public function seeRedirectedToSignin(): void
    {
        $this->I->waitForElementVisible('body', 10);
        $this->I->seeInCurrentUrl('/account/signin');
    }

    public function seeProfileUnavailableModalWithFeedback(): void
    {
        $this->I->waitForText(self::TEXT_UNAVAILABLE, 15);
        $this->I->see(self::TEXT_UNAVAILABLE);
        $this->I->see(self::TEXT_ASK_ADMIN);
        $this->I->see(self::TEXT_ADMIN_LINK);
        $this->I->seeElement(self::FEEDBACK);
        $this->I->seeElement(self::MODAL_BODY);
        $this->I->seeElement(self::BANNER);
    }

    public function dontSeeProfileUnavailableModal(): void
    {
        $this->I->dontSeeElement(self::MODAL_BODY);
        $this->I->dontSeeElement(self::FEEDBACK);
        $this->I->dontSee(self::TEXT_ASK_ADMIN);
    }

    /**
     * Прямой POST обхода UI. Возвращает HTTP-статус и тело.
     *
     * @return array{status:int, body:string}
     */
    public function postSaveTariffId(int $tariffId): array
    {
        $this->I->amOnPage('/');
        $this->I->executeJS(
            'window.__ct2511Post = null;'
            . 'fetch("/account/saveParamsRegOis", {'
            . '  method: "POST",'
            . '  credentials: "same-origin",'
            . '  headers: {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},'
            . '  body: "param[code]=tariffId&param[value]=' . $tariffId . '"'
            . '}).then(function (r) {'
            . '  return r.text().then(function (t) {'
            . '    window.__ct2511Post = {status: r.status, body: t};'
            . '  });'
            . '}).catch(function (e) {'
            . '  window.__ct2511Post = {status: 0, body: String(e)};'
            . '});'
        );
        $this->I->waitForJS('return window.__ct2511Post !== null;', 15);
        $raw = $this->I->executeJS('return window.__ct2511Post;');
        if (is_object($raw)) {
            $raw = json_decode((string) json_encode($raw), true);
        }
        $this->I->assertTrue(is_array($raw), 'POST saveParamsRegOis did not return a result');

        return [
            'status' => (int) ($raw['status'] ?? 0),
            'body' => (string) ($raw['body'] ?? ''),
        ];
    }

    public function logout(): void
    {
        $this->I->amOnPage('/account/logout');
    }

    public function waitReady(): void
    {
        $this->I->waitForElementVisible(self::CHANGE_ROOT, 20);
        $this->I->waitForText(self::TEXT_TITLE, 15);
        $this->I->waitForJS(
            'return !!(window.newTariff && document.getElementById("vue-tariff-change-container")'
            . ' && document.getElementById("vue-tariff-change-container").__vue__);',
            15
        );
    }

    public function clickConnect(): void
    {
        $this->waitReady();
        $this->I->waitForElementClickable(self::CONNECT_BTN, 10);
        $this->I->click(self::CONNECT_BTN);
    }

    /**
     * checkTariff ждёт /account/current, затем синхронно ставит сумму и открывает модалку.
     */
    public function waitForOneClickOpen(int $seconds = 20): void
    {
        $this->I->waitForJS(
            'function findVue(v) {'
            . '  if (!v) { return null; }'
            . '  if (v.clientBalance || typeof v.autoPaymentMinimum !== "undefined") { return v; }'
            . '  if (v.$children) {'
            . '    for (var i = 0; i < v.$children.length; i++) {'
            . '      var f = findVue(v.$children[i]);'
            . '      if (f) { return f; }'
            . '    }'
            . '  }'
            . '  return v.$parent ? findVue(v.$parent) : null;'
            . '}'
            . 'var root = document.getElementById("vue-tariff-change-container");'
            . 'var vue = findVue(root && root.__vue__);'
            . 'return !!(vue && vue.showOneClickPaymentModal);',
            $seconds
        );
    }

    public function seeConnectEnabled(): void
    {
        $this->waitReady();
        $disabled = $this->I->executeJS(
            'var el = document.getElementById("vue-tariff-change-container")'
            . '.querySelector(".tariff-change__action");'
            . 'return !!(el && el.disabled);'
        );
        $this->I->assertFalse((bool) $disabled, 'Кнопка Подключить должна быть доступна');
    }

    public function seeConnectDisabled(): void
    {
        $this->waitReady();
        $disabled = $this->I->executeJS(
            'var el = document.getElementById("vue-tariff-change-container")'
            . '.querySelector(".tariff-change__action");'
            . 'return !!(el && el.disabled);'
        );
        $this->I->assertTrue((bool) $disabled, 'Кнопка Подключить должна быть заблокирована');
    }

    /**
     * @return array{number:int, old:int, new:int, blocked:bool, error:?string, rows:array}
     */
    public function grabPreview(): array
    {
        $raw = $this->I->executeJS(
            'return JSON.stringify({'
            . '  number: window.openOrderNumber,'
            . '  old: window.openOrderCost,'
            . '  new: window.openOrderCostNew,'
            . '  blocked: window.isTariffChangeBlockedByRecalc,'
            . '  error: window.openOrderRecalcError,'
            . '  rows: window.openOrderRows'
            . '});'
        );
        if (is_string($raw)) {
            $raw = json_decode($raw, true);
        } elseif (is_object($raw)) {
            $raw = json_decode((string) json_encode($raw), true);
        }
        $this->I->assertTrue(is_array($raw), 'preview window.* не прочитался');

        return [
            'number' => (int) ($raw['number'] ?? 0),
            'old' => (int) ($raw['old'] ?? 0),
            'new' => (int) ($raw['new'] ?? 0),
            'blocked' => (bool) ($raw['blocked'] ?? false),
            'error' => isset($raw['error']) ? (string) $raw['error'] : null,
            'rows' => is_array($raw['rows'] ?? null) ? $raw['rows'] : [],
        ];
    }

    public function seeRecalcConfirmModal(): void
    {
        $this->I->waitForText(self::TEXT_OPEN_UNPAID, 15);
        $this->I->see(self::TEXT_WILL_RECALC);
        $this->I->see(self::TEXT_CONFIRM_SWITCH);
        $this->I->seeElement(self::ORDERS_TABLE);
        $this->I->see('Да');
        $this->I->see('Нет');
        $this->I->dontSee(self::TEXT_OLD_WARN);
        $this->I->dontSee(self::TEXT_TASK_RECALC_QUESTION);
    }

    public function dontSeeRecalcConfirmModal(): void
    {
        $this->I->dontSee(self::TEXT_CONFIRM_SWITCH);
        $this->I->dontSeeElement(self::MODAL_YES);
    }

    public function confirmRecalcYes(): void
    {
        $this->I->waitForElementClickable(self::MODAL_YES, 10);
        $this->I->click(self::MODAL_YES);
    }

    public function cancelRecalcNo(): void
    {
        $this->I->waitForElementClickable(self::MODAL_NO, 10);
        $this->I->click(self::MODAL_NO);
        $this->I->waitForJS('return true;', 2);
    }

    public function confirmPaymentIfPresent(): void
    {
        try {
            $this->I->waitForElementClickable(self::PAYMENT_YES, 10);
            $this->I->click(self::PAYMENT_YES);
        } catch (\Throwable $e) {
            // тариф без абонплаты: модалки оплаты нет
        }
    }

    public function seeSuccessWithRecalc(): void
    {
        $this->I->waitForText(self::TEXT_SUCCESS_CONNECTED, 20);
        $this->I->see(self::TEXT_SUCCESS_RECALC);
        $this->I->seeElement(self::SUCCESS_OK);
    }

    public function seeRecalcBlockedMessage(): void
    {
        $this->I->waitForText('пересч', 15);
        $this->seeConnectDisabled();
    }

    public function seeOrderRow(int $orderId): void
    {
        $this->I->see((string) $orderId, self::ORDERS_TABLE);
    }

    public function dontSeeOrderId(int $orderId): void
    {
        $this->I->dontSee((string) $orderId);
    }

    public const TEXT_NEGATIVE_BALANCE = 'Невозможно поменять тариф при отрицательном балансе';

    public function dontSeeNegativeBalanceMessage(): void
    {
        $this->I->dontSee(self::TEXT_NEGATIVE_BALANCE);
    }

    public function seeNegativeBalanceMessage(): void
    {
        $this->I->waitForText(self::TEXT_NEGATIVE_BALANCE, 10);
        $this->I->see(self::TEXT_NEGATIVE_BALANCE);
    }

    /**
     * @return array{autoPaymentMinimum:int,autoPaymentPrice:int,realMoney:?int,realMoneyDisplay:?int,showOneClick:bool}
     */
    public function grabAutoPaymentState(): array
    {
        $raw = $this->I->executeJS(
            'function findVue(v) {'
            . '  if (!v) { return null; }'
            . '  if (v.clientBalance || typeof v.autoPaymentMinimum !== "undefined") { return v; }'
            . '  if (v.$children) {'
            . '    for (var i = 0; i < v.$children.length; i++) {'
            . '      var f = findVue(v.$children[i]);'
            . '      if (f) { return f; }'
            . '    }'
            . '  }'
            . '  return v.$parent ? findVue(v.$parent) : null;'
            . '}'
            . 'var root = document.getElementById("vue-tariff-change-container");'
            . 'var vue = findVue(root && root.__vue__);'
            . 'if (!vue) { return null; }'
            . 'var bal = vue.clientBalance || {};'
            . 'return {'
            . '  autoPaymentMinimum: vue.autoPaymentMinimum,'
            . '  autoPaymentPrice: vue.autoPaymentPrice,'
            . '  realMoney: bal.realMoney != null ? bal.realMoney : null,'
            . '  realMoneyDisplay: bal.realMoneyDisplay != null ? bal.realMoneyDisplay : null,'
            . '  showOneClick: !!vue.showOneClickPaymentModal'
            . '};'
        );
        if (is_object($raw)) {
            $raw = json_decode((string) json_encode($raw), true);
        }
        $this->I->assertTrue(is_array($raw), 'tariff change vue state missing');

        return [
            'autoPaymentMinimum' => (int) ($raw['autoPaymentMinimum'] ?? 0),
            'autoPaymentPrice' => (int) ($raw['autoPaymentPrice'] ?? 0),
            'realMoney' => isset($raw['realMoney']) ? (int) $raw['realMoney'] : null,
            'realMoneyDisplay' => isset($raw['realMoneyDisplay']) ? (int) $raw['realMoneyDisplay'] : null,
            'showOneClick' => (bool) ($raw['showOneClick'] ?? false),
        ];
    }

    public function closeOneClickModalIfOpen(): void
    {
        $this->I->executeJS(
            'var root = document.getElementById("vue-tariff-change-container");'
            . 'var vue = root && root.__vue__;'
            . 'if (vue) { vue.showOneClickPaymentModal = false; vue.showConfirmPay = false; }'
        );
    }

}

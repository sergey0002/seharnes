<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Пополнение: /payments/main (каналы yoo / paypal / qiwi, перевод, вывод).
 *
 * Контракт: .doc/qa/flows/payments-replenishment.md
 * Задачи: CT-2602 (kurs / isActive2 / statusDescription2),
 * CT-2609 (квитанция физлица m_pay_bank_f.tpl).
 *
 * data-test на accordion нет. Селекторы: data-paymethod, BEM
 * paymethod-button__choose, input[name=price], заголовок страницы.
 * Шаблоны не правим.
 */
final class PaymentsMainPage extends BasePage
{
    public const URL = '/payments/main';
    public const TITLE = 'Платежи и переводы';
    public const FALLBACK_STATUS = 'Данный канал закрыт на техническое обслуживание. Прием платежей временно не доступен. Сроки возобновления работы уточняйте у администратора сайта';
    public const TRANSFER_ACCOUNT = 'Перевод на расчетный счет оператора';
    public const TRANSFER_USER = 'Перевод средств другому пользователю';
    public const WITHDRAW = 'Вывод средств из системы';
    public const TRANSFER_CODE = 'transfer_to_account';
    public const RECEIPT_TITLE = 'Квитанция для оплаты услуг';
    public const BLOCK_NOTICE = 'ИЗВЕЩЕНИЕ';
    public const BLOCK_RECEIPT = 'КВИТАНЦИЯ';
    public const BTN_RECEIPT = 'Квитанция';

    private const PRICE = '//input[@name="price"]';
    private const PAY_BTN = '//button[contains(@class,"paymethod-button__choose")]';

    public function open(): void
    {
        $this->I->amOnPage(self::URL);
        $this->I->waitForText(self::TITLE, 20);
        $this->I->waitForJS(
            'return !!(window.Vue && document.getElementById("vue-container"));',
            15
        );
    }

    public function openExpectSignin(): void
    {
        $this->I->amOnPage(self::URL);
        $this->I->waitForElement(self::test('login-form'), 20);
        $this->I->see('Вход');
        $this->I->dontSee(self::TITLE);
    }

    public function seeHeading(): void
    {
        $this->I->see(self::TITLE);
    }

    public function seeChannel(string $code): void
    {
        $this->waitChannelPresent($code);
        $found = $this->I->executeJS(
            'return !!document.querySelector("[data-paymethod=\"" + arguments[0] + "\"]");',
            [$code]
        );
        $this->I->assertNotEmpty($found, 'канал ' . $code . ' отсутствует в DOM');
    }

    /**
     * Устойчивое ожидание Vue-рендера: драйверный waitForElement иногда
     * проходит на промежуточном DOM, а следующий seeElement уже падает
     * после перерендера списка. JS-опрос того же селектора стабильнее.
     */
    public function waitChannelPresent(string $code): void
    {
        $this->I->waitForElement($this->paymethod($code), 15);
    }

    /**
     * Сырой ответ POST preview без формы. Нужен для каналов, которых нет
     * в DOM (физлицо, выключен): forceSubmitPreview там бросает исключение,
     * т.к. input искать негде. Возвращает responseText.
     */
    public function postPreviewRaw(string $code, string $price): string
    {
        $html = $this->I->executeJS(
            'var xhr = new XMLHttpRequest();'
            . 'xhr.open("POST", "/payment_channel/preview/" + arguments[0], false);'
            . 'xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");'
            . 'xhr.send("price=" + encodeURIComponent(arguments[1]));'
            . 'var m = xhr.responseText.match(/window\\.wmerror = (".*?");/);'
            . 'if (m) { try { return JSON.parse(m[1]); } catch (e) { return m[1]; } }'
            . 'return xhr.responseText;',
            [$code, $price]
        );

        return (string) $html;
    }

    public function dontSeeChannel(string $code): void
    {
        $this->I->dontSeeElement($this->paymethod($code));
    }

    public function openChannel(string $code): void
    {
        $this->waitChannelPresent($code);
        $this->clickChannelHeader($code);
        $this->I->waitForElement($this->channelScope($code) . self::PRICE, 10);
    }

    /**
     * Клик по видимому заголовку аккордеона (текст/стрелка), а не по
     * иконке-div: иконка маленькая и WebDriver считает ее uninteractable.
     */
    public function clickChannelHeader(string $code): void
    {
        $this->I->click($this->channelScope($code) . '//*[contains(@class,"spoiler-with-icon_text")]');
    }

    public function seePayButtonEnabled(string $code): void
    {
        $btn = $this->channelScope($code) . self::PAY_BTN;
        $this->I->seeElement($btn);
        $this->I->dontSeeElement($btn . '[@disabled]');
    }

    public function seePayButtonDisabled(string $code): void
    {
        $this->I->seeElement($this->channelScope($code) . self::PAY_BTN . '[@disabled]');
    }

    public function seeStatusText(string $text): void
    {
        $this->I->waitForText($text, 15);
        $this->I->see($text);
    }

    public function dontSeeStatusText(string $text): void
    {
        $this->I->dontSee($text);
    }

    public function seeNeighborFlows(): void
    {
        $this->I->seeElement($this->paymethod('transfer_to_account'));
        $this->I->see(self::TRANSFER_ACCOUNT);
        $this->I->seeElement($this->paymethod('transfer_to_user'));
        $this->I->see(self::TRANSFER_USER);
        $this->I->seeElement($this->paymethod('withdrawal'));
        $this->I->see(self::WITHDRAW);
    }

    /**
     * UI при Неисправен disabled. Preview всё равно должен отказать
     * с тем же statusDescription2 (helper на сервере).
     */
    public function forceSubmitPreview(string $code, string $price): void
    {
        $this->I->executeJS(
            'var code = arguments[0];'
            . 'var price = arguments[1];'
            . 'var icon = document.querySelector("[data-paymethod=\"" + code + "\"]");'
            . 'var acc = icon ? icon.closest(".accordion-paymethod") : null;'
            . 'var input = acc ? acc.querySelector("input[name=\\"price\\"]") : null;'
            . 'if (!input) { throw new Error("price input not found for " + code); }'
            . 'input.disabled = false;'
            . 'input.value = price;'
            . 'input.dispatchEvent(new Event("input"));'
            . 'var form = input.closest("form");'
            . 'if (!form) { throw new Error("preview form not found"); }'
            . 'var btn = form.querySelector("button[type=\\"submit\\"]");'
            . 'if (btn) { btn.disabled = false; }'
            . 'form.submit();',
            [$code, $price]
        );
    }

    public function seePreviewRejectPage(string $statusText): void
    {
        $this->I->waitForText($statusText, 15);
        $this->I->see($statusText);
        $this->I->see('Ошибка!');
    }

    /**
     * Preview с auto-payment полями one-click (заказ с нулевым балансом).
     * Возвращает декодированный wmerror или пустую строку при успехе.
     */
    public function postPreviewWithAutoPayment(string $code, string $price, string $orderId, string $orderType): string
    {
        $html = $this->I->executeJS(
            'var xhr = new XMLHttpRequest();'
            . 'xhr.open("POST", "/payment_channel/preview/" + arguments[0], false);'
            . 'xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");'
            . 'xhr.send("price=" + encodeURIComponent(arguments[1])'
            . ' + "&auto-payment-object-id=" + encodeURIComponent(arguments[2])'
            . ' + "&auto-payment-object-type=" + encodeURIComponent(arguments[3]));'
            . 'var m = xhr.responseText.match(/window\\.wmerror = (".*?");/);'
            . 'if (m) { try { return JSON.parse(m[1]); } catch (e) { return m[1]; } }'
            . 'return "";',
            [$code, $price, $orderId, $orderType]
        );

        return (string) $html;
    }

    /**
     * Webhook succeeded JSON напрямую на стенде (Notices читает php://input).
     * Без подписи ЮKassa; сверка getPaymentInfo упрется в API, поэтому для
     * проверки идемпотентности смотрим журнал запросов, а не ct_payment.
     */
    public function postWebhookSucceeded(string $code, int $paymentLogId, string $sum): string
    {
        return (string) $this->I->executeJS(
            'var body = JSON.stringify({type: "notification", event: "payment.succeeded",'
            . ' object: {id: "test-" + arguments[1] + "-" + Date.now(), status: "succeeded", paid: true,'
            . ' amount: {value: arguments[2], currency: "RUB"},'
            . ' metadata: {payment_id: arguments[1]}}});'
            . 'var xhr = new XMLHttpRequest();'
            . 'xhr.open("POST", "/payment_channel/result/" + arguments[0], false);'
            . 'xhr.setRequestHeader("Content-Type", "application/json");'
            . 'xhr.send(body);'
            . 'return xhr.responseText;',
            [$code, $paymentLogId, $sum]
        );
    }

    /**
     * Webhook canceled JSON напрямую на стенде.
     */
    public function postWebhookCanceled(string $code, int $paymentLogId, string $sum): string
    {
        return (string) $this->I->executeJS(
            'var body = JSON.stringify({type: "notification", event: "payment.canceled",'
            . ' object: {status: "canceled", paid: false,'
            . ' amount: {value: arguments[2], currency: "RUB"},'
            . ' cancellation_details: {party: "yoo_kassa", reason: "expired_on_confirmation"},'
            . ' metadata: {payment_id: arguments[1]}}});'
            . 'var xhr = new XMLHttpRequest();'
            . 'xhr.open("POST", "/payment_channel/result/" + arguments[0], false);'
            . 'xhr.setRequestHeader("Content-Type", "application/json");'
            . 'xhr.send(body);'
            . 'return xhr.responseText;',
            [$code, $paymentLogId, $sum]
        );
    }

    /** CT-2609: аккордеон банковского перевода (bankf → preview/kassa). */
    public function openTransferToAccount(): void
    {
        $this->openChannel(self::TRANSFER_CODE);
        $this->I->see(self::BTN_RECEIPT);
    }

    /**
     * CT-2609: submit квитанции в той же вкладке (без print-диалога).
     * bankf для физлица ставит target=_blank и window.print().
     */
    public function submitKassaReceiptSameWindow(string $price): void
    {
        $this->I->executeJS(
            'window.print = function () {};'
            . 'var code = arguments[0];'
            . 'var price = arguments[1];'
            . 'var icon = document.querySelector("[data-paymethod=\"" + code + "\"]");'
            . 'var acc = icon ? icon.closest(".accordion-paymethod") : null;'
            . 'var input = acc ? acc.querySelector("input[name=\\"price\\"]") : null;'
            . 'if (!input) { throw new Error("price input not found for " + code); }'
            . 'input.disabled = false;'
            . 'input.value = price;'
            . 'input.dispatchEvent(new Event("input"));'
            . 'var form = input.closest("form");'
            . 'if (!form) { throw new Error("preview form not found"); }'
            . 'form.target = "_self";'
            . 'var btn = form.querySelector("button[type=\\"submit\\"]");'
            . 'if (btn) { btn.disabled = false; }'
            . 'form.submit();',
            [self::TRANSFER_CODE, $price]
        );
    }

    /**
     * Сырой HTML ответа сервера (не сериализованный DOM браузера).
     * sync XHR: credentials/cookies текущей сессии.
     */
    public function fetchRawKassaReceiptHtml(string $price): string
    {
        $html = $this->I->executeJS(
            'var xhr = new XMLHttpRequest();'
            . 'xhr.open("POST", arguments[0], false);'
            . 'xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");'
            . 'xhr.send("price=" + encodeURIComponent(arguments[1]));'
            . 'if (xhr.status < 200 || xhr.status >= 300) {'
            . '  throw new Error("preview HTTP " + xhr.status + ": " + xhr.responseText.slice(0, 200));'
            . '}'
            . 'return xhr.responseText;',
            ['/payment_channel/preview/kassa', $price]
        );

        return (string) $html;
    }

    /** CT-2609: сырой HTML квитанции валиден в обоих блоках. */
    public function assertValidKassaReceiptRawHtml(string $src): void
    {
        $this->I->assertStringContainsString(self::RECEIPT_TITLE, $src);
        $this->I->assertStringContainsString(self::BLOCK_NOTICE, $src);
        $this->I->assertStringContainsString(self::BLOCK_RECEIPT, $src);
        $broken = preg_match_all('/width="410"[^>]*>\s*<\/tr>/', $src);
        $good = preg_match_all('/width="410"[^>]*>\s*<tr>/', $src);
        $this->I->assertSame(0, $broken, 'сырой HTML: table width=410 не должен начинаться с </tr>');
        $this->I->assertSame(2, $good, 'сырой HTML: оба блока ИЗВЕЩЕНИЕ/КВИТАНЦИЯ открывают <tr>');
        $this->I->assertStringNotContainsString('<small><small>', $src);
        $this->I->assertStringNotContainsString('%PDF', $src);
    }

    private function paymethod(string $code): string
    {
        return '//*[@data-paymethod="' . $code . '"]';
    }

    private function channelScope(string $code): string
    {
        return $this->paymethod($code)
            . '/ancestor::*[contains(@class,"accordion-paymethod")][1]';
    }
}

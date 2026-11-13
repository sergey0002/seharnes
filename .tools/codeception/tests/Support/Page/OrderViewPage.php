<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Карточка заказа клиента: /order/view/{id}.
 *
 * data-test на кнопке отмены нет (templates/Order/view.tpl: class order__cancel).
 * Шаблоны не правим.
 */
final class OrderViewPage extends BasePage
{
    public const STATUS_IN_WORK = 'в работе';
    public const STATUS_PARTIAL = 'выполнен частично';
    public const STATUS_PAYED = 'оплачен';
    public const STATUS_COMPLETED = 'выполнен';
    public const STATUS_CANCELLED = 'отменен';

    private const ROOT = '//*[@id="vue-view-container"]';
    private const CANCEL = '//button[contains(@class,"order__cancel") and contains(normalize-space(.),"Отменить заказ")]';

    public function open(int $orderId): void
    {
        $this->I->amOnPage('/order/view/' . $orderId);
        $this->I->waitForElement(self::ROOT, 20);
    }

    public function waitStatus(string $statusName): void
    {
        $this->I->waitForText($statusName, 20);
        $this->I->see($statusName);
    }

    public function seeCommentContains(string $text): void
    {
        $this->I->waitForText($text, 20);
        $this->I->see($text);
    }

    public function dontSeeCancelButton(): void
    {
        $this->I->dontSeeElement(self::CANCEL);
        $visible = (bool) $this->I->executeJS(
            'var root = document.getElementById("vue-view-container");'
            . 'var vue = root && root.__vue__;'
            . 'if (vue && typeof vue.is_cancel_button !== "undefined") {'
            . '  return !!vue.is_cancel_button;'
            . '}'
            . 'var nodes = document.getElementsByClassName("order__cancel");'
            . 'for (var i = 0; i < nodes.length; i++) {'
            . '  if (nodes[i].offsetParent !== null) { return true; }'
            . '}'
            . 'return false;'
        );
        $this->I->assertFalse($visible, 'Кнопка Отменить заказ не должна быть видна');
    }

    public function postCancel(int $orderId): string
    {
        $raw = $this->I->executeJS(
            'var xhr = new XMLHttpRequest();'
            . 'xhr.open("POST", "/m_router.php?q=order/cancel/" + arguments[0], false);'
            . 'xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");'
            . 'xhr.send("");'
            . 'return String(xhr.status) + "\\n" + String(xhr.responseText || "");',
            [$orderId]
        );

        return (string) $raw;
    }

    /**
     * GET /order/certs/{id} без перехода WebDriver на 500.
     *
     * @return array{http:int, url:string, body:string}
     */
    public function requestCerts(int $orderId): array
    {
        $raw = $this->I->executeJS(
            'var xhr = new XMLHttpRequest();'
            . 'xhr.open("GET", "/order/certs/" + arguments[0], false);'
            . 'xhr.send("");'
            . 'return JSON.stringify({'
            . '  http: xhr.status,'
            . '  url: xhr.responseURL || "",'
            . '  body: String(xhr.responseText || "").slice(0, 400)'
            . '});',
            [$orderId]
        );
        $data = json_decode((string) $raw, true);
        $this->I->assertTrue(is_array($data), 'certs XHR JSON');

        return [
            'http' => (int) ($data['http'] ?? 0),
            'url' => (string) ($data['url'] ?? ''),
            'body' => (string) ($data['body'] ?? ''),
        ];
    }

    public function seePayButton(): void
    {
        $this->I->waitForElement('//button[contains(@class,"order__send") and normalize-space()="Оплатить"]', 10);
        $this->I->see('Оплатить');
    }

    public function grabPaymentSum(): float
    {
        $raw = $this->I->executeJS(
            'var el = document.getElementById("vue-view-container");'
            . 'if (!el || !el.__vue__) { return null; }'
            . 'return el.__vue__.sum;'
        );
        $this->I->assertTrue($raw !== null, 'Vue sum на /order/view не найден');

        return (float) $raw;
    }

    public function acceptPrivacyAndOpenPayConfirm(): void
    {
        $this->I->waitForElement('//*[@id="accept-privacy"]//span[contains(@class,"checkmark")]', 15);
        $this->I->click('//*[@id="accept-privacy"]//span[contains(@class,"checkmark")]');
        $this->I->click('//button[contains(@class,"order__send") and normalize-space()="Оплатить"]');
        $this->I->waitForText('Оплатить услугу средствами со счета?', 15);
    }

    public function seeConfirmPayFromAccountLiteral(): void
    {
        $this->I->see('Оплатить услугу средствами со счета?');
    }

    public function openExpectingNotFound(int $orderId): void
    {
        $this->I->amOnPage('/order/view/' . $orderId);
        $this->I->waitForText('Извините, страница не', 15);
        $this->I->see('Извините, страница не');
    }

    public function seeCancelButton(): void
    {
        $this->I->waitForElement(self::CANCEL, 20);
        $this->I->seeElement(self::CANCEL);
    }

    public function clickCancel(): void
    {
        $this->seeCancelButton();
        $this->I->click(self::CANCEL);
        $this->I->waitForElementNotVisible(self::CANCEL, 20);
    }

    public function seeRemoveDetailsGrid(): void
    {
        $this->I->waitForText('№ заказа:', 20);
        $this->I->see('Ресурсы:');
        $this->I->seeElement('//*[contains(@class,"order-grid")]');
    }

    public function seeOperationTitle(string $expected): void
    {
        $this->I->waitForText('Операция:', 20);
        $this->I->see('Операция:');
        $this->I->see($expected);
    }

    public function cancelPayConfirm(): void
    {
        $xpath = '//button[contains(@class,"formbox__buttons_reset") and contains(.,"Отмена")]';
        $this->I->waitForElement($xpath, 10);
        $this->I->click($xpath);
        $this->I->waitForElementNotVisible($xpath, 10);
    }

    public function seeStatusCancelled(): void
    {
        $this->I->waitForText('отменен', 20);
        $this->I->see('отменен');
    }
}

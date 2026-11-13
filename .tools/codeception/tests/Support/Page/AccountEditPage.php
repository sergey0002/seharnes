<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * /account/edit: аккордеоны сообщений и параметров ОИС.
 *
 * Контракт: .doc/qa/flows/account-messages.md
 * Задачи: CT-2605 (Best Value писем), CT-2603 (одно окно оплаты bool).
 *
 * data-test на чекбоксах нет - селектор по label.checkbox__item + тексту
 * (документированное исключение, шаблоны не правим).
 */
final class AccountEditPage extends BasePage
{
    public const URL = '/account/edit';

    public const LABEL_RECEIVE = 'Возможность получения сообщения от других пользователей';
    public const LABEL_SEND = 'Возможность отправки сообщения другим пользователям';
    public const LABEL_PIN = 'Возможность защиты данных PIN-кодом';
    public const LABEL_CLOSED = 'Возможность скрытого депонирования';
    public const LABEL_PSEUD = 'Возможность депонирования под псевдонимом';

    public const CONFIRM_PREFIX = 'Вы изменили действующее значение';
    public const CONFIRM_PAID = 'Это платная операция';
    public const CONFIRM_CHARGE = 'будет списано с вашего лицевого счета';

    public const ERR_PIN_NO_SERVICE =
        'Возможность установки PIN-кода не предусмотрена для вашей учетной записи. В текущем тарифе вы не можете изменить данную опцию.';

    private const SPOILER_MESSAGES = '//div[contains(@class,"spoiler") and contains(.,"Настройка сообщений")]';
    private const SPOILER_OIS = '//div[contains(@class,"spoiler") and contains(.,"Настройка параметров депонирования ОИС")]';
    private const PAY_NO = '//button[contains(@class,"formbox__buttons_reset") and contains(.,"Нет")]';
    private const PAY_YES = '//button[contains(@class,"formbox__buttons_find") and contains(.,"Оплатить")]';
    private const ERROR_TITLE = '//h2[contains(@class,"modal-header__title") and starts-with(normalize-space(.),"Ошибка")]';

    public function open(): void
    {
        $this->I->amOnPage(self::URL);
        $this->I->waitForText('Настройка сообщений', 20);
    }

    public function openMessagesAccordion(): void
    {
        $this->open();
        $this->installXhrProbe();
        $this->I->click(self::SPOILER_MESSAGES);
        $this->I->waitForText(self::LABEL_RECEIVE, 15);
        $this->I->waitForText(self::LABEL_SEND, 15);
    }

    public function openOisAccordion(): void
    {
        $this->open();
        $this->installXhrProbe();
        $this->I->click(self::SPOILER_OIS);
        $this->I->waitForText(self::LABEL_PIN, 15);
    }

    public function changePassword(string $oldPassword, string $newPassword): void
    {
        $this->open();
        $spoiler = '//div[contains(@class,"spoiler")]//span[normalize-space(.)="Настройка пароля"]';
        $this->I->waitForElement($spoiler, 15);
        $this->I->click($spoiler);
        $this->I->waitForElementVisible('#oldpass', 15);
        $this->I->fillField('#oldpass', $oldPassword);
        $this->I->fillField('#newpass1', $newPassword);
        $this->I->fillField('#newpass2', $newPassword);
        $this->I->click('#sendChangePass');
        $this->I->waitForText('Пароль успешно изменен', 20);
    }

    public function seeLoginInsteadOfEdit(): void
    {
        $this->I->amOnPage('/account/logout');
        $this->I->amOnPage(self::URL);
        $this->I->waitForText('Вход', 20);
        $this->I->dontSee('Настройка сообщений');
    }

    private function checkboxXpath(string $labelPart): string
    {
        return '//label[contains(@class,"checkbox__item") and contains(normalize-space(.),"'
            . $labelPart
            . '")]//input[@type="checkbox"]';
    }

    public function seeCheckbox(string $labelPart, bool $checked, bool $disabled): void
    {
        $xpath = $this->checkboxXpath($labelPart);
        $this->I->waitForElement($xpath, 10);
        $state = $this->I->executeJS(
            'var el = document.evaluate(arguments[0], document, null,'
            . ' XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;'
            . 'if (!el) { return null; }'
            . 'return {checked: !!el.checked, disabled: !!el.disabled};',
            [$xpath]
        );
        if (is_object($state)) {
            $state = json_decode((string) json_encode($state), true);
        }
        $this->I->assertTrue(is_array($state), 'checkbox not found: ' . $labelPart);
        $this->I->assertSame($checked, (bool) $state['checked'], 'checked mismatch: ' . $labelPart);
        $this->I->assertSame($disabled, (bool) $state['disabled'], 'disabled mismatch: ' . $labelPart);
    }

    public function clickCheckbox(string $labelPart): void
    {
        $label = '//label[contains(@class,"checkbox__item") and contains(normalize-space(.),"'
            . $labelPart
            . '")]';
        $this->I->waitForElement($label, 10);
        $this->I->click($label);
    }

    public function seePayConfirm(): void
    {
        $this->I->waitForElement(self::PAY_NO, 20);
        $this->I->seeElement(self::PAY_YES);
        $this->I->dontSee('Недостаточно средств');
    }

    public function seeUnifiedPayConfirm(): void
    {
        $this->I->waitForText(self::CONFIRM_PREFIX, 20);
        $this->I->see(self::CONFIRM_PAID);
        $this->I->see(self::CONFIRM_CHARGE);
        $this->seePayConfirm();
        $this->dontSeeLegacyIncreaseDialogs();
    }

    public function dontSeeLegacyIncreaseDialogs(): void
    {
        $this->I->dontSee('Сейчас вам недоступна возможность защиты данных PIN-кодом');
        $this->I->dontSee('Сейчас вам недоступна данная опция.');
        $this->I->dontSee('Включить данную опцию?');
        $this->I->dontSee('Стоимость этой опции');
    }

    public function dontSeePayConfirm(): void
    {
        $this->I->dontSeeElement(self::PAY_NO);
        $this->I->dontSeeElement(self::PAY_YES);
    }

    public function cancelPayConfirm(): void
    {
        $this->I->click(self::PAY_NO);
        $this->I->waitForElementNotVisible(self::PAY_NO, 15);
    }

    public function confirmPay(): void
    {
        $this->I->click(self::PAY_YES);
        $this->I->waitForElementNotVisible(self::PAY_NO, 20);
    }

    public function seeNoServiceError(string $message): void
    {
        $this->I->waitForElement(self::ERROR_TITLE, 20);
        $this->I->see($message);
        $this->I->dontSee(self::CONFIRM_PREFIX);
        $this->dontSeePayConfirm();
    }

    public function installXhrProbe(): void
    {
        $this->I->executeJS(
            'if (window.__ctXhrProbeInstalled) { window.__ctXhrLog = []; return; }'
            . 'window.__ctXhrLog = [];'
            . 'window.__ctXhrProbeInstalled = true;'
            . 'var open = XMLHttpRequest.prototype.open;'
            . 'XMLHttpRequest.prototype.open = function (method, url) {'
            . '  this.__ctMeta = String(method) + " " + String(url);'
            . '  this.addEventListener("loadstart", function () {'
            . '    window.__ctXhrLog.push(this.__ctMeta);'
            . '  }.bind(this));'
            . '  return open.apply(this, arguments);'
            . '};'
        );
    }

    /**
     * @return list<string>
     */
    public function grabXhrLog(): array
    {
        $raw = $this->I->executeJS('return window.__ctXhrLog || [];');
        if (is_object($raw)) {
            $raw = json_decode((string) json_encode($raw), true);
        }

        return is_array($raw) ? array_values(array_map('strval', $raw)) : [];
    }

    public function seeXhrUrlPart(string $needle): void
    {
        $found = false;
        foreach ($this->grabXhrLog() as $row) {
            if (strpos($row, $needle) !== false) {
                $found = true;
                break;
            }
        }
        $this->I->assertTrue($found, 'ожидался XHR с ' . $needle . ' лог: ' . implode('; ', $this->grabXhrLog()));
    }

    public function dontSeeXhrUrlPart(string $needle): void
    {
        foreach ($this->grabXhrLog() as $row) {
            $this->I->assertTrue(
                strpos($row, $needle) === false,
                'не должно быть XHR: ' . $needle . ' факт: ' . $row
            );
        }
    }
}

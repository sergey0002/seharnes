<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Заказ проверки качества ОИС: /order/check (услуга 7090).
 *
 * Контракт флоу: .doc/qa/flows/order-quality-check.md
 * Задача-источник: CT-2236.
 *
 * Предупреждение качества рендерится компонентом
 * `order-check-quality-warning` (templates/Order/components/make/
 * order-check-quality-warning.tpl) как <span class="red"> внутри
 * обёрток --desktop / --mobile. Атрибута data-test на нём НЕТ,
 * поэтому селектор идёт по классу обёртки: это документированное
 * исключение, шаблон ради теста не правим.
 */
final class OrderCheckPage extends BasePage
{
    public const URL = '/order/check';

    private const WARNING_DESKTOP = '//*[contains(@class,"order-check-quality-warning--desktop")]'
        . '//span[contains(@class,"red")]';

    private const SUBJECT_LIST_TAG = 'order-subject-list2';

    private const FORM = '//*[contains(@class,"order-cert")]';

    public function open(): void
    {
        $this->I->amOnPage(self::URL);
        $this->I->waitForElement(self::FORM, 20);
        $this->I->waitForJS(
            'return !!(window.Vue && document.querySelector(".order-cert-row"));',
            15
        );
    }

    /**
     * Подставляет выбранные ОИС с флагами обложки/образцов прямо в Vue,
     * минуя SOAP. Нужно для матрицы warning без живого реестра.
     *
     * Порядок важен: сперва qualityFlags, затем values. Иначе watch на
     * values вызовет loadQualityFlagsForSelected() и уйдёт реальный XHR
     * (см. scripts/module/order/components/make/order-subject-list2.js).
     *
     * @param array<int, array{uin: string, name: string, issetCover: bool, issetDataBlocks: bool}> $items
     */
    public function seedSubjects(array $items): void
    {
        $payload = array_map(
            static fn(array $i): array => [
                'UIN'             => (string) $i['uin'],
                'name'            => (string) ($i['name'] ?? $i['uin']),
                'issetCover'      => (bool) $i['issetCover'],
                'issetDataBlocks' => (bool) $i['issetDataBlocks'],
            ],
            $items
        );

        $result = $this->I->executeJS(
            'var items = arguments[0];'
            . 'var find = ' . self::jsFindVueComponent() . ';'
            . 'var c = find("' . self::SUBJECT_LIST_TAG . '");'
            . 'if (!c) { return "no-component"; }'
            . 'items.forEach(function (it) {'
            . '  window.Vue.set(c.qualityFlags, it.UIN, {'
            . '    issetCover: it.issetCover, issetDataBlocks: it.issetDataBlocks'
            . '  });'
            . '});'
            . 'c.values = items.slice();'
            . 'c.$emit("input", c.selectedRids);'
            . 'c.emitQualityWarningRids();'
            . 'return "ok";',
            [$payload]
        );

        $this->I->assertSame(
            'ok',
            $result,
            'Компонент ' . self::SUBJECT_LIST_TAG . ' не найден на странице ' . self::URL
        );

        // Дать Vue перерисовать warning до ассертов.
        $this->I->waitForJS('return true;', 2);
    }

    public function seeWarning(): void
    {
        $this->I->waitForElement(self::WARNING_DESKTOP, 10);
        $this->I->seeElement(self::WARNING_DESKTOP);
    }

    public function dontSeeWarning(): void
    {
        $this->I->dontSeeElement(self::WARNING_DESKTOP);
    }

    public function seeWarningContains(string $uin): void
    {
        $this->seeWarning();
        $this->I->see($uin, self::WARNING_DESKTOP);
    }
}

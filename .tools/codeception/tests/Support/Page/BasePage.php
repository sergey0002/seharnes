<?php

declare(strict_types=1);

namespace Tests\Support\Page;

use Tests\Support\AcceptanceTester;

/**
 * База для Page-объектов.
 *
 * Page держит СЕЛЕКТОРЫ и примитивы навигации одного экрана.
 * Бизнес-сценарий собирается слоем Step, специфика задачи — в Cest.
 *
 * Правило: в Cest задачи сырых селекторов быть не должно
 * (проверяет .doc/qa/scripts/check-selectors.php).
 *
 * Приоритет селекторов (см. .doc/qa/index.md):
 *   1. существующий data-test
 *   2. id / стабильный BEM-класс / текст
 *   3. scoped XPath, executeJS для Vue
 * Шаблоны ради теста НЕ правим.
 */
abstract class BasePage
{
    protected AcceptanceTester $I;

    public function __construct(AcceptanceTester $I)
    {
        $this->I = $I;
    }

    /**
     * XPath по атрибуту data-test.
     */
    protected static function test(string $name): string
    {
        return '//*[@data-test="' . $name . '"]';
    }

    /**
     * XPath по data-test внутри другого data-test (scoped).
     */
    protected static function testIn(string $container, string $name): string
    {
        return '//*[@data-test="' . $container . '"]//*[@data-test="' . $name . '"]';
    }

    /**
     * Находит экземпляр Vue-компонента по его тегу (Vue 2: el.__vue__).
     * Возвращает JS-выражение-функцию, пригодное для вставки в executeJS.
     */
    protected static function jsFindVueComponent(): string
    {
        return 'function (tag) {'
            . '  var all = document.querySelectorAll("*");'
            . '  for (var i = 0; i < all.length; i++) {'
            . '    var v = all[i].__vue__;'
            . '    if (v && v.$options && v.$options._componentTag === tag) { return v; }'
            . '  }'
            . '  return null;'
            . '}';
    }
}

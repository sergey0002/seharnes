<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Многошаговая форма депонирования ОИС: /item/start.
 *
 * Контракт: .doc/architecture/deposition.md §1-3, §10-11
 * Флоу и селекторы: .doc/qa/flows/item-draft.md
 *
 * stepslist = 1, 2, 3, 4, 5, 6, preview, 7.
 *
 * Здесь живут ВСЕ селекторы wizard. Cest задачи их не дублирует.
 */
final class WizardPage extends BasePage
{
    public const URL = '/item/start';

    /** Стратегии депонирования (deposition.md §1.1). */
    public const STRATEGY_LITERARY = 'literary';
    public const STRATEGY_PROGRAMM = 'programm';
    public const STRATEGY_SCIENCE  = 'science';
    public const STRATEGY_METHODS  = 'methods';
    public const STRATEGY_FACTS    = 'facts';

    private const CONTAINER = 'item-container';
    private const NEXT_BTN  = 'item-container__next-btn';

    private const STEP2      = 'item-form-step2';
    private const STEP2_NAME = 'item-form-step2__name';
    private const STEP2_DATE = 'item-form-step2__fileDate';
    private const STEP2_DESC = 'item-form-step2__description';

    private const STEP3            = 'item-form-step3';
    private const STEP3_SUBJECT    = 'item-form-step3__subject';
    private const STEP3_SURNAME    = 'item-form-step3__subject-surname';
    private const STEP3_FIRSTNAME  = 'item-form-step3__subject-firstname';
    private const STEP3_SECONDNAME = 'item-form-step3__subject-secondname';
    private const STEP3_BIRTHDATE  = 'item-form-step3__subject-birthdate';

    private const RIGHTS             = 'item-form-step4-rights';
    private const RIGHTS_COPYRIGHTS  = 'item-form-step4-rights__copyrights-value';
    private const RIGHTS_RELATED     = 'item-form-step4-rights__related-value';
    private const RIGHTS_EXCEPTIONAL = 'item-form-step4-rights__exceptional-value';

    private const SAVE_BTN         = 'item-form-buttons__save-btn';
    private const SAVE_MODAL       = 'save-draft-modal';
    private const SAVE_MODAL_SUBMIT = 'save-draft-modal__save-btn';

    /**
     * Текст ошибки валидации поля рендерится как <p class="reg-author-form__error-text">
     * внутри контейнера поля #step-{N}_rafi-{M}. Атрибута data-test нет
     * (item-draft.md ошибочно указывал item-form-step2__name-error).
     */
    private const FIELD_ERROR_CLASS = 'reg-author-form__error-text';

    // =================================================================
    // Навигация
    // =================================================================

    public function open(string $strategy = self::STRATEGY_LITERARY): void
    {
        $this->I->amOnPage(self::URL . '?strategy=' . $strategy);
        $this->I->waitForElement(self::test(self::CONTAINER), 30);
        $this->I->waitForJS(
            'return !!(window.storeVue && window.storeVue.state && window.storeVue.state.Item);',
            20
        );
    }

    /**
     * Кнопка "Продолжить". Не проверяет, что переход удался:
     * для этого есть seeStep() / seeFieldError().
     */
    public function clickNext(): void
    {
        $this->I->click(self::test(self::NEXT_BTN));
    }

    /**
     * Переход вперёд с ожиданием смены шага в Vuex.
     */
    public function goToStep(string $step): void
    {
        $this->clickNext();
        $this->waitForStep($step);
    }

    public function waitForStep(string $step): void
    {
        $this->I->waitForJS(
            'return String(window.storeVue.state.Item.wizard.step) === ' . json_encode($step) . ';',
            20
        );
    }

    /**
     * Текущий шаг из Vuex (источник истины, не DOM: посещённые шаги
     * остаются в DOM под v-show, см. deposition.md §10).
     */
    public function grabCurrentStep(): string
    {
        return (string) $this->I->executeJS(
            'return String(window.storeVue.state.Item.wizard.step);'
        );
    }

    public function seeStep(string $step): void
    {
        $this->I->assertSame($step, $this->grabCurrentStep(), 'Ожидался шаг wizard ' . $step);
    }

    // =================================================================
    // Шаг 2 — описание ОИС
    // =================================================================

    public function fillStep2(string $name, string $creationDate = '01.01.2020', string $description = 'Описание'): void
    {
        $this->I->waitForElement(self::test(self::STEP2), 20);
        $this->I->fillField(self::test(self::STEP2_NAME), $name);
        $this->I->fillField(self::test(self::STEP2_DATE), $creationDate);
        $this->I->fillField(self::test(self::STEP2_DESC), $description);
    }

    public function fillStep2Name(string $name): void
    {
        $this->I->waitForElement(self::test(self::STEP2_NAME), 20);
        $this->I->fillField(self::test(self::STEP2_NAME), $name);
    }

    /**
     * Ждёт загрузки помощника очистки полей (data-edge-space на html).
     */
    public function waitForEdgeSpaceScript(): void
    {
        $this->I->waitForElement('[data-edge-space="1"]', 20);
    }

    /**
     * Заполняет дату и описание шага 2, не трогая поле названия.
     */
    public function fillStep2DateAndDescription(string $creationDate = '01.01.2020', string $description = 'Описание'): void
    {
        $this->I->fillField(self::test(self::STEP2_DATE), $creationDate);
        $this->I->fillField(self::test(self::STEP2_DESC), $description);
    }

    /**
     * Ставит значение в поле названия без события change (загруженные данные).
     */
    public function setNameWithoutChange(string $value): void
    {
        $this->I->executeJS(
            'var el = document.querySelector(\'[data-test="' . self::STEP2_NAME . '"]\');'
            . 'if (!el) { return; }'
            . 'el.value = ' . json_encode($value) . ';'
            . 'el.dispatchEvent(new Event("input", {bubbles:true}));'
        );
    }

    /**
     * Ставит значение и уводит фокус, возвращает итоговое значение поля.
     */
    public function cleanNameByChange(string $value): string
    {
        return (string) $this->I->executeJS(
            'var el = document.querySelector(\'[data-test="' . self::STEP2_NAME . '"]\');'
            . 'if (!el) { return ""; }'
            . 'el.focus();'
            . 'el.value = ' . json_encode($value) . ';'
            . 'el.dispatchEvent(new Event("input", {bubbles:true}));'
            . 'el.dispatchEvent(new Event("change", {bubbles:true}));'
            . 'el.blur();'
            . 'return el.value;'
        );
    }

    /**
     * Видна ли ошибка валидации у поля шага 2 (по data-test поля).
     */
    public function seeFieldError(string $fieldDataTest): void
    {
        $xpath = '//*[@data-test="' . $fieldDataTest . '"]'
            . '/ancestor::label//p[contains(@class,"' . self::FIELD_ERROR_CLASS . '")]';
        $this->I->waitForElement($xpath, 10);
        $this->I->seeElement($xpath);
    }

    public function seeNameError(): void
    {
        $this->seeFieldError(self::STEP2_NAME);
    }

    // =================================================================
    // Шаг 3 — субъекты
    // =================================================================

    public function fillFizikSubject(
        string $surname = 'Фамилия',
        string $firstName = 'Имя',
        string $secondName = 'Отчество',
        string $birthDate = '01.01.1990'
    ): void {
        $this->I->waitForElement(self::test(self::STEP3_SUBJECT), 20);
        $this->I->fillField(self::test(self::STEP3_SURNAME), $surname);
        $this->I->fillField(self::test(self::STEP3_FIRSTNAME), $firstName);
        $this->I->fillField(self::test(self::STEP3_SECONDNAME), $secondName);
        $this->I->fillField(self::test(self::STEP3_BIRTHDATE), $birthDate);
    }

    /**
     * Количество субъектов в Vuex (лимит 12, deposition.md §3 шаг 3).
     */
    public function grabAuthorsCount(): int
    {
        return (int) $this->I->executeJS(
            'var f = window.storeVue.state.Item.forms["3"];'
            . 'return (f && f.form && f.form.authors) ? f.form.authors.length : 0;'
        );
    }

    // =================================================================
    // Шаг 4 — права субъектов
    // =================================================================

    public function checkCopyrights(): void
    {
        $this->I->waitForElement(self::test(self::RIGHTS), 20);
        $this->I->click(self::test(self::RIGHTS_COPYRIGHTS));
    }

    public function checkRelatedRights(): void
    {
        $this->I->click(self::test(self::RIGHTS_RELATED));
    }

    public function checkExceptionalRights(): void
    {
        $this->I->click(self::test(self::RIGHTS_EXCEPTIONAL));
    }

    /**
     * Доступна ли роль смежных прав при текущей стратегии.
     * science отключает все смежные, programm часть (deposition.md §1.2).
     */
    public function isRelatedRightsDisabled(): bool
    {
        return (bool) $this->I->executeJS(
            'var el = document.querySelector("[data-test=\'' . self::RIGHTS_RELATED . '\']");'
            . 'if (!el) { return true; }'
            . 'return !!(el.disabled || el.closest("[disabled]"));'
        );
    }

    // =================================================================
    // Черновик
    // =================================================================

    public function saveDraft(string $draftName): void
    {
        $opened = $this->I->executeJS(
            'var nodes = document.querySelectorAll("[data-test=\'' . self::SAVE_BTN . '\']");'
            . 'for (var i = 0; i < nodes.length; i++) {'
            . '  if (nodes[i].offsetParent !== null) { nodes[i].click(); return "click"; }'
            . '}'
            . 'var all = document.querySelectorAll("*");'
            . 'for (var j = 0; j < all.length; j++) {'
            . '  var v = all[j].__vue__;'
            . '  if (v && typeof v.saveForm === "function" && typeof v.saveDraft === "function") {'
            . '    v.saveForm();'
            . '    return "vue";'
            . '  }'
            . '}'
            . 'return "";'
        );
        $this->I->assertNotSame('', (string) $opened, 'не удалось открыть модалку черновика');
        $this->I->waitForElement(self::test(self::SAVE_MODAL), 15);

        $nameInput = self::test(self::SAVE_MODAL) . '//input[@type="text"]';
        if ($draftName !== '') {
            $this->I->fillField($nameInput, $draftName);
        }

        $this->I->click(self::test(self::SAVE_MODAL_SUBMIT));
        $this->I->waitForText('Черновик успешно сохранен', 15);
    }

    /**
     * Computed Wizard.isset_changes (beforeunload).
     */
    public function grabIssetChanges(): bool
    {
        return (bool) $this->I->executeJS(
            'return !!(window.Wizard && window.Wizard.isset_changes);'
        );
    }

    public function waitUntilClean(int $seconds = 10): void
    {
        $this->I->waitForJS(
            'return !!(window.Wizard && window.Wizard.isset_changes === false);',
            $seconds
        );
    }

    // =================================================================
    // Диагностика стратегии
    // =================================================================

    /**
     * strategyValidationError выставляется бэкендом при рассогласовании
     * strategy и mainType/subType (deposition.md §1.2, §2.2).
     */
    public function grabStrategyValidationError(): string
    {
        return (string) $this->I->executeJS(
            'return window.strategyValidationError ? String(window.strategyValidationError) : "";'
        );
    }

    public function dontSeeStrategyValidationError(): void
    {
        $this->I->assertSame(
            '',
            $this->grabStrategyValidationError(),
            'На старте wizard выставлен strategyValidationError'
        );
    }
}

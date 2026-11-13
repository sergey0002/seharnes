<?php

declare(strict_types=1);

namespace Tests\Support\Step;

use Tests\Support\AcceptanceTester;
use Tests\Support\Page\WizardPage;

/**
 * Бизнес-сценарии депонирования ОИС.
 *
 * Step собирает шаги из Page в осмысленные действия. Здесь НЕТ селекторов:
 * они все в Page\WizardPage. Cest задачи вызывает Step и проверяет только
 * то, что специфично для задачи.
 *
 * Контракт: .doc/architecture/deposition.md
 */
final class DepositionSteps
{
    private AcceptanceTester $I;
    private WizardPage $wizard;

    public function __construct(AcceptanceTester $I)
    {
        $this->I = $I;
        $this->wizard = new WizardPage($I);
    }

    public function wizard(): WizardPage
    {
        return $this->wizard;
    }

    /**
     * Минимальные данные, с которыми wizard доходит до шага прав.
     * Возвращает имя ОИС — по нему потом ищем запись в БД.
     */
    public function fillMinimalUpToRights(string $strategy = WizardPage::STRATEGY_LITERARY): string
    {
        $name = 'AT ' . $strategy . ' ' . date('YmdHis');

        $this->wizard->open($strategy);
        $this->I->checkpoint('wizard-open-' . $strategy);

        $this->wizard->fillStep2($name);
        $this->I->checkpoint('wizard-step2-filled');

        $this->wizard->goToStep('3');
        $this->wizard->fillFizikSubject();
        $this->I->checkpoint('wizard-step3-filled');

        $this->wizard->goToStep('4');
        $this->I->checkpoint('wizard-step4-rights');

        return $name;
    }

    /**
     * Доходит до шага прав и сохраняет черновик.
     * Проверка записи в БД — на стороне Cest (нужен свой набор полей).
     */
    public function createDraft(string $strategy = WizardPage::STRATEGY_LITERARY): string
    {
        $name = $this->fillMinimalUpToRights($strategy);

        $this->wizard->checkCopyrights();
        $this->wizard->saveDraft($name);
        $this->I->checkpoint('wizard-draft-saved');

        return $name;
    }

    /**
     * Обязательное поле шага 2 не пускает дальше.
     * Негативный сценарий из чек-листа .doc/tests.md кат. 2.
     */
    public function assertStep2RequiresName(string $strategy = WizardPage::STRATEGY_LITERARY): void
    {
        $this->wizard->open($strategy);
        $this->wizard->fillStep2Name('');
        $this->wizard->clickNext();
        $this->I->checkpoint('wizard-step2-empty-name');

        $this->wizard->seeStep('2');
        $this->wizard->seeNameError();
    }

    /**
     * Стратегия открывается без ошибки рассогласования strategy/mainType.
     * Прогоняется по всем стратегиям как дымовой тест.
     */
    public function assertStrategyOpens(string $strategy): void
    {
        $this->wizard->open($strategy);
        $this->I->checkpoint('wizard-strategy-' . $strategy);

        $this->wizard->dontSeeStrategyValidationError();
        $this->wizard->seeStep('1');
        $this->I->seeNoConsoleErrors();
    }
}

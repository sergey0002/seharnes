<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * /profile/edit (webpack). Селекторов data-test на форме нет:
 * BEM-класс кнопки, name полей, Vue mixin issetChanges через executeJS.
 *
 * Контракт: .doc/tasks/2607/plan.md, person-profile.md (Edit webpack).
 */
final class ProfileEditPage extends BasePage
{
    public const URL = '/profile/edit';

    public const TITLE = 'Профиль';
    public const TOAST_SAVED = 'Профиль успешно сохранен';
    public const TOAST_REQUIRED = 'Пожалуйста, заполните обязательные поля';
    public const UNLOAD_MSG = 'Измененные данные не сохранены. Закрыть страницу?';

    private const SAVE = '//button[contains(@class,"profile-edit__button-save")]';

    public function open(): void
    {
        $this->I->amOnPage(self::URL);
        $this->I->waitForText(self::TITLE, 30);
        $this->I->waitForElement(self::SAVE, 30);
        $this->I->waitForJS($this->jsFindVm() . 'return !!(findVm() && findVm().init);', 20);
    }

    /**
     * Ждёт загрузки помощника очистки полей.
     */
    public function waitForEdgeSpaceScript(): void
    {
        $this->I->waitForElement('[data-edge-space="1"]', 20);
    }

    /**
     * Ставит значение в поле имени и уводит фокус, возвращает итоговое значение.
     */
    public function cleanFirstnameByChange(string $value): string
    {
        return (string) $this->I->executeJS(
            'var el = document.querySelector("input[name=\\"firstname\\"]");'
            . 'if (!el) { return ""; }'
            . 'el.focus();'
            . 'el.value = ' . json_encode($value) . ';'
            . 'el.dispatchEvent(new Event("input", {bubbles:true}));'
            . 'el.dispatchEvent(new Event("change", {bubbles:true}));'
            . 'el.blur();'
            . 'return el.value;'
        );
    }

    public function clickSave(): void
    {
        $this->I->waitForJS(
            'var btn = document.querySelector(".profile-edit__button-save");'
            . 'return !!(btn && !btn.disabled);',
            10
        );
        $this->I->click(self::SAVE);
    }

    public function fillCareer(string $value): void
    {
        $ok = $this->I->executeJS(
            $this->jsFindVm()
            . 'var vm = findVm();'
            . 'if (!vm || !vm.form || !vm.form.profile) { return false; }'
            . 'vm.form.profile.career = ' . json_encode($value) . ';'
            . 'return vm.issetChanges();'
        );
        $this->I->assertTrue((bool) $ok, 'поле career не изменило dirty-состояние');
    }

    public function checkConsent(): void
    {
        $this->I->executeJS(
            $this->jsFindVm()
            . 'var vm = findVm();'
            . 'if (vm) { vm.isCheckedPersonData = true; }'
        );
        $this->I->waitForJS(
            'var btn = document.querySelector(".profile-edit__button-save");'
            . 'return !!(btn && !btn.disabled);',
            10
        );
    }

    public function dontSeeSaveButton(): void
    {
        $this->I->dontSeeElement(self::SAVE);
    }

    /**
     * Минимальный физлик в Vue-форме, чтобы SaveProfile прошёл валидацию.
     */
    public function ensureMinimalFizik(): void
    {
        $this->I->executeJS(
            $this->jsFindVm()
            . 'var vm = findVm();'
            . 'if (!vm || !vm.form || !vm.form.profile) { return false; }'
            . 'var p = vm.form.profile;'
            . 'if (!p.lastname) { p.lastname = "Тестов"; }'
            . 'if (!p.firstname) { p.firstname = "Иван"; }'
            . 'p.withoutPatronname = 1;'
            . 'p.patronname = p.patronname || "";'
            . 'if (!p.sex) { p.sex = 1; }'
            . 'if (!p.birthDate) { p.birthDate = "01.01.1990"; }'
            . 'if (!p.cityzenship) { p.cityzenship = "RUS"; }'
            . 'if (!p.identityType) { p.identityType = "14"; }'
            . 'if (!p.identitySeria) { p.identitySeria = "1234"; }'
            . 'if (!p.identityNumber) { p.identityNumber = "567890"; }'
            . 'if (!p.identityDate) { p.identityDate = "01.01.2015"; }'
            . 'if (!p.identityResponcible) { p.identityResponcible = "ОВД"; }'
            . 'return true;'
        );
    }

    public function clearLastname(): void
    {
        $ok = $this->I->executeJS(
            $this->jsFindVm()
            . 'var vm = findVm();'
            . 'if (!vm || !vm.form || !vm.form.profile) { return false; }'
            . 'vm.form.profile.lastname = "";'
            . 'return true;'
        );
        $this->I->assertTrue((bool) $ok, 'не удалось очистить lastname');
    }

    public function grabIssetChanges(): bool
    {
        return (bool) $this->I->executeJS(
            $this->jsFindVm()
            . 'var vm = findVm();'
            . 'return !!(vm && vm.issetChanges && vm.issetChanges());'
        );
    }

    public function grabWouldWarnOnUnload(): bool
    {
        return (bool) $this->I->executeJS(
            $this->jsFindVm()
            . 'var vm = findVm();'
            . 'if (!vm || !vm.issetChanges) { return false; }'
            . 'return !!(vm.issetChanges() && !vm.isSavedForm);'
        );
    }

    public function waitUntilClean(int $seconds = 15): void
    {
        $this->I->waitForJS(
            $this->jsFindVm()
            . 'var vm = findVm();'
            . 'return !!(vm && vm.issetChanges && vm.issetChanges() === false && vm.isSavedForm === false);',
            $seconds
        );
    }

    public function seeToastSaved(): void
    {
        $this->I->waitForText(self::TOAST_SAVED, 15);
    }

    public function seeToastRequired(): void
    {
        $this->I->waitForText(self::TOAST_REQUIRED, 10);
    }

    /**
     * CT-2608: client 1 как ИП с фамилией Мурзин (window.type=ip на /profile/edit).
     */
    public function seedClientAsIpWithLastname(string $lastname = 'Мурзин'): void
    {
        $this->I->updateInDatabase('ct_personProfile', [
            'profileType' => 2,
            'lastname' => $lastname,
            'firstname' => 'Иван',
            'withoutPatronname' => 1,
            'patronname' => '',
            'cityzenship' => 'RUS',
            'countryOfBirth' => 'RUS',
        ], ['clientId' => 1]);
    }

    public function restoreClientAsFizik(): void
    {
        $this->I->updateInDatabase('ct_personProfile', [
            'profileType' => 0,
        ], ['clientId' => 1]);
    }

    public function seeWindowType(string $type): void
    {
        $actual = (string) $this->I->executeJS('return String(window.type || "");');
        $this->I->assertSame($type, $actual, 'ожидался window.type=' . $type);
    }

    public function openIpPersonAccordion(): void
    {
        $this->I->executeJS(
            $this->jsFindVm()
            . 'var vm = findVm();'
            . 'if (vm && vm.spoiler) { vm.spoiler.active = 1; }'
        );
        $this->I->waitForElement('input[name="lastname"]', 15);
    }

    /**
     * Программная замена DOM value + bubbling input (сценарий бага CT-2608).
     *
     * @return array{dom:string,model:string}
     */
    public function replaceLastnameViaDomInput(string $from, string $to): array
    {
        $payload = $this->I->executeJS(
            $this->jsFindVm()
            . 'var el = document.querySelector("input[name=\\"lastname\\"]");'
            . 'if (!el) { return {ok:false, reason:"no-input"}; }'
            . 'el.value = ' . json_encode($from) . ';'
            . 'el.dispatchEvent(new Event("input", {bubbles:true}));'
            . 'el.value = ' . json_encode($to) . ';'
            . 'el.dispatchEvent(new Event("input", {bubbles:true}));'
            . 'var vm = findVm();'
            . 'var model = (vm && vm.form && vm.form.profile) ? String(vm.form.profile.lastname || "") : "";'
            . 'return {ok:true, dom:String(el.value || ""), model:model};'
        );
        $this->I->assertIsArray($payload, 'executeJS не вернул объект');
        $this->I->assertTrue(!empty($payload['ok']), 'input[name=lastname] не найден');

        return [
            'dom' => (string) ($payload['dom'] ?? ''),
            'model' => (string) ($payload['model'] ?? ''),
        ];
    }

    /**
     * Несколько способов записи lastname. Нужен для проверки, воспроизводится ли
     * "Кузьминурзин" на релизе с v-mask (Jira: иногда, руками нет).
     *
     * @return array<string, array{dom:string,model:string}>
     */
    public function probeLastnameWriteStrategies(string $from, string $to): array
    {
        $payload = $this->I->executeJS(
            $this->jsFindVm()
            . 'function snap() {'
            . '  var el = document.querySelector("input[name=\\"lastname\\"]");'
            . '  var vm = findVm();'
            . '  var model = (vm && vm.form && vm.form.profile) ? String(vm.form.profile.lastname || "") : "";'
            . '  return {dom: el ? String(el.value || "") : "NOEL", model: model};'
            . '}'
            . 'function resetFrom(from) {'
            . '  var vm = findVm();'
            . '  var el = document.querySelector("input[name=\\"lastname\\"]");'
            . '  if (vm && vm.form && vm.form.profile) { vm.form.profile.lastname = from; }'
            . '  if (el && window.jQuery && jQuery(el).data("inputmask")) {'
            . '    jQuery(el).inputmask("setvalue", from);'
            . '  } else if (el) { el.value = from; }'
            . '}'
            . 'var from = ' . json_encode($from) . ';'
            . 'var to = ' . json_encode($to) . ';'
            . 'var out = {};'
            . 'resetFrom(from);'
            . '(function () {'
            . '  var el = document.querySelector("input[name=\\"lastname\\"]");'
            . '  el.value = to;'
            . '  el.dispatchEvent(new Event("input", {bubbles:true}));'
            . '  out.dom_value_input = snap();'
            . '})();'
            . 'resetFrom(from);'
            . '(function () {'
            . '  var el = document.querySelector("input[name=\\"lastname\\"]");'
            . '  var proto = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value");'
            . '  if (proto && proto.set) { proto.set.call(el, to); } else { el.value = to; }'
            . '  el.dispatchEvent(new Event("input", {bubbles:true}));'
            . '  out.native_setter = snap();'
            . '})();'
            . 'resetFrom(from);'
            . '(function () {'
            . '  var vm = findVm();'
            . '  if (vm && vm.form && vm.form.profile) { vm.form.profile.lastname = to; }'
            . '  out.vue_model = snap();'
            . '})();'
            . 'resetFrom(from);'
            . '(function () {'
            . '  var el = document.querySelector("input[name=\\"lastname\\"]");'
            . '  if (window.jQuery) { jQuery(el).val(to).trigger("input").trigger("change"); }'
            . '  out.jquery_val = snap();'
            . '})();'
            . 'resetFrom(from);'
            . '(function () {'
            . '  var el = document.querySelector("input[name=\\"lastname\\"]");'
            . '  var hasIm = !!(window.jQuery && jQuery(el).data("inputmask"));'
            . '  if (hasIm) { jQuery(el).inputmask("setvalue", to); }'
            . '  out.inputmask_setvalue = snap();'
            . '  out.inputmask_setvalue.hasIm = hasIm;'
            . '})();'
            . 'resetFrom(from);'
            . '(function () {'
            . '  var el = document.querySelector("input[name=\\"lastname\\"]");'
            . '  el.value = el.value + to;'
            . '  el.dispatchEvent(new Event("input", {bubbles:true}));'
            . '  out.append_value = snap();'
            . '})();'
            . 'out.hasJqueryInputmaskPlugin = !!(window.jQuery && jQuery.fn && jQuery.fn.inputmask);'
            . 'return out;'
        );
        $this->I->assertIsArray($payload, 'probe не вернул объект');

        return $payload;
    }

    public function grabLastnameDomAndModel(): array
    {
        $payload = $this->I->executeJS(
            $this->jsFindVm()
            . 'var el = document.querySelector("input[name=\\"lastname\\"]");'
            . 'var vm = findVm();'
            . 'var model = (vm && vm.form && vm.form.profile) ? String(vm.form.profile.lastname || "") : "";'
            . 'return {dom: el ? String(el.value || "") : "", model: model};'
        );

        return [
            'dom' => (string) ($payload['dom'] ?? ''),
            'model' => (string) ($payload['model'] ?? ''),
        ];
    }

    public function seeFirstnameAndPatronnameInputs(): void
    {
        $this->I->seeElement('input[name="firstname"]');
        $this->I->seeElement('input[name="patronname"]');
    }

    private function jsFindVm(): string
    {
        return 'function findVm() {'
            . '  function walk(vm) {'
            . '    if (vm && typeof vm.issetChanges === "function") { return vm; }'
            . '    var kids = vm.$children || [];'
            . '    for (var i = 0; i < kids.length; i++) {'
            . '      var found = walk(kids[i]);'
            . '      if (found) { return found; }'
            . '    }'
            . '    return null;'
            . '  }'
            . '  var btn = document.querySelector(".profile-edit__button-save");'
            . '  var el = btn;'
            . '  while (el) {'
            . '    if (el.__vue__) {'
            . '      var found = walk(el.__vue__);'
            . '      if (found) { return found; }'
            . '    }'
            . '    el = el.parentElement;'
            . '  }'
            . '  return null;'
            . '}';
    }
}

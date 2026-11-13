<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Общие проверки гостевых форм signup/signin: красная *, Vue vs HTML5,
 * блокировка submit без POST.
 *
 * CSS-маркер обязательности: .formbox__lable.require-lable:after
 * (styles/css/style.css, цвет #db1515). Шаблоны ради теста не правим.
 */
abstract class AccountGuestFormPage extends BasePage
{
    public const STAR_COLOR_RGB = 'rgb(219, 21, 21)';
    public const REQUIRED_MESSAGE = 'Поле обязательно для заполнения';

    /**
     * @return array{content:string,color:string,className:string,hidden:bool}|null
     */
    protected function grabLabelStar(string $labelText): ?array
    {
        $raw = $this->I->executeJS(
            'var needle = arguments[0];'
            . 'var labels = document.querySelectorAll("label");'
            . 'var el = null;'
            . 'for (var i = 0; i < labels.length; i++) {'
            . '  var t = (labels[i].textContent || "").replace(/\\s+/g, " ").trim();'
            . '  if (t.indexOf(needle) === 0 || t === needle) { el = labels[i]; break; }'
            . '}'
            . 'if (!el) { return null; }'
            . 'var cs = window.getComputedStyle(el, ":after");'
            . 'var vis = window.getComputedStyle(el);'
            . 'var hidden = vis.display === "none" || vis.visibility === "hidden"'
            . '  || el.offsetParent === null;'
            . 'return {content: cs.content, color: cs.color, className: el.className, hidden: hidden};',
            [$labelText]
        );

        if ($raw === null) {
            return null;
        }
        if (is_object($raw)) {
            $raw = json_decode((string) json_encode($raw), true);
        }

        return is_array($raw) ? $raw : null;
    }

    public function seeRequiredStar(string $labelText): void
    {
        $info = $this->grabLabelStar($labelText);
        $this->I->assertTrue(is_array($info), 'лейбл не найден: ' . $labelText);
        if (!empty($info['hidden'])) {
            $this->I->comment('лейбл скрыт (капча выключена): ' . $labelText);

            return;
        }
        $content = str_replace(['"', "'"], '', (string) $info['content']);
        $this->I->assertSame('*', $content, 'нет * у лейбла: ' . $labelText . ' content=' . $info['content']);
        $this->I->assertSame(
            self::STAR_COLOR_RGB,
            (string) $info['color'],
            'цвет * не #db1515 у: ' . $labelText
        );
        $this->I->assertTrue(
            strpos((string) $info['className'], 'require-lable') !== false,
            'нет класса require-lable у: ' . $labelText
        );
        $this->I->assertTrue(
            strpos((string) $info['className'], 'formbox__lable') !== false,
            'нет класса formbox__lable у: ' . $labelText
        );
    }

    public function dontSeeRequiredStar(string $labelText): void
    {
        $info = $this->grabLabelStar($labelText);
        $this->I->assertTrue(is_array($info), 'лейбл не найден: ' . $labelText);
        $content = str_replace(['"', "'"], '', (string) $info['content']);
        $this->I->assertTrue(
            $content === '' || $content === 'none' || $content === 'normal',
            'неожиданная * у необязательного поля: ' . $labelText . ' content=' . $info['content']
        );
        $this->I->assertTrue(
            strpos((string) $info['className'], 'require-lable') === false,
            'require-lable не должен быть у: ' . $labelText
        );
    }

    /**
     * @return list<string>
     */
    protected function grabNativeRequiredNames(string $formSelector): array
    {
        $raw = $this->I->executeJS(
            'var form = document.querySelector(arguments[0]);'
            . 'if (!form) { return []; }'
            . 'var nodes = form.querySelectorAll("input, textarea, select");'
            . 'var names = [];'
            . 'for (var i = 0; i < nodes.length; i++) {'
            . '  if (nodes[i].required) { names.push(nodes[i].name || nodes[i].id || ("idx"+i)); }'
            . '}'
            . 'return names;',
            [$formSelector]
        );
        if (is_object($raw)) {
            $raw = json_decode((string) json_encode($raw), true);
        }

        return is_array($raw) ? array_values(array_map('strval', $raw)) : [];
    }

    public function seeNoNativeHtml5Required(string $formSelector): void
    {
        $this->I->assertSame(
            [],
            $this->grabNativeRequiredNames($formSelector),
            'ожидалась Vue-валидация, не HTML5 required'
        );
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

    public function dontSeeXhrUrlPart(string $needle): void
    {
        foreach ($this->grabXhrLog() as $row) {
            $this->I->assertTrue(
                strpos($row, $needle) === false,
                'не должно быть XHR: ' . $needle . ' факт: ' . $row
            );
        }
    }

    public function dropCaptchaConsoleNoise(): void
    {
        $this->I->executeJS(
            'window.__testConsoleErrors = (window.__testConsoleErrors || []).filter(function (s) {'
            . '  s = String(s);'
            . '  return s.indexOf("yastatic") === -1'
            . '    && s.indexOf("smartcaptcha") === -1'
            . '    && s.indexOf("Minified React") === -1;'
            . '});'
        );
    }

    public function ensureGuest(): void
    {
        $this->I->amOnPage('/account/logout');
    }
}

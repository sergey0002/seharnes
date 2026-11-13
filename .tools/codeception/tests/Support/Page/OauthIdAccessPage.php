<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Кнопки входа по внешним ID на signin/signup и серверный guard OAuth.
 *
 * Кнопки: a.signup-another__item[data-signup="{image}"] (Vue bind cl.image).
 * Шаблоны не правим. Контракт флагов: CT-2231 / configs/oauth.php active.
 */
final class OauthIdAccessPage extends BasePage
{
    private const SOCIAL_ITEM = '//a[contains(@class,"signup-another__item") and @data-signup="%s"]';
    private const DISABLED_MSG_PREFIX = 'OAuth provider is disabled: ';

    public function openSignin(): void
    {
        $this->I->amOnPage('/account/logout');
        $this->I->amOnPage(SigninPage::URL);
        $this->I->waitForElement(self::test('login-form'), 20);
        $this->I->see('Вход');
    }

    public function openSignup(): void
    {
        $this->I->amOnPage('/account/logout');
        $this->I->amOnPage(SignupPage::URL);
        $this->I->waitForElement('//form[contains(@class,"form-signup")]', 20);
        $this->I->see('Регистрация');
    }

    public function seeSocialButton(string $imageKey): void
    {
        $this->I->waitForElement(sprintf(self::SOCIAL_ITEM, $imageKey), 10);
        $this->I->seeElement(sprintf(self::SOCIAL_ITEM, $imageKey));
    }

    public function dontSeeSocialButton(string $imageKey): void
    {
        $this->I->dontSeeElement(sprintf(self::SOCIAL_ITEM, $imageKey));
    }

    /**
     * @return list<string>
     */
    public function grabClientNamesFromWindow(): array
    {
        $raw = $this->I->executeJS(
            'return (window.clients || []).map(function (c) { return c && c.name ? String(c.name) : ""; });'
        );
        if (!is_array($raw)) {
            return [];
        }
        $names = [];
        foreach ($raw as $name) {
            if (is_string($name) && $name !== '') {
                $names[] = $name;
            }
        }

        return $names;
    }

    public function seeClientNameInWindow(string $name): void
    {
        $names = $this->grabClientNamesFromWindow();
        $this->I->assertTrue(
            in_array($name, $names, true),
            'window.clients должен содержать ' . $name . ', есть: ' . implode(',', $names)
        );
    }

    public function dontSeeClientNameInWindow(string $name): void
    {
        $names = $this->grabClientNamesFromWindow();
        $this->I->assertFalse(
            in_array($name, $names, true),
            'window.clients не должен содержать ' . $name . ', есть: ' . implode(',', $names)
        );
    }

    public function grabGetUrlBody(string $provider): string
    {
        $origin = (string) $this->I->executeJS('return window.location.origin;');
        $path = '/oauth/geturl/' . rawurlencode($provider)
            . '?origin=' . rawurlencode($origin);

        return $this->I->grabSameOriginGet($path);
    }

    public function seeGetUrlDisabled(string $provider): void
    {
        $raw = $this->grabGetUrlBody($provider);
        $needle = self::DISABLED_MSG_PREFIX . $provider;
        $this->I->assertTrue(
            strpos($raw, $needle) !== false,
            'ожидали disabled для ' . $provider . ', ответ: ' . $raw
        );
    }

    public function seeGetUrlHasLogonUrl(string $provider): void
    {
        $raw = $this->grabGetUrlBody($provider);
        $this->I->assertTrue(
            strpos($raw, '"url"') !== false,
            'ожидали url в geturl для ' . $provider . ', ответ: ' . $raw
        );
        $this->I->assertTrue(
            strpos($raw, self::DISABLED_MSG_PREFIX) === false,
            'geturl для активного провайдера не должен быть disabled: ' . $raw
        );
    }

    /**
     * @param array<string, string> $fields
     */
    public function postOauthRegister(array $fields): string
    {
        $query = http_build_query($fields);

        return (string) $this->I->executeJS(
            'var xhr = new XMLHttpRequest();'
            . 'xhr.open("POST", "/oauth/register", false);'
            . 'xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");'
            . 'xhr.send(arguments[0]);'
            . 'return String(xhr.status) + "\\n" + String(xhr.responseText || "");',
            [$query]
        );
    }

    public function seeRegisterDisabled(string $provider): void
    {
        $email = 'oauth-disabled-' . $provider . '-' . time() . '@example.invalid';
        $raw = $this->postOauthRegister([
            'email' => $email,
            'family' => 'Test',
            'login' => 'testlogin',
            'name' => 'Test',
            'ref' => '',
            'ext_uid' => 'ext-uid-disabled-' . $provider,
            'client' => $provider,
            'pname' => '',
        ]);
        $this->I->assertTrue(
            strpos($raw, self::DISABLED_MSG_PREFIX . $provider) !== false,
            'ожидали disabled на register для ' . $provider . ', ответ: ' . $raw
        );
        $this->I->dontSeeInDatabase('ct_client', ['email' => $email]);
    }

    public function seeVkIdConfigEnabled(bool $expected): void
    {
        $raw = $this->I->grabSameOriginGet('/oauth/js');
        $enabled = $this->extractVkIdEnabled($raw);
        $this->I->assertSame(
            $expected,
            $enabled,
            'vkIdConfig.enabled должен быть ' . ($expected ? 'true' : 'false')
        );
    }

    private function extractVkIdEnabled(string $oauthJsBody): bool
    {
        if (!preg_match("/JSON\\.parse\\(atob\\('([A-Za-z0-9+\\/=]+)'\\)\\)/", $oauthJsBody, $m)) {
            $this->I->fail('в /oauth/js не найден vkIdConfig base64');
        }
        $json = base64_decode($m[1], true);
        $this->I->assertTrue($json !== false, 'vkIdConfig base64 не декодируется');
        $data = json_decode((string) $json, true);
        $this->I->assertTrue(is_array($data), 'vkIdConfig JSON битый');
        $this->I->assertTrue(array_key_exists('enabled', $data), 'vkIdConfig без enabled');

        return (bool) $data['enabled'];
    }
}

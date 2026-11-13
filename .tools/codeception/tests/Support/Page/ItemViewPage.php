<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Карточка регистрационной информации /item/view/{UIN}.
 *
 * Контракт: .doc/qa/flows/admin-item-soap-json.md
 * Задача: CT-2596 (JSON SOAP в блоке Для администратора).
 *
 * JSON виден только ClientService::IsAdmin / ADMIN_IDS, не ct_user /admin
 * и не владельцу (authorization.md П-13).
 */
final class ItemViewPage extends BasePage
{
    public const URL_PREFIX = '/item/view/';

    public const TITLE_ADMIN_BLOCK = 'Для администратора';
    public const TITLE_JSON_SOAP = 'JSON SOAP';
    public const LABEL_SHOW_JSON = 'Показать JSON';
    public const LABEL_HIDE_JSON = 'Скрыть JSON';
    public const LABEL_PRINT = 'Печать сертификата';
    public const LABEL_QUALITY = 'ПРИЗНАК КАЧЕСТВА ОБЪЕКТА';
    public const MSG_OWNER_FORBIDDEN = 'Доступ к этой странице закрыт ее владельцем!';

    /** Кандидаты ADMIN_IDS со стенда (authorization.md П-13). */
    public const ADMIN_CLIENT_CANDIDATES = [28, 35, 1];

    private const TOGGLE = 'admin-soap-json-toggle';
    private const BODY = 'admin-soap-json-body';
    private const ITEM_MAIN = 'item-main';

    public function open(string $uin): void
    {
        $this->I->amOnPage(self::URL_PREFIX . $uin);
        $this->I->waitForElement('//body', 20);
    }

    public function openMyRegistrations(): void
    {
        $this->I->amOnPage('/item/main');
        $this->I->waitForElement(self::test(self::ITEM_MAIN), 30);
        $this->I->waitForText('Мои регистрации', 30);
    }

    /**
     * Первый UIN из таблицы "Мои регистрации", либо QA_ITEM_VIEW_UIN.
     */
    public function grabFirstRegistrationUin(): string
    {
        $fromEnv = getenv('QA_ITEM_VIEW_UIN');
        if (is_string($fromEnv) && $fromEnv !== '') {
            return $fromEnv;
        }

        $this->openMyRegistrations();
        $this->I->waitForJS(
            'var nodes = document.getElementsByClassName("table__uin");'
            . 'return nodes && nodes.length > 0;',
            40
        );

        $uin = $this->I->executeJS(
            'var nodes = document.getElementsByClassName("table__uin");'
            . 'if (!nodes || !nodes.length) { return ""; }'
            . 'var href = nodes[0].getAttribute("href") || "";'
            . 'var m = href.match(/item\\/view\\/([^/?#]+)/);'
            . 'if (m) { return m[1]; }'
            . 'return (nodes[0].textContent || "").trim();'
        );

        $this->I->assertTrue(is_string($uin) && $uin !== '', 'нет UIN в Мои регистрации и нет QA_ITEM_VIEW_UIN');

        return $uin;
    }

    public function pickAdminClientId(): int
    {
        foreach (self::ADMIN_CLIENT_CANDIDATES as $id) {
            if ($this->I->grabNumRecords('ct_client', ['id' => $id]) > 0) {
                return $id;
            }
        }

        $this->I->fail('нет клиента из ADMIN_IDS (28, 35, 1) в ct_client');

        return 0;
    }

    public function seeAdminSoapJsonToggle(): void
    {
        $this->I->waitForText(self::TITLE_ADMIN_BLOCK, 30);
        $this->I->see(self::TITLE_ADMIN_BLOCK);
        $this->I->see(self::TITLE_JSON_SOAP);
        $this->I->waitForElement(self::test(self::TOGGLE), 15);
        $this->I->see(self::LABEL_SHOW_JSON);
    }

    public function dontSeeAdminSoapJsonToggle(): void
    {
        $this->I->dontSeeElement(self::test(self::TOGGLE));
        $this->I->dontSee(self::TITLE_JSON_SOAP);
        $this->I->dontSee(self::LABEL_SHOW_JSON);
    }

    public function seeOwnerForbidden(): void
    {
        $this->I->waitForText(self::MSG_OWNER_FORBIDDEN, 20);
        $this->I->see(self::MSG_OWNER_FORBIDDEN);
    }

    public function expandSoapJson(): void
    {
        $this->I->click(self::test(self::TOGGLE));
        $this->I->waitForElementVisible(self::test(self::BODY), 10);
        $this->I->see(self::LABEL_HIDE_JSON);
    }

    public function collapseSoapJson(): void
    {
        $this->I->click(self::test(self::TOGGLE));
        $this->I->waitForElementNotVisible(self::test(self::BODY), 10);
        $this->I->see(self::LABEL_SHOW_JSON);
    }

    /**
     * @return array<string, mixed>
     */
    public function grabSoapJsonPayload(): array
    {
        $payload = $this->I->executeJS(
            'if (typeof window.soapRegJson !== "string" || !window.soapRegJson) { return {__empty: true}; }'
            . 'try { return JSON.parse(window.soapRegJson); }'
            . 'catch (e) { return {__parseError: String(e)}; }'
        );

        if (is_object($payload)) {
            $payload = json_decode((string) json_encode($payload), true);
        }

        $this->I->assertTrue(is_array($payload), 'soapRegJson не разобрался как объект');
        $this->I->assertArrayNotHasKey('__empty', $payload, 'window.soapRegJson пуст');
        $this->I->assertArrayNotHasKey('__parseError', $payload, 'window.soapRegJson не JSON');
        $this->I->assertArrayNotHasKey('error', $payload, 'экспорт вернул error');

        return $payload;
    }

    public function seeSoapJsonMatchesUin(string $uin): void
    {
        $payload = $this->grabSoapJsonPayload();
        $this->I->assertSame($uin, (string) ($payload['UIN'] ?? ''), 'UIN в JSON не совпал с карточкой');
        $this->I->assertTrue(isset($payload['Name']) && is_string($payload['Name']), 'в JSON нет Name');
        $this->I->assertTrue(isset($payload['WorkType']) && !is_array($payload['WorkType']), 'WorkType должен быть скаляр SOAP, не HumanForm');
        $this->I->assertTrue(isset($payload['ViewRights']) && !is_array($payload['ViewRights']), 'ViewRights должен быть скаляр SOAP');

        if (!empty($payload['RegistrationDate']) && is_string($payload['RegistrationDate'])) {
            $this->I->assertTrue(
                str_contains($payload['RegistrationDate'], 'T'),
                'RegistrationDate должен быть формата конвертера Y-m-d\\TH:i:s'
            );
        }
    }

    public function seeNeighborAdminItemControls(): void
    {
        $this->I->see(self::LABEL_PRINT);
        $this->I->see(self::LABEL_QUALITY);
    }

    public function soapJsonIsEmptyInWindow(): bool
    {
        $raw = $this->I->executeJS('return window.soapRegJson;');

        return $raw === null || $raw === '' || $raw === false;
    }
}

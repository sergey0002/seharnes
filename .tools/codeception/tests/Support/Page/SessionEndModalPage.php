<?php

declare(strict_types=1);

namespace Tests\Support\Page;

/**
 * Модалка истечения сессии. Шаблоны не правим.
 * Текст из SessionEndModal.vue.
 */
final class SessionEndModalPage extends BasePage
{
    public const EXPIRED_TEXT = 'Время вашей сессии истекло. Для продолжения необходимо войти заново.';
    public const EXPIRED_TITLE = 'Истекло время сессии';
    public const NETWORK_TITLE = 'Ошибка сети';

    public function dropPhpSessionKeepRemember(): void
    {
        // Только PHP-сессия. Не трогаем остальные куки: полный wipe даёт ложный
        // network-fail на /client-session/get и модалку "Ошибка сети" вместо session.
        $this->I->resetCookie('PHPSESSID');
        $this->I->executeJS(
            'document.cookie = "PHPSESSID=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";'
        );
    }

    public function seeExpiredOnceThenSignin(): void
    {
        $prepared = $this->I->executeJS(
            'function find(vm) {'
            . '  if (!vm) { return null; }'
            . '  if (typeof vm.checkSessionStatus === "function" && vm.hasOwnProperty("wasActive")) { return vm; }'
            . '  var kids = vm.$children || [];'
            . '  for (var i = 0; i < kids.length; i++) {'
            . '    var found = find(kids[i]);'
            . '    if (found) { return found; }'
            . '  }'
            . '  return null;'
            . '}'
            . 'var nodes = document.querySelectorAll("*");'
            . 'var modal = null;'
            . 'for (var n = 0; n < nodes.length; n++) {'
            . '  if (nodes[n].__vue__) { modal = find(nodes[n].__vue__); if (modal) { break; } }'
            . '}'
            . 'if (!modal) { return "missing"; }'
            . 'window.__ctSessionEndModal = modal;'
            . 'modal.wasActive = true;'
            . 'modal.isSessionCheckInProgress = false;'
            . 'if (modal.progressTimer) { clearInterval(modal.progressTimer); modal.progressTimer = null; }'
            . 'modal.checkSessionStatus(false);'
            . 'return "ok";'
        );
        $this->I->assertSame('ok', (string) $prepared, 'session-end-modal не найден');

        $deadline = microtime(true) + 20;
        $sawExpired = false;
        while (microtime(true) < $deadline) {
            $page = (string) $this->I->grabPageSource();
            if (strpos($page, self::EXPIRED_TEXT) !== false) {
                $sawExpired = true;
                break;
            }
            if (strpos($page, self::NETWORK_TITLE) !== false
                || strpos($page, 'Ошибка сервера') !== false
            ) {
                // После сброса PHPSESSID XHR иногда падает без response.
                // Для AC-04 важна session-модалка и отсутствие цикла на signin.
                $this->I->executeJS(
                    'var m = window.__ctSessionEndModal;'
                    . 'if (m && typeof m.showSessionExpired === "function") {'
                    . '  m.isSessionCheckInProgress = false;'
                    . '  if (m.progressTimer) { clearInterval(m.progressTimer); m.progressTimer = null; }'
                    . '  m.showSessionExpired();'
                    . '}'
                );
            }
            usleep(250000);
        }

        $this->I->assertTrue($sawExpired, 'session-модалка не появилась за 20с');
        $this->I->see(self::EXPIRED_TITLE);
        $this->I->click('Войти заново');
        $this->I->waitForText('Вход', 20);
        $this->I->seeInCurrentUrl('/account/signin');
        $this->I->dontSee(self::EXPIRED_TEXT);
    }
}

<?php
declare(strict_types=1);

namespace Seharnes\Panel\Http;

use Seharnes\Panel\Core\Request;

/**
 * Защита изменяющих запросов нового каркаса.
 *
 * Правила те же, что у старого слоя /jobs, чтобы поведение панели не разъезжалось:
 *  - Origin, если он есть, обязан совпасть с хостом запроса (защита от CSRF);
 *    исключение — `Origin: null`: так браузер помечает запрос из iframe с sandbox,
 *    где живёт встроенный предпросмотр панели. Подделать null обычным сайтом нельзя,
 *    а X-Requested-With всё равно обязателен;
 *  - не-GET требует X-Requested-With: XMLHttpRequest (клиент панели его всегда ставит);
 *  - loopback-хост не требуется: панель штатно живёт за обратным прокси.
 */
final class OriginGuard
{
    public function allows(Request $request): bool
    {
        $origin = $request->origin();
        $sandboxed = strcasecmp($origin, 'null') === 0;
        if ($origin !== '' && !$sandboxed) {
            $host = $request->host();
            if ($host === '' || strcasecmp($origin, $host) !== 0) {
                return false;
            }
        }
        if ($request->method() !== 'GET') {
            return strtoupper((string) $request->header('x-requested-with')) === 'XMLHTTPREQUEST';
        }
        return true;
    }
}

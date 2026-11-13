<?php
declare(strict_types=1);

namespace Seharnes\Panel\Support;

use Seharnes\Panel\Core\Request;

/**
 * Локализация интерфейса: словари в resources/lang/<lang>.json.
 *
 * Язык выбирается так: ?lang= -> cookie panel_lang -> Accept-Language -> ru.
 * Словарь целиком уходит в браузер один раз (bootstrap), чтобы JS не ходил за строками.
 */
final class I18n
{
    public const DEFAULT = 'ru';
    public const COOKIE = 'panel_lang';
    /** @var array<string, list<string>> */
    private const SUPPORTED = [
        'ru' => ['ru', 'be', 'uk', 'kk'],
        'en' => ['en'],
    ];

    /** @var array<string, string> */
    private array $dictionary;
    /** @var list<string> */
    private array $available;

    public function __construct(private readonly string $langDir, private readonly string $lang)
    {
        $this->dictionary = $this->load($lang);
        $this->available = $this->discover();
    }

    public static function fromRequest(string $langDir, Request $request): self
    {
        return new self($langDir, self::negotiate($request));
    }

    public static function negotiate(Request $request): string
    {
        $query = strtolower((string) $request->query('lang', ''));
        if ($query !== '' && self::isSupported($query)) {
            return self::normalize($query);
        }
        $cookie = strtolower((string) $request->cookie(self::COOKIE, ''));
        if ($cookie !== '' && self::isSupported($cookie)) {
            return self::normalize($cookie);
        }
        $accept = strtolower((string) $request->header('accept-language'));
        foreach (explode(',', $accept) as $part) {
            $code = substr(trim(explode(';', $part)[0]), 0, 2);
            if ($code !== '' && self::isSupported($code)) {
                return self::normalize($code);
            }
        }
        return self::DEFAULT;
    }

    public function lang(): string
    {
        return $this->lang;
    }

    /** @return list<string> */
    public function available(): array
    {
        return $this->available;
    }

    /** @return array<string, string> */
    public function dictionary(): array
    {
        return $this->dictionary;
    }

    /** @param array<string, string|int> $params */
    public function t(string $key, array $params = []): string
    {
        $value = $this->dictionary[$key] ?? $key;
        foreach ($params as $name => $replacement) {
            $value = str_replace('{' . $name . '}', (string) $replacement, $value);
        }
        return $value;
    }

    private static function isSupported(string $code): bool
    {
        foreach (self::SUPPORTED as $supported => $aliases) {
            if ($code === $supported || in_array($code, $aliases, true)) {
                return true;
            }
        }
        return false;
    }

    private static function normalize(string $code): string
    {
        foreach (self::SUPPORTED as $supported => $aliases) {
            if ($code === $supported || in_array($code, $aliases, true)) {
                return $supported;
            }
        }
        return self::DEFAULT;
    }

    /** @return array<string, string> */
    private function load(string $lang): array
    {
        $file = $this->langDir . '/' . $lang . '.json';
        if (!is_file($file)) {
            $file = $this->langDir . '/' . self::DEFAULT . '.json';
        }
        $raw = is_file($file) ? @file_get_contents($file) : false;
        $data = $raw === false ? null : json_decode($raw, true);
        return is_array($data) ? array_map(static fn ($v): string => (string) $v, $data) : [];
    }

    /** @return list<string> */
    private function discover(): array
    {
        $found = [];
        foreach (glob($this->langDir . '/*.json') ?: [] as $file) {
            $found[] = basename($file, '.json');
        }
        sort($found);
        return $found === [] ? [self::DEFAULT] : $found;
    }
}

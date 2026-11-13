<?php
declare(strict_types=1);

namespace Seharnes\Panel\Domain\Harness;

/**
 * Состояние переноса харнеса: источник обновления, квитанция установки, корень.
 *
 * Только чтение: класс ничего не меняет, поэтому его безопасно звать на каждый
 * просмотр страницы «Контроль харнеса». Источники — те же файлы, что у старой
 * админки: .doc/harness-source.json и .doc/web/state/transfer/receipt.json.
 */
final class HarnessStatus
{
    private const SOURCES = ['.doc/harness-source.json', '.doc/harness-source.example.json'];

    public function __construct(private readonly string $rootDir)
    {
    }

    /**
     * Источник обновления из Git.
     *
     * Настроенным считается только harness-source.json: example-файл показывает
     * пример и не должен выглядеть как рабочий источник.
     *
     * @return array{configured: bool, file: string, url: string, ref: string, profile: string}
     */
    public function source(): array
    {
        foreach (self::SOURCES as $name) {
            $data = $this->readJson($this->rootDir . '/' . $name);
            if ($data === null) {
                continue;
            }
            return [
                'configured' => $name === self::SOURCES[0],
                'file' => $name,
                'url' => (string) ($data['url'] ?? ''),
                'ref' => (string) ($data['ref'] ?? ''),
                'profile' => (string) ($data['profile'] ?? ''),
            ];
        }
        return ['configured' => false, 'file' => '', 'url' => '', 'ref' => '', 'profile' => ''];
    }

    /**
     * Квитанция последней установки: она же baseline для «локально изменённых».
     *
     * @return array{present: bool, profile: string, commit: string, files: int, mtime: string}
     */
    public function receipt(): array
    {
        $path = $this->rootDir . '/.doc/web/state/transfer/receipt.json';
        $data = $this->readJson($path);
        if ($data === null) {
            return ['present' => false, 'profile' => '', 'commit' => '', 'files' => 0, 'mtime' => ''];
        }
        $files = $data['files'] ?? null;
        return [
            'present' => true,
            'profile' => (string) ($data['profile'] ?? ''),
            'commit' => substr((string) ($data['commit'] ?? ''), 0, 12),
            'files' => is_array($files) ? count($files) : 0,
            'mtime' => date('Y-m-d H:i', (int) filemtime($path)),
        ];
    }

    /**
     * Полный снимок для страницы и API.
     *
     * @return array{root: string, source: array<string, mixed>, receipt: array<string, mixed>}
     */
    public function snapshot(): array
    {
        return [
            'root' => $this->rootDir,
            'source' => $this->source(),
            'receipt' => $this->receipt(),
        ];
    }

    /** @return array<string, mixed>|null */
    private function readJson(string $path): ?array
    {
        if (!is_file($path)) {
            return null;
        }
        $raw = @file_get_contents($path);
        if ($raw === false) {
            return null;
        }
        $data = json_decode($raw, true);
        return is_array($data) ? $data : null;
    }
}

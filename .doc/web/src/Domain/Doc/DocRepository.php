<?php
declare(strict_types=1);

namespace Seharnes\Panel\Domain\Doc;

use FilesystemIterator;
use RecursiveDirectoryIterator;
use RecursiveIteratorIterator;
use Seharnes\Panel\Support\Markdown;
use Seharnes\Panel\Support\PathGuard;
use Seharnes\Panel\Support\Text;

/**
 * Единственный источник канонической документации проекта.
 *
 * Источники (порядок важен для списка):
 *   architecture — .doc/architecture/*.json (машинное описание) и *.md;
 *   harnes       — .doc/harnes/**\/*.md (канон харнеса, 70+ документов).
 *
 * Правила: файлы и каталоги с "_" в начале служебные и в список не попадают;
 * любой путь проверяется PathGuard, наружу отдаётся только то, что лежит в .doc.
 */
final class DocRepository
{
    private const SOURCES = [
        'architecture' => 'architecture',
        'harnes' => 'harnes',
    ];

    /** @var null|list<DocItem> */
    private ?array $cache = null;

    public function __construct(private readonly string $docDir)
    {
    }

    /** @return list<string> Коды источников, по которым есть каталог. */
    public function sources(): array
    {
        $present = [];
        foreach (self::SOURCES as $code => $dir) {
            if (is_dir($this->docDir . '/' . $dir)) {
                $present[] = $code;
            }
        }
        return $present;
    }

    /** @return list<DocItem> */
    public function all(): array
    {
        if ($this->cache !== null) {
            return $this->cache;
        }
        $items = [];
        foreach ($this->sources() as $source) {
            $dir = $this->docDir . '/' . self::SOURCES[$source];
            foreach ($this->collect($source, $dir) as $item) {
                $items[] = $item;
            }
        }
        usort($items, static function (DocItem $a, DocItem $b): int {
            if ($a->source !== $b->source) {
                return strcmp($a->source, $b->source);
            }
            return strcasecmp($a->title, $b->title);
        });
        return $this->cache = $items;
    }

    /** @return list<DocItem> */
    public function filter(?string $query = null, ?string $source = null): array
    {
        $query = trim((string) $query);
        return array_values(array_filter($this->all(), static function (DocItem $item) use ($query, $source): bool {
            if ($source !== null && $source !== '' && $item->source !== $source) {
                return false;
            }
            return Text::contains($item->title . ' ' . $item->path . ' ' . $item->status, $query);
        }));
    }

    /** @return array<string, list<DocItem>> Список, сгруппированный по источнику. */
    public function grouped(?string $query = null, ?string $source = null): array
    {
        $groups = [];
        foreach ($this->filter($query, $source) as $item) {
            $groups[$item->source][] = $item;
        }
        return $groups;
    }

    public function find(string $id): ?DocItem
    {
        $id = trim($id, '/');
        if ($id === '') {
            return null;
        }
        foreach ($this->all() as $item) {
            if ($item->id === $id) {
                return $item;
            }
        }
        // Совместимость со старыми ссылками: doc=foo ищет architecture/foo.
        if (!str_contains($id, '/') && PathGuard::safeId($id)) {
            foreach ($this->all() as $item) {
                if ($item->id === 'architecture/' . $id) {
                    return $item;
                }
            }
        }
        return null;
    }

    /** @return list<DocItem> */
    private function collect(string $source, string $dir): array
    {
        $items = [];
        if ($source === 'architecture') {
            foreach (glob($dir . '/*.json') ?: [] as $file) {
                $name = basename($file, '.json');
                if (str_starts_with($name, '_')) {
                    continue;
                }
                $item = $this->fromJson($source, $file, 'architecture/' . $name);
                if ($item !== null) {
                    $items[] = $item;
                }
            }
        }
        foreach ($this->markdownFiles($dir) as $file) {
            $relative = PathGuard::relative($dir, $file);
            $id = $source . '/' . substr($relative, 0, -3);
            if (!PathGuard::safeId($id)) {
                continue;
            }
            $item = $this->fromMarkdown($source, $file, $id);
            if ($item !== null) {
                $items[] = $item;
            }
        }
        return $items;
    }

    /** @return list<string> */
    private function markdownFiles(string $dir): array
    {
        $iterator = new RecursiveIteratorIterator(
            new RecursiveDirectoryIterator($dir, FilesystemIterator::SKIP_DOTS)
        );
        $files = [];
        foreach ($iterator as $file) {
            if (!$file->isFile() || strtolower($file->getExtension()) !== 'md') {
                continue;
            }
            $absolute = $file->getPathname();
            $relative = PathGuard::relative($dir, $absolute);
            $skip = false;
            foreach (explode('/', $relative) as $segment) {
                if ($segment === '' || $segment[0] === '_' || $segment[0] === '.') {
                    $skip = true;
                    break;
                }
            }
            if (!$skip) {
                $files[] = $absolute;
            }
        }
        sort($files);
        return $files;
    }

    private function fromMarkdown(string $source, string $file, string $id): ?DocItem
    {
        $raw = $this->read($file);
        if ($raw === null) {
            return null;
        }
        $meta = FrontMatter::parse($raw);
        $mtime = (int) @filemtime($file);
        return new DocItem(
            id: $id,
            source: $source,
            path: PathGuard::relative($this->docDir, $file),
            format: 'md',
            title: $meta['title'] ?? Markdown::firstHeading($raw, basename($file, '.md')),
            status: $meta['status'] ?? '',
            updated: $meta['updated'] ?? gmdate('Y-m-d', $mtime),
            absolutePath: $file,
            mtime: $mtime,
            toc: Markdown::toc($raw),
            markdown: $raw,
        );
    }

    private function fromJson(string $source, string $file, string $id): ?DocItem
    {
        $raw = $this->read($file);
        if ($raw === null) {
            return null;
        }
        $data = json_decode($raw, true);
        if (!is_array($data)) {
            return null;
        }
        $meta = is_array($data['metadata'] ?? null) ? $data['metadata'] : [];
        $sections = is_array($data['sections'] ?? null) ? array_values($data['sections']) : [];
        $findings = is_array($data['findings'] ?? null) ? array_values($data['findings']) : [];
        $toc = [];
        foreach ($sections as $index => $section) {
            $toc[] = [
                'id' => (string) ($section['id'] ?? 'sec-' . ($index + 1)),
                'title' => Markdown::plain((string) ($section['title'] ?? '')),
                'level' => 2,
            ];
        }
        $fallback = PathGuard::fileWithin(dirname($file), basename($file, '.json') . '.md');
        return new DocItem(
            id: $id,
            source: $source,
            path: PathGuard::relative($this->docDir, $file),
            format: 'json',
            title: Markdown::plain((string) ($meta['title'] ?? $id)),
            status: (string) ($meta['source_status'] ?? $meta['status'] ?? ''),
            updated: (string) ($meta['updated_at'] ?? $meta['updated'] ?? ''),
            absolutePath: $file,
            mtime: (int) @filemtime($file),
            toc: $toc,
            sections: array_map(static fn (array $section): array => [
                'id' => (string) ($section['id'] ?? ''),
                'title' => (string) ($section['title'] ?? ''),
                'body_markdown' => (string) ($section['body_markdown'] ?? ''),
            ], $sections),
            findings: array_map(static fn (array $finding): array => [
                'id' => (string) ($finding['id'] ?? ''),
                'title' => (string) ($finding['title'] ?? ''),
                'statement' => (string) ($finding['statement'] ?? ''),
            ], $findings),
            markdown: $fallback !== null ? $this->read($fallback) : null,
        );
    }

    private function read(string $file): ?string
    {
        $docReal = realpath($this->docDir);
        $real = realpath($file);
        if ($docReal === false || $real === false || !str_starts_with($real, $docReal . DIRECTORY_SEPARATOR)) {
            return null;
        }
        $raw = @file_get_contents($real);
        return $raw === false ? null : $raw;
    }
}

<?php
declare(strict_types=1);

namespace Seharnes\Panel\Domain\Doc;

/**
 * Документ канонической документации: значение, а не поведение.
 *
 * Один и тот же объект отдаётся и в новый интерфейс (toArray), и старым страницам
 * (toLegacyRow), поэтому формат данных не разъезжается между двумя UI.
 */
final class DocItem
{
    /**
     * @param list<array{id: string, title: string, level: int}> $toc
     * @param list<array{id: string, title: string, body_markdown: string}> $sections
     * @param list<array{id: string, title: string, statement: string}> $findings
     */
    public function __construct(
        public readonly string $id,
        public readonly string $source,
        public readonly string $path,
        public readonly string $format,
        public readonly string $title,
        public readonly string $status,
        public readonly string $updated,
        public readonly string $absolutePath,
        public readonly int $mtime,
        public readonly array $toc = [],
        public readonly array $sections = [],
        public readonly array $findings = [],
        public readonly ?string $markdown = null,
    ) {
    }

    public function hasStructuredSections(): bool
    {
        return $this->sections !== [];
    }

    /** @return array<string, mixed> */
    public function toArray(): array
    {
        return [
            'id' => $this->id,
            'source' => $this->source,
            'path' => $this->path,
            'format' => $this->format,
            'title' => $this->title,
            'status' => $this->status,
            'updated' => $this->updated,
            'mtime' => $this->mtime,
            'toc' => $this->toc,
            'nSections' => count($this->sections),
            'nFindings' => count($this->findings),
        ];
    }

    /** @return array<string, mixed> Совместимость со старыми страницами панели. */
    public function toLegacyRow(): array
    {
        return [
            'name' => $this->id,
            'id' => $this->id,
            'source' => $this->source,
            'source_label' => $this->source,
            'ext' => $this->format,
            'path' => $this->path,
            'title' => $this->title,
            'status' => $this->status,
            'updated' => $this->updated,
            'updated_fmt' => $this->updated,
            'n_sections' => count($this->sections),
            'n_findings' => count($this->findings),
            'mtime' => $this->mtime,
        ];
    }
}

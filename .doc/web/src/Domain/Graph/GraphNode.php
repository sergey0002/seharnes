<?php
declare(strict_types=1);

namespace Seharnes\Panel\Domain\Graph;

/**
 * Узел графа харнеса.
 *
 * Тип узла определяет, как показать его в правой панели:
 * skill/doc/rule/mcp — markdown, script/config — как файл, прочее — как есть.
 */
final class GraphNode
{
    /** @param array<string, mixed> $raw */
    public function __construct(
        public readonly string $id,
        public readonly string $kind,
        public readonly string $label,
        public readonly string $path,
        public readonly array $raw,
    ) {
    }

    /** @param array<string, mixed> $node */
    public static function fromIndex(array $node): self
    {
        $id = (string) ($node['id'] ?? '');
        return new self(
            id: $id,
            kind: (string) ($node['type'] ?? 'unknown'),
            label: (string) ($node['label'] ?? $id),
            path: (string) ($node['path'] ?? ''),
            raw: $node,
        );
    }

    public function isTextual(): bool
    {
        return in_array($this->kind, ['doc', 'rule', 'skill'], true);
    }

    /** @return array<string, mixed> */
    public function toArray(): array
    {
        return [
            'id' => $this->id,
            'kind' => $this->kind,
            'label' => $this->label,
            'path' => $this->path,
            'environment' => (string) ($this->raw['environment'] ?? ''),
            'canonical' => (bool) ($this->raw['canonical'] ?? false),
            'description' => (string) ($this->raw['description'] ?? ''),
            'analysis' => (string) ($this->raw['analysis'] ?? ''),
            'transferable' => (bool) ($this->raw['transferable'] ?? false),
        ];
    }
}

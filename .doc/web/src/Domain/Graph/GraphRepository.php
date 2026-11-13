<?php
declare(strict_types=1);

namespace Seharnes\Panel\Domain\Graph;

use Seharnes\Panel\Support\PathGuard;

/**
 * Чтение сгенерированного графа харнеса (его строит harness_mirror.py).
 *
 * Репозиторий только читает: graph.json, nodes/*.json. Если каталога данных нет,
 * вызывающий получает пустое состояние с подсказкой, а не 500.
 */
final class GraphRepository
{
    /** @var array<string, mixed>|null */
    private ?array $graph = null;

    public function __construct(
        private readonly string $dataDir,
        private readonly string $rootDir = '',
    ) {
    }

    public function exists(): bool
    {
        return PathGuard::fileWithin($this->dataDir, 'graph.json') !== null;
    }

    /** @return array<string, mixed> */
    public function summary(): array
    {
        $graph = $this->graph();
        if ($graph === null) {
            return ['available' => false, 'nodes' => 0, 'edges' => 0, 'kinds' => [], 'stats' => []];
        }
        $kinds = [];
        foreach ($graph['nodes'] ?? [] as $node) {
            $kind = (string) ($node['type'] ?? 'unknown');
            $kinds[$kind] = ($kinds[$kind] ?? 0) + 1;
        }
        ksort($kinds);
        return [
            'available' => true,
            'nodes' => count($graph['nodes'] ?? []),
            'edges' => count($graph['edges'] ?? []),
            'kinds' => $kinds,
            'stats' => is_array($graph['stats'] ?? null) ? $graph['stats'] : [],
            'schema' => (string) ($graph['schema'] ?? ''),
        ];
    }

    /**
     * Компактный граф для отрисовки: без содержимого файлов.
     *
     * @return array{nodes: list<array<string, mixed>>, edges: list<array<string, mixed>>}
     */
    public function view(?string $kind = null, bool $linkedOnly = false): array
    {
        $graph = $this->graph();
        if ($graph === null) {
            return ['nodes' => [], 'edges' => []];
        }
        $edges = array_values(array_filter(
            is_array($graph['edges'] ?? null) ? $graph['edges'] : [],
            static fn ($edge): bool => is_array($edge)
        ));
        $linked = [];
        foreach ($edges as $edge) {
            $linked[(string) ($edge['source'] ?? '')] = true;
            $linked[(string) ($edge['target'] ?? '')] = true;
        }
        $nodes = [];
        foreach ($graph['nodes'] ?? [] as $node) {
            if (!is_array($node)) {
                continue;
            }
            $nodeKind = (string) ($node['type'] ?? '');
            if ($kind !== null && $kind !== '' && $nodeKind !== $kind) {
                continue;
            }
            $id = (string) ($node['id'] ?? '');
            if ($linkedOnly && !isset($linked[$id])) {
                continue;
            }
            // Дерево и карточки графа показывают реальную структуру файлов, поэтому
            // кроме пути отдаём имя файла и короткое описание: второй запрос на узел
            // ради подписи в списке не нужен.
            $summary = trim((string) ($node['summary'] ?? ''));
            if ($summary === '') {
                $summary = trim((string) ($node['heading'] ?? ''));
            }
            $nodes[] = [
                'id' => $id,
                'kind' => $nodeKind,
                'label' => (string) ($node['label'] ?? $id),
                'path' => (string) ($node['path'] ?? ''),
                'file' => (string) ($node['file'] ?? basename((string) ($node['path'] ?? ''))),
                'summary' => self::shorten($summary, 140),
                'analysis' => (string) ($node['analysis'] ?? ''),
                'environment' => (string) ($node['environment'] ?? ''),
                'canonical' => (bool) ($node['canonical'] ?? false),
            ];
        }
        $ids = [];
        foreach ($nodes as $node) {
            $ids[$node['id']] = true;
        }
        $edges = array_values(array_filter($edges, static fn (array $edge): bool => isset($ids[(string) ($edge['source'] ?? '')]) && isset($ids[(string) ($edge['target'] ?? '')])));
        return ['nodes' => $nodes, 'edges' => array_map(static fn (array $edge): array => [
            'source' => (string) ($edge['source'] ?? ''),
            'target' => (string) ($edge['target'] ?? ''),
            'type' => (string) ($edge['type'] ?? ''),
        ], $edges)];
    }

    /** Обрезка длинного описания без mbstring: по словам, чтобы не рвать буквы. */
    private static function shorten(string $text, int $limit): string
    {
        $text = trim(preg_replace('/\s+/u', ' ', $text) ?? '');
        if ($text === '' || strlen($text) <= $limit) {
            return $text;
        }
        $cut = substr($text, 0, $limit);
        // substr режет байты: отступаем к границе символа UTF-8.
        while ($cut !== '' && (ord($cut[strlen($cut) - 1]) & 0xC0) === 0x80) {
            $cut = substr($cut, 0, -1);
        }
        $space = strrpos($cut, ' ');
        return ($space !== false ? substr($cut, 0, $space) : $cut) . '…';
    }

    public function find(string $id): ?GraphNode
    {
        $graph = $this->graph();
        if ($graph === null) {
            return null;
        }
        foreach ($graph['nodes'] ?? [] as $node) {
            if (is_array($node) && (string) ($node['id'] ?? '') === $id) {
                return GraphNode::fromIndex($node);
            }
        }
        return null;
    }

    /**
     * Содержимое узла: текст файла из nodes/*.json плюс связи.
     *
     * @return array<string, mixed>
     */
    public function detail(string $id): array
    {
        $node = $this->find($id);
        if ($node === null) {
            return ['status' => 'failed', 'error' => 'node not found'];
        }
        $payload = ['node' => $node->toArray(), 'relations' => $this->relations($id), 'blocks' => []];
        $file = PathGuard::fileWithin($this->dataDir, (string) ($node->raw['json'] ?? ''));
        $data = $file !== null ? json_decode((string) @file_get_contents($file), true) : null;
        if (!is_array($data)) {
            return $payload + ['status' => 'empty'];
        }
        $blocks = [];
        foreach ($data['content_blocks'] ?? [] as $block) {
            if (!is_array($block)) {
                continue;
            }
            $raw = (string) ($block['raw_content'] ?? '');
            $blocks[] = [
                'id' => (string) ($block['block_id'] ?? ''),
                'type' => (string) ($block['block_type'] ?? ''),
                'header' => (string) ($block['header_text'] ?? ''),
                'raw' => $raw,
            ];
        }
        $payload['blocks'] = $blocks;
        $payload['node_kind'] = $node->kind;
        $payload['file'] = $this->fileInfo($node);
        $payload['meta'] = [
            'global_relations' => is_array($data['global_relations'] ?? null) ? count($data['global_relations']) : 0,
            'sources_of_truth' => is_array($data['sources_of_truth'] ?? null) ? $data['sources_of_truth'] : [],
            'lifecycle' => is_array($data['lifecycle'] ?? null) ? $data['lifecycle'] : [],
        ];
        $payload['status'] = 'ok';
        return $payload;
    }

    /**
     * Файл узла: путь, размер, право на правку и текст для редактора.
     *
     * Текст отдаётся только для файлов, которые панель имеет право менять:
     * так редактор не появляется там, где запись всё равно запрещена.
     *
     * @return array<string, mixed>
     */
    private function fileInfo(GraphNode $node): array
    {
        $policy = EditPolicy::check($node, $this->rootDir);
        if (!$policy['editable'] || $policy['absolute'] === null) {
            return ['editable' => false, 'reason' => $policy['reason'], 'path' => $node->path];
        }
        $content = @file_get_contents((string) $policy['absolute']);
        return [
            'editable' => true,
            'reason' => '',
            'path' => $node->path,
            'size' => $policy['size'],
            'content' => $content === false ? '' : $content,
        ];
    }

    /**
     * Связи узла в обе стороны, с человекочитаемым направлением.
     *
     * @return list<array{type: string, direction: string, id: string, label: string, kind: string}>
     */
    public function relations(string $id): array
    {
        $graph = $this->graph();
        if ($graph === null) {
            return [];
        }
        $labels = [];
        foreach ($graph['nodes'] ?? [] as $node) {
            if (is_array($node)) {
                $labels[(string) ($node['id'] ?? '')] = [
                    'label' => (string) ($node['label'] ?? ''),
                    'kind' => (string) ($node['type'] ?? ''),
                ];
            }
        }
        $relations = [];
        foreach ($graph['edges'] ?? [] as $edge) {
            if (!is_array($edge)) {
                continue;
            }
            $source = (string) ($edge['source'] ?? '');
            $target = (string) ($edge['target'] ?? '');
            if ($source === $id) {
                $other = $target;
                $direction = 'out';
            } elseif ($target === $id) {
                $other = $source;
                $direction = 'in';
            } else {
                continue;
            }
            $relations[] = [
                'type' => (string) ($edge['type'] ?? ''),
                'direction' => $direction,
                'id' => $other,
                'label' => $labels[$other]['label'] ?? $other,
                'kind' => $labels[$other]['kind'] ?? '',
            ];
        }
        usort($relations, static fn (array $a, array $b): int => strcmp($a['type'] . $a['id'], $b['type'] . $b['id']));
        return $relations;
    }

    /** @return array<string, mixed>|null */
    private function graph(): ?array
    {
        if ($this->graph !== null) {
            return $this->graph;
        }
        $file = PathGuard::fileWithin($this->dataDir, 'graph.json');
        if ($file === null) {
            return null;
        }
        $raw = @file_get_contents($file);
        $data = $raw === false ? null : json_decode($raw, true);
        if (!is_array($data)) {
            return null;
        }
        return $this->graph = $data;
    }

}

<?php
declare(strict_types=1);

use Seharnes\Panel\Core\Config;
use Seharnes\Panel\Domain\Doc\DocRepository;
use Seharnes\Panel\Domain\Graph\EditPolicy;
use Seharnes\Panel\Domain\Graph\GraphNode;
use Seharnes\Panel\Domain\Graph\GraphRepository;
use Seharnes\Panel\Domain\Job\JobRepository;

/** Готовит каталог .doc с двумя источниками документации. */
function makeDocs(string $root): string
{
    $doc = $root . '/.doc';
    writeFile($doc . '/harnes/state/01-alpha.md', "# Альфа\n\n<!-- meta\nstatus: actual\nupdated: 2026-11-13\n-->\n\n## Суть\n\nТекст альфы.\n");
    writeFile($doc . '/harnes/plan/beta.md', "# Бета\n\n## Раздел\n\nТекст беты.\n");
    writeFile($doc . '/harnes/_hidden.md', "# Скрытый\n");
    writeFile($doc . '/architecture/demo.json', json_encode([
        'metadata' => ['title' => 'Демо', 'source_status' => 'actual', 'updated_at' => '2026-11-01'],
        'sections' => [['id' => 's1', 'title' => 'Раздел JSON', 'body_markdown' => 'Тело.']],
        'findings' => [['id' => 'F-1', 'title' => 'Находка', 'statement' => 'Описание.']],
    ], JSON_UNESCAPED_UNICODE));
    writeFile($doc . '/architecture/_service.json', '{"metadata":{"title":"служебный"}}');
    return $doc;
}

return [
    'doc repository lists md and json, skips underscore' => static function (): void {
        withTempDir(static function (string $root): void {
            $doc = makeDocs($root);
            $repo = new DocRepository($doc);
            $items = $repo->all();

            Assert::same(3, count($items), 'three visible documents');
            $ids = array_map(static fn ($item): string => $item->id, $items);
            sort($ids);
            Assert::same(['architecture/demo', 'harnes/plan/beta', 'harnes/state/01-alpha'], $ids);
            Assert::same(['architecture', 'harnes'], $repo->sources());
        });
    },

    'doc repository reads front matter and toc' => static function (): void {
        withTempDir(static function (string $root): void {
            $repo = new DocRepository(makeDocs($root));
            $doc = $repo->find('harnes/state/01-alpha');
            Assert::notNull($doc);
            Assert::same('Альфа', $doc->title);
            Assert::same('actual', $doc->status);
            Assert::same('2026-11-13', $doc->updated);
            Assert::same('harnes/state/01-alpha.md', $doc->path);
            Assert::same(1, count($doc->toc));
        });
    },

    'doc repository falls back to file name and mtime' => static function (): void {
        withTempDir(static function (string $root): void {
            $repo = new DocRepository(makeDocs($root));
            $doc = $repo->find('harnes/plan/beta');
            Assert::notNull($doc);
            Assert::same('Бета', $doc->title);
            Assert::same('', $doc->status);
            Assert::true($doc->updated !== '', 'updated falls back to file date');
        });
    },

    'doc repository resolves json sections and legacy ids' => static function (): void {
        withTempDir(static function (string $root): void {
            $repo = new DocRepository(makeDocs($root));
            $doc = $repo->find('demo');
            Assert::notNull($doc, 'legacy bare id resolves to architecture/*');
            Assert::same('architecture/demo', $doc->id);
            Assert::same('Демо', $doc->title);
            Assert::same(1, count($doc->sections));
            Assert::contains('Тело.', $doc->sections[0]['body_markdown'], 'domain keeps raw markdown, view renders it');
            Assert::same(1, count($doc->findings));
        });
    },

    'doc repository filters by query and source' => static function (): void {
        withTempDir(static function (string $root): void {
            $repo = new DocRepository(makeDocs($root));
            Assert::same(1, count($repo->filter('бета')));
            Assert::same(1, count($repo->filter(null, 'architecture')));
            Assert::same(0, count($repo->filter('нет-такого')));
            $groups = $repo->grouped();
            Assert::same(1, count($groups['architecture']));
            Assert::same(2, count($groups['harnes']));
        });
    },

    'doc repository rejects traversal and missing ids' => static function (): void {
        withTempDir(static function (string $root): void {
            writeFile($root . '/secret.md', "# SECRET\n");
            $repo = new DocRepository(makeDocs($root));
            Assert::same(null, $repo->find('../secret'));
            Assert::same(null, $repo->find('harnes/../../secret'));
            Assert::same(null, $repo->find('нет-документа'));
        });
    },

    'graph repository reports empty state without data dir' => static function (): void {
        $repo = new GraphRepository(sys_get_temp_dir() . '/no-such-mirror-' . bin2hex(random_bytes(4)));
        $summary = $repo->summary();
        Assert::false($summary['available']);
        Assert::same(0, $summary['nodes']);
        Assert::same([], $repo->view()['nodes']);
        Assert::same(null, $repo->find('skill:x'));
    },

    'graph repository reads summary, view and relations' => static function (): void {
        withTempDir(static function (string $data): void {
            $nodes = [
                ['id' => 'skill:a', 'type' => 'skill', 'label' => 'a', 'path' => '.agents/skills/a/SKILL.md', 'environment' => 'agents', 'canonical' => true, 'json' => 'nodes/skill__a.json'],
                ['id' => 'rule:b', 'type' => 'rule', 'label' => 'b', 'path' => '.cursor/rules/b.mdc', 'environment' => 'cursor', 'canonical' => true, 'json' => 'nodes/rule__b.json'],
                ['id' => 'doc:c', 'type' => 'doc', 'label' => 'c', 'path' => '.doc/c.md', 'environment' => 'docs', 'canonical' => false, 'json' => 'nodes/doc__c.json'],
                ['id' => 'config:d', 'type' => 'config', 'label' => 'd', 'path' => 'config/d.json', 'environment' => 'agents', 'canonical' => true, 'json' => 'nodes/config__d.json'],
            ];
            $edges = [
                ['source' => 'skill:a', 'target' => 'rule:b', 'type' => 'governed_by'],
                ['source' => 'skill:a', 'target' => 'doc:c', 'type' => 'reads_context'],
            ];
            writeFile($data . '/graph.json', json_encode([
                'schema' => 'harness-graph/2.3',
                'nodes' => $nodes,
                'edges' => $edges,
                'stats' => ['canonical' => 2, 'drift' => 0],
            ], JSON_UNESCAPED_UNICODE));
            writeFile($data . '/nodes/skill__a.json', json_encode([
                'content_blocks' => [
                    ['block_id' => 'b000', 'block_type' => 'frontmatter', 'raw_content' => "---\nname: a\n---", 'header_text' => null],
                    ['block_id' => 'b001', 'block_type' => 'body', 'raw_content' => "## Суть\n\nТекст узла.", 'header_text' => ''],
                ],
            ], JSON_UNESCAPED_UNICODE));

            $repo = new GraphRepository($data);
            $summary = $repo->summary();
            Assert::true($summary['available']);
            Assert::same(4, $summary['nodes']);
            Assert::same(2, $summary['edges']);
            Assert::same(1, $summary['kinds']['skill']);

            Assert::same(1, count($repo->view('rule')['nodes']));
            $linked = $repo->view(null, true)['nodes'];
            Assert::same(3, count($linked), 'only nodes with edges survive the filter');
            Assert::false(in_array('config:d', array_column($linked, 'id'), true), 'config:d has no edges and must be excluded');

            $detail = $repo->detail('skill:a');
            Assert::same('ok', $detail['status']);
            Assert::same(2, count($detail['blocks']));
            Assert::same('frontmatter', $detail['blocks'][0]['type']);
            Assert::contains('name: a', $detail['blocks'][0]['raw'], 'frontmatter block keeps raw yaml');
            Assert::same('body', $detail['blocks'][1]['type']);
            Assert::contains('Суть', $detail['blocks'][1]['raw']);
            Assert::same('skill', $detail['node_kind']);
            Assert::same(2, count($detail['relations']));
            Assert::same('out', $detail['relations'][0]['direction']);

            $incoming = $repo->relations('rule:b');
            Assert::same(1, count($incoming));
            Assert::same('in', $incoming[0]['direction']);

            Assert::same('failed', $repo->detail('skill:нет')['status']);
        });
    },

    'job repository reads status and tail' => static function (): void {
        withTempDir(static function (string $state): void {
            $id = 'job_20260101_101010_abcd';
            writeFile($state . '/jobs/' . $id . '/status.json', json_encode([
                'action' => 'harness_build', 'label' => 'Пересобрать', 'status' => 'ok',
                'progress' => 100, 'started_at' => '2026-01-01T10:10:10Z', 'ended_at' => '2026-01-01T10:10:20Z', 'exit_code' => 0,
            ], JSON_UNESCAPED_UNICODE));
            writeFile($state . '/jobs/' . $id . '/log.txt', "line1\nline2\nline3\n");

            $repo = new JobRepository($state);
            $recent = $repo->recent();
            Assert::same(1, count($recent));
            Assert::same('harness_build', $recent[0]['action']);

            $status = $repo->status($id, 2);
            Assert::notNull($status);
            Assert::same(['line2', 'line3'], $status['log_tail']);
            Assert::same(null, $repo->status('../../etc/passwd'));
            Assert::same(null, $repo->status('job_20260101_101010_0000'));
        });
    },

    'config resolves service paths' => static function (): void {
        withTempDir(static function (string $root): void {
            writeFile($root . '/.doc/web/config/service.json', json_encode([
                'data_dir' => '.doc/skil_data/mirror', 'state_dir' => '.doc/web/state', 'profile' => 'core', 'writable' => false,
            ]));
            writeFile($root . '/.doc/web/config/actions.json', json_encode([
                'actions' => [
                    ['id' => 'a1', 'enabled' => true, 'label' => 'A1'],
                    ['id' => 'a2', 'enabled' => false, 'label' => 'A2'],
                ],
            ]));
            $config = Config::fromWebDir($root . '/.doc/web');
            Assert::same($root . '/.doc/skil_data/mirror', $config->dataDir());
            Assert::same($root . '/.doc/web/state', $config->stateDir());
            Assert::same('core', $config->profile());
            Assert::false($config->isWritable());
            Assert::same(2, count($config->actions()));
            Assert::same('A1', $config->action('a1')['label']);
            Assert::same(null, $config->action('nope'));
        });
    },
    'edit policy allows only canonical text files inside the repo' => static function (): void {
        withTempDir(static function (string $root): void {
            writeFile($root . '/.agents/skills/demo/SKILL.md', "# demo\n");
            $node = static fn (array $raw): GraphNode => GraphNode::fromIndex($raw + [
                'id' => 'skill:demo', 'type' => 'skill', 'label' => 'demo',
                'path' => '.agents/skills/demo/SKILL.md', 'canonical' => true,
            ]);

            $allowed = EditPolicy::check($node([]), $root);
            Assert::true($allowed['editable'], 'canonical md inside repo is editable');
            Assert::true($allowed['size'] > 0);

            Assert::same('copy', EditPolicy::check($node(['canonical' => false]), $root)['reason']);
            Assert::same('no-path', EditPolicy::check($node(['path' => '']), $root)['reason']);
            Assert::same('binary', EditPolicy::check($node(['path' => '.agents/a.bin']), $root)['reason']);
            Assert::same('outside-repo', EditPolicy::check($node(['path' => '../outside.md']), $root)['reason']);
            Assert::same('outside-repo', EditPolicy::check($node(['path' => '.agents/skills/gone/SKILL.md']), $root)['reason']);
        });
    },

    'graph detail marks file editable and returns content' => static function (): void {
        withTempDir(static function (string $root): void {
            $data = $root . '/.doc/skil_data/mirror';
            writeFile($data . '/graph.json', json_encode([
                'nodes' => [[
                    'id' => 'skill:a', 'type' => 'skill', 'label' => 'a',
                    'path' => '.agents/skills/a/SKILL.md', 'canonical' => true, 'json' => 'nodes/skill__a.json',
                ]],
                'edges' => [],
            ], JSON_UNESCAPED_UNICODE));
            writeFile($data . '/nodes/skill__a.json', json_encode([
                'content_blocks' => [['block_id' => 'b', 'block_type' => 'body', 'raw_content' => "## Суть\n\nТекст.", 'header_text' => '']],
            ], JSON_UNESCAPED_UNICODE));
            writeFile($root . '/.agents/skills/a/SKILL.md', "# a\n\n## Суть\n\nТекст.\n");
            $repo = new GraphRepository($data, $root);
            $detail = $repo->detail('skill:a');
            Assert::true($detail['file']['editable'], 'skill file is editable');
            Assert::contains('Суть', $detail['file']['content']);
            Assert::same('.agents/skills/a/SKILL.md', $detail['file']['path']);

            $readonly = new GraphRepository($data);
            $plain = $readonly->detail('skill:a');
            Assert::false($plain['file']['editable'], 'without repo root nothing is writable');
            Assert::same('no-root', $plain['file']['reason']);
        });
    },
];

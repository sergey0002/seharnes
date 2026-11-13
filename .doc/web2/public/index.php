<?php
// .doc/web/public/index.php - панель харнеса: задачи, документация, аналитика диалогов.
// Только чтение JSON/MD из .doc, без БД и без ИИ. Совместимость: PHP 7.1 - 8.x.
require_once __DIR__ . '/../app/lib.php';
require_once __DIR__ . '/../app/jobs.php';

function h($s) {
    return htmlspecialchars((string)$s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

// Минимальный рендер markdown из body_markdown (заголовки, списки, bold, код, ссылки, таблицы).
function md_render($text) {
    $text = preg_replace('/<!--[\s\S]*?-->/', '', (string)$text);
    $text = str_replace("\r\n", "\n", (string)$text);
    $chunks = preg_split('/(```[\s\S]*?```)/', $text, -1, PREG_SPLIT_DELIM_CAPTURE);
    $out = '';
    foreach ($chunks as $i => $c) {
        if ($i % 2 === 1) {
            $code = preg_replace('/^```[a-zA-Z0-9+\-]*\n?/', '', $c);
            $code = preg_replace('/```\s*$/', '', $code);
            $out .= '<pre><code>' . h($code) . '</code></pre>';
            continue;
        }
        $out .= md_block($c);
    }
    return $out;
}

function md_inline($s) {
    $s = h($s);
    $s = preg_replace('/`([^`]+)`/', '<code>$1</code>', $s);
    $s = preg_replace('/\[x\]/i', '<span class="task-check done">готово</span>', $s);
    $s = preg_replace('/\[ \]/', '<span class="task-check todo">не сделано</span>', $s);
    $s = preg_replace('/\*\*([^*]+)\*\*/', '<strong>$1</strong>', $s);
    $s = preg_replace_callback('/\[([^\]]+)\]\(([^)]+)\)/', function ($m) {
        $url = $m[2];
        if (!preg_match('~^(https?://|#|/|mailto:)~', $url)) {
            return $m[1];
        }
        return '<a href="' . h($url) . '">' . $m[1] . '</a>';
    }, $s);
    return $s;
}

function md_block($text) {
    $lines = explode("\n", $text);
    $html = '';
    $para = array();
    $list = array();
    $table = array();
    $flush_para = function () use (&$html, &$para) {
        if ($para) {
            $html .= '<p>' . nl2br(md_inline(implode("\n", $para))) . '</p>';
            $para = array();
        }
    };
    $flush_list = function () use (&$html, &$list, $flush_para) {
        $flush_para();
        if ($list) {
            $html .= '<ul>';
            foreach ($list as $li) {
                $html .= '<li>' . md_inline($li) . '</li>';
            }
            $html .= '</ul>';
            $list = array();
        }
    };
    $flush_table = function () use (&$html, &$table, $flush_list) {
        $flush_list();
        if ($table) {
            $html .= '<table>';
            foreach ($table as $ri => $row) {
                if (preg_match('/^[\s|:\-]+$/', $row)) {
                    continue;
                }
                $cells = array_map('trim', explode('|', trim($row, ' |')));
                $tag = $ri === 0 ? 'th' : 'td';
                $html .= '<tr>';
                foreach ($cells as $c) {
                    $html .= '<' . $tag . '>' . md_inline($c) . '</' . $tag . '>';
                }
                $html .= '</tr>';
            }
            $html .= '</table>';
            $table = array();
        }
    };
    foreach ($lines as $line) {
        $t = rtrim($line);
        if (preg_match('/^(#{1,4})\s+(.*)$/', $t, $m)) {
            $flush_table();
            $lvl = strlen($m[1]);
            $html .= '<h' . ($lvl + 2) . '>' . md_inline($m[2]) . '</h' . ($lvl + 2) . '>';
        } elseif (preg_match('/^(\d+\.\s+|[-*]\s+)(.*)$/', $t, $m)) {
            $flush_para();
            if ($table) {
                $flush_table();
            }
            $list[] = $m[2];
        } elseif (strpos($t, '|') !== false && substr_count($t, '|') >= 2) {
            $flush_para();
            if ($list) {
                $flush_list();
            }
            $table[] = $t;
        } elseif (trim($t) === '') {
            $flush_table();
        } else {
            if ($table) {
                $flush_table();
            }
            if ($list && !preg_match('/^(\s{2,}|\t)/', $line)) {
                $flush_list();
            }
            $para[] = $t;
        }
    }
    $flush_table();
    return $html;
}

function self_url($params) {
    return '/index.php?' . http_build_query($params);
}

function biz_text($value) {
    if (is_array($value)) {
        if (isset($value['text'])) {
            return (string)$value['text'];
        }
        $parts = array();
        foreach ($value as $item) {
            $parts[] = biz_text($item);
        }
        return implode("\n", $parts);
    }
    return (string)$value;
}

function chart_options($legend, $log = false) {
    $options = array(
        'responsive' => true,
        'maintainAspectRatio' => false,
        'plugins' => array('legend' => array('display' => $legend, 'position' => 'bottom')),
    );
    if (!$legend) {
        $options['scales'] = $log
            ? array('y' => array('type' => 'logarithmic', 'min' => 1))
            : array('y' => array('beginAtZero' => true));
    }
    return $options;
}

function bar_chart($labels, $values, $color) {
    return array(
        'type' => 'bar',
        'data' => array(
            'labels' => $labels,
            'datasets' => array(array(
                'data' => $values,
                'backgroundColor' => $color,
                'borderRadius' => 3,
            )),
        ),
        'options' => chart_options(false),
    );
}

function chart_colors($count) {
    $palette = array('#2563eb', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
        '#14b8a6', '#f97316', '#64748b', '#eab308', '#06b6d4', '#ec4899');
    $out = array();
    for ($i = 0; $i < $count; $i++) {
        $out[] = $palette[$i % count($palette)];
    }
    return $out;
}

function analytics_chart_configs($data, $prefix, $with_sessions = true, $findings_label = 'Сессии') {
    $charts = array();
    if (!is_array($data)) {
        return $charts;
    }
    if ($with_sessions && !empty($data['sessions'])) {
        $labels = array();
        $values = array();
        foreach (array_reverse($data['sessions']) as $row) {
            $labels[] = $row['date'] . ' ' . substr($row['session_id'], 0, 10);
            $values[] = $row['tokens'];
        }
        $charts[$prefix . 'Sessions'] = array(
            'type' => 'bar',
            'data' => array(
                'labels' => $labels,
                'datasets' => array(array(
                    'label' => 'Токены без кэша',
                    'data' => $values,
                    'backgroundColor' => '#2563eb',
                    'borderRadius' => 4,
                )),
            ),
            'options' => chart_options(false),
        );
    }
    if (!empty($data['findings'])) {
        $charts[$prefix . 'Findings'] = array(
            'type' => 'bar',
            'data' => array(
                'labels' => array_keys($data['findings']),
                'datasets' => array(array(
                    'label' => $findings_label,
                    'data' => array_values($data['findings']),
                    'backgroundColor' => '#f59e0b',
                    'borderRadius' => 4,
                )),
            ),
            'options' => chart_options(false),
        );
    }
    if (!empty($data['tools'])) {
        $tools = array_slice($data['tools'], 0, 8);
        $charts[$prefix . 'Tools'] = array(
            'type' => 'bar',
            'data' => array(
                'labels' => array_map(function ($row) { return $row['name']; }, $tools),
                'datasets' => array(array(
                    'label' => 'Вызовы',
                    'data' => array_map(function ($row) { return $row['calls']; }, $tools),
                    'backgroundColor' => '#10b981',
                    'borderRadius' => 4,
                )),
            ),
            'options' => chart_options(false),
        );
    }
    if (!empty($data['mcp'])) {
        $mcp_labels = array_map(function ($row) { return $row['server']; }, $data['mcp']);
        $charts[$prefix . 'McpIn'] = bar_chart($mcp_labels, array_map(function ($row) { return $row['tokens_in']; }, $data['mcp']), '#2563eb');
        $charts[$prefix . 'McpCache'] = bar_chart($mcp_labels, array_map(function ($row) { return $row['cache']; }, $data['mcp']), '#0ea5e9');
        $charts[$prefix . 'McpOut'] = bar_chart($mcp_labels, array_map(function ($row) { return $row['tokens_out']; }, $data['mcp']), '#10b981');
        $charts[$prefix . 'Mcp'] = array(
            'type' => 'doughnut',
            'data' => array(
                'labels' => $mcp_labels,
                'datasets' => array(array(
                    'data' => array_map(function ($row) { return $row['calls']; }, $data['mcp']),
                    'backgroundColor' => chart_colors(count($data['mcp'])),
                )),
            ),
            'options' => chart_options(true),
        );
    }
    if (!empty($data['models'])) {
        $model_labels = array_map(function ($row) { return $row['model']; }, $data['models']);
        $charts[$prefix . 'ModelIn'] = bar_chart($model_labels, array_map(function ($row) { return $row['tokens_in']; }, $data['models']), '#2563eb');
        $charts[$prefix . 'ModelCache'] = bar_chart($model_labels, array_map(function ($row) { return $row['cache']; }, $data['models']), '#0ea5e9');
        $charts[$prefix . 'ModelOut'] = bar_chart($model_labels, array_map(function ($row) { return $row['tokens_out']; }, $data['models']), '#10b981');
    }
    if (!empty($data['cli'])) {
        $cli_rows = array_slice($data['cli'], 0, 10);
        $cli_labels = array_map(function ($row) { return $row['name']; }, $cli_rows);
        $charts[$prefix . 'CliCalls'] = bar_chart($cli_labels, array_map(function ($row) { return $row['calls']; }, $cli_rows), '#8b5cf6');
        $charts[$prefix . 'CliIn'] = bar_chart($cli_labels, array_map(function ($row) { return $row['tokens_in']; }, $cli_rows), '#2563eb');
        $charts[$prefix . 'CliCache'] = bar_chart($cli_labels, array_map(function ($row) { return $row['cache']; }, $cli_rows), '#0ea5e9');
        $charts[$prefix . 'CliOut'] = bar_chart($cli_labels, array_map(function ($row) { return $row['tokens_out']; }, $cli_rows), '#10b981');
    }
    if (!empty($data['token_split'])) {
        $split = $data['token_split'];
        $charts[$prefix . 'Split'] = array(
            'type' => 'doughnut',
            'data' => array(
                'labels' => isset($split['labels']) ? $split['labels'] : array(),
                'datasets' => array(array(
                    'data' => isset($split['values']) ? $split['values'] : array(),
                    'backgroundColor' => array('#2563eb', '#0ea5e9', '#7c3aed', '#10b981', '#f59e0b'),
                )),
            ),
            'options' => chart_options(true),
        );
    }
    return $charts;
}

function analytics_charts_html($prefix, $charts) {
    if (!$charts) {
        return '';
    }
    $has = function ($suffix) use ($prefix, $charts) {
        return isset($charts[$prefix . $suffix]);
    };
    ob_start();
    ?>
        <div class="charts">
          <?php if ($has('Split')): ?>
          <div class="card">
            <h3>Структура токенов</h3>
            <div class="chart-box"><canvas id="<?php echo h($prefix . 'Split'); ?>"></canvas></div>
          </div>
          <?php endif; ?>
          <?php if ($has('Sessions')): ?>
          <div class="card chart-wide">
            <h3>Токены по сессиям</h3>
            <div class="chart-box"><canvas id="<?php echo h($prefix . 'Sessions'); ?>"></canvas></div>
          </div>
          <?php endif; ?>
          <?php if ($has('Findings')): ?>
          <div class="card">
            <h3>Находки по кодам</h3>
            <div class="chart-box"><canvas id="<?php echo h($prefix . 'Findings'); ?>"></canvas></div>
          </div>
          <?php endif; ?>
          <?php if ($has('Tools')): ?>
          <div class="card">
            <h3>Инструменты</h3>
            <div class="chart-box"><canvas id="<?php echo h($prefix . 'Tools'); ?>"></canvas></div>
          </div>
          <?php endif; ?>
          <?php if ($has('McpIn')): ?>
          <div class="card chart-wide">
            <h3>MCP: токены по серверам</h3>
            <div class="chart-triple">
              <div><h4>Свежий ввод</h4><div class="chart-box"><canvas id="<?php echo h($prefix . 'McpIn'); ?>"></canvas></div></div>
              <div><h4>Кэш</h4><div class="chart-box"><canvas id="<?php echo h($prefix . 'McpCache'); ?>"></canvas></div></div>
              <div><h4>Исходящие</h4><div class="chart-box"><canvas id="<?php echo h($prefix . 'McpOut'); ?>"></canvas></div></div>
            </div>
            <p class="muted card-note">Каждый график со своей линейной шкалой. Токены execute-сообщения делятся поровну между серверами вызова.</p>
          </div>
          <?php endif; ?>
          <?php if ($has('ModelIn')): ?>
          <div class="card chart-wide">
            <h3>Токены по моделям</h3>
            <div class="chart-triple">
              <div><h4>Свежий ввод</h4><div class="chart-box"><canvas id="<?php echo h($prefix . 'ModelIn'); ?>"></canvas></div></div>
              <div><h4>Кэш</h4><div class="chart-box"><canvas id="<?php echo h($prefix . 'ModelCache'); ?>"></canvas></div></div>
              <div><h4>Исходящие</h4><div class="chart-box"><canvas id="<?php echo h($prefix . 'ModelOut'); ?>"></canvas></div></div>
            </div>
            <p class="muted card-note">Каждый график со своей линейной шкалой.</p>
          </div>
          <?php endif; ?>
          <?php if ($has('CliCalls')): ?>
          <div class="card chart-wide">
            <h3>Bash: вызовы по CLI</h3>
            <div class="chart-box"><canvas id="<?php echo h($prefix . 'CliCalls'); ?>"></canvas></div>
          </div>
          <div class="card chart-wide">
            <h3>Bash: токены по CLI</h3>
            <div class="chart-triple">
              <div><h4>Свежий ввод</h4><div class="chart-box"><canvas id="<?php echo h($prefix . 'CliIn'); ?>"></canvas></div></div>
              <div><h4>Кэш</h4><div class="chart-box"><canvas id="<?php echo h($prefix . 'CliCache'); ?>"></canvas></div></div>
              <div><h4>Исходящие</h4><div class="chart-box"><canvas id="<?php echo h($prefix . 'CliOut'); ?>"></canvas></div></div>
            </div>
            <p class="muted card-note">Токены сообщения делятся между инструментами, вызванными в этом сообщении.</p>
          </div>
          <?php endif; ?>
          <?php if ($has('Mcp')): ?>
          <div class="card">
            <h3>MCP: вызовы (шт)</h3>
            <div class="chart-box"><canvas id="<?php echo h($prefix . 'Mcp'); ?>"></canvas></div>
          </div>
          <?php endif; ?>
        </div>
    <?php
    return ob_get_clean();
}

function analytics_tables_html($data) {
    $tools = isset($data['tools']) && is_array($data['tools']) ? $data['tools'] : array();
    $mcp = isset($data['mcp']) && is_array($data['mcp']) ? $data['mcp'] : array();
    $cli = isset($data['cli']) && is_array($data['cli']) ? $data['cli'] : array();
    $models = isset($data['models']) && is_array($data['models']) ? $data['models'] : array();
    $providers = isset($data['providers']) && is_array($data['providers']) ? $data['providers'] : array();
    $findings = isset($data['findings']) && is_array($data['findings']) ? $data['findings'] : array();
    $has_median = false;
    foreach ($tools as $row) {
        if (isset($row['median_ms'])) {
            $has_median = true;
            break;
        }
    }
    $has_mcp_tools = false;
    foreach ($mcp as $row) {
        $count = 0;
        if (isset($row['tools']) && is_array($row['tools'])) {
            $count = count($row['tools']);
        } elseif (isset($row['tools'])) {
            $count = (int)$row['tools'];
        }
        if ($count > 0 || !empty($row['tool_rows'])) {
            $has_mcp_tools = true;
            break;
        }
    }
    $finding_list = isset($findings[0]) && is_array($findings[0]);
    $cli_total = count($cli);
    $cli_rows = array_slice($cli, 0, 20);
    $tool_cols = 4 + ($has_median ? 2 : 0);
    $mcp_cols = 4 + ($has_mcp_tools ? 1 : 0) + 3;
    $mcp_tool_rows = function ($server) {
        if (isset($server['tool_rows']) && is_array($server['tool_rows'])) {
            return $server['tool_rows'];
        }
        $rows = array();
        if (isset($server['tools']) && is_array($server['tools'])) {
            foreach ($server['tools'] as $name => $calls) {
                $rows[] = array('name' => (string)$name, 'calls' => (int)$calls);
            }
        }
        usort($rows, function ($x, $y) { return $y['calls'] - $x['calls']; });
        return $rows;
    };
    ob_start();
    ?>
      <h2>Инструменты (<?php echo count($tools); ?>)</h2>
      <?php if ($tools): ?>
      <table class="data">
        <tr><th>Инструмент</th><th class="num">Вызовы</th><th class="num">Ошибки</th><th class="num">Таймауты</th><?php if ($has_median): ?><th class="num">Медиана</th><th class="num">p95</th><?php endif; ?></tr>
        <?php foreach ($tools as $tool): ?>
        <?php $is_bash = $tool['name'] === 'bash' && $cli; ?>
        <tr<?php echo $is_bash ? ' class="expandable" data-detail="tool-bash" tabindex="0" role="button" aria-expanded="false"' : ''; ?>>
          <td><?php if ($is_bash): ?><span class="expander">+</span><?php endif; ?><?php echo h($tool['name']); ?></td>
          <td class="num"><?php echo (int)$tool['calls']; ?></td>
          <td class="num"><?php echo (int)$tool['errors']; ?></td>
          <td class="num"><?php echo (int)$tool['timeouts']; ?></td>
          <?php if ($has_median): ?>
          <td class="num"><?php echo (int)$tool['median_ms']; ?> мс</td>
          <td class="num"><?php echo (int)$tool['p95_ms']; ?> мс</td>
          <?php endif; ?>
        </tr>
        <?php if ($is_bash): ?>
        <tr class="detail-row" data-detail="tool-bash" hidden>
          <td colspan="<?php echo $tool_cols; ?>">
            <table class="data nested">
              <tr><th>CLI</th><th class="num">Вызовы</th><th class="num">Ошибки</th><th class="num">Свежий ввод</th><th class="num">Кэш</th><th class="num">Исходящие</th><th class="num">Стоимость</th></tr>
              <?php foreach (array_slice($cli, 0, 20) as $row): ?>
              <tr>
                <td><?php echo h($row['name']); ?></td>
                <td class="num"><?php echo (int)$row['calls']; ?></td>
                <td class="num"><?php echo (int)$row['errors']; ?></td>
                <td class="num"><?php echo h(fmt_num($row['tokens_in'])); ?></td>
                <td class="num"><?php echo h(fmt_num($row['cache'])); ?></td>
                <td class="num"><?php echo h(fmt_num($row['tokens_out'])); ?></td>
                <td class="num"><?php echo h(number_format(isset($row['cost']) ? $row['cost'] : 0, 4, '.', '')); ?> <?php echo h(price_currency()); ?></td>
              </tr>
              <?php endforeach; ?>
            </table>
          </td>
        </tr>
        <?php endif; ?>
        <?php endforeach; ?>
      </table>
      <?php else: ?><p class="muted">Вызовов инструментов нет.</p><?php endif; ?>

      <h2>MCP (<?php echo count($mcp); ?>)</h2>
      <?php if ($mcp): ?>
      <table class="data">
        <tr><th>Сервер</th><th class="num">Вызовы</th><th class="num">Ошибки</th><?php if ($has_mcp_tools): ?><th class="num">Инструментов</th><?php endif; ?><th class="num">Свежий ввод</th><th class="num">Кэш</th><th class="num">Исходящие</th><th class="num">Стоимость</th></tr>
        <?php foreach ($mcp as $server): ?>
        <?php $rows = $mcp_tool_rows($server); $detail_id = 'mcp-' . preg_replace('/[^a-z0-9_]/i', '_', $server['server']); ?>
        <tr<?php echo $rows ? ' class="expandable" data-detail="' . h($detail_id) . '" tabindex="0" role="button" aria-expanded="false"' : ''; ?>>
          <td><?php if ($rows): ?><span class="expander">+</span><?php endif; ?><?php echo h($server['server']); ?></td>
          <td class="num"><?php echo (int)$server['calls']; ?></td>
          <td class="num"><?php echo (int)$server['errors']; ?></td>
          <?php if ($has_mcp_tools): ?><td class="num"><?php echo count($rows); ?></td><?php endif; ?>
          <td class="num"><?php echo h(fmt_num($server['tokens_in'])); ?></td>
          <td class="num"><?php echo h(fmt_num($server['cache'])); ?></td>
          <td class="num"><?php echo h(fmt_num($server['tokens_out'])); ?></td>
          <td class="num"><?php echo h(number_format(isset($server['cost']) ? $server['cost'] : 0, 4, '.', '')); ?> <?php echo h(price_currency()); ?></td>
        </tr>
        <?php if ($rows): ?>
        <tr class="detail-row" data-detail="<?php echo h($detail_id); ?>" hidden>
          <td colspan="<?php echo $mcp_cols; ?>">
            <table class="data nested">
              <tr><th>Инструмент</th><th class="num">Вызовы</th><th class="num">Стоимость</th></tr>
              <?php foreach ($rows as $row): ?>
              <?php $row_cost = ((int)$server['calls'] > 0) ? ((isset($server['cost']) ? $server['cost'] : 0) * (int)$row['calls'] / (int)$server['calls']) : 0; ?>
              <tr><td><?php echo h($row['name']); ?></td><td class="num"><?php echo (int)$row['calls']; ?></td><td class="num"><?php echo h(number_format($row_cost, 4, '.', '')); ?> <?php echo h(price_currency()); ?></td></tr>
              <?php endforeach; ?>
            </table>
          </td>
        </tr>
        <?php endif; ?>
        <?php endforeach; ?>
      </table>
      <?php else: ?><p class="muted">Вызовов MCP нет.</p><?php endif; ?>

      <h2>Модели (<?php echo count($models); ?>)</h2>
      <?php if ($models): ?>
      <table class="data">
        <tr><th>Модель</th><th class="num">Свежий ввод</th><th class="num">Кэш</th><th class="num">Исходящие</th><th class="num">Reasoning</th><th class="num">Стоимость, <?php echo h(price_currency()); ?></th></tr>
        <?php foreach ($models as $model): ?>
        <tr>
          <td><?php echo h($model['model']); ?></td>
          <td class="num"><?php echo h(fmt_num($model['tokens_in'])); ?></td>
          <td class="num"><?php echo h(fmt_num($model['cache'])); ?></td>
          <td class="num"><?php echo h(fmt_num($model['tokens_out'])); ?></td>
          <td class="num"><?php echo h(fmt_num($model['reasoning'])); ?></td>
          <td class="num"><?php echo h(number_format($model['cost'], 4, '.', '')); ?> <?php echo h(price_currency()); ?></td>
        </tr>
        <?php endforeach; ?>
      </table>
      <?php else: ?><p class="muted">Данных по моделям нет.</p><?php endif; ?>

      <h2>Провайдеры (<?php echo count($providers); ?>)</h2>
      <?php if ($providers): ?>
      <table class="data">
        <tr><th>Провайдер</th><th class="num">Сессии</th><th class="num">Свежий ввод</th><th class="num">Кэш</th><th class="num">Исходящие</th><th class="num">Стоимость</th></tr>
        <?php foreach ($providers as $provider): ?>
        <tr>
          <td><?php echo h(provider_label($provider['provider'])); ?></td>
          <td class="num"><?php echo (int)$provider['sessions']; ?></td>
          <td class="num"><?php echo h(fmt_num($provider['tokens_in'])); ?></td>
          <td class="num"><?php echo h(fmt_num($provider['cache'])); ?></td>
          <td class="num"><?php echo h(fmt_num($provider['tokens_out'])); ?></td>
          <td class="num"><?php echo h(number_format($provider['cost'], 4, '.', '')); ?> <?php echo h(price_currency($provider['provider'])); ?></td>
        </tr>
        <?php endforeach; ?>
      </table>
      <?php else: ?><p class="muted">Провайдеры не определены.</p><?php endif; ?>

      <h2>Находки (<?php echo count($findings); ?>)</h2>
      <?php if ($findings): ?>
      <table class="data">
        <tr><th>Код</th><th class="num">Событий</th><?php if ($finding_list): ?><th>Описание</th><?php endif; ?></tr>
        <?php if ($finding_list): ?>
          <?php foreach ($findings as $finding): ?>
          <tr>
            <td><code><?php echo h($finding['code']); ?></code></td>
            <td class="num"><?php echo (int)$finding['count']; ?></td>
            <td><?php echo h($finding['detail']); ?></td>
          </tr>
          <?php endforeach; ?>
        <?php else: ?>
          <?php foreach ($findings as $code => $count): ?>
          <tr>
            <td><code><?php echo h($code); ?></code></td>
            <td class="num"><?php echo (int)$count; ?></td>
          </tr>
          <?php endforeach; ?>
        <?php endif; ?>
      </table>
      <?php else: ?><p class="muted">Находок нет.</p><?php endif; ?>
    <?php
    return ob_get_clean();
}

$tab = 'tasks';
if (isset($_GET['tab']) && in_array($_GET['tab'], array('tasks', 'docs', 'analytics'), true)) {
    $tab = $_GET['tab'] === 'analytics' ? 'tasks' : $_GET['tab'];
}
$q = isset($_GET['q']) ? trim((string)$_GET['q']) : '';
$rel_filter = isset($_GET['release']) ? trim((string)$_GET['release']) : '';
$assignee_filter = isset($_GET['assignee']) ? trim((string)$_GET['assignee']) : '';
$project_cookie = 'panel_project';
$project_filter = '';
if (isset($_GET['project'])) {
    $project_filter = trim((string)$_GET['project']);
} elseif (isset($_COOKIE[$project_cookie])) {
    $project_filter = trim((string)$_COOKIE[$project_cookie]);
}
$sel_task = isset($_GET['id']) && valid_task_id($_GET['id']) ? $_GET['id'] : '';
$sel_doc = isset($_GET['doc']) && valid_doc_name($_GET['doc']) ? $_GET['doc'] : '';
$show_unassigned = isset($_GET['unassigned']) && (string)$_GET['unassigned'] === '1';
$sel_session = isset($_GET['session']) && valid_session_id($_GET['session']) ? (string)$_GET['session'] : '';

$tasks = list_tasks();
$releases = list_releases($tasks);
$assignees = list_assignees($tasks);

$filtered = array();
foreach ($tasks as $t) {
    if ($rel_filter !== '' && $t['release'] !== $rel_filter) {
        continue;
    }
    if ($q !== '' && stripos($t['id'] . ' ' . $t['title'], $q) === false) {
        continue;
    }
    if ($assignee_filter !== '' && $t['assignee'] !== $assignee_filter) {
        continue;
    }
    $filtered[] = $t;
}
$allowed_task_ids = array();
foreach ($filtered as $t) {
    $allowed_task_ids[] = $t['id'];
}

$arch_list = list_arch_docs();
$arch_filtered = array();
foreach ($arch_list as $a) {
    if ($q !== '' && $tab === 'docs' && stripos($a['name'] . ' ' . $a['title'], $q) === false) {
        continue;
    }
    $arch_filtered[] = $a;
}

$task_detail = $sel_task !== '' ? get_task_detail($sel_task) : null;
$arch_detail = $sel_doc !== '' ? get_arch_doc($sel_doc) : null;
if ($sel_doc !== '' && $arch_detail !== null) {
    $tab = 'docs';
}
if ($task_detail !== null) {
    $tab = 'tasks';
}

$session_detail = null;
if ($sel_session !== '') {
    $session_detail = unassigned_session_detail($sel_session);
    if ($session_detail === null) {
        $sel_session = '';
    } else {
        $tab = 'tasks';
        $task_detail = null;
        $show_unassigned = true;
    }
}

$panel_actions = jobs_visible_actions($sel_task, array('task', 'analytics'));

$all_unassigned = $tab === 'tasks' ? list_unassigned_sessions() : array();
$project_options = list_dialog_projects($all_unassigned);
uasort($project_options, function ($a, $b) {
    $cmp = strnatcasecmp($a['label'], $b['label']);
    return $cmp !== 0 ? $cmp : strcmp($a['id'], $b['id']);
});
if ($project_filter !== '' && !isset($project_options[$project_filter])) {
    $project_filter = '';
}
if (isset($_GET['project'])) {
    if ($project_filter === '') {
        setcookie($project_cookie, '', time() - 3600, '/');
    } else {
        setcookie($project_cookie, $project_filter, time() + 15552000, '/');
    }
}
$unassigned_matching = array();
foreach ($all_unassigned as $u) {
    $project_key = $u['project_id'] !== '' ? $u['project_id'] : $u['project'];
    if ($project_filter !== '' && $project_key !== $project_filter) {
        continue;
    }
    if ($q !== '' && stripos($u['session_id'] . ' ' . $u['role'] . ' ' . $u['model'] . ' ' . $u['title'] . ' ' . $u['project_label'], $q) === false) {
        continue;
    }
    $unassigned_matching[] = $u;
}
$unassigned_sessions = $show_unassigned ? $unassigned_matching : array();

$side_params = array(
    'tab' => 'tasks',
    'release' => $rel_filter,
    'assignee' => $assignee_filter,
    'project' => $project_filter,
    'q' => $q,
);
if ($show_unassigned) {
    $side_params['unassigned'] = '1';
}

$task_analytics = $task_detail !== null ? task_dialogs($sel_task, $project_filter) : null;
$analytics = null;
if ($tab === 'tasks' && $task_detail === null && $session_detail === null) {
    $analytics = analytics_dataset($allowed_task_ids, $project_filter, unassigned_analytics($unassigned_matching));
}

$charts = array();
if ($task_analytics !== null && $task_analytics['present']) {
    $charts = analytics_chart_configs($task_analytics, 'task', true, 'Сессии');
}
if ($session_detail !== null) {
    $session_summary = $session_detail['summary'];
    $session_findings = array();
    foreach ($session_detail['findings'] as $finding) {
        $session_findings[$finding['code']] = (int)$finding['count'];
    }
    $session_chart_data = array(
        'token_split' => array(
            'labels' => array('Свежий ввод', 'Чтение кэша', 'Запись кэша', 'Выход', 'Reasoning'),
            'values' => array(
                $session_summary['tokens_in'],
                $session_summary['cache_read'],
                $session_summary['cache_write'],
                $session_summary['tokens_out'],
                $session_summary['reasoning'],
            ),
        ),
        'findings' => $session_findings,
        'tools' => $session_detail['tools'],
        'mcp' => $session_detail['mcp'],
        'models' => $session_detail['models'],
        'cli' => $session_detail['cli'],
    );
    $charts = array_merge($charts, analytics_chart_configs($session_chart_data, 'session', false, 'События'));
}
if ($analytics !== null) {
    $top = array_slice($analytics['tasks'], 0, 12);
    $charts['topTasks'] = array(
        'type' => 'bar',
        'data' => array(
            'labels' => array_map(function ($row) { return '#' . $row['id']; }, $top),
            'datasets' => array(array(
                'label' => 'Токены без кэша',
                'data' => array_map(function ($row) { return $row['tokens']; }, $top),
                'backgroundColor' => '#2563eb',
                'borderRadius' => 4,
            )),
        ),
        'options' => chart_options(false),
    );
    $charts['tokenSplit'] = array(
        'type' => 'doughnut',
        'data' => array(
            'labels' => array('Свежий ввод', 'Чтение кэша', 'Запись кэша', 'Выход', 'Reasoning'),
            'datasets' => array(array(
                'data' => array(
                    $analytics['totals']['tokens_in'],
                    $analytics['totals']['cache_read'],
                    $analytics['totals']['cache_write'],
                    $analytics['totals']['tokens_out'],
                    $analytics['totals']['tokens_reasoning'],
                ),
                'backgroundColor' => array('#2563eb', '#0ea5e9', '#7c3aed', '#10b981', '#f59e0b'),
            )),
        ),
        'options' => chart_options(true),
    );
    if ($analytics['findings']) {
        $charts['findings'] = array(
            'type' => 'bar',
            'data' => array(
                'labels' => array_keys($analytics['findings']),
                'datasets' => array(array(
                    'label' => 'Сессии',
                    'data' => array_values($analytics['findings']),
                    'backgroundColor' => '#f59e0b',
                    'borderRadius' => 4,
                )),
            ),
            'options' => chart_options(false),
        );
    }
    if ($analytics['mcp']) {
        if ($analytics['models']) {
            $model_labels = array_map(function ($row) { return $row['model']; }, $analytics['models']);
            $charts['modelIn'] = bar_chart($model_labels, array_map(function ($row) { return $row['tokens_in']; }, $analytics['models']), '#2563eb');
            $charts['modelCache'] = bar_chart($model_labels, array_map(function ($row) { return $row['cache']; }, $analytics['models']), '#0ea5e9');
            $charts['modelOut'] = bar_chart($model_labels, array_map(function ($row) { return $row['tokens_out']; }, $analytics['models']), '#10b981');
        }
        $mcp_labels = array_map(function ($row) { return $row['server']; }, $analytics['mcp']);
        $charts['mcpIn'] = bar_chart($mcp_labels, array_map(function ($row) { return $row['tokens_in']; }, $analytics['mcp']), '#2563eb');
        $charts['mcpCache'] = bar_chart($mcp_labels, array_map(function ($row) { return $row['cache']; }, $analytics['mcp']), '#0ea5e9');
        $charts['mcpOut'] = bar_chart($mcp_labels, array_map(function ($row) { return $row['tokens_out']; }, $analytics['mcp']), '#10b981');
        if ($analytics['cli']) {
            $cli_rows = array_slice($analytics['cli'], 0, 12);
            $cli_labels = array_map(function ($row) { return $row['name']; }, $cli_rows);
            $charts['cliCalls'] = bar_chart($cli_labels, array_map(function ($row) { return $row['calls']; }, $cli_rows), '#8b5cf6');
            $charts['cliIn'] = bar_chart($cli_labels, array_map(function ($row) { return $row['tokens_in']; }, $cli_rows), '#2563eb');
            $charts['cliCache'] = bar_chart($cli_labels, array_map(function ($row) { return $row['cache']; }, $cli_rows), '#0ea5e9');
            $charts['cliOut'] = bar_chart($cli_labels, array_map(function ($row) { return $row['tokens_out']; }, $cli_rows), '#10b981');
        }
        $charts['mcp'] = array(
            'type' => 'doughnut',
            'data' => array(
                'labels' => array_map(function ($row) { return $row['server']; }, $analytics['mcp']),
                'datasets' => array(array(
                    'data' => array_map(function ($row) { return $row['calls']; }, $analytics['mcp']),
                    'backgroundColor' => chart_colors(count($analytics['mcp'])),
                )),
            ),
            'options' => chart_options(true),
        );
    }
    if ($analytics['roles']) {
        $charts['roles'] = array(
            'type' => 'bar',
            'data' => array(
                'labels' => array_keys($analytics['roles']),
                'datasets' => array(array(
                    'label' => 'Сессии',
                    'data' => array_values($analytics['roles']),
                    'backgroundColor' => '#8b5cf6',
                    'borderRadius' => 4,
                )),
            ),
            'options' => chart_options(false),
        );
    }
}

$manifest = $analytics !== null ? read_json_file(doc_dir() . '/task-analytics/out/state/manifest.json') : null;
?>
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Панель харнеса</title>
<link rel="stylesheet" href="/assets/style.css">
<?php if ($charts): ?>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<?php endif; ?>
</head>
<body>
<header class="top">
  <div class="top-inner">
    <a class="logo" href="<?php echo h(self_url(array('tab' => 'tasks'))); ?>">Панель харнеса</a>
    <nav>
      <a class="<?php echo $tab === 'tasks' ? 'active' : ''; ?>" href="<?php echo h(self_url(array('tab' => 'tasks'))); ?>">Задачи <span class="count"><?php echo count($tasks); ?></span></a>
      <a class="<?php echo $tab === 'docs' ? 'active' : ''; ?>" href="<?php echo h(self_url(array('tab' => 'docs'))); ?>">Документация <span class="count"><?php echo count($arch_list); ?></span></a>
      <a href="/harness/">Харнес</a>
    </nav>
  </div>
</header>
<div class="layout">
  <main>
    <?php if ($panel_actions): ?>
    <section class="panel-actions" id="panel-actions" data-task="<?php echo h($sel_task); ?>">
      <h2>Действия</h2>
      <div class="panel-actions-buttons">
        <?php foreach ($panel_actions as $a): ?>
          <button type="button" class="action-btn" data-action="<?php echo h($a['id']); ?>" data-task-param="<?php echo isset($a['params']['task']) ? '1' : '0'; ?>"<?php echo !empty($a['confirm']) ? ' data-confirm="1"' : ''; ?>><?php echo h($a['label']); ?></button>
        <?php endforeach; ?>
      </div>
      <div class="job-status" hidden>
        <div class="job-line">
          <strong class="job-label"></strong>
          <span class="job-state"></span>
          <span class="job-message muted"></span>
        </div>
        <progress class="job-progress" max="100"></progress>
        <button type="button" class="job-cancel" hidden>Отменить</button>
        <pre class="job-log" hidden></pre>
      </div>
    </section>
    <?php endif; ?>
    <?php if ($tab === 'tasks' && $task_detail === null && $session_detail === null): ?>
      <h1>Задачи</h1>
      <p class="muted">Список отсортирован по последнему изменению: новые сверху. Клик открывает задачу, у задач с диалогами есть блок метрик и графики.</p>
      <div class="kpis">
        <div class="kpi"><span class="kpi-label">Задач</span><span class="kpi-value"><?php echo count($filtered); ?></span></div>
        <div class="kpi"><span class="kpi-label">С диалогами</span><span class="kpi-value"><?php echo (int)$analytics['totals']['tasks']; ?></span></div>
        <div class="kpi"><span class="kpi-label">Токены диалогов (без кэша)</span><span class="kpi-value"><?php echo h(fmt_num($analytics['totals']['tokens_in'] + $analytics['totals']['tokens_out'] + $analytics['totals']['tokens_reasoning'])); ?></span></div>
      </div>
    <?php endif; ?>
    <?php if ($tab === 'docs' && $arch_detail === null): ?>
      <h1>Архитектурная документация</h1>
      <p class="muted">Справа список документов из architecture/*.json. Клик открывает документ: секции, файлы, подводные камни.</p>
    <?php endif; ?>

    <?php if ($analytics !== null): ?>
      <h2 id="analytics">Аналитика диалогов</h2>
      <p class="muted">
        Источник: <code>.doc/task-analytics/out</code>, база Kilo read-only.
        Данные подчиняются фильтру справа: проект, релиз, ответственный и поиск.
        <?php if (isset($manifest['generated_at'])): ?>Последний прогон: <?php echo h($manifest['generated_at']); ?>.<?php endif; ?>
        Обновить: <code>python3 .agents/skills/task-router/children/analytics/scripts/task-analytics.py scan --allow-partial</code>
      </p>
      <div class="kpis">
        <div class="kpi"><span class="kpi-label">Сессии в задачах</span><span class="kpi-value"><?php echo (int)$analytics['totals']['sessions']; ?></span></div>
        <div class="kpi"><span class="kpi-label">Задачи с диалогами</span><span class="kpi-value"><?php echo (int)$analytics['totals']['tasks']; ?></span></div>
        <div class="kpi"><span class="kpi-label">Токены без кэша</span><span class="kpi-value"><?php echo h(fmt_num($analytics['totals']['tokens_in'] + $analytics['totals']['tokens_out'] + $analytics['totals']['tokens_reasoning'])); ?></span></div>
        <div class="kpi"><span class="kpi-label">Обработано контекста</span><span class="kpi-value"><?php echo h(fmt_num($analytics['totals']['tokens_in'] + $analytics['totals']['cache_read'] + $analytics['totals']['cache_write'])); ?></span></div>
        <div class="kpi"><span class="kpi-label">Свежий ввод</span><span class="kpi-value"><?php echo h(fmt_num($analytics['totals']['tokens_in'])); ?></span></div>
        <div class="kpi"><span class="kpi-label">Кэш</span><span class="kpi-value"><?php echo h(fmt_num($analytics['totals']['cache_read'])); ?></span></div>
        <div class="kpi"><span class="kpi-label">Исходящие</span><span class="kpi-value"><?php echo h(fmt_num($analytics['totals']['tokens_out'])); ?></span></div>
        <div class="kpi"><span class="kpi-label">Активное время (все сессии)</span><span class="kpi-value"><?php echo h(fmt_minutes($analytics['totals']['active_ms'] + $analytics['unassigned']['active_ms'])); ?></span></div>
        <div class="kpi"><span class="kpi-label">Без задачи</span><span class="kpi-value"><?php echo (int)$analytics['unassigned']['sessions']; ?></span></div>
        <div class="kpi"><span class="kpi-label">Токены без задачи</span><span class="kpi-value"><?php echo h(fmt_num($analytics['unassigned']['tokens'])); ?></span></div>
      </div>
      <p class="muted card-note">Активное время: сумма интервалов между событиями сессий, паузы больше 15 минут не учитываются.</p>

      <div class="charts">
        <div class="card chart-wide">
          <h3>Топ задач по токенам</h3>
          <div class="chart-box"><canvas id="topTasks"></canvas></div>
        </div>
        <div class="card">
          <h3>Структура токенов</h3>
          <div class="chart-box"><canvas id="tokenSplit"></canvas></div>
        </div>
        <div class="card">
          <h3>Находки по кодам</h3>
          <div class="chart-box"><canvas id="findings"></canvas></div>
        </div>
        <div class="card chart-wide">
          <h3>MCP: токены по серверам</h3>
          <div class="chart-triple">
            <div><h4>Свежий ввод</h4><div class="chart-box"><canvas id="mcpIn"></canvas></div></div>
            <div><h4>Кэш</h4><div class="chart-box"><canvas id="mcpCache"></canvas></div></div>
            <div><h4>Исходящие</h4><div class="chart-box"><canvas id="mcpOut"></canvas></div></div>
          </div>
          <p class="muted card-note">Каждый график со своей линейной шкалой. Токены execute-сообщения делятся поровну между серверами вызова.</p>
        </div>
        <div class="card chart-wide">
          <h3>Токены по моделям</h3>
          <div class="chart-triple">
            <div><h4>Свежий ввод</h4><div class="chart-box"><canvas id="modelIn"></canvas></div></div>
            <div><h4>Кэш</h4><div class="chart-box"><canvas id="modelCache"></canvas></div></div>
            <div><h4>Исходящие</h4><div class="chart-box"><canvas id="modelOut"></canvas></div></div>
          </div>
          <p class="muted card-note">Каждый график со своей линейной шкалой.</p>
        </div>
        <div class="card chart-wide">
          <h3>Bash: вызовы по CLI</h3>
          <div class="chart-box"><canvas id="cliCalls"></canvas></div>
        </div>
        <div class="card chart-wide">
          <h3>Bash: токены по CLI</h3>
          <div class="chart-triple">
            <div><h4>Свежий ввод</h4><div class="chart-box"><canvas id="cliIn"></canvas></div></div>
            <div><h4>Кэш</h4><div class="chart-box"><canvas id="cliCache"></canvas></div></div>
            <div><h4>Исходящие</h4><div class="chart-box"><canvas id="cliOut"></canvas></div></div>
          </div>
          <p class="muted card-note">Токены сообщения делятся между инструментами, вызванными в этом сообщении.</p>
        </div>
        <div class="card">
          <h3>MCP: вызовы (шт)</h3>
          <div class="chart-box"><canvas id="mcp"></canvas></div>
        </div>
        <div class="card">
          <h3>Роли сессий</h3>
          <div class="chart-box"><canvas id="roles"></canvas></div>
        </div>
      </div>

      <h2>Задачи с диалогами</h2>
      <table class="data">
        <tr><th>Задача</th><th class="num">Сессии</th><th class="num">Токены без кэша</th><th class="num">Активное время</th><th class="num">Находки</th></tr>
        <?php foreach ($analytics['tasks'] as $row): ?>
          <tr>
            <td><a href="<?php echo h(self_url(array('tab' => 'tasks', 'id' => $row['id']))); ?>">#<?php echo h($row['id']); ?></a> <?php echo h($row['title']); ?></td>
            <td class="num"><?php echo (int)$row['sessions']; ?></td>
            <td class="num"><?php echo h(fmt_num($row['tokens'])); ?></td>
            <td class="num"><?php echo h(fmt_minutes($row['active_ms'])); ?></td>
            <td class="num"><?php echo (int)$row['findings']; ?></td>
          </tr>
        <?php endforeach; ?>
      </table>

      <h2>Диалоги без задачи</h2>
      <?php if ($unassigned_matching): ?>
      <table class="data">
        <tr><th>Сессия</th><th>Начало</th><th>Проект</th><th class="num">Токены без кэша</th><th class="num">Стоимость</th></tr>
        <?php foreach (array_slice($unassigned_matching, 0, 30) as $u): ?>
        <tr>
          <td><a href="<?php echo h(self_url(array_merge($side_params, array('session' => $u['session_id'], 'unassigned' => '1')))); ?>"><code><?php echo h(substr($u['session_id'], 0, 14)); ?></code></a> <?php echo h($u['title'] !== '' ? $u['title'] : 'нет первого сообщения'); ?></td>
          <td><?php echo h($u['date']); ?></td>
          <td><?php echo h($u['project_label']); ?></td>
          <td class="num"><?php echo h(fmt_num($u['tokens'])); ?></td>
          <td class="num"><?php echo h(number_format(isset($u['cost']) ? $u['cost'] : 0, 2, '.', '')); ?> <?php echo h(price_currency(isset($u['provider']) ? $u['provider'] : '')); ?></td>
        </tr>
        <?php endforeach; ?>
      </table>
      <?php if (count($unassigned_matching) > 30): ?><p class="muted">Показаны последние 30 из <?php echo count($unassigned_matching); ?>. <a href="<?php echo h(self_url(array_merge($side_params, array('unassigned' => '1')))); ?>">Показать все в правом меню</a>.</p><?php endif; ?>
      <?php else: ?>
      <p class="muted">Диалогов без задачи нет.</p>
      <?php endif; ?>

      <?php if (!empty($analytics['providers'])): ?>
      <h2>Провайдеры</h2>
      <table class="data">
        <tr><th>Провайдер</th><th class="num">Сессии</th><th class="num">Свежий ввод</th><th class="num">Кэш</th><th class="num">Исходящие</th><th class="num">Стоимость</th></tr>
        <?php foreach ($analytics['providers'] as $provider): ?>
        <tr>
          <td><?php echo h(provider_label($provider['provider'])); ?></td>
          <td class="num"><?php echo (int)$provider['sessions']; ?></td>
          <td class="num"><?php echo h(fmt_num($provider['tokens_in'])); ?></td>
          <td class="num"><?php echo h(fmt_num($provider['cache'])); ?></td>
          <td class="num"><?php echo h(fmt_num($provider['tokens_out'])); ?></td>
          <td class="num"><?php echo h(number_format($provider['cost'], 4, '.', '')); ?> <?php echo h(price_currency($provider['provider'])); ?></td>
        </tr>
        <?php endforeach; ?>
      </table>
      <?php endif; ?>
    <?php endif; ?>

    <?php if ($session_detail !== null): $sd = $session_detail; $ss = $sd['summary']; ?>
      <div class="crumbs"><a href="<?php echo h(self_url($side_params)); ?>">Задачи</a> / диалог без задачи</div>
      <h1>Диалог без задачи</h1>
      <p class="muted">Сессия не привязана к задаче. Показаны детерминированные метрики: токены, запросы, вызовы инструментов и время. ИИ-отчет не формируется.</p>
      <table class="meta">
        <tr><th>Сессия</th><td><code><?php echo h($ss['session_id']); ?></code></td></tr>
        <tr><th>Старт</th><td><?php echo h($ss['date'] !== '' ? $ss['date'] : 'нет данных'); ?></td></tr>
        <tr><th>Роль</th><td><?php echo h($ss['role'] !== '' ? $ss['role'] : 'не указана'); ?></td></tr>
        <tr><th>Модель</th><td><?php echo h($ss['model'] !== '' ? $ss['model'] : 'не указана'); ?></td></tr>
        <tr><th>Провайдер</th><td><?php echo h(provider_label(isset($ss['provider']) ? $ss['provider'] : '')); ?></td></tr>
        <tr><th>Проект</th><td><?php echo h($ss['project_label'] !== '' ? $ss['project_label'] : 'не определён'); ?><?php if ($ss['project'] !== '') { echo ' <span class="muted"><code>' . h($ss['project']) . '</code></span>'; } ?></td></tr>
        <tr><th>Стоимость</th><td><?php echo h(number_format(isset($ss['cost']) ? $ss['cost'] : 0, 2, '.', '')); ?> <?php echo h(price_currency(isset($ss['provider']) ? $ss['provider'] : '')); ?></td></tr>
        <tr><th>Первое сообщение</th><td><?php echo h($ss['title'] !== '' ? $ss['title'] : 'нет текста'); ?></td></tr>
        <tr><th>Привязка</th><td><?php echo h($ss['status']); ?></td></tr>
        <tr><th>Длительность</th><td><?php echo h(fmt_minutes($ss['duration_ms'])); ?></td></tr>
        <tr><th>Активное время</th><td><?php echo h(fmt_minutes($ss['active_ms'])); ?></td></tr>
        <tr><th>Финал</th><td><?php echo $ss['final'] ? 'завершена' : 'открыта'; ?></td></tr>
      </table>
      <div class="kpis">
        <div class="kpi"><span class="kpi-label">Запросов</span><span class="kpi-value"><?php echo h(fmt_num($ss['requests'])); ?></span></div>
        <div class="kpi"><span class="kpi-label">Токены без кэша</span><span class="kpi-value"><?php echo h(fmt_num($ss['tokens'])); ?></span></div>
        <div class="kpi"><span class="kpi-label">Обработано контекста</span><span class="kpi-value"><?php echo h(fmt_num($ss['context'])); ?></span></div>
        <div class="kpi"><span class="kpi-label">Свежий ввод</span><span class="kpi-value"><?php echo h(fmt_num($ss['tokens_in'])); ?></span></div>
        <div class="kpi"><span class="kpi-label">Кэш</span><span class="kpi-value"><?php echo h(fmt_num($ss['cache_read'])); ?></span></div>
        <div class="kpi"><span class="kpi-label">Исходящие</span><span class="kpi-value"><?php echo h(fmt_num($ss['tokens_out'])); ?></span></div>
        <div class="kpi"><span class="kpi-label">Reasoning</span><span class="kpi-value"><?php echo h(fmt_num($ss['reasoning'])); ?></span></div>
        <div class="kpi"><span class="kpi-label">Вызовов инструментов</span><span class="kpi-value"><?php echo h(fmt_num($ss['tool_calls'])); ?></span></div>
        <div class="kpi"><span class="kpi-label">Вызовов MCP</span><span class="kpi-value"><?php echo h(fmt_num($ss['mcp_calls'])); ?></span></div>
        <div class="kpi"><span class="kpi-label">Находки</span><span class="kpi-value"><?php echo (int)$ss['findings']; ?></span></div>
      </div>
      <p class="muted card-note">Токены без кэша: свежий ввод, исходящие и reasoning. Обработано контекста: полный промпт каждого запроса вместе с кэшем.</p>
      <?php echo analytics_charts_html('session', $charts); ?>

      <?php echo analytics_tables_html(array(
          'tools' => $sd['tools'],
          'mcp' => $sd['mcp'],
          'cli' => $sd['cli'],
          'models' => $sd['models'],
          'findings' => $sd['findings'],
      )); ?>

      <?php if ($sd['warnings']): ?>
      <h2>Предупреждения</h2>
      <ul><?php foreach ($sd['warnings'] as $warning): ?><li><?php echo h($warning); ?></li><?php endforeach; ?></ul>
      <?php endif; ?>

      <?php
        $wf = isset($sd['workflow']) && is_array($sd['workflow']) ? $sd['workflow'] : array();
        $wf_tags = array();
        foreach (array('classes', 'domains', 'skills') as $wf_key) {
            if (isset($wf[$wf_key]) && is_array($wf[$wf_key])) {
                foreach ($wf[$wf_key] as $wf_value) {
                    $wf_tags[] = (string)$wf_value;
                }
            }
        }
      ?>
      <?php if ($wf_tags): ?>
      <h2>Рабочий контур</h2>
      <p><?php foreach ($wf_tags as $wf_tag) { echo '<span class="tag">' . h($wf_tag) . '</span> '; } ?></p>
      <?php endif; ?>
    <?php endif; ?>

    <?php if ($task_detail !== null): $s = $task_detail['summary']; ?>
      <div class="crumbs"><a href="<?php echo h(self_url($side_params)); ?>">Задачи</a> / #<?php echo h($s['id']); ?></div>
      <h1>#<?php echo h($s['id']); ?> <?php echo h($s['title']); ?></h1>
      <p class="jira-link"><a href="https://copytrust-team.atlassian.net/browse/CT-<?php echo h($s['id']); ?>" target="_blank" rel="noopener">Открыть CT-<?php echo h($s['id']); ?> в Jira</a></p>
      <table class="meta">
        <tr><th>Релиз</th><td><?php echo h($s['release'] === 'no-release' ? 'без релиза' : $s['release']); ?></td></tr>
        <tr><th>Ветка</th><td><code><?php echo h($s['branch'] !== '' ? $s['branch'] : '—'); ?></code></td></tr>
        <tr><th>Статус Jira</th><td><span class="jstatus"><?php echo h($s['jira_status']); ?></span></td></tr>
        <tr><th>Ответственный</th><td><?php echo h($s['assignee'] !== '' ? $s['assignee'] : '—'); ?></td></tr>
        <tr><th>Обновлено</th><td><?php echo h($s['updated_fmt'] !== '' ? $s['updated_fmt'] : '—'); ?></td></tr>
        <tr><th>Jira created</th><td><?php echo h($s['jira_created'] !== '' ? $s['jira_created'] : 'нет в task.json'); ?></td></tr>
        <tr><th>Jira updated</th><td><?php echo h($s['jira_updated'] !== '' ? $s['jira_updated'] : 'нет в task.json'); ?></td></tr>
        <tr><th>Jira история</th><td>комментариев <?php echo count($task_detail['jira_comments']); ?>, изменений <?php echo count($task_detail['jira_changelog']); ?></td></tr>
        <tr><th>Локальное изменение</th><td><?php echo h($s['last_touched']); ?></td></tr>
        <tr><th>Ревизия</th><td><?php echo (int)$s['revision']; ?></td></tr>
        <tr><th>Jira</th><td><?php echo h($task_detail['issue_key']); ?> (комментариев: <?php echo (int)$task_detail['comments_n']; ?>, экспорт: <?php echo h(fmt_iso_utc($task_detail['exported_at'])); ?>)</td></tr>
        <tr><th>Счетчики</th><td>секций <?php echo (int)$s['n_sections']; ?>, файлов <?php echo (int)$s['n_files']; ?>, находок <?php echo (int)$s['n_findings']; ?>, диалогов <?php echo (int)$s['n_dialogs']; ?></td></tr>
      </table>

      <h2 id="activity">Лента активности Jira</h2>
      <?php if ($task_detail['jira_activity']): ?>
      <div class="timeline">
        <?php foreach (array_slice($task_detail['jira_activity'], 0, 40) as $ev): ?>
        <div class="tl-item tl-<?php echo h($ev['kind']); ?>">
          <div class="tl-dot"></div>
          <div class="tl-body">
            <div class="tl-head">
              <strong><?php echo h($ev['author'] !== '' ? $ev['author'] : 'Jira'); ?></strong>
              <span class="tl-date"><?php echo h(fmt_iso_utc($ev['at'])); ?></span>
              <span class="tl-kind"><?php echo $ev['kind'] === 'comment' ? 'комментарий' : 'изменение'; ?></span>
            </div>
            <?php if ($ev['kind'] === 'comment'): ?>
              <div class="tl-text"><?php
                $body = trim((string)$ev['text']);
                if ($body === '') {
                    $body = $ev['body'] ? '(текст в ADF body)' : '(пусто)';
                }
                $body = preg_replace('/^###\s*/m', '', $body);
                $body = preg_replace("/\n{3,}/", "\n\n", $body);
                echo nl2br(h(mb_substr($body, 0, 900)));
              ?></div>
            <?php else: ?>
              <div class="tl-tags">
                <?php foreach ($ev['items'] as $item): ?>
                  <span class="tl-tag"><?php echo h($item['field']); ?>: <?php echo h($item['from']); ?> &rarr; <?php echo h($item['to']); ?></span>
                <?php endforeach; ?>
              </div>
            <?php endif; ?>
          </div>
        </div>
        <?php endforeach; ?>
      </div>
      <?php else: ?>
      <p class="muted">В снимке Jira нет комментариев и изменений. Обновите задачу через gototask.</p>
      <?php endif; ?>

      <h2 id="business-logic">Бизнес-логика</h2>
      <?php $bl = isset($task_detail['business_logic']['facts']) && is_array($task_detail['business_logic']['facts']) ? $task_detail['business_logic']['facts'] : array(); ?>
      <?php if ($bl): ?>
      <div class="cards">
        <?php foreach ($bl as $fact): ?>
        <div class="biz-card">
          <h3><?php echo h(isset($fact['title']) ? $fact['title'] : (isset($fact['statement']) ? $fact['statement'] : (isset($fact['id']) ? $fact['id'] : 'fact'))); ?></h3>
          <p><strong>Тип:</strong> <code><?php echo h(isset($fact['fact_type']) ? $fact['fact_type'] : 'business_rule'); ?></code>
             <strong>Статус:</strong> <?php echo h(isset($fact['status']) ? $fact['status'] : ''); ?>
             <?php if (!empty($fact['rule_id'])): ?><strong>Правило:</strong> <code><?php echo h($fact['rule_id']); ?></code><?php endif; ?>
          </p>
          <?php if (!empty($fact['statement'])): ?><p><?php echo nl2br(h($fact['statement'])); ?></p><?php endif; ?>
          <?php
            $allAnchors = array();
            foreach ($fact['conditions'] ?? array() as $condition) {
                foreach ($condition['code_anchors'] ?? array() as $anchor) {
                    $anchorText = isset($anchor['file']) ? $anchor['file'] : '';
                    if (!empty($anchor['symbol'])) {
                        $anchorText .= ':' . $anchor['symbol'];
                    } elseif (!empty($anchor['line_start'])) {
                        $anchorText .= ':' . $anchor['line_start'];
                    }
                    if ($anchorText !== '' && !in_array($anchorText, $allAnchors, true)) {
                        $allAnchors[] = $anchorText;
                    }
                }
            }
          ?>
          <?php if ($allAnchors): ?>
          <div class="muted">Код:
            <?php foreach ($allAnchors as $anchorText): ?><code><?php echo h($anchorText); ?></code> <?php endforeach; ?>
          </div>
          <?php endif; ?>
          <?php
            $anchorLabel = isset($fact['anchor_status']) ? $fact['anchor_status'] : 'missing';
            $anchorLabel = array('exact' => 'точный', 'partial' => 'общий', 'missing' => 'не найден')[$anchorLabel] ?? $anchorLabel;
            $testLabel = isset($fact['test_status']) ? $fact['test_status'] : 'manual';
            $testLabel = array('covered' => 'покрыто', 'planned' => 'планируется', 'manual' => 'ручная проверка', 'missing' => 'не найден')[$testLabel] ?? $testLabel;
          ?>
          <p class="muted">Код: <?php echo h($anchorLabel); ?> · Тесты: <?php echo h($testLabel); ?><?php if (!empty($fact['evidence_ref'])): ?> · Источник: <code><?php echo h($fact['evidence_ref']); ?></code><?php endif; ?></p>
        </div>
        <?php endforeach; ?>
      </div>
      <?php endif; ?>

      <?php $bu = isset($task_detail['business_logic']['unconfirmed']) && is_array($task_detail['business_logic']['unconfirmed']) ? $task_detail['business_logic']['unconfirmed'] : array(); ?>
      <?php if ($bu): ?>
      <h3 style="margin-top:18px">Неподтвержденные правила <span class="badge unconfirmed"><?php echo count($bu); ?></span></h3>
      <p class="muted">Эти правила не прошли проверку и не считаются подтвержденной бизнес-логикой. Показаны причина карантина и все метрики последней проверки.</p>
      <div class="cards">
        <?php foreach ($bu as $u): ?>
        <?php
          $m = isset($u['metrics']) && is_array($u['metrics']) ? $u['metrics'] : array();
          $checks = isset($m['checks']) && is_array($m['checks']) ? $m['checks'] : array();
          $anchorLabel = isset($u['anchor_status']) ? $u['anchor_status'] : 'missing';
          $anchorLabel = array('exact' => 'точный', 'partial' => 'общий', 'missing' => 'не найден')[$anchorLabel] ?? $anchorLabel;
          $testLabel = isset($u['test_status']) ? $u['test_status'] : 'missing';
          $testLabel = array('covered' => 'покрыто', 'planned' => 'планируется', 'manual' => 'ручная проверка', 'missing' => 'не найден')[$testLabel] ?? $testLabel;
        ?>
        <div class="biz-card unconfirmed">
          <h3><?php echo h(isset($u['title']) ? $u['title'] : (isset($u['candidate_id']) ? $u['candidate_id'] : 'unconfirmed')); ?></h3>
          <p>
            <span class="badge unconfirmed">не подтверждено</span>
            <strong>Причина:</strong> <code><?php echo h(isset($u['reason']) ? $u['reason'] : 'unknown'); ?></code>
            <strong>Score:</strong> <?php echo h(isset($m['score']) ? (string)$m['score'] : 'n/a'); ?>
            <?php if (!empty($u['candidate_id'])): ?><strong>Кандидат:</strong> <code><?php echo h($u['candidate_id']); ?></code><?php endif; ?>
          </p>
          <?php if (!empty($u['statement'])): ?><p><?php echo nl2br(h($u['statement'])); ?></p><?php endif; ?>
          <?php if ($checks): ?>
          <p class="muted">Проверки:
            <?php foreach ($checks as $name => $value): ?>
              <code><?php echo h($name); ?></code>: <span class="<?php echo $value ? 'check-ok' : 'check-fail'; ?>"><?php echo $value ? 'ok' : 'fail'; ?></span>
            <?php endforeach; ?>
          </p>
          <?php endif; ?>
          <p class="muted">
            Якорь: <?php echo h($anchorLabel); ?> ·
            Тесты: <?php echo h($testLabel); ?> ·
            Следующая проверка: <?php echo h(isset($m['next_check_at']) ? $m['next_check_at'] : 'не назначена'); ?> ·
            Попытки: <?php echo h(isset($m['attempts']) ? (string)$m['attempts'] : '0'); ?>
            <?php if (!empty($m['quarantine_id'])): ?> · Карантин: <code><?php echo h($m['quarantine_id']); ?></code><?php endif; ?>
          </p>
        </div>
        <?php endforeach; ?>
      </div>
      <?php endif; ?>

      <?php if (!$bl && !$bu): ?>
      <p class="muted">В task.json нет verified business_logic.facts и правил в карантине.</p>
      <?php endif; ?>

      <h2 id="dialogs">Диалоги и метрики</h2>
      <?php if ($task_analytics !== null && $task_analytics['present']): $at = $task_analytics['totals']; ?>
        <?php if ($task_analytics['plan_state'] !== null): $ps = $task_analytics['plan_state']; ?>
          <p>Состояние плана:
            <span class="badge plan-<?php echo h(isset($ps['status']) ? $ps['status'] : 'unknown'); ?>"><?php echo h(isset($ps['status']) ? $ps['status'] : 'unknown'); ?></span>
            <?php if (isset($ps['outcome'])): ?><span class="muted">исход: <?php echo h($ps['outcome']); ?></span><?php endif; ?>
          </p>
        <?php endif; ?>
        <details class="collapse" open>
        <summary>Метрики токенов и инструментов</summary>
        <div class="kpis">
          <div class="kpi"><span class="kpi-label">Сессии</span><span class="kpi-value"><?php echo (int)$at['sessions']; ?></span></div>
          <div class="kpi"><span class="kpi-label">Запросов</span><span class="kpi-value"><?php echo h(fmt_num($at['requests'])); ?></span></div>
          <div class="kpi"><span class="kpi-label">Токены без кэша</span><span class="kpi-value"><?php echo h(fmt_num($at['tokens_in'] + $at['tokens_out'] + $at['tokens_reasoning'])); ?></span></div>
          <div class="kpi"><span class="kpi-label">Обработано контекста</span><span class="kpi-value"><?php echo h(fmt_num($at['tokens_in'] + $at['cache_read'] + $at['cache_write'])); ?></span></div>
          <div class="kpi"><span class="kpi-label">Свежий ввод</span><span class="kpi-value"><?php echo h(fmt_num($at['tokens_in'])); ?></span></div>
          <div class="kpi"><span class="kpi-label">Кэш</span><span class="kpi-value"><?php echo h(fmt_num($at['cache_read'])); ?></span></div>
          <div class="kpi"><span class="kpi-label">Исходящие</span><span class="kpi-value"><?php echo h(fmt_num($at['tokens_out'])); ?></span></div>
          <div class="kpi"><span class="kpi-label">Reasoning</span><span class="kpi-value"><?php echo h(fmt_num($at['tokens_reasoning'])); ?></span></div>
          <div class="kpi"><span class="kpi-label">Средний контекст на запрос</span><span class="kpi-value"><?php echo h(fmt_num($at['requests'] > 0 ? (int)round(($at['tokens_in'] + $at['cache_read'] + $at['cache_write']) / $at['requests']) : 0)); ?></span></div>
          <div class="kpi"><span class="kpi-label">Активное время</span><span class="kpi-value"><?php echo h(fmt_minutes($at['active_ms'])); ?></span></div>
          <div class="kpi"><span class="kpi-label">Находки</span><span class="kpi-value"><?php echo (int)$at['findings']; ?></span></div>
        </div>
        <p class="muted card-note">Токены без кэша - свежий ввод, исходящие и reasoning; так считает Kilo. Обработано контекста - полный промпт каждого запроса, кэш перечитывается заново. Активное время: паузы больше 15 минут не учитываются.</p>
        <?php echo analytics_charts_html('task', $charts); ?>
        </details>
        <table class="data">
          <tr><th>Сессия</th><th>Дата</th><th>Роль</th><th>Модель</th><th>Провайдер</th><th class="num">Запросов</th><th class="num">Токены без кэша</th><th class="num">Контекст с кэшем</th><th class="num">Активно</th><th class="num">Находки</th><th class="num">Стоимость</th><th>Финал</th></tr>
          <?php foreach ($task_analytics['sessions'] as $row): ?>
            <tr>
              <td><code title="<?php echo h($row['session_id']); ?>"><?php echo h(substr($row['session_id'], 0, 14)); ?></code></td>
              <td><?php echo h($row['date']); ?></td>
              <td><?php echo h($row['role']); ?></td>
              <td><?php echo h($row['model']); ?></td>
              <td><?php echo h(provider_label(isset($row['provider']) ? $row['provider'] : '')); ?></td>
              <td class="num"><?php echo h(fmt_num($row['requests'])); ?></td>
              <td class="num"><?php echo h(fmt_num($row['tokens_in'] + $row['tokens_out'] + $row['reasoning'])); ?></td>
              <td class="num"><?php echo h(fmt_num($row['tokens_in'] + $row['cache_read'] + $row['cache_write'])); ?></td>
              <td class="num"><?php echo h(fmt_minutes($row['active_ms'])); ?></td>
              <td class="num"><?php echo (int)$row['findings']; ?></td>
              <td class="num"><?php echo h(number_format(isset($row['cost']) ? $row['cost'] : 0, 2, '.', '')); ?> <?php echo h(price_currency(isset($row['provider']) ? $row['provider'] : '')); ?></td>
              <td><?php echo $row['final'] ? '<span class="badge fresh">done</span>' : '<span class="badge stale">open</span>'; ?></td>
            </tr>
          <?php endforeach; ?>
        </table>
        <?php echo analytics_tables_html(array(
            'tools' => $task_analytics['tools'],
            'mcp' => $task_analytics['mcp'],
            'cli' => $task_analytics['cli'],
            'models' => $task_analytics['models'],
            'providers' => $task_analytics['providers'],
            'findings' => $task_analytics['findings'],
        )); ?>
      <?php else: ?>
        <p class="muted">Для этой задачи диалогов в базе нет. Проверить: <code>python3 .agents/skills/task-router/children/analytics/scripts/task-analytics.py report --task <?php echo h($s['id']); ?></code></p>
      <?php endif; ?>

      <?php $cr = $task_detail['change_report']; ?>
      <h2 id="business">Бизнес-аналитика</h2>
      <?php if ($cr !== null): ?>
        <?php
          $biz_summary = isset($cr['summary']) && is_array($cr['summary']) ? $cr['summary'] : array();
          $biz_logic = isset($cr['logic']) && is_array($cr['logic']) ? $cr['logic'] : array();
          $biz_business_changes = isset($cr['business_changes']) && is_array($cr['business_changes']) ? $cr['business_changes'] : array();
          $biz_changes = isset($cr['changes']) && is_array($cr['changes']) ? $cr['changes'] : array();
          $biz_risks = isset($cr['risks']) && is_array($cr['risks']) ? $cr['risks'] : array();
          $biz_tests = isset($cr['tests']) && is_array($cr['tests']) ? $cr['tests'] : array();
        ?>
        <div class="biz-grid">
          <div class="biz-card"><h3>Проблема</h3><p><?php echo nl2br(h(isset($biz_summary['problem']) ? $biz_summary['problem'] : '')); ?></p></div>
          <div class="biz-card"><h3>Решение</h3><p><?php echo nl2br(h(isset($biz_summary['solution']) ? $biz_summary['solution'] : '')); ?></p></div>
          <div class="biz-card"><h3>Результат</h3><p><?php echo nl2br(h(isset($biz_summary['result']) ? $biz_summary['result'] : '')); ?></p></div>
        </div>
        <div class="biz-logic">
          <div><h4>Было</h4><p><?php echo nl2br(h(biz_text(isset($biz_logic['before']) ? $biz_logic['before'] : ''))); ?></p></div>
          <div><h4>Стало</h4><p><?php echo nl2br(h(biz_text(isset($biz_logic['after']) ? $biz_logic['after'] : ''))); ?></p></div>
          <div><h4>Дельта</h4><p><?php echo nl2br(h(biz_text(isset($biz_logic['delta']) ? $biz_logic['delta'] : ''))); ?></p></div>
        </div>
        <?php if ($biz_business_changes): ?>
        <h3>Что меняется для бизнеса</h3>
        <table class="data">
          <tr><th>Что меняется</th><th>Правило</th><th>Код</th><th>Тесты</th></tr>
          <?php foreach ($biz_business_changes as $change): ?>
          <tr>
            <td><?php echo h(isset($change['title']) ? $change['title'] : ''); ?></td>
            <td><?php echo nl2br(h(isset($change['statement']) ? $change['statement'] : '')); ?></td>
            <td><?php echo h(isset($change['code']) && is_array($change['code']) ? implode(', ', $change['code']) : ''); ?></td>
            <td><?php echo h(isset($change['tests']) && is_array($change['tests']) ? implode(', ', $change['tests']) : ''); ?></td>
          </tr>
          <?php endforeach; ?>
        </table>
        <?php endif; ?>
        <?php if ($biz_changes): ?>
        <details class="collapse">
          <summary>Технические изменения (<?php echo count($biz_changes); ?>)</summary>
          <table class="data">
            <tr><th>Что</th><th>Было</th><th>Стало</th><th>Зачем</th></tr>
            <?php foreach ($biz_changes as $change): ?>
            <tr>
              <td><?php echo h(isset($change['title']) ? $change['title'] : ''); ?></td>
              <td><?php echo nl2br(h(biz_text(isset($change['before']) ? $change['before'] : ''))); ?></td>
              <td><?php echo nl2br(h(biz_text(isset($change['after']) ? $change['after'] : ''))); ?></td>
              <td><?php echo nl2br(h(biz_text(isset($change['rationale']) ? $change['rationale'] : ''))); ?></td>
            </tr>
            <?php endforeach; ?>
          </table>
        </details>
        <?php endif; ?>
        <div class="biz-meta">
          <span>Риски: <?php echo count($biz_risks); ?></span>
          <span>Проверки: <?php echo count($biz_tests); ?></span>
          <?php if (!empty($cr['_has_html'])): ?>
            <a class="btn" href="/files/tasks/<?php echo h($s['id']); ?>/reports/change-report/report.html" target="_blank" rel="noopener">Открыть полный отчёт</a>
          <?php endif; ?>
        </div>
      <?php else: ?>
        <?php $fallback_facts = isset($task_detail['business_logic']['facts']) && is_array($task_detail['business_logic']['facts']) ? $task_detail['business_logic']['facts'] : array(); ?>
        <?php $fallback_unconfirmed = isset($task_detail['business_logic']['unconfirmed']) && is_array($task_detail['business_logic']['unconfirmed']) ? $task_detail['business_logic']['unconfirmed'] : array(); ?>
        <?php if ($fallback_facts): ?>
          <p class="muted">Полный change-report не сформирован. Verified бизнес-правила задачи доступны в разделе <a href="#business-logic">Бизнес-логика</a>.</p>
        <?php elseif ($fallback_unconfirmed): ?>
          <p class="muted">Полный change-report не сформирован. Подтвержденных правил нет, правила из карантина с метриками доступны в разделе <a href="#business-logic">Бизнес-логика</a>.</p>
        <?php else: ?>
          <p class="muted">Бизнес-отчёт не сформирован: для задачи нет <code>report-model.json</code> и нет verified бизнес-правил. Его готовит скил <code>task-change-report</code>.</p>
        <?php endif; ?>
      <?php endif; ?>

      <?php if (!empty($task_detail['relations'])): ?>
      <h2 id="related-tasks">Связанные задачи</h2>
      <ul class="related-tasks">
        <?php foreach ($task_detail['relations'] as $rel): ?>
          <?php
            $target = isset($rel['target']['document_id']) ? (string)$rel['target']['document_id'] : '';
            if (!preg_match('/task:(\d+)/', $target, $m)) { continue; }
            $relId = $m[1];
            $reason = isset($rel['reason']) ? (string)$rel['reason'] : '';
          ?>
          <li><a href="<?php echo h(self_url(array('tab' => 'tasks', 'id' => $relId))); ?>">CT-<?php echo h($relId); ?></a><?php if ($reason !== ''): ?> · <?php echo h($reason); ?><?php endif; ?></li>
        <?php endforeach; ?>
      </ul>
      <?php endif; ?>

      <?php if ($task_detail['tags']): ?>
        <p>Теги: <?php foreach ($task_detail['tags'] as $tg) { echo '<span class="tag">' . h(is_array($tg) ? json_encode($tg, JSON_UNESCAPED_UNICODE) : $tg) . '</span> '; } ?></p>
      <?php endif; ?>

      <?php $visible_sections = array_values(array_filter($task_detail['sections'], function ($sec) { return trim((string)($sec['body_markdown'] ?? '')) !== '' && mb_stripos($sec['title'], 'Связанные задачи') === false; })); ?>
      <h2>Содержание</h2>
      <ul class="toc">
        <?php foreach ($visible_sections as $sec): ?>
          <li><a href="#<?php echo h($sec['id']); ?>"><?php echo h($sec['title']); ?></a></li>
        <?php endforeach; ?>
      </ul>
      <?php foreach ($visible_sections as $sec): ?>
        <section id="<?php echo h($sec['id']); ?>">
          <h2><?php echo h($sec['title']); ?></h2>
          <div class="<?php echo (mb_stripos($sec['title'], 'История') !== false || mb_stripos($sec['title'], 'Принятые решения') !== false) ? 'history-list' : ((mb_stripos($sec['title'], 'Заметки') !== false || mb_stripos($sec['title'], 'Сделано') !== false || mb_stripos($sec['title'], 'В процессе') !== false) ? 'task-notes' : ''); ?>">
            <?php echo md_render(isset($sec['body_markdown']) ? $sec['body_markdown'] : ''); ?>
          </div>
        </section>
      <?php endforeach; ?>

      <h2>Файлы (<?php echo count($task_detail['files']); ?>)</h2>
      <?php if ($task_detail['files']): ?>
      <table>
        <tr><th>ID</th><th>Путь</th><th>Состояние</th></tr>
        <?php foreach ($task_detail['files'] as $f): ?>
          <tr><td><?php echo h($f['id']); ?></td><td><code><?php echo h($f['path']); ?></code></td><td><?php echo h(isset($f['state']) ? $f['state'] : ''); ?></td></tr>
        <?php endforeach; ?>
      </table>
      <?php else: ?><p class="muted">Файлы в task.json не зафиксированы.</p><?php endif; ?>

      <h2>Подводные камни (<?php echo count($task_detail['findings']); ?>)</h2>
      <?php foreach ($task_detail['findings'] as $fn): ?>
        <div class="finding"><strong><?php echo h(isset($fn['id']) ? $fn['id'] : ''); ?> <?php echo h(isset($fn['title']) ? $fn['title'] : ''); ?></strong>
        <div><?php echo md_render(isset($fn['statement']) ? $fn['statement'] : ''); ?></div></div>
      <?php endforeach; ?>
      <?php if (!$task_detail['findings']): ?><p class="muted">Нет.</p><?php endif; ?>

      <?php if ($task_detail['decisions']): ?>
      <h2>Решения (<?php echo count($task_detail['decisions']); ?>)</h2>
      <ul><?php foreach ($task_detail['decisions'] as $dc): ?>
        <li><?php echo h(is_array($dc) ? (isset($dc['title']) ? $dc['title'] : json_encode($dc, JSON_UNESCAPED_UNICODE)) : $dc); ?></li>
      <?php endforeach; ?></ul>
      <?php endif; ?>

      <h2>Дифф (diff.files.md)</h2>
      <?php if ($task_detail['diff']['present']): ?>
        <p>Unique files: <?php echo (int)$task_detail['diff']['unique']; ?></p>
        <ul class="files"><?php foreach ($task_detail['diff']['files'] as $fp): ?>
          <li><code><?php echo h($fp); ?></code></li>
        <?php endforeach; ?></ul>
      <?php else: ?><p class="muted">diff.files.md отсутствует.</p><?php endif; ?>

      <h2>Отчеты (workflow-context.json)</h2>
      <?php if ($task_detail['reports']): foreach ($task_detail['reports'] as $rep): ?>
        <div class="report">
          <strong><?php echo h($rep['report']); ?></strong>
          <span class="muted">шагов <?php echo (int)$rep['n_steps']; ?>, файлов scope <?php echo count($rep['scope_files']); ?>, коммитов <?php echo count($rep['scope_commits']); ?></span>
          <table>
            <tr><th>Источник</th><th>Роль</th><th>Свежесть</th></tr>
            <?php foreach ($rep['sources'] as $src): ?>
              <tr><td><code><?php echo h($src['path']); ?></code></td><td><?php echo h($src['role']); ?></td>
              <td><span class="badge <?php echo h($src['state']); ?>"><?php echo h($src['state']); ?></span></td></tr>
            <?php endforeach; ?>
          </table>
        </div>
      <?php endforeach; else: ?><p class="muted">Отчетов нет.</p><?php endif; ?>

      <?php if ($task_detail['task_md'] !== null): ?>
      <details><summary>task.md (сырой экспорт Jira)</summary><pre><?php echo h($task_detail['task_md']); ?></pre></details>
      <?php endif; ?>
    <?php endif; ?>

    <?php if ($arch_detail !== null): $as = $arch_detail['summary']; ?>
      <div class="crumbs"><a href="<?php echo h(self_url(array('tab' => 'docs'))); ?>">Документация</a> / <?php echo h($as['name']); ?></div>
      <h1><?php echo h($as['title']); ?></h1>
      <table class="meta">
        <tr><th>Файл</th><td><code>architecture/<?php echo h($as['name']); ?>.json</code></td></tr>
        <tr><th>Статус</th><td><?php echo h($as['status']); ?></td></tr>
        <tr><th>Обновлено</th><td><?php echo h($as['updated']); ?></td></tr>
        <tr><th>Счетчики</th><td>секций <?php echo (int)$as['n_sections']; ?>, находок <?php echo (int)$as['n_findings']; ?></td></tr>
      </table>
      <h2>Содержание</h2>
      <ul class="toc">
        <?php foreach ($arch_detail['sections'] as $sec): ?>
          <li><a href="#<?php echo h($sec['id']); ?>"><?php echo h($sec['title']); ?></a></li>
        <?php endforeach; ?>
      </ul>
      <?php foreach ($arch_detail['sections'] as $sec): ?>
        <section id="<?php echo h($sec['id']); ?>">
          <h2><?php echo h($sec['title']); ?></h2>
          <?php echo md_render(isset($sec['body_markdown']) ? $sec['body_markdown'] : ''); ?>
        </section>
      <?php endforeach; ?>
      <h2>Подводные камни (<?php echo count($arch_detail['findings']); ?>)</h2>
      <?php foreach ($arch_detail['findings'] as $fn): ?>
        <div class="finding"><strong><?php echo h(isset($fn['id']) ? $fn['id'] : ''); ?> <?php echo h(isset($fn['title']) ? $fn['title'] : ''); ?></strong>
        <div><?php echo md_render(isset($fn['statement']) ? $fn['statement'] : ''); ?></div></div>
      <?php endforeach; ?>
      <?php if (!$arch_detail['findings']): ?><p class="muted">Нет.</p><?php endif; ?>
    <?php endif; ?>
  </main>

  <aside>
    <?php if ($tab === 'tasks'): ?>
    <form method="get" class="filter">
      <input type="hidden" name="tab" value="tasks">
      <label>Проект диалогов
        <select name="project">
          <option value="">все</option>
          <?php foreach ($project_options as $p): ?>
            <option value="<?php echo h($p['id']); ?>"<?php echo $p['id'] === $project_filter ? ' selected' : ''; ?>><?php echo h($p['label']); ?> (<?php echo (int)$p['count']; ?>)</option>
          <?php endforeach; ?>
        </select>
      </label>
      <label>Релиз
        <select name="release">
          <option value="">все</option>
          <?php foreach ($releases as $r): ?>
            <option value="<?php echo h($r); ?>"<?php echo $r === $rel_filter ? ' selected' : ''; ?>><?php echo h($r); ?></option>
          <?php endforeach; ?>
        </select>
      </label>
      <label>Ответственный
        <select name="assignee">
          <option value="">все</option>
          <?php foreach ($assignees as $name => $count): ?>
            <option value="<?php echo h($name); ?>"<?php echo $name === $assignee_filter ? ' selected' : ''; ?>><?php echo h($name); ?> (<?php echo (int)$count; ?>)</option>
          <?php endforeach; ?>
        </select>
      </label>
      <label>Поиск<input type="search" id="side-search" name="q" value="<?php echo h($q); ?>" placeholder="номер или слово"></label>
      <label class="check"><input type="checkbox" name="unassigned" value="1"<?php echo $show_unassigned ? ' checked' : ''; ?>> Диалоги без задач</label>
      <button type="submit">Применить</button>
    </form>
    <ul class="side-list" id="side-list">
      <?php if ($show_unassigned): ?>
      <li class="side-sep"><span class="side-sep-title">Диалоги без задачи</span><span class="trel"><?php echo count($unassigned_sessions); ?></span></li>
      <?php foreach ($unassigned_sessions as $u): ?>
      <li data-search="<?php echo h($u['session_id'] . ' ' . $u['role'] . ' ' . $u['model'] . ' ' . $u['title'] . ' ' . $u['project_label']); ?>" class="<?php echo $u['session_id'] === $sel_session ? 'sel' : ''; ?>">
        <a href="<?php echo h(self_url(array_merge($side_params, array('session' => $u['session_id'])))); ?>">
          <span class="tid u"><?php echo h(substr($u['session_id'], 0, 14)); ?></span>
          <span class="trel">без задачи</span>
          <span class="jstatus-sm"><?php echo h($u['role'] !== '' ? $u['role'] : 'сессия'); ?></span>
          <span class="ttitle"><?php echo h($u['title'] !== '' ? $u['title'] : ($u['model'] !== '' ? $u['model'] : 'нет первого сообщения')); ?></span>
          <span class="tmeta"><?php if ($u['project_label'] !== '') { echo 'проект ' . h($u['project_label']) . ' · '; } ?><?php if ($u['model'] !== '') { echo h($u['model']) . ' · '; } ?><?php echo h($u['date']); ?><?php if ($u['date'] !== '') { echo ' · '; } ?><?php echo h(fmt_num($u['tokens'])); ?> токенов без кэша · <?php echo (int)$u['tool_calls']; ?> вызовов · <?php echo h(fmt_minutes($u['active_ms'])); ?><?php if ($u['findings'] > 0) { echo ' · находки ' . (int)$u['findings']; } ?> · <?php echo h(number_format(isset($u['cost']) ? $u['cost'] : 0, 2, '.', '')); ?> <?php echo h(price_currency(isset($u['provider']) ? $u['provider'] : '')); ?></span>
        </a>
      </li>
      <?php endforeach; ?>
      <?php if (!$unassigned_sessions): ?><li class="side-empty muted">Нет диалогов без задачи.</li><?php endif; ?>
      <li class="side-sep"><span class="side-sep-title">Задачи</span><span class="trel"><?php echo count($filtered); ?></span></li>
      <?php endif; ?>
      <?php foreach ($filtered as $t): ?>
      <li data-search="<?php echo h($t['id'] . ' ' . $t['title']); ?>" class="<?php echo $t['id'] === $sel_task ? 'sel' : ''; ?>">
        <a href="<?php echo h(self_url(array_merge($side_params, array('id' => $t['id'])))); ?>">
          <span class="tid">#<?php echo h($t['id']); ?></span>
          <span class="trel"><?php echo h($t['release']); ?></span>
          <?php if ($t['n_dialogs'] > 0): ?><span class="tbadge">диалоги <?php echo (int)$t['n_dialogs']; ?></span><?php endif; ?>
          <span class="jstatus-sm"><?php echo h($t['jira_status']); ?></span>
          <span class="ttitle"><?php echo h($t['title']); ?></span>
          <span class="tmeta" title="Jira: <?php echo h($t['jira_updated'] !== '' ? $t['jira_updated'] : 'нет'); ?> | локально: <?php echo h($t['last_touched'] !== '' ? $t['last_touched'] : 'нет'); ?>"><?php
            if ($t['jira_updated'] !== '') {
                echo 'Jira ' . h($t['jira_updated']);
            } elseif ($t['last_touched'] !== '') {
                echo 'лок. ' . h($t['last_touched']);
            }
            if ($t['analytics_tokens'] > 0) { echo ' · ' . h(fmt_num($t['analytics_tokens'])) . ' токенов без кэша'; }
            if ($t['assignee'] !== '') { echo ' · отв. ' . h($t['assignee']); }
          ?></span>
          <?php if (isset($t['analytics_cost']) && $t['analytics_cost'] > 0): ?><span class="tcost"><?php echo h(number_format($t['analytics_cost'], 2, '.', '')); ?> <?php echo h(price_currency()); ?></span><?php endif; ?>
        </a>
      </li>
      <?php endforeach; ?>
    </ul>
    <p class="muted">Показано <?php echo count($filtered); ?> из <?php echo count($tasks); ?><?php if ($show_unassigned): ?> · без задачи: <?php echo count($unassigned_sessions); ?><?php endif; ?>.</p>
    <?php elseif ($tab === 'docs'): ?>
    <form method="get" class="filter">
      <input type="hidden" name="tab" value="docs">
      <label>Поиск<input type="search" id="side-search" name="q" value="<?php echo h($q); ?>" placeholder="имя или заголовок"></label>
      <button type="submit">Применить</button>
    </form>
    <ul class="side-list" id="side-list">
      <?php foreach ($arch_filtered as $a): ?>
      <li data-search="<?php echo h($a['name'] . ' ' . $a['title']); ?>" class="<?php echo $a['name'] === $sel_doc ? 'sel' : ''; ?>">
        <a href="<?php echo h(self_url(array('tab' => 'docs', 'doc' => $a['name'], 'q' => $tab === 'docs' ? $q : ''))); ?>">
          <span class="ttitle"><?php echo h($a['title']); ?></span>
          <span class="tmeta"><?php echo h($a['name']); ?><?php if ($a['updated'] !== '') { echo ' · ' . h($a['updated']); } ?></span>
        </a>
      </li>
      <?php endforeach; ?>
    </ul>
    <p class="muted">Показано <?php echo count($arch_filtered); ?> из <?php echo count($arch_list); ?>.</p>
    <?php else: ?>
    <h3 class="side-title">Топ задач по токенам</h3>
    <ul class="side-list">
      <?php if ($analytics !== null): foreach (array_slice($analytics['tasks'], 0, 15) as $row): ?>
      <li>
        <a href="<?php echo h(self_url(array('tab' => 'tasks', 'id' => $row['id']))); ?>">
          <span class="tid">#<?php echo h($row['id']); ?></span>
          <span class="tmeta"><?php echo h(fmt_num($row['tokens'])); ?> токенов без кэша · <?php echo h(fmt_minutes($row['active_ms'])); ?></span>
          <?php if (isset($row['cost']) && $row['cost'] > 0): ?><span class="tcost"><?php echo h(number_format($row['cost'], 2, '.', '')); ?> <?php echo h(price_currency()); ?></span><?php endif; ?>
          <span class="ttitle"><?php echo h($row['title']); ?></span>
        </a>
      </li>
      <?php endforeach; endif; ?>
    </ul>
    <p class="muted">Без задачи: <?php echo (int)$analytics['unassigned']['sessions']; ?> сессий, <?php echo h(fmt_num($analytics['unassigned']['tokens'])); ?> токенов.</p>
    <?php endif; ?>
  </aside>
</div>
<?php if ($charts): ?>
<script type="application/json" id="chart-data"><?php echo json_encode($charts, JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT); ?></script>
<?php endif; ?>
<script src="/assets/app.js"></script>
</body>
</html>

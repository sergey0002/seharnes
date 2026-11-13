<?php
// Harness admin page: canon control, Git update, link and documentation scans.
// PHP 7.1 compatible. Read-only except the explicit job actions.

function harness_admin_root() {
    $root = repo_root();
    return $root === false ? '' : $root;
}

function harness_admin_source() {
    $root = harness_admin_root();
    if ($root === '') {
        return array('configured' => false);
    }
    foreach (array('.doc/harness-source.json', '.doc/harness-source.example.json') as $name) {
        $path = $root . '/' . $name;
        if (!is_file($path)) {
            continue;
        }
        $raw = @file_get_contents($path);
        $data = $raw === false ? null : json_decode($raw, true);
        if (!is_array($data)) {
            continue;
        }
        return array(
            'configured' => $name === '.doc/harness-source.json',
            'file' => $name,
            'url' => isset($data['url']) ? (string) $data['url'] : '',
            'ref' => isset($data['ref']) ? (string) $data['ref'] : '',
            'profile' => isset($data['profile']) ? (string) $data['profile'] : '',
        );
    }
    return array('configured' => false);
}

function harness_admin_receipt() {
    $root = harness_admin_root();
    $path = $root . '/.doc/web/state/transfer/receipt.json';
    if (!is_file($path)) {
        return array('present' => false);
    }
    $raw = @file_get_contents($path);
    $data = $raw === false ? null : json_decode($raw, true);
    if (!is_array($data)) {
        return array('present' => false);
    }
    return array(
        'present' => true,
        'profile' => isset($data['profile']) ? (string) $data['profile'] : '',
        'commit' => isset($data['commit']) ? substr((string) $data['commit'], 0, 12) : '',
        'files' => isset($data['files']) && is_array($data['files']) ? count($data['files']) : 0,
        'mtime' => date('Y-m-d H:i', (int) filemtime($path)),
    );
}

function harness_admin_audit($checks) {
    $root = harness_admin_root();
    $script = $root . '/.agents/skills/harness-router/children/harness-core/scripts/audit_harness.py';
    if ($root === '' || !is_file($script)) {
        return array('status' => 'failed', 'error' => 'audit script missing');
    }
    $allowed = array('canon', 'links', 'docs');
    $selected = array();
    foreach (explode(',', (string) $checks) as $item) {
        $item = trim($item);
        if (in_array($item, $allowed, true)) {
            $selected[] = $item;
        }
    }
    if (!$selected) {
        $selected = $allowed;
    }
    $command = 'python3 ' . escapeshellarg($script)
        . ' --root ' . escapeshellarg($root)
        . ' --checks ' . escapeshellarg(implode(',', $selected))
        . ' --json 2>&1';
    $output = shell_exec($command);
    $data = is_string($output) ? json_decode(trim($output), true) : null;
    if (!is_array($data)) {
        return array('status' => 'failed', 'error' => 'audit failed', 'raw' => substr((string) $output, 0, 2000));
    }
    return $data;
}

function harness_admin_h($value) {
    return htmlspecialchars((string) $value, ENT_QUOTES, 'UTF-8');
}

function harness_admin_page() {
    $source = harness_admin_source();
    $receipt = harness_admin_receipt();
    $root = harness_admin_root();
    header('Content-Type: text/html; charset=utf-8');
    header('Cache-Control: no-store');
    ?>
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Харнес: контроль и обновление</title>
<style>
 body { font-family: system-ui, -apple-system, Segoe UI, sans-serif; margin: 0; background: #f6f7f9; color: #1c1f23; }
 header { background: #1c1f23; color: #fff; padding: 14px 22px; display: flex; gap: 18px; align-items: center; }
 header a { color: #cbd5e1; text-decoration: none; font-size: 14px; }
 header a:hover { color: #fff; }
 main { padding: 22px; max-width: 1180px; margin: 0 auto; }
 section { background: #fff; border: 1px solid #e2e6ea; border-radius: 10px; padding: 16px 18px; margin-bottom: 16px; }
 h2 { font-size: 16px; margin: 0 0 12px; }
 h3 { font-size: 14px; margin: 16px 0 8px; color: #475569; }
 .row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
 button { font: inherit; padding: 8px 14px; border-radius: 8px; border: 1px solid #cbd5e1; background: #fff; cursor: pointer; }
 button.primary { background: #1d4ed8; border-color: #1d4ed8; color: #fff; }
 button.danger { border-color: #b91c1c; color: #b91c1c; }
 button:disabled { opacity: .55; cursor: default; }
 table { border-collapse: collapse; width: 100%; font-size: 13px; }
 th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #eef1f4; vertical-align: top; }
 code, pre { background: #f1f5f9; border-radius: 6px; }
 pre { padding: 10px; overflow: auto; max-height: 340px; font-size: 12px; }
 .pill { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 12px; font-weight: 600; }
 .ok { background: #dcfce7; color: #166534; }
 .bad { background: #fee2e2; color: #991b1b; }
 .warn { background: #fef3c7; color: #92400e; }
 .muted { color: #64748b; font-size: 13px; }
 .log { white-space: pre-wrap; font-size: 12px; background: #0f172a; color: #e2e8f0; padding: 10px; border-radius: 8px; max-height: 300px; overflow: auto; }
</style>
</head>
<body>
<header>
  <strong>Харнес</strong>
  <a href="/">Задачи</a>
  <a href="/harness/">Просмотрщик графа</a>
  <a href="/harness-admin/">Контроль и обновление</a>
</header>
<main>

<section>
  <h2>Источник и состояние</h2>
  <table>
    <tr><th style="width:220px">Источник</th><td>
      <?php if (!empty($source['configured'])): ?>
        <code><?php echo harness_admin_h($source['url']); ?></code>,
        ref <code><?php echo harness_admin_h($source['ref']); ?></code>,
        профиль <code><?php echo harness_admin_h($source['profile']); ?></code>
      <?php else: ?>
        <span class="pill warn">не настроен</span>
        <span class="muted">Создайте <code>.doc/harness-source.json</code> на основе <code>.doc/harness-source.example.json</code>.</span>
      <?php endif; ?>
    </td></tr>
    <tr><th>Последняя установка</th><td>
      <?php if (!empty($receipt['present'])): ?>
        профиль <code><?php echo harness_admin_h($receipt['profile']); ?></code>,
        коммит <code><?php echo harness_admin_h($receipt['commit']); ?></code>,
        файлов <?php echo (int) $receipt['files']; ?>,
        <?php echo harness_admin_h($receipt['mtime']); ?>
      <?php else: ?>
        <span class="pill warn">receipt отсутствует</span>
        <span class="muted">Первый перенос/обновление создаст его; без baseline локальные файлы считаются изменёнными и сохраняются.</span>
      <?php endif; ?>
    </td></tr>
    <tr><th>Корень</th><td><code><?php echo harness_admin_h($root); ?></code></td></tr>
  </table>
</section>

<section>
  <h2>Действия</h2>
  <div class="row">
    <button data-job="harness_update" data-confirm="1">Предпросмотр обновления из Git</button>
    <button class="primary" data-job="harness_update_apply" data-confirm="1">Обновить харнес из Git</button>
    <button data-job="sync_views" data-confirm="1">Пересобрать вью сред</button>
    <button data-job="harness_build">Пересобрать граф</button>
    <button data-job="harness_check">Проверить граф</button>
  </div>
  <h3>Сканы</h3>
  <div class="row">
    <button data-scan="canon">Контроль канона и мусора</button>
    <button data-scan="links">Битые ссылки</button>
    <button data-scan="docs">Документация и JSON</button>
    <button data-scan="canon,links,docs">Все сканы</button>
  </div>
  <div id="job-log" class="log" style="display:none"></div>
</section>

<section>
  <h2>Результат сканов</h2>
  <div id="scan-out" class="muted">Нажмите кнопку скана.</div>
</section>

</main>
<script>
(function () {
  function post(url, body) {
    return fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}, body: JSON.stringify(body)})
      .then(function (r) { return r.json(); });
  }
  function showLog(text) {
    var box = document.getElementById('job-log');
    box.style.display = 'block';
    box.textContent = text;
  }
  function poll(id) {
    fetch('/jobs/status?id=' + encodeURIComponent(id), {headers: {'X-Requested-With': 'XMLHttpRequest'}})
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var tail = (data.log_tail || []).join('\n');
        showLog((data.status || '') + ' · ' + (data.message || '') + '\n' + tail);
        if (data.status === 'queued' || data.status === 'running') {
          setTimeout(function () { poll(id); }, 2000);
        }
      })
      .catch(function (e) { showLog('ошибка опроса: ' + e); });
  }
  document.querySelectorAll('button[data-job]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var action = btn.getAttribute('data-job');
      if (btn.getAttribute('data-confirm') === '1' && !window.confirm('Запустить ' + action + '?')) {
        return;
      }
      btn.disabled = true;
      post('/jobs', {action: action, params: {}})
        .then(function (res) {
          btn.disabled = false;
          if (res && res.id) { showLog('запущено ' + res.id); poll(res.id); }
          else { showLog('ошибка запуска: ' + JSON.stringify(res)); }
        })
        .catch(function (e) { btn.disabled = false; showLog('ошибка: ' + e); });
    });
  });

  function renderScan(data) {
    var out = document.getElementById('scan-out');
    var html = '';
    if (!data || !data.checks) {
      out.innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
      return;
    }
    data.checks.forEach(function (check) {
      var pill = check.status === 'passed' ? 'ok' : 'bad';
      html += '<h3>' + check.check + ' <span class="pill ' + pill + '">' + check.status + '</span></h3>';
      if (check.check === 'canon') {
        html += '<table>'
          + '<tr><th>Канон обязательных файлов</th><td>' + (check.missing_required.length ? '<span class="pill bad">' + check.missing_required.length + '</span>' : '<span class="pill ok">OK</span>') + '</td></tr>'
          + '<tr><th>Секреты в дереве</th><td>' + check.secrets.count + '</td></tr>'
          + '<tr><th>Мусор вне структуры</th><td>' + check.junk.count + (check.junk.tops.length ? ' <span class="muted">(' + check.junk.tops.join(', ') + ')</span>' : '') + '</td></tr>'
          + '<tr><th>Сгенерированные вью</th><td>' + check.generated_views.count + ' <span class="muted">пересобираются синком, не правятся руками</span></td></tr>'
          + '<tr><th>Runtime-состояние</th><td>' + check.runtime_state.count + '</td></tr>'
          + '</table>';
        if (check.junk.sample.length) {
          html += '<pre>' + check.junk.sample.join('\n') + '</pre>';
        }
      } else if (check.check === 'links') {
        html += '<p>Битых ссылок: <strong>' + check.broken_total + '</strong> в ' + check.files + ' файлах.</p>';
        html += '<table><tr><th>Файл</th><th>Ссылок</th><th>Примеры</th></tr>';
        check.top.slice(0, 15).forEach(function (row) {
          html += '<tr><td><code>' + row.file + '</code></td><td>' + row.count + '</td><td><code>' + row.links.slice(0, 3).join('</code>, <code>') + '</code></td></tr>';
        });
        html += '</table>';
      } else {
        html += '<table>'
          + '<tr><th>Ошибки JSON</th><td>' + check.json_errors.length + '</td></tr>'
          + '<tr><th>Без front matter</th><td>' + check.missing_front_matter.length + '</td></tr>'
          + '<tr><th>Не в индексе</th><td>' + check.unindexed.length + '</td></tr>'
          + '</table>';
        if (check.json_errors.length) {
          html += '<pre>' + check.json_errors.map(function (e) { return e.file + ': ' + e.error; }).join('\n') + '</pre>';
        }
      }
    });
    out.innerHTML = html;
  }

  document.querySelectorAll('button[data-scan]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var checks = btn.getAttribute('data-scan');
      btn.disabled = true;
      document.getElementById('scan-out').textContent = 'сканирую…';
      fetch('/harness-admin/api/audit?checks=' + encodeURIComponent(checks))
        .then(function (r) { return r.json(); })
        .then(function (data) { btn.disabled = false; renderScan(data); })
        .catch(function (e) { btn.disabled = false; document.getElementById('scan-out').textContent = 'ошибка: ' + e; });
    });
  });
})();
</script>
</body>
</html>
    <?php
    return true;
}

function harness_admin_serve($path) {
    if ($path === '/harness-admin') {
        header('Location: /harness-admin/', true, 301);
        return true;
    }
    $method = isset($_SERVER['REQUEST_METHOD']) ? strtoupper((string) $_SERVER['REQUEST_METHOD']) : 'GET';
    if ($path === '/harness-admin/' && $method === 'GET') {
        return harness_admin_page();
    }
    if ($path === '/harness-admin/api/status' && $method === 'GET') {
        harness_send_json(array('status' => 'ok', 'source' => harness_admin_source(),
                                'receipt' => harness_admin_receipt(), 'root' => harness_admin_root()));
        return true;
    }
    if ($path === '/harness-admin/api/audit' && $method === 'GET') {
        $checks = isset($_GET['checks']) ? (string) $_GET['checks'] : 'canon,links,docs';
        $report = harness_admin_audit($checks);
        harness_send_json($report, isset($report['status']) && $report['status'] === 'failed' ? 200 : 200);
        return true;
    }
    http_response_code(404);
    echo 'not found';
    return true;
}

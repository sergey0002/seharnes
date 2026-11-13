// .doc/web/public/assets/app.js - живой фильтр списка и графики Chart.js.
// Серверный фильтр через форму и таблицы остаются fallback без JS/CDN.
(function () {
  var input = document.getElementById('side-search');
  var list = document.getElementById('side-list');
  if (input && list) {
    input.addEventListener('input', function () {
      var needle = input.value.toLowerCase();
      var items = list.getElementsByTagName('li');
      for (var i = 0; i < items.length; i++) {
        var hay = (items[i].getAttribute('data-search') || '').toLowerCase();
        items[i].style.display = hay.indexOf(needle) === -1 ? 'none' : '';
      }
    });
  }
})();

(function () {
  var form = document.querySelector('form.filter');
  if (!form) {
    return;
  }
  var project = form.querySelector('select[name="project"]');
  var unassigned = form.querySelector('input[name="unassigned"]');
  if (project && unassigned) {
    project.addEventListener('change', function () {
      if (project.value !== '') {
        unassigned.checked = true;
      }
      var expires = project.value === ''
        ? 'Thu, 01 Jan 1970 00:00:00 GMT'
        : new Date(Date.now() + 15552000 * 1000).toUTCString();
      document.cookie = 'panel_project=' + encodeURIComponent(project.value) + '; path=/; expires=' + expires;
    });
  }
})();

(function () {
  var holder = document.getElementById('chart-data');
  if (!holder) {
    return;
  }
  var charts;
  try {
    charts = JSON.parse(holder.textContent || '{}');
  } catch (e) {
    return;
  }
  function fmtNumber(value) {
    return Number(value).toLocaleString('ru-RU');
  }
  function fallback(canvas, config) {
    var box = canvas.parentNode;
    var labels = (config.data && config.data.labels) || [];
    var dataset = (config.data && config.data.datasets && config.data.datasets[0]) || {};
    var values = dataset.data || [];
    var colors = dataset.backgroundColor || '#2563eb';
    if (!Array.isArray(colors)) {
      var single = colors;
      colors = [];
      for (var c = 0; c < values.length; c++) { colors.push(single); }
    }
    var datasets = (config.data && config.data.datasets) || [];
    var html = '';
    if (datasets.length > 1) {
      var maxima = datasets.map(function (ds) {
        return Math.max.apply(null, (ds.data || []).concat([1]));
      });
      html = '<div class="fallback-groups">';
      for (var g = 0; g < labels.length; g++) {
        html += '<div class="fg-row"><span class="fg-label" title="' + labels[g] + '">' + labels[g] + '</span><span class="fg-bars">';
        for (var d = 0; d < datasets.length; d++) {
          var val = (datasets[d].data && datasets[d].data[g]) || 0;
          var width = Math.max(2, Math.round((val / maxima[d]) * 100));
          var color = datasets[d].backgroundColor;
          if (Array.isArray(color)) {
            color = color[g % color.length];
          }
          html += '<span class="fg-line"><span class="fg-name">' + datasets[d].label + '</span>'
            + '<span class="fg-track"><span class="fg-fill" style="width:' + width + '%;background:' + color + '"></span></span>'
            + '<span class="fg-val">' + fmtNumber(val) + '</span></span>';
        }
        html += '</span></div>';
      }
      html += '</div>';
    } else if (config.type === 'doughnut' || config.type === 'pie') {
      var total = values.reduce(function (a, b) { return a + b; }, 0) || 1;
      html = '<div class="fallback-legend">';
      for (var i = 0; i < labels.length; i++) {
        var pct = Math.round((values[i] / total) * 1000) / 10;
        html += '<div class="fb-legend-row"><span class="fb-dot" style="background:' + colors[i % colors.length] + '"></span>'
          + '<span class="fb-legend-label">' + labels[i] + '</span>'
          + '<span class="fb-legend-val">' + fmtNumber(values[i]) + ' · ' + pct + '%</span></div>';
      }
      html += '</div>';
    } else {
      var max = Math.max.apply(null, values.concat([1]));
      html = '<div class="fallback-bars">';
      for (var j = 0; j < labels.length; j++) {
        var width = Math.max(2, Math.round((values[j] / max) * 100));
        html += '<div class="fb-row"><span class="fb-label" title="' + labels[j] + '">' + labels[j] + '</span>'
          + '<span class="fb-track"><span class="fb-fill" style="width:' + width + '%;background:' + colors[j % colors.length] + '"></span></span>'
          + '<span class="fb-value">' + fmtNumber(values[j]) + '</span></div>';
      }
      html += '</div>';
    }
    box.classList.add('chart-box--fallback');
    box.innerHTML = html + '<p class="muted fb-note">CDN Chart.js недоступен, показан упрощённый вид.</p>';
  }
  if (typeof Chart === 'undefined') {
    Object.keys(charts).forEach(function (id) {
      var canvas = document.getElementById(id);
      if (canvas) {
        fallback(canvas, charts[id]);
      }
    });
    return;
  }
  Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif';
  Chart.defaults.color = '#475569';
  Object.keys(charts).forEach(function (id) {
    var canvas = document.getElementById(id);
    if (!canvas) {
      return;
    }
    new Chart(canvas.getContext('2d'), charts[id]);
  });
})();

(function () {
  var box = document.getElementById('panel-actions');
  if (!box || typeof fetch !== 'function') {
    return;
  }
  var statusBox = box.querySelector('.job-status');
  var labelEl = box.querySelector('.job-label');
  var stateEl = box.querySelector('.job-state');
  var messageEl = box.querySelector('.job-message');
  var bar = box.querySelector('.job-progress');
  var logEl = box.querySelector('.job-log');
  var cancelBtn = box.querySelector('.job-cancel');
  var buttons = box.querySelectorAll('.action-btn');
  var task = box.getAttribute('data-task') || '';
  var current = null;
  var timer = null;
  var TERMINAL = ['ok', 'failed', 'cancelled', 'timeout'];

  function setBusy(busy) {
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].disabled = busy;
    }
  }

  function render(status) {
    statusBox.hidden = false;
    labelEl.textContent = status.label || status.action || '';
    var state = status.status || 'unknown';
    stateEl.textContent = state;
    stateEl.className = 'job-state ' + state;
    messageEl.textContent = status.message || '';
    if (typeof status.progress === 'number') {
      bar.value = Math.max(0, Math.min(100, status.progress));
    } else {
      bar.removeAttribute('value');
    }
    var lines = status.log_tail || [];
    logEl.textContent = lines.join('\n');
    logEl.hidden = lines.length === 0;
    cancelBtn.hidden = !status.can_cancel;
    if (TERMINAL.indexOf(state) >= 0) {
      stateEl.textContent = state + (status.exit_code !== null && status.exit_code !== undefined ? ' (' + status.exit_code + ')' : '');
    }
  }

  function stopPolling() {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  }

  function poll() {
    if (!current) {
      return;
    }
    stopPolling();
    fetch('/jobs/status?id=' + encodeURIComponent(current), {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin'
    }).then(function (response) {
      return response.json();
    }).then(function (status) {
      render(status);
      if (TERMINAL.indexOf(status.status) >= 0) {
        current = null;
        setBusy(false);
        return;
      }
      timer = setTimeout(poll, 1000);
    }).catch(function () {
      timer = setTimeout(poll, 3000);
    });
  }

  function attach(id) {
    current = id;
    setBusy(true);
    render({ label: '', status: 'queued', message: 'в очереди', progress: 0, log_tail: [], can_cancel: true });
    poll();
  }

  function start(action, needsTask) {
    stopPolling();
    setBusy(true);
    var params = {};
    if (needsTask && task) {
      params.task = task;
    }
    render({ label: action, status: 'queued', message: 'отправка', progress: null, log_tail: [], can_cancel: false });
    fetch('/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin',
      body: JSON.stringify({ action: action, params: params })
    }).then(function (response) {
      return response.json().then(function (body) {
        return { code: response.status, body: body };
      });
    }).then(function (result) {
      if (result.code === 202 && result.body.id) {
        attach(result.body.id);
        return;
      }
      if (result.code === 409 && result.body.id) {
        attach(result.body.id);
        return;
      }
      setBusy(false);
      render({ label: action, status: 'failed', message: result.body.error || 'ошибка запуска', progress: null, log_tail: [], can_cancel: false });
    }).catch(function (error) {
      setBusy(false);
      render({ label: action, status: 'failed', message: String(error.message || error), progress: null, log_tail: [], can_cancel: false });
    });
  }

  for (var i = 0; i < buttons.length; i++) {
    buttons[i].addEventListener('click', function () {
      var action = this.getAttribute('data-action');
      if (!action) {
        return;
      }
      if (this.getAttribute('data-confirm') === '1' && !window.confirm('Запустить ' + action + '?')) {
        return;
      }
      start(action, this.getAttribute('data-task-param') === '1');
    });
  }

  if (cancelBtn) {
    cancelBtn.addEventListener('click', function () {
      if (!current) {
        return;
      }
      cancelBtn.disabled = true;
      fetch('/jobs/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
        body: JSON.stringify({ id: current })
      }).then(function (response) {
        return response.json();
      }).then(function () {
        cancelBtn.disabled = false;
      }).catch(function () {
        cancelBtn.disabled = false;
      });
    });
  }

  fetch('/jobs', {
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
    credentials: 'same-origin'
  }).then(function (response) {
    return response.json();
  }).then(function (data) {
    var jobs = (data && data.jobs) || [];
    for (var j = 0; j < jobs.length; j++) {
      if (jobs[j].status === 'queued' || jobs[j].status === 'running' || jobs[j].status === 'cancelling') {
        attach(jobs[j].id);
        break;
      }
    }
  }).catch(function () {});
})();

(function () {
  function detailFor(row) {
    var key = row.getAttribute('data-detail');
    var next = row.nextElementSibling;
    if (key && next && next.classList.contains('detail-row') && next.getAttribute('data-detail') === key) {
      return next;
    }
    return null;
  }

  function toggle(row) {
    var detail = detailFor(row);
    if (!detail) {
      return;
    }
    var open = detail.hidden;
    detail.hidden = !open;
    row.classList.toggle('expanded', open);
    row.setAttribute('aria-expanded', open ? 'true' : 'false');
    var mark = row.querySelector('.expander');
    if (mark) {
      mark.textContent = open ? '-' : '+';
    }
  }

  document.addEventListener('click', function (event) {
    var row = event.target.closest ? event.target.closest('tr.expandable') : null;
    if (row) {
      toggle(row);
    }
  });

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Enter' && event.key !== ' ') {
      return;
    }
    var row = event.target.closest ? event.target.closest('tr.expandable') : null;
    if (row) {
      event.preventDefault();
      toggle(row);
    }
  });
})();

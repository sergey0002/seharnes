/**
 * Раздел «Граф харнеса».
 *
 * Три части страницы и три источника поведения:
 * 1. Дерево слева — реальная структура файлов (как в старом просмотрщике миррора:
 *    `.agents/skills/...` без служебного сегмента `children`), а не список по типам.
 *    Тип файла виден по цветной плашке, свёрнутые папки помнятся в localStorage.
 * 2. Канвас — SVG-карточки в колонках по типам (раскладка barycenter, как в эталоне)
 *    либо «эго»-раскладка вокруг выбранного узла: входящие слева, исходящие справа.
 * 3. Правая панель — карточка элемента и данные API. Выбор узла подсвечивается сразу,
 *    карточка приходит из кэша или с полосой загрузки; связи и JSON — как в эталоне.
 */
import { debounce, escapeHtml, on, qs, qsa } from '../core/dom.js';

/** Буквы на плашке типа и порядок колонок — из старого просмотрщика. */
const KIND_GLYPH = { skill: 'S', rule: 'R', script: 'P', config: 'C', doc: 'D', mcp: 'M' };
const KIND_ORDER = ['rule', 'skill', 'mcp', 'script', 'doc', 'config'];

/** Цвета связей: те же имена, что в graph.json. */
const EDGE_COLORS = {
  invokes_tool: '#98c379',
  delegates_to: '#4aa3df',
  governed_by: '#e06c75',
  reads_context: '#a9b1ba',
  mirrors: '#e5c07b',
  synced_by: '#c678dd',
  enforces_gate: '#56b6c2',
  constrained_by: '#d19a66',
};

/** Геометрия карточки графа (совпадает с эталоном просмотрщика). */
const CARD = { w: 240, h: 58, colGap: 34, rowGap: 16, pad: 24 };
/** Высота колонки: длинные типы (докшта 350, скрипты 296) делим на несколько колонок. */
const ROWS_PER_COLUMN = 26;
const CLOSED_KEY = 'panel.graphTree.closed';

export function mountGraph({ api, i18n, endpoints, dock }) {
  const root = qs('[data-graph-root]');
  if (!root) return;

  const svg = qs('[data-graph-svg]');
  const wrap = qs('[data-graph-canvas-wrap]');
  const treeHost = qs('[data-graph-list]');
  const rightElement = qs('[data-right-element]');
  const rightColumn = qs('[data-right-panel]');
  const apiHost = qs('[data-right-api]');
  const rightHint = qs('[data-right-kind]');
  const progress = qs('[data-right-progress]');
  const kindFilter = qs('[data-graph-kind]');
  const linkedFilter = qs('[data-graph-linked]');
  const isolatedFilter = qs('[data-graph-isolated]');
  const mirrorsFilter = qs('[data-graph-mirrors]');
  const edgesToggle = qs('[data-graph-edges]');
  const search = qs('[data-graph-search]');
  const countLabel = qs('[data-graph-count]');

  const state = {
    nodes: [],
    edges: [],
    byId: new Map(),
    degrees: new Map(),
    layout: { pos: new Map(), width: 0, height: 0 },
    viewport: { x: 0, y: 0, k: 1 },
    selected: null,
    focus: null,
    hover: null,
    query: '',
    dragging: false,
    pointer: { x: 0, y: 0, moved: false },
    details: new Map(),
    request: null,
    originalSource: '',
    saving: false,
  };

  const closed = readClosed();
  /** nodeId → ключи папок: чтобы раскрыть путь к выбранному узлу. */
  const nodeDirs = new Map();

  function readClosed() {
    try {
      const raw = JSON.parse(localStorage.getItem(CLOSED_KEY) || '[]');
      return new Set(Array.isArray(raw) ? raw : []);
    } catch (error) {
      return new Set();
    }
  }

  const saveClosed = () => {
    try {
      localStorage.setItem(CLOSED_KEY, JSON.stringify([...closed]));
    } catch (error) { /* приватный режим — просто не запоминаем */ }
  };

  /* --------------------------- Фильтры --------------------------- */
  const matchesQuery = (node) => {
    const needle = state.query.toLowerCase();
    if (!needle) return true;
    return `${node.label} ${node.id} ${node.path} ${node.file || ''} ${node.summary || ''}`
      .toLowerCase().includes(needle);
  };

  const passesFilters = (node) => {
    if (!mirrorsFilter?.checked && node.canonical === false) return false;
    if (kindFilter?.value && node.kind !== kindFilter.value) return false;
    const degree = state.degrees.get(node.id) || 0;
    if (linkedFilter?.checked && degree === 0) return false;
    if (isolatedFilter?.checked && degree > 0) return false;
    return matchesQuery(node);
  };

  const visibleNodes = () => state.nodes.filter(passesFilters);

  /* --------------------------- Дерево файлов --------------------------- */
  /**
   * Части пути для дерева.
   *
   * Скилы лежат в `.agents/skills/<...>/children/<child>/SKILL.md`, но служебный
   * сегмент `children` в структуре ничего не значит — эталон просмотрщика его
   * вырезает, и дерево читается как обычные вложенные папки.
   */
  const pathParts = (node) => {
    const path = String(node.path || '');
    if (!path) return null;
    let parts = path.split('/').filter(Boolean);
    if (parts[0] === '.agents' && parts[1] === 'skills') {
      parts = parts.filter((part) => part !== 'children');
    }
    return parts.length ? parts : null;
  };

  /** Одно дерево по реальным путям: папки — из пути, файлы — узлы графа. */
  const buildTree = (nodes) => {
    const rootDir = { name: '', path: '', dirs: new Map(), files: new Map() };
    nodeDirs.clear();
    const orphans = [];
    nodes.forEach((node) => {
      const parts = pathParts(node);
      if (!parts) {
        orphans.push(node);
        return;
      }
      let cursor = rootDir;
      const keys = [];
      parts.slice(0, -1).forEach((segment) => {
        const key = cursor.path ? `${cursor.path}/${segment}` : segment;
        keys.push(key);
        if (!cursor.dirs.has(segment)) {
          cursor.dirs.set(segment, { name: segment, path: key, dirs: new Map(), files: new Map() });
        }
        cursor = cursor.dirs.get(segment);
      });
      const filePath = parts.join('/');
      if (!cursor.files.has(filePath)) cursor.files.set(filePath, []);
      cursor.files.get(filePath).push(node);
      nodeDirs.set(node.id, keys);
    });
    return { rootDir, orphans };
  };

  const countNodes = (dir) => [...dir.files.values()].reduce((sum, list) => sum + list.length, 0)
    + [...dir.dirs.values()].reduce((sum, child) => sum + countNodes(child), 0);

  const isEmptyDir = (dir) => countNodes(dir) === 0;

  /** Ранг файла: SKILL.md и README.md выше остальных, как в эталоне. */
  const fileRank = (path) => {
    if (/\/SKILL\.md$/.test(path)) return 0;
    if (/\/README\.md$/.test(path)) return 1;
    return 2;
  };

  const rowHtml = (node, depth) => {
    const degree = state.degrees.get(node.id) || 0;
    const hint = (node.summary || node.label || '').trim();
    const fileName = node.file || node.path.split('/').pop() || node.id;
    return `
      <button type="button" class="tree__row tree__row--file${node.id === state.selected ? ' is-active' : ''}"
              data-node-id="${escapeHtml(node.id)}" data-kind="${escapeHtml(node.kind)}"
              style="--depth:${depth}"
              title="${escapeHtml(`${node.path}\n${node.kind}${node.canonical ? '' : ' · копия'}\nсвязей: ${degree}`)}">
        <span class="tree__caret" aria-hidden="true"></span>
        <span class="tree__mark tree__mark--${escapeHtml(node.kind)}" aria-hidden="true">${escapeHtml(KIND_GLYPH[node.kind] || '?')}</span>
        <span class="tree__label">${escapeHtml(fileName)}</span>
        <span class="tree__deg${degree ? '' : ' tree__deg--zero'}">${degree}</span>
        <span class="tree__hint">${escapeHtml(hint)}</span>
      </button>`;
  };

  /** Файл, у которого несколько узлов (`.cursor/mcp.json`), раскрывается как папка. */
  const fileGroupHtml = (filePath, nodes, depth) => {
    const key = `file:${filePath}`;
    const isClosed = closed.has(key);
    const name = filePath.split('/').pop();
    return `
      <div class="tree__dir${isClosed ? ' is-closed' : ''}" data-tree-dir-wrap="${escapeHtml(key)}">
        <button type="button" class="tree__row tree__row--dir tree__row--filegroup"
                data-tree-file="${escapeHtml(key)}" aria-expanded="${isClosed ? 'false' : 'true'}"
                style="--depth:${depth}" title="${escapeHtml(filePath)}">
          <span class="tree__caret" aria-hidden="true"></span>
          <span class="tree__label">${escapeHtml(name)}</span>
          <span class="counter counter--sm">${nodes.length}</span>
        </button>
        <div class="tree__children">${nodes.map((node) => rowHtml(node, depth + 1)).join('')}</div>
      </div>`;
  };

  const dirHtml = (dir, depth) => {
    const isClosed = closed.has(dir.path);
    const router = /-router$/.test(dir.name);
    const dirs = [...dir.dirs.values()]
      .filter((child) => !isEmptyDir(child))
      .sort((a, b) => a.name.localeCompare(b.name));
    const files = [...dir.files.entries()]
      .sort((a, b) => fileRank(a[0]) - fileRank(b[0]) || a[0].localeCompare(b[0]));
    const children = [
      ...dirs.map((child) => dirHtml(child, depth + 1)),
      ...files.map(([filePath, nodes]) => (nodes.length > 1
        ? fileGroupHtml(filePath, nodes, depth + 1)
        : rowHtml(nodes[0], depth + 1))),
    ].join('');
    return `
      <div class="tree__dir${isClosed ? ' is-closed' : ''}" data-tree-dir-wrap="${escapeHtml(dir.path)}">
        <button type="button" class="tree__row tree__row--dir${router ? ' is-router' : ''}"
                data-tree-dir="${escapeHtml(dir.path)}"
                aria-expanded="${isClosed ? 'false' : 'true'}" style="--depth:${depth}"
                title="${escapeHtml(dir.path)}">
          <span class="tree__caret" aria-hidden="true"></span>
          <span class="tree__label">${escapeHtml(dir.name)}</span>
          <span class="counter counter--sm">${countNodes(dir)}</span>
        </button>
        <div class="tree__children">${children}</div>
      </div>`;
  };

  const renderTree = () => {
    if (!treeHost) return;
    const nodes = visibleNodes();
    if (countLabel) countLabel.textContent = String(nodes.length);
    if (nodes.length === 0) {
      treeHost.innerHTML = `<p class="empty">${escapeHtml(i18n.t('docs.noResults'))}</p>`;
      return;
    }
    const { rootDir, orphans } = buildTree(nodes);
    const dirs = [...rootDir.dirs.values()].sort((a, b) => a.name.localeCompare(b.name));
    treeHost.innerHTML = [
      ...dirs.map((child) => dirHtml(child, 0)),
      ...orphans.map((node) => rowHtml(node, 0)),
    ].join('');
  };

  /* --------------------------- Раскладка канваса --------------------------- */
  const byLabel = (a, b) => (a.label || '').localeCompare(b.label || '');

  /** Колонки по типам с упорядочиванием по среднему положению соседей. */
  const layoutColumns = (nodes, edges) => {
    const byKind = new Map();
    nodes.forEach((node) => {
      if (!byKind.has(node.kind)) byKind.set(node.kind, []);
      byKind.get(node.kind).push(node);
    });
    const columns = KIND_ORDER
      .filter((kind) => byKind.has(kind))
      .map((kind) => ({ kind, list: byKind.get(kind).slice().sort(byLabel) }));
    [...byKind.keys()]
      .filter((kind) => !KIND_ORDER.includes(kind))
      .forEach((kind) => columns.push({ kind, list: byKind.get(kind).slice().sort(byLabel) }));

    const neighbours = new Map();
    nodes.forEach((node) => neighbours.set(node.id, new Set()));
    edges.forEach((edge) => {
      neighbours.get(edge.source)?.add(edge.target);
      neighbours.get(edge.target)?.add(edge.source);
    });

    const rowOf = () => {
      const map = new Map();
      columns.forEach((column) => column.list.forEach((node, index) => {
        map.set(node.id, index / Math.max(1, column.list.length - 1));
      }));
      return map;
    };

    for (let pass = 0; pass < 4; pass += 1) {
      const order = pass % 2 === 0 ? columns : columns.slice().reverse();
      const rows = rowOf();
      order.forEach((column) => {
        column.list = column.list.map((node, index) => {
          const positions = [...(neighbours.get(node.id) || [])]
            .map((id) => rows.get(id)).filter((value) => value !== undefined);
          const bary = positions.length
            ? positions.reduce((a, b) => a + b, 0) / positions.length
            : index / Math.max(1, column.list.length - 1);
          return { node, bary };
        }).sort((a, b) => a.bary - b.bary).map((item) => item.node);
      });
    }

    const pos = new Map();
    let columnIndex = 0;
    let maxRows = 0;
    columns.forEach((column) => {
      for (let start = 0; start < column.list.length; start += ROWS_PER_COLUMN) {
        const chunk = column.list.slice(start, start + ROWS_PER_COLUMN);
        maxRows = Math.max(maxRows, chunk.length);
        chunk.forEach((node, rowIndex) => {
          pos.set(node.id, {
            x: CARD.pad + columnIndex * (CARD.w + CARD.colGap),
            y: CARD.pad + rowIndex * (CARD.h + CARD.rowGap),
            node,
          });
        });
        columnIndex += 1;
      }
    });
    return {
      pos,
      width: CARD.pad * 2 + Math.max(0, columnIndex - 1) * (CARD.w + CARD.colGap) + CARD.w,
      height: CARD.pad * 2 + Math.max(0, maxRows - 1) * (CARD.h + CARD.rowGap) + CARD.h,
    };
  };

  /** «Эго»-раскладка: входящие слева, узел в центре, исходящие справа. */
  const layoutFocus = (nodes, edges, focusId) => {
    const out = new Set();
    const inc = new Set();
    edges.forEach((edge) => {
      if (edge.source === focusId) out.add(edge.target);
      if (edge.target === focusId) inc.add(edge.source);
    });
    const focusNode = nodes.find((node) => node.id === focusId);
    const incoming = nodes.filter((node) => node.id !== focusId && inc.has(node.id)).sort(byLabel);
    const outgoing = nodes.filter((node) => node.id !== focusId && out.has(node.id)).sort(byLabel);
    const columnWidth = CARD.w + 130;
    const rows = Math.max(incoming.length, outgoing.length, 1);
    const pos = new Map();
    const place = (list, x) => {
      list.forEach((node, index) => {
        pos.set(node.id, { x, y: CARD.pad + index * (CARD.h + CARD.rowGap), node });
      });
    };
    let x = CARD.pad;
    if (incoming.length) { place(incoming, x); x += columnWidth; }
    const centerX = x;
    x += columnWidth;
    if (outgoing.length) place(outgoing, x);
    if (focusNode) {
      const centerY = CARD.pad + Math.floor((rows - 1) / 2) * (CARD.h + CARD.rowGap);
      pos.set(focusId, { x: centerX, y: centerY, node: focusNode });
    }
    return {
      pos,
      width: Math.max(centerX + columnWidth, CARD.pad * 2 + CARD.w),
      height: CARD.pad * 2 + Math.max(0, rows - 1) * (CARD.h + CARD.rowGap) + CARD.h,
    };
  };

  const relayout = () => {
    const nodes = visibleNodes();
    const focusId = state.focus && nodes.some((node) => node.id === state.focus) ? state.focus : null;
    const edges = visibleEdges(nodes, focusId);
    state.layout = focusId
      ? layoutFocus(nodes, edges, focusId)
      : layoutColumns(nodes, edges);
    return { nodes, edges, focusId };
  };

  /** Рёбра только между видимыми узлами; в фокусе — только рёбра выбранного. */
  const visibleEdges = (nodes, focusId) => {
    const ids = new Set(nodes.map((node) => node.id));
    return state.edges.filter((edge) => {
      if (!ids.has(edge.source) || !ids.has(edge.target)) return false;
      if (focusId) return edge.source === focusId || edge.target === focusId;
      return true;
    });
  };

  /* --------------------------- Канвас: SVG --------------------------- */
  const truncate = (text, limit) => {
    const value = String(text || '').replace(/\s+/g, ' ').trim();
    return value.length > limit ? `${value.slice(0, limit - 1)}…` : value;
  };

  const pathTitle = (node) => {
    const path = String(node.path || node.id);
    const parts = path.split('/');
    return parts.length > 2 ? `…/${parts.slice(-2).join('/')}` : path;
  };

  const cardSvg = (entry) => {
    const { node, x, y } = entry;
    const color = `var(--kind-${node.kind})`;
    const selected = node.id === state.selected ? ' is-selected' : '';
    const title = truncate(node.summary || node.label, 30);
    const meta = [node.kind, node.environment || '—', node.analysis || '—'].filter(Boolean).join(' · ');
    return `<g class="gcard${selected}" data-node-id="${escapeHtml(node.id)}" transform="translate(${x},${y})">
      <rect class="gcard__box" width="${CARD.w}" height="${CARD.h}" rx="6"></rect>
      <rect class="gcard__bar" x="0" y="6" width="4" height="${CARD.h - 12}" fill="${color}"></rect>
      <rect class="gcard__mark" x="12" y="8" width="13" height="13" rx="3" fill="${color}"></rect>
      <text class="gcard__glyph" x="18.5" y="18">${escapeHtml(KIND_GLYPH[node.kind] || '?')}</text>
      <text class="gcard__title" x="32" y="19">${escapeHtml(title)}</text>
      <text class="gcard__sub" x="14" y="33">${escapeHtml(truncate(pathTitle(node), 36))}</text>
      <text class="gcard__meta" x="14" y="47">${escapeHtml(meta)}</text>
    </g>`;
  };

  /** Одно визуальное ребро на пару «источник → цель · тип»: параллельные складываем. */
  const edgeSvg = (edges) => {
    const grouped = new Map();
    edges.forEach((edge) => {
      const key = `${edge.source}\u0000${edge.target}\u0000${edge.type}`;
      const seen = grouped.get(key);
      if (seen) { seen.count += 1; return; }
      grouped.set(key, { edge, count: 1 });
    });
    const pairTotal = new Map();
    grouped.forEach(({ edge }) => {
      const pair = `${edge.source}>${edge.target}`;
      pairTotal.set(pair, (pairTotal.get(pair) || 0) + 1);
    });
    const pairSeen = new Map();
    const parts = [];
    grouped.forEach(({ edge, count }) => {
      const from = state.layout.pos.get(edge.source);
      const to = state.layout.pos.get(edge.target);
      if (!from || !to) return;
      const pair = `${edge.source}>${edge.target}`;
      const index = pairSeen.get(pair) || 0;
      pairSeen.set(pair, index + 1);
      const total = pairTotal.get(pair) || 1;
      const offset = total > 1 ? (index - (total - 1) / 2) * 5 : 0;
      const rightwards = to.x >= from.x;
      const x1 = rightwards ? from.x + CARD.w : from.x;
      const y1 = from.y + CARD.h / 2 + offset;
      const x2 = rightwards ? to.x : to.x + CARD.w;
      const y2 = to.y + CARD.h / 2 + offset;
      const bend = Math.max(26, Math.abs(x2 - x1) * 0.45);
      const c1 = x1 + (rightwards ? bend : -bend);
      const c2 = x2 + (rightwards ? -bend : bend);
      const color = EDGE_COLORS[edge.type] || 'var(--text-faint)';
      const width = (1.1 + Math.min(3, count - 1) * 0.35).toFixed(2);
      const label = `${edge.type}${count > 1 ? ` ×${count}` : ''} · ${state.byId.get(edge.source)?.label || edge.source} → ${state.byId.get(edge.target)?.label || edge.target}`;
      parts.push(`<path class="gedge" data-tip="${escapeHtml(label)}"
        d="M${x1},${y1} C${c1},${y1} ${c2},${y2} ${x2},${y2}"
        stroke="${color}" stroke-width="${width}"></path>`);
    });
    return parts.join('');
  };

  const applyTransform = () => {
    const world = qs('.canvas__world', svg);
    if (!world) return;
    const { x, y, k } = state.viewport;
    world.setAttribute('transform', `translate(${x},${y}) scale(${k})`);
  };

  const renderCanvas = () => {
    if (!svg) return;
    const { nodes, edges, focusId } = relayout();
    const showEdges = edgesToggle?.checked !== false;
    const cards = [...state.layout.pos.entries()]
      .sort((a, b) => a[1].y - b[1].y)
      .map(([, entry]) => cardSvg(entry))
      .join('');
    svg.innerHTML = `<g class="canvas__world">${showEdges ? edgeSvg(edges) : ''}${cards}</g>`;
    applyTransform();
    const empty = qs('[data-graph-empty]');
    if (empty) empty.hidden = nodes.length > 0;
    const chip = qs('[data-graph-focus-clear]');
    if (chip) {
      chip.hidden = !focusId;
      const label = qs('[data-graph-focus-label]', chip);
      if (focusId && label) {
        label.textContent = i18n.t('graph.focusChip', {
          label: state.byId.get(focusId)?.label || focusId,
        });
      }
    }
  };

  /** Подсветка: без перерисовки, только классы и прозрачность. */
  const highlight = (nodeId) => {
    if (!svg) return;
    const hot = new Set();
    if (nodeId) {
      hot.add(nodeId);
      state.edges.forEach((edge) => {
        if (edge.source === nodeId) hot.add(edge.target);
        if (edge.target === nodeId) hot.add(edge.source);
      });
    }
    qsa('.gcard', svg).forEach((card) => {
      const id = card.dataset.nodeId;
      card.classList.toggle('is-dim', Boolean(nodeId) && !hot.has(id));
    });
    qsa('.gedge', svg).forEach((path) => {
      path.classList.toggle('is-hot', false);
    });
    state.hover = nodeId;
  };

  const showTooltip = (text, event) => {
    let tip = qs('.canvas__tooltip', wrap);
    if (!text) {
      tip?.remove();
      return;
    }
    if (!tip) {
      tip = document.createElement('div');
      tip.className = 'canvas__tooltip';
      wrap.appendChild(tip);
    }
    tip.textContent = text;
    const rect = wrap.getBoundingClientRect();
    tip.style.left = `${event.clientX - rect.left}px`;
    tip.style.top = `${event.clientY - rect.top}px`;
  };

  /* --------------------------- Выбор узла --------------------------- */
  const setProgress = (active) => {
    if (progress) progress.hidden = !active;
    rightColumn?.classList.toggle('is-loading', active);
  };

  /** Каркас карточки на время запроса: имя, путь и тип уже известны из списка. */
  const skeletonHtml = (node) => `
    <div class="node-card node-card--skeleton" data-node-card data-node-id="${escapeHtml(node.id)}">
      <div class="node-card__head">
        <span class="chip chip--${escapeHtml(node.kind)}">${escapeHtml(node.kind)}</span>
        <h3 class="node-card__title">${escapeHtml(node.label)}</h3>
      </div>
      <dl class="kv kv--tight">
        <div class="kv__row"><dt>${escapeHtml(i18n.t('graph.nodeId'))}</dt><dd><code>${escapeHtml(node.id)}</code></dd></div>
        ${node.path ? `<div class="kv__row"><dt>${escapeHtml(i18n.t('graph.nodePath'))}</dt><dd><code>${escapeHtml(node.path)}</code></dd></div>` : ''}
      </dl>
      <p class="muted" data-node-loading>${escapeHtml(i18n.t('graph.loadingCard'))}</p>
      <div class="skeleton"><span></span><span></span><span></span><span></span></div>
    </div>`;

  const select = async (node, options = {}) => {
    if (!node) return;
    state.selected = node.id;
    updateSelectionMarks();
    revealNode(node.id);
    if (!options.silent) {
      try {
        history.replaceState(null, '', `#node=${encodeURIComponent(node.id)}`);
      } catch (error) { /* песочница без history — не критично */ }
    }
    if (rightHint) rightHint.textContent = `${node.kind}${node.canonical ? '' : ` · ${i18n.t('graph.copyTag')}`}`;
    const apiHint = qs('[data-right-api-hint]');
    if (apiHint) apiHint.textContent = `GET graph/node · ${node.id}`;

    const cached = state.details.get(node.id);
    if (cached) {
      renderDetail(cached);
      return;
    }
    if (rightElement) rightElement.innerHTML = skeletonHtml(node);
    setProgress(true);

    state.request?.abort();
    const controller = new AbortController();
    state.request = controller;
    try {
      const entry = await api.get(endpoints.graphNode, { id: node.id });
      const payload = entry.response || {};
      if (controller.signal.aborted) return;
      if (!entry.ok || !payload.data) {
        if (rightElement) {
          rightElement.innerHTML = `<p class="muted">${escapeHtml(payload.error || i18n.t('common.error', { message: 'graph/node' }))}</p>`;
        }
        return;
      }
      state.details.set(node.id, payload);
      renderDetail(payload);
      dock.append(`# ${node.id} · ${(payload.data.relations || []).length} ${i18n.t('graph.relationsShort')}`, 'line-dim');
    } catch (error) {
      if (rightElement) rightElement.innerHTML = `<p class="muted">${escapeHtml(String(error))}</p>`;
    } finally {
      if (!controller.signal.aborted) setProgress(false);
    }
  };

  /** Карточка элемента (верх правой панели) и связи + JSON (низ). */
  const renderDetail = (payload) => {
    if (rightElement && payload.html?.right) rightElement.innerHTML = payload.html.right;
    mountEditor(payload.data?.node);
    renderApi(payload.data);
  };

  const updateSelectionMarks = () => {
    qsa('.gcard', svg || document).forEach((card) => {
      card.classList.toggle('is-selected', card.dataset.nodeId === state.selected);
    });
    qsa('[data-node-id]', treeHost || document).forEach((item) => {
      item.classList.toggle('is-active', item.dataset.nodeId === state.selected);
    });
  };

  /** Раскрыть путь к узлу и прокрутить строку в дереве. */
  const revealNode = (nodeId) => {
    const keys = nodeDirs.get(nodeId) || [];
    let changed = false;
    keys.forEach((key) => {
      if (closed.delete(key)) changed = true;
    });
    if (changed) {
      saveClosed();
      renderTree();
    }
    qs(`[data-node-id="${CSS.escape(nodeId)}"]`, treeHost)?.scrollIntoView({ block: 'nearest' });
  };

  /* --------------------------- Данные API --------------------------- */
  const relationRow = (relation) => `
    <li class="rel-list__item">
      <span class="rel-list__dir rel-list__dir--${escapeHtml(relation.direction)}"
            title="${escapeHtml(i18n.t(relation.direction === 'out' ? 'api.relationsOut' : 'api.relationsIn'))}">
        ${relation.direction === 'out' ? '→' : '←'}
      </span>
      <span class="rel-list__type">${escapeHtml(relation.type)}</span>
      <button type="button" class="link-btn" data-node-open="${escapeHtml(relation.id)}">
        <i class="dot dot--${escapeHtml(relation.kind)}" aria-hidden="true"></i>
        ${escapeHtml(relation.label)}
      </button>
    </li>`;

  const renderApi = (data) => {
    if (!apiHost || !data) return;
    const relations = data.relations || [];
    const out = relations.filter((relation) => relation.direction === 'out');
    const inc = relations.filter((relation) => relation.direction === 'in');
    const jsonText = JSON.stringify(data.node || {}, null, 2);
    const kb = Math.max(1, Math.round(new Blob([jsonText]).size / 1024));
    apiHost.innerHTML = `
      <div class="api-blocks">
        <section class="api-block">
          <h4 class="api-block__title">${escapeHtml(i18n.t('graph.relOut'))} (${out.length})</h4>
          ${out.length ? `<ul class="rel-list">${out.map(relationRow).join('')}</ul>` : `<p class="muted">${escapeHtml(i18n.t('graph.noRelations'))}</p>`}
        </section>
        <section class="api-block">
          <h4 class="api-block__title">${escapeHtml(i18n.t('graph.relIn'))} (${inc.length})</h4>
          ${inc.length ? `<ul class="rel-list">${inc.map(relationRow).join('')}</ul>` : `<p class="muted">${escapeHtml(i18n.t('graph.noRelations'))}</p>`}
        </section>
        <section class="api-block">
          <div class="api-block__head">
            <h4 class="api-block__title">${escapeHtml(i18n.t('graph.nodeJson'))}</h4>
            <span class="muted">${kb} ${escapeHtml(i18n.t('graph.kb'))}</span>
            <button type="button" class="ghost-btn ghost-btn--sm" data-node-json-toggle>${escapeHtml(i18n.t('graph.hide'))}</button>
            <button type="button" class="ghost-btn ghost-btn--sm" data-node-json-copy>${escapeHtml(i18n.t('common.copy'))}</button>
          </div>
          <pre class="api-json" data-node-json>${escapeHtml(jsonText)}</pre>
        </section>
      </div>`;
  };

  on(apiHost || document, 'click', '[data-node-json-toggle]', (event, target) => {
    const pre = qs('[data-node-json]', apiHost);
    if (!pre) return;
    pre.hidden = !pre.hidden;
    target.textContent = i18n.t(pre.hidden ? 'graph.show' : 'graph.hide');
  });

  on(apiHost || document, 'click', '[data-node-json-copy]', () => {
    const pre = qs('[data-node-json]', apiHost);
    if (pre) navigator.clipboard?.writeText(pre.textContent).catch(() => {});
  });

  on(apiHost || document, 'click', '[data-node-open]', (event, target) => {
    const node = state.byId.get(target.dataset.nodeOpen);
    if (node) select(node);
  });

  on(rightElement || document, 'click', '[data-node-open]', (event, target) => {
    const node = state.byId.get(target.dataset.nodeOpen);
    if (node) select(node);
  });

  on(rightElement || document, 'click', '[data-node-focus]', (event, target) => {
    const id = target.dataset.nodeFocus;
    setFocus(state.focus === id ? null : id);
  });

  const setFocus = (id) => {
    state.focus = id;
    renderCanvas();
    if (id) {
      fitView();
      const node = state.byId.get(id);
      if (node) select(node, { silent: true });
    }
  };

  /* --------------------------- Редактор файла --------------------------- */
  const setEditorState = (text, tone = '') => {
    const label = qs('[data-editor-state]', rightElement);
    if (!label) return;
    label.textContent = text;
    label.className = `editor__state${tone ? ` editor__state--${tone}` : ' muted'}`;
  };

  const mountEditor = (node) => {
    const file = qs('[data-node-file]', rightElement);
    const source = qs('[data-node-source]', rightElement);
    if (!file || !source || !node) return;
    state.originalSource = source.value;
    if (file.dataset.editable !== '1') {
      const reason = file.dataset.reason || '';
      if (reason) setEditorState(i18n.t(`graph.readOnlyReason.${reason}`) || reason);
      return;
    }
    setEditorState('');
    source.addEventListener('keydown', (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        saveNode(node.id);
      }
    });
    source.addEventListener('input', () => {
      const dirty = source.value !== state.originalSource;
      setEditorState(dirty ? i18n.t('graph.editDirty') : '', dirty ? 'warn' : '');
    });
  };

  const toggleEdit = (editing) => {
    const source = qs('[data-node-source]', rightElement);
    const preview = qs('[data-node-preview]', rightElement);
    const editBtn = qs('[data-node-edit]', rightElement);
    const saveBtn = qs('[data-node-save]', rightElement);
    const resetBtn = qs('[data-node-reset]', rightElement);
    if (!source || !preview) return;
    source.hidden = !editing;
    preview.hidden = editing;
    if (editBtn) editBtn.hidden = editing;
    if (saveBtn) saveBtn.hidden = !editing;
    if (resetBtn) resetBtn.hidden = !editing;
    if (editing) source.focus();
  };

  on(rightElement || document, 'click', '[data-node-edit]', () => toggleEdit(true));

  on(rightElement || document, 'click', '[data-node-reset]', () => {
    const source = qs('[data-node-source]', rightElement);
    if (source) source.value = state.originalSource;
    setEditorState('');
    toggleEdit(false);
  });

  on(rightElement || document, 'click', '[data-node-reload]', () => {
    const node = state.byId.get(state.selected);
    if (!node) return;
    state.details.delete(node.id);
    select(node, { silent: true });
  });

  on(rightElement || document, 'click', '[data-node-save]', () => saveNode(state.selected));

  const saveNode = async (nodeId) => {
    const source = qs('[data-node-source]', rightElement);
    if (!source || !nodeId || state.saving) return;
    if (source.value === state.originalSource) {
      setEditorState(i18n.t('graph.editNoChanges'));
      return;
    }
    state.saving = true;
    setEditorState(i18n.t('common.loading'));
    dock.append(`# save ${nodeId}`, 'line-cmd');
    try {
      const entry = await api.post(endpoints.graphNode, { id: nodeId, content: source.value });
      const payload = entry.response || {};
      if (!entry.ok || payload.status !== 'ok') {
        setEditorState(payload.error || 'error', 'err');
        dock.append(`! ${payload.error || 'save failed'}`, 'line-err');
        return;
      }
      state.originalSource = source.value;
      state.details.delete(nodeId);
      if (rightElement && payload.html?.right) rightElement.innerHTML = payload.html.right;
      mountEditor(state.byId.get(nodeId));
      setEditorState(i18n.t('graph.editSaved'), 'ok');
      dock.append(`# saved ${nodeId}`, 'line-ok');
      await load({ keepViewport: true });
    } finally {
      state.saving = false;
    }
  };

  /* --------------------------- Загрузка --------------------------- */
  const load = async ({ keepViewport = false } = {}) => {
    const entry = await api.get(endpoints.graphView, { kind: '' });
    const data = entry.response?.data || { nodes: [], edges: [] };
    state.nodes = data.nodes || [];
    state.edges = data.edges || [];
    state.byId = new Map(state.nodes.map((node) => [node.id, node]));
    state.degrees = new Map();
    state.edges.forEach((edge) => {
      state.degrees.set(edge.source, (state.degrees.get(edge.source) || 0) + 1);
      state.degrees.set(edge.target, (state.degrees.get(edge.target) || 0) + 1);
    });
    renderTree();
    renderCanvas();
    if (!keepViewport) resetView();
  };

  const statsNodes = qs('[data-stat-nodes]');
  const statsEdges = qs('[data-stat-edges]');
  if (statsNodes || statsEdges) {
    api.get(endpoints.graphSummary).then((entry) => {
      const data = entry.response?.data || {};
      if (statsNodes) statsNodes.textContent = String(data.nodes ?? 0);
      if (statsEdges) statsEdges.textContent = String(data.edges ?? 0);
      const empty = qs('[data-graph-empty]');
      if (empty) empty.hidden = Boolean(data.available);
    });
  }

  /* --------------------------- События дерева --------------------------- */
  const toggleKey = (key) => {
    if (closed.has(key)) closed.delete(key);
    else closed.add(key);
    saveClosed();
    const wrapEl = qs(`[data-tree-dir-wrap="${CSS.escape(key)}"]`, treeHost);
    const isClosed = closed.has(key);
    wrapEl?.classList.toggle('is-closed', isClosed);
    const button = qs(`[data-tree-dir="${CSS.escape(key)}"], [data-tree-file="${CSS.escape(key)}"]`, treeHost);
    button?.setAttribute('aria-expanded', isClosed ? 'false' : 'true');
  };

  on(treeHost || document, 'click', '[data-tree-dir]', (event, target) => {
    toggleKey(target.dataset.treeDir);
  });

  on(treeHost || document, 'click', '[data-tree-file]', (event, target) => {
    toggleKey(target.dataset.treeFile);
  });

  on(treeHost || document, 'click', '[data-node-id]', (event, target) => {
    const node = state.byId.get(target.dataset.nodeId);
    if (node) select(node);
  });

  /* --------------------------- Канвас: мышь и зум --------------------------- */
  const pointerWorld = (event) => {
    const rect = svg.getBoundingClientRect();
    const { x, y, k } = state.viewport;
    return { x: (event.clientX - rect.left - x) / k, y: (event.clientY - rect.top - y) / k };
  };

  svg?.addEventListener('pointerdown', (event) => {
    state.dragging = true;
    state.pointer = { x: event.clientX, y: event.clientY, moved: false };
    svg.classList.add('is-dragging');
    svg.setPointerCapture(event.pointerId);
  });

  svg?.addEventListener('pointermove', (event) => {
    if (state.dragging) {
      const dx = event.clientX - state.pointer.x;
      const dy = event.clientY - state.pointer.y;
      if (Math.abs(dx) + Math.abs(dy) > 2) state.pointer.moved = true;
      state.pointer = { x: event.clientX, y: event.clientY, moved: state.pointer.moved };
      state.viewport.x += dx;
      state.viewport.y += dy;
      applyTransform();
      return;
    }
    const card = event.target.closest?.('.gcard');
    const edge = event.target.closest?.('.gedge');
    if (card) {
      const node = state.byId.get(card.dataset.nodeId);
      highlight(card.dataset.nodeId);
      showTooltip(node ? `${node.label}\n${node.path}\n${node.kind}${node.canonical ? '' : ' · копия'}` : '', event);
      svg.style.cursor = 'pointer';
      return;
    }
    if (edge) {
      showTooltip(edge.dataset.tip || '', event);
      svg.style.cursor = 'crosshair';
      return;
    }
    if (state.hover) highlight(null);
    showTooltip(null, event);
    svg.style.cursor = 'grab';
  });

  svg?.addEventListener('pointerup', (event) => {
    const moved = state.pointer.moved;
    state.dragging = false;
    svg.classList.remove('is-dragging');
    // Подсказка не должна висеть после клика: она описывает элемент под курсором.
    showTooltip(null, event);
    if (moved) return;
    const card = event.target.closest?.('.gcard');
    if (card) {
      const node = state.byId.get(card.dataset.nodeId);
      if (node) select(node);
    }
  });

  svg?.addEventListener('pointerleave', () => {
    highlight(null);
    showTooltip(null, { clientX: 0, clientY: 0 });
  });

  svg?.addEventListener('wheel', (event) => {
    event.preventDefault();
    const rect = svg.getBoundingClientRect();
    const pointerX = event.clientX - rect.left;
    const pointerY = event.clientY - rect.top;
    const { x, y, k } = state.viewport;
    const next = Math.min(2.4, Math.max(0.08, k * Math.exp(-event.deltaY * 0.0015)));
    state.viewport = {
      k: next,
      x: pointerX - ((pointerX - x) * next) / k,
      y: pointerY - ((pointerY - y) * next) / k,
    };
    applyTransform();
  }, { passive: false });

  /** Стартовый вид: масштаб 1 и левый верхний угол, как у старого просмотрщика. */
  const resetView = () => {
    state.viewport = { k: 1, x: 0, y: 0 };
    applyTransform();
  };

  const fitView = () => {
    if (!svg || !wrap) return;
    const { width, height } = state.layout;
    if (!width || !height) return;
    const scale = Math.min(
      (wrap.clientWidth - 24) / width,
      (wrap.clientHeight - 24) / height,
      1,
    );
    state.viewport = { k: Math.max(0.08, scale), x: 12, y: 12 };
    applyTransform();
  };

  on(root, 'click', '[data-graph-zoom]', (event, target) => {
    const action = target.dataset.graphZoom;
    if (action === 'fit') {
      fitView();
      return;
    }
    const factor = action === 'in' ? 1.25 : 0.8;
    state.viewport.k = Math.min(2.4, Math.max(0.08, state.viewport.k * factor));
    applyTransform();
  });

  on(root, 'click', '[data-graph-focus-clear]', () => setFocus(null));

  /* --------------------------- Фильтры --------------------------- */
  edgesToggle?.addEventListener('change', () => renderCanvas());

  const reflow = () => {
    renderTree();
    renderCanvas();
  };

  [linkedFilter, isolatedFilter, mirrorsFilter].forEach((input) => {
    input?.addEventListener('change', () => {
      if (input === linkedFilter && input.checked && isolatedFilter) isolatedFilter.checked = false;
      if (input === isolatedFilter && input.checked && linkedFilter) linkedFilter.checked = false;
      if (state.focus && !visibleNodes().some((node) => node.id === state.focus)) state.focus = null;
      reflow();
    });
  });

  kindFilter?.addEventListener('change', () => {
    renderTree();
    renderCanvas();
  });

  search?.addEventListener('input', debounce(() => {
    state.query = search.value.trim();
    reflow();
  }, 150));

  window.addEventListener('resize', debounce(() => applyTransform(), 120));

  /* --------------------------- Старт --------------------------- */
  window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && state.focus) setFocus(null);
  });

  load().then(() => {
    dock.append(`# graph: ${state.nodes.length} nodes, ${state.edges.length} edges`, 'line-dim');
    const match = /^#node=(.+)$/.exec(window.location.hash || '');
    if (match) {
      const node = state.byId.get(decodeURIComponent(match[1]));
      if (node) select(node);
    }
  });

  window.addEventListener('hashchange', () => {
    const match = /^#node=(.+)$/.exec(window.location.hash || '');
    if (!match) return;
    const node = state.byId.get(decodeURIComponent(match[1]));
    if (node && node.id !== state.selected) select(node);
  });
}

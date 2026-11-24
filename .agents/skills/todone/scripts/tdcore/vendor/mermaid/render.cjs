#!/usr/bin/env node
/*
 * Offline AUTODOC Mermaid adapter.
 *
 * The Mermaid runtime is the pinned, vendored npm distribution next to this
 * file. jsdom is only a build-time DOM host; generated SVG never references
 * it, Mermaid, a stylesheet, a font, or the network.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { parseHTML } = require('./dom-host.cjs');

const runtimePath = path.join(__dirname, 'mermaid.min.js');
const input = fs.readFileSync(0, 'utf8');

function exposeDom(window) {
  const names = [
    'window', 'document', 'navigator', 'Element', 'HTMLElement', 'SVGElement',
    'Node', 'DOMParser', 'XMLSerializer', 'getComputedStyle',
    'MutationObserver', 'CSSStyleSheet', 'customElements', 'Event', 'MouseEvent'
  ];
  for (const name of names) {
    if (window[name] !== undefined) global[name] = window[name];
  }
  global.CSSStyleSheet = global.CSSStyleSheet || class CSSStyleSheet {
    constructor() { this.cssRules = []; }
    replaceSync() {}
    insertRule(rule) { this.cssRules.push(rule); return this.cssRules.length - 1; }
  };
  global.getComputedStyle = global.getComputedStyle || (() => ({ getPropertyValue: () => '' }));
  global.requestAnimationFrame = (callback) => setTimeout(callback, 0);
  global.cancelAnimationFrame = (handle) => clearTimeout(handle);
  global.performance = { now: () => Date.now() };
  global.location = window.location || { href: 'http://autodoc.invalid/' };
}

function number(value, fallback = 0) {
  const result = Number.parseFloat(String(value || '').replace('px', ''));
  return Number.isFinite(result) ? result : fallback;
}

function translate(element) {
  let x = 0;
  let y = 0;
  let current = element;
  while (current && current.getAttribute) {
    const transform = current.getAttribute('transform') || '';
    const match = transform.match(/translate\(\s*([-+0-9.eE]+)(?:[ ,]+([-+0-9.eE]+))?\s*\)/);
    if (match) {
      x += number(match[1]);
      y += number(match[2], 0);
    }
    current = current.parentElement;
  }
  return { x, y };
}

function localRect(element) {
  if (!element || !element.getAttribute) return null;
  const tag = String(element.tagName || '').toLowerCase();
  if (tag === 'rect') {
    return {
      x: number(element.getAttribute('x')),
      y: number(element.getAttribute('y')),
      width: number(element.getAttribute('width'), 24),
      height: number(element.getAttribute('height'), 20)
    };
  }
  if (tag === 'circle' || tag === 'ellipse') {
    const rx = number(element.getAttribute('rx'), number(element.getAttribute('r'), 12));
    const ry = number(element.getAttribute('ry'), number(element.getAttribute('r'), 12));
    return { x: number(element.getAttribute('cx')) - rx,
      y: number(element.getAttribute('cy')) - ry, width: rx * 2, height: ry * 2 };
  }
  if (tag === 'text' || tag === 'foreignobject') {
    const text = String(element.textContent || '').trim();
    return { x: number(element.getAttribute('x')),
      y: number(element.getAttribute('y')) - 16,
      width: Math.max(24, text.length * 8), height: 20 };
  }
  return null;
}

function nodeRect(element) {
  const shape = element && element.querySelector
    ? (element.querySelector('rect.label-container') || element.querySelector('rect.basic') || element.querySelector('rect'))
    : null;
  return localRect(shape);
}

function svgBounds(svg) {
  const nodes = Array.from(svg.querySelectorAll('g.node'));
  if (!nodes.length) return { x: 0, y: 0, width: 100, height: 100 };
  let left = Infinity;
  let top = Infinity;
  let right = -Infinity;
  let bottom = -Infinity;
  for (const node of nodes) {
    const rect = nodeRect(node);
    if (!rect) continue;
    const point = translate(node);
    left = Math.min(left, rect.x + point.x);
    top = Math.min(top, rect.y + point.y);
    right = Math.max(right, rect.x + point.x + rect.width);
    bottom = Math.max(bottom, rect.y + point.y + rect.height);
  }
  if (!Number.isFinite(left) || !Number.isFinite(top)) {
    return { x: 0, y: 0, width: 100, height: 100 };
  }
  // Leave room for arrowheads, labels, and the focus outline. Mermaid adds
  // its own small outer margin after reading this box.
  return { x: left - 12, y: top - 12,
    width: Math.max(40, right - left + 24), height: Math.max(40, bottom - top + 24) };
}

function installSvgPolyfills(window) {
  window.SVGElement.prototype.getBBox = function getBBox() {
    const tag = String(this.tagName || '').toLowerCase();
    if (tag === 'svg') return svgBounds(this);
    if (this.classList && this.classList.contains('node')) {
      return nodeRect(this) || { x: 0, y: 0, width: 100, height: 30 };
    }
    const rect = localRect(this) || localRect(this.querySelector && this.querySelector('rect'));
    if (rect) return rect;
    const text = String(this.textContent || '').trim();
    return { x: 0, y: 0, width: Math.max(24, text.length * 8), height: 20 };
  };
  window.SVGElement.prototype.getComputedTextLength = function getComputedTextLength() {
    return String(this.textContent || '').trim().length * 8;
  };
  window.SVGElement.prototype.getTotalLength = function getTotalLength() {
    return 100;
  };
}

function safeId(value) {
  return 'autodoc_' + String(value || 'diagram').replace(/[^A-Za-z0-9_-]+/g, '_').slice(0, 100);
}

function normalizeSvg(svg) {
  let result = String(svg || '').trim();
  result = result.replace(/role="graphics-document document"/g, 'role="img"');
  if (!/\srole="img"/.test(result)) {
    result = result.replace(/^<svg\b/, '<svg role="img"');
  }
  // Mermaid's SVG is the sole renderer of shapes. Keep its generated markup,
  // but reject accidental executable or network-bearing output at the adapter
  // boundary so an unsafe diagram cannot enter the offline bundle.
  if (/<(?:script|iframe|object|embed)\b/i.test(result)) {
    throw new Error('Mermaid output contains executable or embedded markup');
  }
  if (/(?:href|xlink:href|src)=["'](?:https?:|file:|javascript:|data:|\/\/)/i.test(result)) {
    throw new Error('Mermaid output contains an external URL');
  }
  return result;
}

async function main() {
  let payload;
  try {
    payload = JSON.parse(input || '[]');
  } catch (error) {
    throw new Error('adapter input is not JSON: ' + error.message);
  }
  const jobs = Array.isArray(payload) ? payload : (payload.diagrams || []);
  const { window } = parseHTML('<!doctype html><html><body></body></html>');
  exposeDom(window);
  installSvgPolyfills(window);
  vm.runInThisContext(fs.readFileSync(runtimePath, 'utf8'), { filename: runtimePath });
  if (!global.mermaid || typeof global.mermaid.render !== 'function') {
    throw new Error('pinned Mermaid runtime did not expose mermaid.render');
  }
  global.mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'strict',
    deterministicIds: true,
    deterministicIDSeed: 'todone-autodoc',
    theme: 'base',
    fontFamily: 'Arial, sans-serif',
    htmlLabels: false,
    flowchart: {
      useMaxWidth: false,
      htmlLabels: false,
      curve: 'basis',
      wrappingWidth: 260,
      nodeSpacing: 55,
      rankSpacing: 60,
      padding: 16
    },
    themeVariables: {
      background: '#f5f9fd',
      fontFamily: 'Arial, sans-serif',
      fontSize: '14px',
      primaryColor: '#eaf3fc',
      primaryTextColor: '#132a42',
      primaryBorderColor: '#4b7697',
      lineColor: '#58758e',
      secondaryColor: '#e7f7f1',
      tertiaryColor: '#f0e9ff',
      edgeLabelBackground: '#eef4f8',
      clusterBkg: '#f5f9fd',
      clusterBorder: '#9bb3c8'
    }
  });
  const result = {};
  for (const job of jobs) {
    const diagramId = String(job.diagram_id || 'diagram');
    const renderId = safeId(diagramId);
    const rendered = await global.mermaid.render(renderId, String(job.source || ''));
    result[diagramId] = normalizeSvg(rendered.svg);
  }
  process.stdout.write(JSON.stringify(result));
}

main().catch((error) => {
  process.stderr.write((error && error.stack) ? error.stack : String(error));
  process.exitCode = 1;
});

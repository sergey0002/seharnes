/**
 * Выдвижная левая панель для узкого экрана.
 *
 * На широком экране панель всегда на месте и модуль ничего не делает:
 * кнопка скрыта стилями, состояние ящика остаётся closed.
 * Панель закрывается по Esc, по затемнению и после выбора элемента,
 * чтобы список не занимал экран поверх только что открытого документа.
 */
import { qs } from './dom.js';

const NARROW = 760;

export function createDrawer() {
  const workspace = qs('[data-workspace]');
  const toggle = qs('[data-drawer-toggle]');
  const scrim = qs('[data-drawer-close]');
  if (!workspace || !toggle) return { close() {} };

  const isOpen = () => workspace.dataset.drawer === 'open';

  const set = (open) => {
    workspace.dataset.drawer = open ? 'open' : 'closed';
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    document.body.classList.toggle('drawer-open', open);
  };

  toggle.addEventListener('click', () => set(!isOpen()));
  scrim?.addEventListener('click', () => set(false));

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && isOpen()) set(false);
  });

  // Выбор элемента списка закрывает ящик: дальше человек читает контент.
  workspace.addEventListener('click', (event) => {
    if (!isOpen() || window.innerWidth > NARROW) return;
    if (event.target instanceof Element && event.target.closest('[data-doc-id], [data-node-id]')) {
      set(false);
    }
  });

  // При переходе на широкий экран ящик сбрасывается, чтобы не остался залипший скрим.
  window.addEventListener('resize', () => {
    if (window.innerWidth > NARROW && isOpen()) set(false);
  });

  return { close: () => set(false) };
}

/**
 * Разделитель правой панели: верхняя часть (элемент) и нижняя (данные API).
 * Высота запоминается в localStorage; поддержаны стрелки клавиатуры.
 */
const KEY = 'panel.rightSplit';

export function createSplitter() {
  const panel = document.querySelector('.rightpanel');
  const top = document.querySelector('[data-right-top]');
  const handle = document.querySelector('[data-right-splitter]');
  if (!panel || !top || !handle) return {};

  let ratio = 0.62;
  try {
    const saved = Number(localStorage.getItem(KEY));
    if (saved > 0.2 && saved < 0.85) ratio = saved;
  } catch (error) { /* приватный режим */ }

  const apply = (value) => {
    ratio = Math.min(0.85, Math.max(0.2, value));
    top.style.flexBasis = `${(ratio * 100).toFixed(1)}%`;
  };

  const save = () => {
    try {
      localStorage.setItem(KEY, String(ratio));
    } catch (error) { /* игнорируем */ }
  };

  apply(ratio);

  const onPointerDown = (event) => {
    event.preventDefault();
    const rect = panel.getBoundingClientRect();
    panel.classList.add('is-resizing');

    const move = (moveEvent) => {
      const offset = moveEvent.clientY - rect.top;
      apply(offset / rect.height);
    };
    const up = () => {
      panel.classList.remove('is-resizing');
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      save();
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };

  handle.addEventListener('pointerdown', onPointerDown);
  handle.addEventListener('keydown', (event) => {
    if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;
    event.preventDefault();
    apply(ratio + (event.key === 'ArrowDown' ? 0.05 : -0.05));
    save();
  });

  return { apply };
}

/**
 * Тема оформления: светлая, тёмная, как в системе.
 *
 * Меняется атрибут data-theme на <html>; все цвета живут в CSS-переменных,
 * поэтому переключение не перерисовывает разметку и не требует перезагрузки.
 */
const KEY = 'panel.theme';
const ORDER = ['system', 'light', 'dark'];

export function createTheme({ store }) {
  const root = document.documentElement;
  const media = window.matchMedia('(prefers-color-scheme: dark)');

  const read = () => {
    try {
      const value = localStorage.getItem(KEY);
      return ORDER.includes(value) ? value : 'system';
    } catch (error) {
      return 'system';
    }
  };

  const effective = (mode) => (mode === 'system' ? (media.matches ? 'dark' : 'light') : mode);

  const apply = (mode) => {
    root.dataset.theme = effective(mode);
    root.dataset.themeMode = mode;
    store.set({ themeMode: mode, theme: root.dataset.theme });
  };

  const set = (mode) => {
    const next = ORDER.includes(mode) ? mode : 'system';
    try {
      localStorage.setItem(KEY, next);
    } catch (error) {
      /* приватный режим — тема просто не запомнится */
    }
    apply(next);
  };

  const toggle = () => set(effective(read()) === 'dark' ? 'light' : 'dark');

  media.addEventListener('change', () => {
    if (read() === 'system') apply('system');
  });

  apply(read());

  return { get mode() { return root.dataset.themeMode || 'system'; }, set, toggle, apply };
}

/**
 * Локализация на клиенте.
 *
 * Словарь приходит вместе со страницей (bootstrap), поэтому строки доступны
 * сразу и без дополнительного запроса. Смена языка ставит cookie и перезагружает
 * страницу: серверный рендер и клиент всегда говорят на одном языке.
 */
const COOKIE = 'panel_lang';

export function createI18n({ store, dictionary, lang, availableLangs }) {
  let dict = { ...(dictionary || {}) };
  let current = lang || 'ru';

  const t = (key, params = {}) => {
    const template = dict[key] ?? key;
    return Object.entries(params).reduce(
      (acc, [name, value]) => acc.replaceAll(`{${name}}`, String(value)),
      template,
    );
  };

  const apply = (root = document) => {
    root.querySelectorAll('[data-i18n]').forEach((node) => {
      const key = node.getAttribute('data-i18n');
      if (!key) return;
      node.textContent = t(key);
    });
    root.querySelectorAll('[data-i18n-placeholder]').forEach((node) => {
      const key = node.getAttribute('data-i18n-placeholder');
      if (key) node.setAttribute('placeholder', t(key));
    });
    root.querySelectorAll('[data-i18n-title]').forEach((node) => {
      const key = node.getAttribute('data-i18n-title');
      if (key) node.setAttribute('title', t(key));
    });
  };

  const setLanguage = async (next, apiEndpoint) => {
    if (!availableLangs.includes(next)) return;
    document.cookie = `${COOKIE}=${encodeURIComponent(next)}; path=/; max-age=31536000; samesite=lax`;
    if (apiEndpoint) {
      const first = await fetch(`${apiEndpoint}?lang=${encodeURIComponent(next)}`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      }).then((response) => response.json()).catch(() => null);
      if (first?.data?.dictionary) dict = first.data.dictionary;
    }
    current = next;
    store.set({ lang: next });
    window.location.reload();
  };

  return {
    get lang() { return current; },
    get availableLangs() { return availableLangs; },
    t,
    apply,
    setLanguage,
  };
}

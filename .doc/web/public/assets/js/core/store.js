/**
 * Крошечное наблюдаемое хранилище состояния.
 *
 * Компоненты не общаются напрямую: они пишут в стор и подписываются на изменения.
 * Глубина одна — этого достаточно панели и это дешевле любого фреймворка.
 */
export function createStore(initial = {}) {
  const state = { ...initial };
  const listeners = new Map();

  const emit = (keys) => {
    const seen = new Set();
    keys.forEach((key) => {
      const group = key.split('.')[0];
      if (seen.has(group)) return;
      seen.add(group);
      (listeners.get(group) || []).forEach((listener) => listener(state));
      (listeners.get('*') || []).forEach((listener) => listener(state, group));
    });
  };

  return {
    get state() {
      return state;
    },
    get(key, fallback = undefined) {
      return key.split('.').reduce((acc, part) => (acc == null ? undefined : acc[part]), state) ?? fallback;
    },
    set(patch) {
      const changed = [];
      Object.entries(patch).forEach(([key, value]) => {
        if (state[key] !== value) {
          state[key] = value;
          changed.push(key);
        }
      });
      if (changed.length) emit(changed);
      return state;
    },
    push(key, value) {
      const list = Array.isArray(state[key]) ? state[key] : [];
      list.push(value);
      state[key] = list;
      emit([key]);
      return list;
    },
    on(key, listener) {
      const group = key.split('.')[0];
      if (!listeners.has(group)) listeners.set(group, new Set());
      listeners.get(group).add(listener);
      return () => listeners.get(group).delete(listener);
    },
  };
}

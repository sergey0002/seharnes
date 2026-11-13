/**
 * Клиент API панели.
 *
 * Каждый вызов попадает в историю стора: вкладка «JSON» показывает реальные
 * запросы и ответы, а не отдельную копию данных.
 */
export function createApi({ store, endpoints }) {
  const history = [];
  let sequence = 0;

  const nextId = () => {
    sequence += 1;
    return sequence;
  };

  const buildUrl = (path, query) => {
    const url = new URL(path, window.location.origin);
    Object.entries(query || {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value));
      }
    });
    return url.toString();
  };

  async function request(path, { method = 'GET', query = null, body = null, quiet = false } = {}) {
    const id = nextId();
    const started = performance.now();
    const init = {
      method,
      headers: { 'X-Requested-With': 'XMLHttpRequest', Accept: 'application/json' },
      credentials: 'same-origin',
    };
    if (body !== null) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(body);
    }
    let status = 0;
    let payload = null;
    let failed = false;
    try {
      const response = await fetch(buildUrl(path, query), init);
      status = response.status;
      payload = await response.json().catch(() => null);
    } catch (error) {
      failed = true;
      status = 0;
      payload = { status: 'failed', error: String(error) };
    }
    const entry = {
      id,
      method,
      path,
      query,
      url: buildUrl(path, query),
      status,
      ok: !failed && status >= 200 && status < 300,
      ms: Math.round(performance.now() - started),
      at: new Date().toISOString(),
      response: payload,
    };
    history.unshift(entry);
    if (history.length > 60) history.pop();
    if (!quiet) {
      store.set({ apiHistory: history.slice(), lastApi: entry });
    }
    return entry;
  }

  return {
    history,
    get: (path, query, options = {}) => request(path, { ...options, query }),
    post: (path, body, options = {}) => request(path, { ...options, method: 'POST', body }),
    endpoint: (name) => endpoints[name] || '',
  };
}

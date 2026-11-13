/**
 * Чтение серверного bootstrap: язык, словарь, эндпоинты, начальное состояние.
 * Один JSON-блок в разметке — единственный канал «сервер -> клиент» на старте.
 */
export function readBoot() {
  const node = document.getElementById('panel-boot');
  if (!node) {
    return { lang: 'ru', dictionary: {}, endpoints: {}, base: '/panel', section: '', selected: null };
  }
  let data = {};
  try {
    data = JSON.parse(node.textContent || '{}');
  } catch (error) {
    console.error('panel: cannot parse bootstrap', error);
  }
  return { dictionary: {}, endpoints: {}, availableLangs: ['ru'], ...data };
}

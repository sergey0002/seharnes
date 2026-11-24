# Создать очередь

```bash
tqueue init site --root <root>
tqueue init release --root <root> --path /work/release-queue
```

Команда регистрирует `alias → absolute path` в `<root>/.todone/queues.json` и
создаёт `<queue>/.todone/index.json` с пустым `items`. `data/` появляется при
первой записи. Не редактируй `queues.json`/`index.json` руками.

После создания:

```bash
tqueue list --queue site --root <root>
tqueue board --queue site --root <root>
```

Если в проекте несколько очередей, всегда называй `--queue`.

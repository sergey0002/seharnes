# Локальный эмбеддинг-стек Ollama

<!-- meta
type: architecture
status: actual
updated: 2026-11-09
related: [./15-mcp-stack.md]
tags: [ollama, embeddings, graphiti, wsl, cpu, qwen3, docker]
-->

## Суть

Эмбеддинги для локальных ИИ-инструментов на машине разработчика считает Ollama внутри WSL.
Сервер `0.0.0.0:11434`, модель `qwen3-embedding:0.6b` (1024 измерения), тёплая латентность 99-117 ms на CPU.
Установка нативная в WSL (`/home/newuser/.local/ollama-main/`), без Docker.
Сервер запускается systemd-юнитом `ollama-qwen.service` и стартует при загрузке WSL.
Причина отказа от Docker-контейнера `fastembed-api` (`michaelf34/infinity:latest`, 14.3 ГБ) и от iGPU Radeon 780M: CPU Ryzen 8845HS с ядром Zen4 быстрее бенчмарка 780M через Vulkan, а WSL не отдаёт `/dev/dri` для iGPU.
Предыдущий стек FastEmbed (`infinity_emb`, модель `intfloat/multilingual-e5-small`, 384 измерения) остановлен, контейнер `fastembed-api` удалён.
Контейнер `graphiti` работает и с 2026-11-09 считает эмбеддинги через Ollama: `http://host.docker.internal:11434/v1`, модель `qwen3-embedding:0.6b`, 1024 измерения.

> **AI:** читай этот документ, если нужен эндпоинт эмбеддингов в WSL, настройка Graphiti на Ollama, диагностика GPU в WSL или причины раздувания VHDX от Docker-образов.
> Ресурсы машины (VmmemWSL, диск, VHDX): local-dev-resources.md (проект Target).
> См. также: конфиг Graphiti `.cursor/mcp-stack/graphiti/config.yaml`, compose `.cursor/mcp-stack/graphiti/docker-compose.yml`, документация скила `.agents/skills/graphiti/docs/mcp/graphiti.md`.

---

## Установка

| Компонент | Путь | Детали |
|---|---|---|
| Бинарник Ollama | `/home/newuser/.local/ollama-main/bin/ollama` | v0.40.15, 4.9 ГБ, включает ROCm-библиотеки и ядро `libggml-cpu-zen4.so` |
| Модели | `/home/newuser/.local/ollama-models/` | `qwen3-embedding:0.6b`, 639 МБ |
| Лог сервера | `/tmp/kilo/ollama-serve.log` | дописывается systemd-юнитом `ollama-qwen.service` |

Установка из релизов GitHub (`ollama-linux-amd64.tar.zst` + `ollama-linux-amd64-rocm.tar.zst`), распаковка `python3 -c` с пакетом `zstandard` (`pip install --user --break-system-packages zstandard`), ROCm-библиотеки скопированы в основную папку командой `cp -rn`.

### Запуск сервера

Сервер работает как systemd-юнит пользователя `ollama-qwen.service`:

```bash
systemctl --user status ollama-qwen.service
systemctl --user restart ollama-qwen.service
```

Юнит лежит в `~/.config/systemd/user/ollama-qwen.service` и включён в `default.target`.
`Linger=yes` для пользователя `newuser` поднимает юнит при старте WSL без входа в сессию.
Ручной запуск для отладки:

```bash
OLLAMA_HOST=0.0.0.0 OLLAMA_MODELS=/home/newuser/.local/ollama-models \
  /home/newuser/.local/ollama-main/bin/ollama serve
```

### Проверка

```bash
curl -s http://127.0.0.1:11434/api/embed \
  -d '{"model":"qwen3-embedding:0.6b","input":"проверка"}'
```

Ожидаемый результат: JSON с `embeddings[0]` длиной 1024.

---

## Результаты тестов

Сервер v0.40.15, WSL Ubuntu, CPU Ryzen 7 8845HS. Прогон 2026-11-08: 11 проверок, 11 PASS.
Повторная проверка 2026-11-09 после перехода на systemd: `GET /api/tags` вернул `qwen3-embedding:0.6b` с `embedding_length: 1024`, `POST /api/embed` и `POST /v1/embeddings` вернули векторы длиной 1024, порт `*:11434` слушает процесс `ollama`.

| Проверка | Результат |
|---|---|
| Health endpoint `GET /` | PASS |
| Модель в реестре `GET /api/tags` | PASS |
| `/api/embed`: 1024 измерения | PASS |
| `/v1/embeddings` ([OI]-совместимый): 200, 1024 dim | PASS |
| Детерминизм: тот же вход даёт тот же вектор | PASS |
| Батч: 4 входа дают 4 вектора | PASS |
| Мультиязычность RU/EN: векторы без NaN | PASS |
| Длинный текст 2000 слов: принимается, транкейтится | PASS |
| Семантика: похожие фразы cos 0.700, далёкие cos 0.344 | PASS |
| Тёплая латентность (5 запросов) | 99-117 ms |
| Параллелизм: 4 одновременных запроса | все 200 |

Размерность 1024 подтверждена на обеих версиях API.

---

## Почему CPU, а не iGPU Radeon 780M

| Вариант | Статус | Причина |
|---|---|---|
| Ollama в WSL на CPU | рабочий | ядро `libggml-cpu-zen4.so`, тёплая латентность 99-117 ms |
| Ollama в WSL на 780M | не работает | WSL не отдаёт `/dev/dri`; проверены `HSA_OVERRIDE_GFX_VERSION=11.0.2` и `OLLAMA_IGPU_ENABLE=1`, GPU не обнаруживается |
| Ollama в Docker внутри WSL | отклонено | те же ограничения GPU + образ ollama 3.2 ГБ при медленной сети |
| Ollama на Windows хосте | запасной | бенчмарк 780M через Vulkan даёт 875 ms (источник: `qiurui144/local-ai-bench`, `reports/amd-windows-igpu.en.md`), медленнее CPU |
| ONNX DirectML в WSL | не выбран | требует `onnxruntime-directml` и своего сервера; выигрыш для e5-small незначителен |

ROCm официально не поддерживает gfx1103 (780M) в WSL; матрицы поддержки AMD включают только дискретные RX 7000/9000.

---

## Graphiti на Ollama (выполнен)

Конфиг Graphiti `.cursor/mcp-stack/graphiti/config.yaml` и compose `.cursor/mcp-stack/graphiti/docker-compose.yml` с 2026-11-09 указывают на Ollama:

```yaml
embedder:
  provider: "openai"
  model: "qwen3-embedding:0.6b"
  dimensions: 1024
  providers:
    openai:
      api_key: "ollama"
      api_url: "http://host.docker.internal:11434/v1"
```

Фактический env контейнера `graphiti` после пересоздания: `EMBEDDER_API_URL=http://host.docker.internal:11434/v1`, `EMBEDDER_MODEL=qwen3-embedding:0.6b`, `EMBEDDER_DIMENSIONS=1024`, `EMBEDDER_API_KEY=ollama`.
Проверка из контейнера: `POST http://host.docker.internal:11434/v1/embeddings` вернул вектор длиной 1024.
Граф FalkorDB на момент переключения был пуст (0 узлов), поэтому переиндексация не потребовалась.
При переходе с 384 на 1024 на заполненном графе очисти том `falkordb_data` и переиндексируй эпизоды, иначе старые векторы несовместимы.

---

## jdocmunch на Qwen (замер, не включено)

2026-11-09 проверен jdocmunch на этом векторизаторе: OpenAI-compatible endpoint
`http://127.0.0.1:11434/v1`, модель `qwen3-embedding:0.6b`, 1024 измерения.
Замер на двух стратифицированных корпусах: архитектура 616 секций, задачи и
точные термины 243 секции.

На архитектуре векторы лучше: MRR 0.623 у lexical, 0.752 у hybrid 0.2 и 0.842
у semantic-only. На задачах и точных терминах лучше lexical: 0.933 против 0.875
у hybrid и 0.586 у semantic-only.

Векторы в jdocmunch не включены: рабочий индекс остается лексическим, лаунчер
передает `--embeddings off`. Полная пересборка 29287 секций занимает около
5 часов при окне 300 символов.

Отчет, скрипт и результаты:
`.doc/skil_data/jdocmunch-benchmark/README.md` в проекте Target.

## Очистка Docker-образов, связанных со стеком

Образы предыдущего стека занимают место в `ext4.vhdx` (рост VHDX, см. local-dev-resources.md §9 (проект Target)):

| Образ | Размер | Содержимое |
|---|---|---|
| `michaelf34/infinity:latest` | 14.3 ГБ | слой `COPY /app /app` 8.76 ГБ: все модели эмбеддингов, vision и audio |
| `zepai/knowledge-graph-mcp:1.1.3` | 10.9 ГБ | слой `sfw uv sync --extra providers --extra azure` 6.38 ГБ: torch, transformers, sentence-transformers и все LLM-провайдеры |
| `nousresearch/hermes-agent:latest` | 4.56 ГБ | агент |

Тома `copytrust-graphiti_ollama_data` и `graphiti_ollama_data` удалены 2026-11-08 (мёртвые, объявлены в compose, но не смонтированы). Ollama работает отдельным systemd-сервисом вне Docker, в стек Graphiti не входит.
Если старый стек не нужен, удали образы `docker rmi` и выполни сжатие VHDX по local-dev-resources §9.2.

---

## Известные ограничения

- Ollama в WSL видит только CPU: имена `inference compute` в логе показывают `library=cpu`.
- CLI `ollama list` требует запущенный сервер; при остановленном сервере команда отвечает `could not connect`.
- Юнит `ollama-qwen.service` стартует при загрузке WSL благодаря `Linger=yes`. Если linger выключен, сервер поднимется только после входа пользователя.
- Сеть медленная: тарболы Ollama 1-1.5 ГБ качаются 10-15 минут на медленном канале.

---

## История изменений

| Дата | Что изменилось | Почему |
|---|---|---|
| 2026-11-08 | Создан документ: установка Ollama в WSL, модель qwen3-embedding:0.6b, тесты, отказ от iGPU и Docker, план переноса Graphiti | Проблема 100% Disk от Docker/AI-процессов; поиск рабочего эмбеддинг-движка для 8845HS; остановка контейнеров fastembed-api и graphiti |
| 2026-11-09 | Ollama переведён на systemd-юнит `ollama-qwen.service` с автозапуском, Graphiti переключён с FastEmbed 7997/e5-small/384 на Ollama 11434/qwen3-embedding:0.6b/1024 | Убраны расхождения между документацией, env контейнера и фактически запущенным эмбеддером |
| 2026-11-09 | Проверен jdocmunch на qwen3-embedding:0.6b: архитектура лучше с векторами, задачи и точные термины лучше лексически; векторы не включены | Оценить применение векторизатора к поиску документации, отчет в `.doc/skil_data/jdocmunch-benchmark/` |

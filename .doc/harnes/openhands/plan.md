# План развертывания и переноса OpenHands в Docker

<!-- meta
type: plan
status: completed
version: 1.1
updated: 2026-11-07
applies-to: devops, openhands, docker, wsl
related: [README.md, .tools/openhands/compose.yaml, .doc/harnes/index.md]
tags: [openhands, agent, docker, wsl, migration, devops]
-->

---

## 1. Цель и архитектурная концепция

Цель: развернуть автономного AI-разработчика OpenHands в изолированном Docker-контейнере на локальном WSL2 по тому же принципу, что и Hermes Agent. Обеспечить сохранение настроек, учетных данных и рабочей области в постоянном хранилище, подготовить структуру каталога для бесшовного переноса на удаленный Linux-сервер.

### Принцип разделения состояния и движка

- Движок: stateless Docker-образ `docker.openhands.dev/openhands/openhands:latest`.
- Состояние и креды: каталог `./state` (монтируется в `/.openhands-state` контейнера). В нем сохраняются настройки провайдеров, API-ключи, история диалогов и сессии.
- Рабочая область: каталог `./workspace` (монтируется в `/opt/workspace_base`). В нем агент создает код, выполняет git-команды и сохраняет проектные файлы.
- Песочница исполнения: Docker socket (`/var/run/docker.sock`) для создания изолированных runtime-контейнеров командной строки.
- Управление: файл `compose.yaml` в `.tools/openhands/`.

---

## 2. Диагностика сети и выбор портов

Стандартный порт OpenHands равен 3000. В текущем окружении WSL2 порт 3000 занят контейнером `graphiti`.
Для предотвращения конфликта портов внешний порт для OpenHands назначен на `3001`:

| Сервис | Порт внутри контейнера | Порт на хосте WSL2 / Windows | Статус порта на хосте |
|--------|------------------------|------------------------------|-----------------------|
| `graphiti` | 3000 | 3000 | Занят |
| `openhands` | 3000 | 3001 | Свободен |
| `hermes-agent` | 9119 | 9119 | Занят Hermes |

Доступ к веб-панели OpenHands открывается по адресу `http://localhost:3001`.

---

## 3. Структура каталога .tools/openhands

Все файлы сервиса размещаются в каталоге `.tools/openhands/`:

```
.tools/openhands/
├── compose.yaml          # Конфигурация Docker Compose
├── .env                  # Локальные переменные окружения и ключи
├── .env.example          # Шаблон переменных с описанием параметров
├── state/                # Хранилище настроек, токенов и сессий (/.openhands-state)
└── workspace/            # Рабочая директория проектов (/opt/workspace_base)
```

---

## 4. Конфигурация сервиса

### 4.1 Файл compose.yaml

```yaml
services:
  openhands:
    image: docker.openhands.dev/openhands/openhands:latest
    container_name: openhands-app
    restart: unless-stopped
    ports:
      - "3001:3000"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./state:/.openhands-state
      - ./workspace:/opt/workspace_base
    environment:
      - OH_PERSISTENCE_DIR=/.openhands-state
      - SANDBOX_RUNTIME_CONTAINER_IMAGE=docker.openhands.dev/openhands/runtime:latest
      - WORKSPACE_MOUNT_PATH=/opt/workspace_base
      - LOG_ALL_EVENTS=true
      - SANDBOX_USER_ID=1000
      - LLM_MODEL=${LLM_MODEL:-}
      - LLM_API_KEY=${LLM_API_KEY:-}
      - LLM_BASE_URL=${LLM_BASE_URL:-}
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

### 4.2 Шаблон .env.example

```bash
# Модель LLM (например: anthropic/claude-3-5-sonnet-20241022, openrouter/anthropic/claude-3.5-sonnet, openai/gpt-4o)
LLM_MODEL=

# Ключ доступа к выбранному провайдеру LLM
LLM_API_KEY=

# Кастомный URL эндпоинта
LLM_BASE_URL=

# Порт на хосте
OPENHANDS_PORT=3001
```

---

## 5. Управление учетными данными (Креды)

Креды для OpenHands настраиваются двумя путями:
1. **Через веб-интерфейс**: при первом открытии `http://localhost:3001` в окне Settings вводятся API-ключ и выбирается модель. Настройки записываются в файл `.tools/openhands/state/settings.json`.
2. **Через файл .env**: переменные `LLM_MODEL` и `LLM_API_KEY` считываются при старте контейнера, что исключает ручной ввод при автоматическом развертывании.

---

## 6. Пошаговый сценарий переноса на сервер

### Шаг 1. Экспорт на локальной машине
```bash
cd /home/newuser/projects/copytrust/testdeploydocker/.tools/openhands
tar -czvf openhands-server-bundle.tar.gz compose.yaml .env state/ workspace/
```

### Шаг 2. Копирование на сервер
```bash
scp openhands-server-bundle.tar.gz user@server-ip:/opt/openhands/
```

### Шаг 3. Запуск на сервере
```bash
cd /opt/openhands
tar -xzvf openhands-server-bundle.tar.gz
docker compose up -d
```

Все сессии, ключи и файлы репозитория в рабочей области сохраняются полностью.

---

## 7. Чек-лист готовности

- [x] Образ `docker.openhands.dev/openhands/openhands:latest` скачан в Docker.
- [x] Каталог `.tools/openhands` сформирован.
- [x] Контейнер `openhands-app` запущен и отвечает по порту 3001.
- [x] Проверено открытие страницы `http://localhost:3001` в браузере (HTTP 200 OK).
- [x] Настройки и база данных SQLite зафиксированы в `state/`.
- [x] Документация подготовлена в `.doc/harnes/openhands/`.

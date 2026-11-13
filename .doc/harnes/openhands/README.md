# OpenHands - Эксплуатация и документация развертывания

<!-- meta
type: operational
status: actual
version: 1.0
updated: 2026-11-07
applies-to: devops, openhands, docker, wsl
related: [plan.md, file://wsl.localhost/Ubuntu/home/newuser/projects/copytrust/testdeploydocker/.tools/openhands/compose.yaml]
tags: [openhands, agent, docker, wsl, dashboard, migration]
-->

---

## 1. Общие сведения

Автономный агент разработки программного обеспечения OpenHands развернут в Docker на WSL2. Сервис настроен по единому архитектурному стандарту с Hermes Agent: stateless-образ контейнера, изолированное постоянное хранилище и готовность к быстрому переносу на сервер.

| Параметр | Значение |
|----------|----------|
| **Контейнер** | `openhands-app` |
| **Образ** | `docker.openhands.dev/openhands/openhands:latest` |
| **Статус** | Запущен, активен (Up), код ответа HTTP 200 OK |
| **Веб-интерфейс** | `http://localhost:3001` |
| **Внутренний порт** | `3000` |
| **Каталог стека** | `.tools/openhands/` |
| **Конфигурация Compose** | `.tools/openhands/compose.yaml` |
| **Хранилище состояния** | `.tools/openhands/state/` (монтируется в `/.openhands-state`) |
| **Рабочая директория** | `.tools/openhands/workspace/` (монтируется в `/opt/workspace_base`) |
| **Песочница исполнения** | Docker socket (`/var/run/docker.sock`) |

---

## 2. Веб-интерфейс и учетные данные (Креды)

### 2.1 Адрес интерфейса

Интерфейс доступен в браузере Windows по адресу:
**`http://localhost:3001`**

Порт 3000 на хосте занят сервисом `graphiti`, поэтому для OpenHands назначен порт 3001.

### 2.2 Настройка кредов и моделей

Подключен локальный OpenAI-совместимый шлюз FreeLLM API:
- **Эндпоинт**: `http://localhost:3100/v1` (для контейнера OpenHands транслируется через `http://host.docker.internal:3100/v1`).
- **Модель**: `auto:smart` (в LiteLLM / OpenHands регистрируется как `openai/auto:smart`).
- **Ключ API**: `freellmapi-e5606967251f76ce8065ca27311f3e8762defd9e358ccf43`.
- **Локальный сервис FreeLLM**: `C:\aifree\freellmapi\`, запуск через `start-freellmapi.vbs` или `start-freellmapi.cmd`.
- **Проброс в WSL**: служба `freellmapi-forward.service` (`socat TCP4-LISTEN:3100,fork,reuseaddr TCP4:$HOST_IP:3100`), что делает порт 3100 доступным как в WSL, так и внутри Docker через `host.docker.internal`.
- **Статус готовности**: `llm_api_key_set: true` подтвержден через API `/api/v1/settings`.

Резервный провайдер (OpenRouter):
- **Провайдер**: OpenRouter (`https://openrouter.ai/api/v1`)
- **Модель**: `openrouter/openrouter/free`
- **Ключ API**: сохранен в виде комментария в `.tools/openhands/.env`.
- Особенность тарифа: 50 бесплатных запросов в день на аккаунт.

Для смены модели:
- В интерфейсе: меню Settings -> LLM -> поле Model.
- В файле `.env`: параметр `LLM_MODEL` в `.tools/openhands/.env`.

---

## 3. Архитектура песочницы и безопасность

OpenHands выполняет написание кода, запуск тестов и команд bash в изолированном runtime-контейнере через Docker socket:
- Образ рантайма: `docker.openhands.dev/openhands/runtime:latest`.
- Пользователь рантайма: `enduser` с UID 1000, что совпадает с правами пользователя WSL2 и исключает конфликты прав на созданные файлы.
- Код проектов сохраняется в `.tools/openhands/workspace/`.

---

## 4. Конфигурация compose.yaml

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

---

## 5. Команды управления

Все команды выполняются из каталога `.tools/openhands/` в WSL2:

```bash
cd /home/newuser/projects/copytrust/testdeploydocker/.tools/openhands

# Проверка статуса контейнера
docker compose ps

# Просмотр логов в реальном времени
docker compose logs -f

# Перезапуск сервиса
docker compose restart

# Остановка сервиса
docker compose down
```

---

## 6. Процедура переноса на удаленный сервер

Перенос на сервер выполняется без потери истории, базы данных и кода:

### Шаг 1. Создание архива
```bash
cd /home/newuser/projects/copytrust/testdeploydocker/.tools/openhands
tar --exclude='workspace/.git' -czvf openhands-bundle.tar.gz compose.yaml .env state/ workspace/
```

### Шаг 2. Копирование на сервер
```bash
scp openhands-bundle.tar.gz user@server-ip:/opt/openhands/
```

### Шаг 3. Запуск на сервере
```bash
cd /opt/openhands
tar -xzvf openhands-bundle.tar.gz
docker compose up -d
```

### Шаг 4. Настройка публичного доступа на сервере
1. Привязать порт к loopback в `compose.yaml`:
   ```yaml
   ports:
     - "127.0.0.1:3000:3000"
   ```
2. Поднять обратный прокси Nginx или Caddy с SSL-сертификатом Let's Encrypt и настроить Basic Auth.

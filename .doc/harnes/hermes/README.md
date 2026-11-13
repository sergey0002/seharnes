# Hermes Agent - Эксплуатация и документация развертывания

<!-- meta
type: operational
status: actual
version: 1.0
updated: 2026-11-07
applies-to: devops, hermes, docker, wsl
related: [plan.md, file://wsl.localhost/Ubuntu/home/newuser/projects/copytrust/testdeploydocker/.tools/hermes/compose.yaml]
tags: [hermes, agent, docker, wsl, dashboard, migration]
-->

---

## 1. Общие сведения

Локальный автономный AI-агент Hermes Agent развернут в Docker на WSL2. Сервис настроен с постоянным хранилищем состояния и веб-интерфейсом управления.

| Параметр | Значение |
|----------|----------|
| **Контейнер** | `hermes-agent` |
| **Образ** | `nousresearch/hermes-agent:latest` |
| **Статус** | Запущен, активен (Up), код ответа HTTP 200 OK |
| **Веб-интерфейс** | `http://localhost:9119` |
| **API Gateway** | `http://localhost:8642` |
| **Каталог стека** | `.tools/hermes/` |
| **Конфигурация Compose** | `.tools/hermes/compose.yaml` |
| **Хранилище состояния** | `.tools/hermes/data/` (монтируется в `/opt/data`) |
| **Сетевой режим** | `network_mode: host` (WSL2 loopback) |

---

## 2. Веб-интерфейс (Hermes Dashboard)

### 2.1 Адрес и авторизация

Интерфейс доступен в браузере Windows по адресу:
**`http://localhost:9119`**

Особенность аутентификации:
Hermes Agent требует обязательную авторизацию при привязке к внешним адресам (`0.0.0.0`). Использование `network_mode: host` и привязка к `127.0.0.1` переводят агент в локальный доверенный режим (`window.__HERMES_AUTH_REQUIRED__=false`). Вход из браузера Windows на `http://localhost:9119` выполняется напрямую без пароля.

### 2.2 Разделы интерфейса

1. **Chat**: интерактивный диалог с агентом, переключение активного профиля.
2. **Config**: настройка провайдеров LLM (OpenRouter, Anthropic, OpenAI, локальные модели), ввод API-ключей, выбор модели по умолчанию.
3. **Skills**: реестр навыков агента (44 встроенных системных навыка плюс пользовательские навыки).
4. **Memories**: просмотр долгосрочной памяти (`MEMORY.md`, `USER.md`) и истории диалогов.

---

## 3. Архитектура и хранение данных

Все изменяемые данные агента вынесены в подкаталог `.tools/hermes/data/`. Сам контейнер остается stateless.

Структура каталога `.tools/hermes/`:
```
.tools/hermes/
├── compose.yaml          # Конфигурация Docker Compose
└── data/                 # Точка монтирования /opt/data
    ├── config.yaml       # Конфигурация провайдеров и моделей
    ├── memories/         # Долговременная память
    ├── skills/           # Навыки агента
    └── sessions.db       # База данных сессий
```

### Действующий файл compose.yaml

```yaml
services:
  hermes:
    image: nousresearch/hermes-agent:latest
    container_name: hermes-agent
    restart: unless-stopped
    command: gateway run
    network_mode: host
    volumes:
      - ./data:/opt/data
    environment:
      - HERMES_DASHBOARD=1
      - HERMES_DASHBOARD_HOST=127.0.0.1
      - HERMES_DASHBOARD_PORT=9119
      - API_SERVER_ENABLED=true
      - API_SERVER_HOST=127.0.0.1
      - API_SERVER_KEY=hermes-local-token-secret-12345
      - API_SERVER_CORS_ORIGINS=*
      - TERMINAL_ENV=local
```

---

## 4. Команды управления

Все команды выполняются из каталога `.tools/hermes/` в WSL2:

```bash
cd /home/newuser/projects/copytrust/testdeploydocker/.tools/hermes

# Проверка статуса контейнера
docker compose ps

# Просмотр логов в реальном времени
docker compose logs -f

# Перезапуск сервиса
docker compose restart

# Остановка сервиса
docker compose down

# Выполнение запроса через CLI агента
docker compose exec hermes hermes "Привет! Проверь доступные инструменты."
```

---

## 5. Процедура переноса на удаленный сервер

Перенос на сервер не требует повторной настройки навыков и памяти.

### Шаг 1. Создание архива на локальной машине

В каталоге `.tools/hermes/`:
```bash
tar --exclude='data/logs/*' --exclude='data/cache/*' -czvf hermes-bundle.tar.gz compose.yaml data/
```

### Шаг 2. Копирование на сервер

```bash
scp hermes-bundle.tar.gz user@server-ip:/opt/hermes/
```

### Шаг 3. Развертывание на сервере

На удаленном сервере:
```bash
cd /opt/hermes
tar -xzvf hermes-bundle.tar.gz
docker compose up -d
```

### Шаг 4. Настройка безопасности на публичном сервере

При развертывании на сервере с публичным IP-адресом:
1. Заменить в `compose.yaml` параметр `network_mode: host` на публикацию портов с привязкой к loopback:
   ```yaml
   ports:
     - "127.0.0.1:9119:9119"
     - "127.0.0.1:8642:8642"
   ```
2. Настроить обратный прокси Nginx или Caddy с HTTPS-сертификатом Let's Encrypt.
3. Закрыть доступ к веб-панели через HTTP Basic Auth или настроить сессионный токен `HERMES_DASHBOARD_SESSION_TOKEN`.

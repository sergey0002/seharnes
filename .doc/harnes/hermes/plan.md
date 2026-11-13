# План развертывания и переноса Hermes Agent в Docker

<!-- meta
type: plan
status: completed
version: 1.1
updated: 2026-11-07
applies-to: devops, hermes, docker, wsl
related: [README.md, .tools/hermes/compose.yaml, .doc/harnes/index.md]
tags: [hermes, agent, docker, wsl, migration, devops]
-->

---

## 1. Цель и концепция архитектуры

Цель: развернуть автономного AI-агента Hermes Agent (образ `nousresearch/hermes-agent:latest`) в изолированном Docker-контейнере на локальном WSL2, полностью настроить рабочее окружение (модели, шлюз, веб-панель управления, хранилище навыков и долговременной памяти) и подготовить структуру файлов так, чтобы перенос на удаленный Linux-сервер выполнялся копированием одного каталога и запуском одной команды `docker compose up -d`.

### Архитектурный принцип переносимости

Переносимость строится на разделении движка и данных:
- Движок: stateless Docker-образ `nousresearch/hermes-agent:latest`.
- Состояние: локальный каталог `./data` (монтируется в контейнер по пути `/opt/data`).
- Переменные окружения: файл `.env`.
- Управление: файл `compose.yaml`.

Все знания агента, история диалогов, обученные навыки (`skills/`), долговременная память (`MEMORY.md`, `USER.md`) и конфигурация (`config.yaml`) сохраняются строго в каталоге `./data`. Контейнер не хранит уникальных данных внутри своего слоя.

---

## 2. Диагностика текущего окружения WSL2

Проверка хоста WSL2 показала готовность к развертыванию:

| Компонент / Ресурс | Фактическое состояние | Требование |
|--------------------|-----------------------|------------|
| Docker Engine | 29.1.3 | Готов |
| Docker Compose | v2.40.3 | Готов |
| Доступная память RAM | ~3.4 ГБ доступно (из 15 ГБ) | Минимум 2 ГБ для работы агента |
| Дисковое пространство | 871 ГБ свободно | Минимум 5 ГБ под образы и кэш |
| Порт 8642 (Hermes Gateway / API) | Свободен | Требуется для API-сервера |
| Порт 9119 (Hermes Dashboard) | Свободен | Требуется для веб-интерфейса |

---

## 3. Целевая структура каталога .tools/hermes

Все компоненты агента размещаются в выделенном каталоге `.tools/hermes/`:

```
.tools/hermes/
├── compose.yaml          # Конфигурация сервисов Docker Compose
├── .env                  # Локальные переменные и секреты (не коммитится в Git)
├── .env.example          # Шаблон переменных с описанием параметров
├── data/                 # Точка монтирования в /opt/data контейнера
│   ├── config.yaml       # Основная конфигурация агента и моделей
│   ├── memories/         # Долговременная память (MEMORY.md, USER.md)
│   ├── skills/           # Каталог динамически обученных навыков агента
│   └── sessions.db       # База данных сессий и истории диалогов
└── scripts/              # Вспомогательные скрипты автоматизации
    ├── setup.sh          # Первичная инициализация через interactive wizard
    ├── start.sh          # Фоновый запуск сервисов
    ├── stop.sh           # Остановка контейнеров
    ├── cli.sh            # Вход в интерактивный терминал агента
    └── export-bundle.sh  # Создание переносимого архива для сервера
```

---

## 4. Конфигурация компонентов

### 4.1 Файл compose.yaml

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

Примечания по параметрам:
- Режим `network_mode: host` и привязка к `127.0.0.1` обеспечивают доверенный локальный доступ к Dashboard без пароля (`window.__HERMES_AUTH_REQUIRED__=false`).
- Из браузера Windows доступ открывается по адресу `http://localhost:9119`.
- `HERMES_DASHBOARD=1` запускает веб-панель управления внутри того же контейнера.
- `TERMINAL_ENV=local` позволяет агенту выполнять команды в контексте своего окружения.

### 4.2 Шаблон .env.example

```bash
# Ключ авторизации для доступа к OpenAI-совместимому API Hermes Gateway
API_SERVER_KEY=change-me-to-secure-token-32-chars

# Ключи провайдеров LLM (укажите один или несколько)
OPENROUTER_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# Провайдер и модель по умолчанию
DEFAULT_PROVIDER=openrouter
DEFAULT_MODEL=nousresearch/hermes-3-llama-3.1-70b

# Опционально: интеграция с мессенджерами для удаленного управления
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USERS=
DISCORD_BOT_TOKEN=

# Идентификатор пользователя на хосте для корректных прав на файлы
HERMES_UID=1000
HERMES_GID=1000
```

---

## 5. Пошаговый план внедрения на локальном WSL2

### Этап 1. Подготовка каталогов и окружения
1. Создать каталог `.tools/hermes` и подкаталоги `data`, `scripts`.
2. Назначить права доступа на каталог `data` текущему пользователю WSL2 (`chown -R 1000:1000 data`).
3. Подготовить файлы `compose.yaml` и `.env.example`.
4. Скопировать `.env.example` в `.env` и сгенерировать надежный `API_SERVER_KEY` командой:
   `openssl rand -hex 16`.

### Этап 2. Первичная инициализация конфигурации
1. Запустить разовый интерактивный мастер конфигурации Hermes:
   ```bash
   docker run -it --rm -v $(pwd)/data:/opt/data nousresearch/hermes-agent setup
   ```
2. Выбрать основного провайдера (OpenRouter, OpenAI, Anthropic или собственный локальный эндпоинт).
3. Ввести API-ключи. Мастер запишет параметры в `data/config.yaml` и `data/.env`.
4. Проверить создание файлов `data/config.yaml` и структуры подкаталогов `data/memories`, `data/skills`.

### Этап 3. Запуск и проверка работоспособности
1. Запустить стек сервиса:
   ```bash
   docker compose up -d
   ```
2. Проверить статус запуска через `docker compose ps` и лог через `docker compose logs -f`.
3. Проверить доступность API-сервера:
   ```bash
   curl -i http://localhost:8642/health
   ```
4. Открыть в браузере веб-панель Hermes Dashboard: `http://localhost:9119`.
5. Провести тестовый запрос через интерактивный CLI:
   ```bash
   docker compose exec -it hermes-agent hermes "Привет! Представься и перечисли свои доступные инструменты."
   ```

### Этап 4. Верификация сохранения данных
1. Создать тестовый навык или зафиксировать тестовое воспоминание через агент.
2. Перезапустить контейнер: `docker compose restart`.
3. Убедиться, что воспоминания и навыки сохранились в каталоге `data/memories/` и `data/skills/`.

---

## 6. Стратегия переноса на удаленный сервер

Поскольку контейнер не привязан к локальному железу, перенос состоит из четырех действий:

### Шаг 1. Экспорт на локальном WSL (скрипт export-bundle.sh)
Скрипт собирает архив без временных файлов и кэша:
```bash
#!/usr/bin/env bash
set -euo pipefail

TARGET_ARCHIVE="hermes-server-bundle.tar.gz"
echo "Сборка архива $TARGET_ARCHIVE..."

tar --exclude='data/logs/*' \
    --exclude='data/cache/*' \
    --exclude='*.tmp' \
    -czvf "$TARGET_ARCHIVE" \
    compose.yaml \
    .env \
    data/ \
    scripts/

echo "Архив успешно создан: $TARGET_ARCHIVE"
```

### Шаг 2. Передача архива на сервер
```bash
scp hermes-server-bundle.tar.gz user@server-ip:/opt/hermes/
```

### Шаг 3. Распаковка и запуск на сервере
```bash
# На удаленном сервере:
cd /opt/hermes
tar -xzvf hermes-server-bundle.tar.gz
docker compose up -d
```

### Шаг 4. Настройка защищенного доступа на сервере
1. Оставить порты 8642 и 9119 привязанными к `127.0.0.1` в `compose.yaml`.
2. Настроить обратный прокси Nginx или Caddy с SSL-сертификатом Let's Encrypt для доступа к Web Dashboard.
3. Добавить базовую HTTP-аутентификацию (Basic Auth) или закрыть панель через VPN (WireGuard/Tailscale).

---

## 7. Чек-лист готовности и статуса

- [x] Образ `nousresearch/hermes-agent:latest` успешно загружен в WSL2 Docker.
- [x] Каталог `.tools/hermes` создан и изолирован.
- [x] Контейнер `hermes-agent` запущен и активен.
- [x] Порт 9119 слушает, Dashboard доступен по `http://localhost:9119` (код HTTP 200 OK).
- [x] Каталог `data/` сохраняет состояние (`memories/`, `skills/`, `sessions.db`).
- [ ] Экспорт архива `hermes-server-bundle.tar.gz` перед переносом на прод-сервер.
- [ ] Перенос и запуск `docker compose up -d` на сервере.

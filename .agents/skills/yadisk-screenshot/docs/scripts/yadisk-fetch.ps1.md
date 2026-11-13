# Скрипт: `.agents/skills/yadisk-screenshot/scripts/yadisk-fetch.ps1`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, yadisk-fetch, yandex-disk]
-->

## Суть
Скачивает файл (обычно скриншот) по публичной ссылке Яндекс.Диска и сохраняет в `.doc/skil_data/yadisk-screenshot/imd/`. Имя файла детерминировано по SHA256-хешу нормализованного URL — повторный запуск с той же ссылкой не качает заново, а возвращает путь к уже существующему файлу (cache hit). Используется публичный API Яндекс.Диска (cloud-api.yandex.net) — авторизация не требуется. Финальный путь к файлу выводится в stdout (Write-Output), статус — в Host/stderr.

## Когда запускать
Когда пользователь присылает публичную ссылку Яндекс.Диска (скриншот/файл) — скрипт вызывается автоматически через триггер `yadisk-screenshot` скила или вручную. Если не запустить — нет локального файла для анализа/вложения в контекст.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| -Url | | string | да | | Публичная ссылка на Яндекс.Диск (disk.yandex.ru/i/..., disk.yandex.ru/d/..., yadi.sk/i/...) |
| -OutputDir | | string | нет | `<script>/imd` | Папка для сохранения файла |
| -NamePrefix | | string | нет | `yadisk` | Префикс имени файла. Итог: `<prefix>_<sha256[0..11]>.<ext>` |
| -Force | | switch | нет | | Перекачать, даже если файл с таким хешем уже есть (игнорировать кэш) |
| -Quiet | | switch | нет | | Не выводить статус, только итоговый путь в stdout |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех (включая cache hit) | Идём дальше, путь в stdout |
| 1 | API не вернул `href` (ошибка метаданных/доступа) | Проверить, что ссылка публичная; сообщить пользователю |
| 2 | Не удалось скачать файл (сеть/права) | Проблема сети/прав; сообщить пользователю |
| 3 | Неверный URL (не Яндекс.Диск) | Перепроверить извлечённую ссылку |

## Что читает и что пишет
**Читает:**
- Параметр `-Url` (публичная ссылка)
- При необходимости создаёт каталог `-OutputDir`

**Пишет:**
- Файл в `-OutputDir` с именем `<prefix>_<sha256[0..11]>.<ext>`
- stdout — абсолютный путь к скачанному файлу (последняя строка вывода)
- stderr — статус/прогресс (если не `-Quiet`)

## Побочные эффекты
- HTTP запросы к `cloud-api.yandex.net` (метаданные + скачивание)
- Создание каталога `-OutputDir` при отсутствии
- Запись файла на диск

## Окружение и зависимости
- PowerShell 5.1+ / PowerShell Core 7+
- Поддержка TLS 1.2
- Сетевой доступ к `cloud-api.yandex.net` (порт 443)

## Примеры
```powershell
# Скачать скриншот
powershell -NoProfile -ExecutionPolicy Bypass -File .agents/skills/yadisk-screenshot/scripts/yadisk-fetch.ps1 -Url "https://disk.yandex.ru/i/HUpAFmr_sBwddQ"

# Только путь в stdout (для встраивания в контекст)
$img = & powershell -NoProfile -ExecutionPolicy Bypass -File .agents/skills/yadisk-screenshot/scripts/yadisk-fetch.ps1 -Url $link -Quiet

# Принудительное перескачивание
powershell -NoProfile -ExecutionPolicy Bypass -File .agents/skills/yadisk-screenshot/scripts/yadisk-fetch.ps1 -Url $link -Force
```

## Ограничения
- Ссылка должна быть **публичной** (открывается без логина в браузере)
- Не предлагать пользователю скачивать вручную, если можно вызвать скрипт
- Папка `.doc/` целиком **не коммитится в git** — локальная техническая директория. Файлы в `imd/` живут только локально.
- Поддержка: PowerShell 5+ (Windows из коробки).

## Связи
- Скил: `yadisk-screenshot` (триггеры, кэш, интеграция с агентом)
- README: `.doc/skil_data/yadisk-screenshot/README.md`
- Канон скила: `.agents/skills/yadisk-screenshot/SKILL.md`

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)
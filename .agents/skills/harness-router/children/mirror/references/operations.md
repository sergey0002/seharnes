# Эксплуатация harness-mirror

<!-- meta
type: reference
status: actual
updated: 2026-11-02
tags: [harness, mirror, systemd, operations]
-->

---

## Суть

Операционные сценарии скила: автозапуск просмотрщика, статический просмотр,
проверка переносимости и диагностика. Устройство команд и формата узлов описано в
`implementation.md`, интеграция с панелью в `panel-integration.md`.

---

## Автозапуск

Просмотрщик и API записи это отдельный процесс. Для автозапуска используется
systemd user unit.

`~/.config/systemd/user/harness-mirror.service`:

```ini
[Unit]
Description=Harness Mirror viewer and edit API on 127.0.0.1:8090
After=network.target

[Service]
Type=simple
WorkingDirectory=<путь к проекту>
ExecStart=/usr/bin/python3 <путь к проекту>/.agents/skills/harness-router/children/mirror/scripts/harness_mirror.py serve --host 127.0.0.1 --port 8090
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now harness-mirror.service
systemctl --user status harness-mirror.service
journalctl --user -u harness-mirror.service -f
```

Для запуска до входа в систему нужен linger:

```bash
loginctl enable-linger $USER
```

Если systemd недоступен, просмотрщик запускается вручную командой `serve` или
добавляется в стартовый скрипт проекта.

---

## Статический просмотр

Без записи просмотрщик отдается любым статическим сервером с корнем в каталоге
данных:

```bash
python3 -m http.server 8091 --directory .cursor/.state/harness-mirror
```

В этом режиме API записи недоступен, файлы только читаются.

---

## Проверка переносимости

```bash
# запуск из копии в другой среде
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py --root . scan

# запуск без cwd проекта
cd /tmp && python3 /path/to/project/.agents/skills/harness-router/children/mirror/scripts/harness_mirror.py \
  --root /path/to/project check
```

---

## Диагностика

| Симптом | Причина | Что делать |
|---|---|---|
| `root not found` | нет `.git` и `.cursor` вверх по дереву | передать `--root` |
| `node_id collision` | два файла дают одно имя | переименовать файл, не править id вручную |
| `lossless round trip failed` | файл менялся после разбора | повторить `scan --force` |
| `projection_of target missing` | канон не попал в скан | добавить канон в `--paths` |
| пустая карта в браузере | `graph.json` не найден | проверить каталог данных и адрес |
| `mirror is generated` | попытка записи в зеркало | править канон, затем синхронизация |
| `api: только чтение` | открыт статический файл просмотрщика | запустить `serve` и открыть его адрес |
| `anchor not found` | агент прислал текст, которого нет в блоке | взять точную строку из файла |
| `resolved target is not an indexed node` | указан несуществующий идентификатор цели | взять id из индекса или поставить `unresolved` |
| `unresolved relation keeps a target` | старый узел, состояние лечится сканом | повторить `scan` |
| `missing` у связи | файл цели удален или не проиндексирован | вернуть файл или выполнить `scan` |

---

## Ограничения

- Каталог данных по умолчанию лежит внутри папки скила и начинается с точки,
  поэтому не попадает в зеркала и parity. При переносе его исключают.
- Просмотрщик не выполняет код из узлов и экранирует поля.
- API записи принимает только loopback-запросы.
- Связи описывают только явные упоминания в тексте.

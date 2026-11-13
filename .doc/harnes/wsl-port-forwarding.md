# WSL Port Forwarding: проблемы и решение

<!-- meta
type: harness-doc
status: actual
updated: 2026-11-08
tags: [wsl, port-forwarding, nat, netsh, task-scheduler, localhostForwarding, networkingMode]
related: [local-dev-resources.md, .wslconfig]
-->

---

## Суть

При использовании `networkingMode=nat` в `.wslconfig` (необходимо из-за BSOD 0x133 при `mirrored`) **проброс портов через `localhostForwarding=true` не сохраняется после `wsl --shutdown`**.

Симптомы:
- Порты 8030, 8077, 8000 и др. работают после первого старта WSL
- После `wsl --shutdown` (в т.ч. при сжатии VHDX через батник) порты отваливаются
- Внутри WSL всё работает (`curl 127.0.0.1:8030` → 200), из Windows — нет (`curl localhost:8030` → timeout)

---

## Причина

В `nat` режиме WSL создаёт NAT-правила **динамически при старте**. `localhostForwarding=true` включает автопроброс, но:
1. Правила создаются **только при старте WSL**
2. После `wsl --shutdown` они теряются
3. При следующем старте WSL иногда не восстанавливаются (race condition / timing в WSL networking stack)

---

## Решение: постоянный `netsh` через Task Scheduler (Option A)

### 1. PowerShell-скрипт: `C:\Scripts\WSL-PortForward.ps1`

```powershell
<# 
.SYNOPSIS
    Persistent WSL port forwarding for nat mode.
    Runs at WSL startup / Windows logon / Task Scheduler trigger.

.NOTES
    Required ports defined in $Ports array below.
    Run with highest privileges in Task Scheduler.
#>

$Ports = @(
    # Обязательные (Copytrust, dsh, Graphiti, Ollama)
    8030,   # Copytrust сайт (copytrust-dev-php-apache-1)
    8031,   # MySQL Copytrust (copytrust-dev-mysql-1)
    8077,   # dsh web (web-tools-1)
    8000,   # Graphiti MCP (graphiti)
    3000,   # FalkorDB Browser (graphiti)
    6379,   # Redis (graphiti)
    11434,  # Ollama API (эмбеддинги qwen3-embedding:0.6b)

    # Опциональные (запускать по необходимости)
    3001,   # OpenHands (если запущен)
    7080,   # Sourcegraph (если запущен стек)
    33306,  # Assignment MySQL
    38080,  # Assignment nginx
    36379,  # Assignment Redis
    4444,   # Selenium/Chromedriver
    9515,   # Chromedriver
    8031,   # MySQL Copytrust (duplicate для MCP relay)
    7080,   # Sourcegraph MCP endpoint
)

function Get-WslIP {
    $ip = (wsl.exe hostname -I).Trim()
    if (-not $ip -or $ip -eq "") {
        Write-Error "WSL не запущен или не вернул IP"
        exit 1
    }
    return $ip
}

$wslIP = Get-WslIP
Write-Host "WSL IP: $wslIP" -ForegroundColor Cyan

foreach ($port in $Ports) {
    # Удаляем старое правило (игнорируем ошибки, если не существует)
    netsh interface portproxy delete v4tov4 listenport=$port listenaddress=0.0.0.0 2>$null

    # Создаём новое правило
    $result = netsh interface portproxy add v4tov4 listenport=$port listenaddress=0.0.0.0 connectport=$port connectaddress=$wslIP
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Port $port -> $wslIP:$port [OK]" -ForegroundColor Green
    } else {
        Write-Warning "  Port $port FAILED: $result"
    }
}

netsh interface portproxy show v4tov4
```

### 2. Установка задачи в Task Scheduler

**Вариант А — По входу пользователя (самый простой):**
1. Открой `Task Scheduler` (`taskschd.msc`)
2. `Create Task...`
3. **General:**
   - Name: `WSL Port Forward (nat mode)`
   - Run whether user is logged on or not: **No** (нужен интерактивный вход для `wsl.exe`)
   - Run with highest privileges: **Yes**
3. **Triggers:**
   - New → `At log on` → Specific user: `NewUser` → Enabled
   - (опционально) New → `On event` → Log: `Microsoft-Windows-WSL/Operational` → Source: `WSL` → Event ID: `1` (WSL started)
4. **Actions:**
   - New → Start a program: `powershell.exe`
   - Arguments: `-NoProfile -ExecutionPolicy Bypass -File C:\Scripts\WSL-PortForward.ps1`
5. **Conditions / Settings:**Defaults OK

**Вариант Б — По событию WSL started (надежнее для `wsl --shutdown`):**
- Trigger: `On event` → Log: `Microsoft-Windows-WSL/Operational` → Event ID: `1`

---

## Список портов (актуальный на 2026-11-08)

### Обязательные (всегда пробрасывать)

| Порт | Сервис | Контейнер / Процесс | Bind в WSL |
|------|--------|---------------------|------------|
| **8030** | Copytrust сайт | `copytrust-dev-php-apache-1` | `0.0.0.0:8030→80` |
| **8031** | MySQL Copytrust | `copytrust-dev-mysql-1` | `0.0.0.0:8031→3306` |
| **8077** | dsh web | `web-tools-1` | `0.0.0.0:8077→8077` |
| **8000** | Graphiti MCP | `graphiti` | `127.0.0.1:8000` |
| **3000** | FalkorDB Browser | `graphiti` | `127.0.0.1:3000` |
| **6379** | Redis (Graphiti) | `graphiti` | `127.0.0.1:6379` |
| **11434** | **Ollama API** | Ollama (WSL процесс) | `0.0.0.0:11434` |

### Опциональные (по требованию)

| Порт | Сервис | Примечание |
|------|--------|------------|
| 3001 | OpenHands | если контейнер запущен |
| 7080 | Sourcegraph | если стек запущен |
| 33306 | Assignment MySQL | если стек запущен |
| 38080 | Assignment nginx | если стек запущен |
| 36379 | Assignment Redis | если стек запущен |
| 4444 | Selenium | для e2e тестов |
| 9515 | Chromedriver | для Codeception |

---

## Причины отвала портов в этом диалоге

| Действие | Почему помогло вернуть порты |
|----------|-------------------------------|
| `wsl --shutdown` (многократный) | **Полный рестарт WSL** → NAT-таблица пересоздалась заново |
| `fstrim` + `Optimize-VHD` | Освободил I/O, убрал таймауты сетевого стека |
| Перезапуск Docker-контейнеров | Пересоздал сетевые endpoints |

**Вывод:** `wsl --shutdown` — единственное действие из наших, которое реально пересоздаёт NAT-таблицу. Без постоянного `netsh` после следующего shutdown порты снова отвалятся.

---

## Быстрый ручной fix (PowerShell от админа)

```powershell
$wslIP = (wsl.exe hostname -I).Trim()
8030,8031,8077,8000,3000,6379,11434 | ForEach-Object {
  netsh interface portproxy delete v4tov4 listenport=$_ listenaddress=0.0.0.0 2>$null
  netsh interface portproxy add v4tov4 listenport=$_ listenaddress=0.0.0.0 connectport=$_ connectaddress=$wslIP
}
netsh interface portproxy show v4tov4
```

---

## Связанные документы

- local-dev-resources.md (проект Target) — §11 (BSOD, networkingMode, port forwarding)
- `.wslconfig` — `networkingMode=nat`, `localhostForwarding=true`
- `.wslconfig` example в корне проекта

---

## История изменений

| Дата | Изменение |
|------|-----------|
| 2026-11-08 | Создан документ: описана проблема localhostForwarding в nat режиме, решение через netsh + Task Scheduler, полный список портов |
<#
.SYNOPSIS
    Экспорт AI-kit (Cursor + Codex) и инфраструктуры .doc/ в новый каталог проекта.

.DESCRIPTION
    Канон рядом с документом: .agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1 (+ .doc/rebase_project.md).
    Реализует перенос по .doc/rebase_project.md (профиль FULL или CORE).
    Создаёт целевую папку, копирует необходимое (без секретов kit и без tasks/{N}),
    не меняет Git по умолчанию, готовит mcp.env из example, правит Serena project_name.
    Если Target уже имел mcp.json/config.toml: по умолчанию MERGE -
    серверы kit (sourcegraph, graphify, …) + Target-only (laravel-boost, …).
    Отключить: -SkipMcpMerge.

    Запуск из Cursor (корень образца testdeploydocker):

      powershell -NoProfile -ExecutionPolicy Bypass -File .agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1 `
        -Target "C:\laragon\www\test"

    Из WSL (если Target - Windows-путь):

      powershell.exe -NoProfile -ExecutionPolicy Bypass -File .agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1 `
        -Target "C:\laragon\www\test"

.PARAMETER Target
    Каталог нового проекта (будет создан). Пример: C:\laragon\www\test

.PARAMETER Source
    Корень репозитория-образца. По умолчанию: родитель .doc/ (корень текущего репо).

.PARAMETER Profile
    Full (разработка харнеса и работа с кодом) или Core (без данных задач и полной документации харнеса). Default: Full

.PARAMETER ProjectName
    Имя для .serena/project.yml. По умолчанию - имя папки Target.

.PARAMETER IncludeKilo
    Копировать .kilo / kilo.json (без node_modules).

.PARAMETER SkipTools
    Не копировать безопасный набор .tools (docker/test/php конфиги без .env, dump.sql, vendor).

.PARAMETER SkipRuntimeDeps
    Не копировать node_modules php-toolchain и vendor (phpstan/phpda + codeception).
    По умолчанию копируются - без них phpstan-mcp / php-deps / codeception тесты не стартуют.

.PARAMETER SkipGitInit
    Совместимый флаг запрета git init (по умолчанию Git не меняется).

.PARAMETER SkipExclude
    Совместимый флаг запрета изменения .git/info/exclude.

.PARAMETER InitGit
    Явно создать Git в Target, если его нет; origin не назначается.

.PARAMETER ManageGitExclude
    Явно разрешить запись управляемого блока в .git/info/exclude Target.

.PARAMETER IncludeDocs
    Не исключать .doc/: документация проекта может быть добавлена в git.
    Харнес (среды и tooling) остается исключенным.

.PARAMETER SkipPreflight
    Не строить SHA256-манифест перед копированием. Копирование все равно
    перезаписывает совпавшие пути; сверка нужна только для отчёта.

.PARAMETER RunSetup
    После копирования запустить .cursor\setup.ps1 и .codex\setup.ps1 (нужны Node/сеть).
    При уже скопированных runtime deps обычно не обязателен.

.PARAMETER SkipSiblingConfig
    Не создавать пустой sibling ..\.config рядом с Target.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1 -Target "C:\laragon\www\test"

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1 `
      -Target "C:\laragon\www\myapp" -Profile Core -ProjectName myapp -RunSetup
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Target,

    [string]$Source = '',

    [ValidateSet('Full', 'Core')]
    [string]$Profile = 'Full',

    # migrate: первый перенос, конфликты и анализ локальных компонентов.
    # clean: удалить kit-компоненты Target и установить только kit.
    # update: обновить kit поверх уже перенесенного проекта без разбора конфликтов.
    [ValidateSet('migrate', 'clean', 'update')]
    [string]$Mode = 'migrate',

    [string]$ProjectName = '',

    [switch]$IncludeKilo,
    [switch]$SkipTools,
    [switch]$SkipRuntimeDeps,
    [switch]$SkipGitInit,
    [switch]$SkipExclude,
    [switch]$InitGit,
    [switch]$ManageGitExclude,
    [switch]$IncludeDocs,
    [switch]$RunSetup,

    # По умолчанию: после копирования kit влить Target-only MCP (boost/…).
    # Kit-серверы (sourcegraph, …) остаются из образца.
    [switch]$SkipMcpMerge,

    # По умолчанию создаём sibling ..\.config; передайте -SkipSiblingConfig чтобы не создавать
    [switch]$SkipSiblingConfig,

    # Точное зеркало kit: удаляет в Target файлы, которых нет в образце.
    # По умолчанию выключено, чтобы повторный экспорт не стирал файлы проекта.
    [switch]$MirrorKit,

    # Порт Serena для Target. 0: взять из .dsh/scripts/serena-shared.sh,
    # иначе первый свободный после порта образца.
    [int]$SerenaPort = 0,

    # Не считать SHA256-манифест перед копированием. Copy и так перезаписывает
    # совпавшие пути; сверка нужна только для отчёта и предупреждения.
    [switch]$SkipPreflight,

    # Не сохранять бэкап перезаписываемых файлов. По умолчанию бэкап включен.
    [switch]$SkipBackup,

    # Не запускать анализ локальных компонентов после переноса.
    [switch]$SkipReview,

    # Не спрашивать подтверждение на перезапись (для автоматизации).
    [switch]$Yes
)

# Defaults: runtime deps ON (MCP/phpstan/tests). Opt out via -Skip*
$CopyRuntimeDeps = -not $SkipRuntimeDeps
$MigrateMode = $Mode -eq 'migrate'
$CleanMode = $Mode -eq 'clean'
$UpdateMode = $Mode -eq 'update'
$EffectiveMirror = $MirrorKit -or $CleanMode
if (($InitGit -and $SkipGitInit) -or ($ManageGitExclude -and $SkipExclude)) {
    throw 'Conflicting Git options: opt-in and corresponding Skip cannot be combined.'
}
if ($CleanMode -and $SkipBackup) {
    throw 'clean удаляет kit-компоненты Target: запуск без бэкапа запрещён, уберите -SkipBackup'
}

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:StepIndex = 0
$script:StepStart = $null
$script:StepName = ''
$script:StepOk = 0
$script:StepWarn = 0
$script:StepRows = New-Object System.Collections.Generic.List[object]

function Complete-Step {
    if ($null -eq $script:StepStart) { return }
    $duration = [math]::Round(((Get-Date) - $script:StepStart).TotalSeconds, 1)
    $status = if ($script:StepWarn -gt 0) { 'WARN' } else { 'OK' }
    $line = "    [{0}] {1}: {2}, ok={3}, warn={4}, {5}s" -f `
        $script:StepIndex, $script:StepName, $status, $script:StepOk, $script:StepWarn, $duration
    $color = if ($script:StepWarn -gt 0) { 'Yellow' } else { 'Gray' }
    Write-Host $line -ForegroundColor $color
    $script:StepRows.Add([pscustomobject]@{
        Index = $script:StepIndex
        Name = $script:StepName
        Status = $status
        Ok = $script:StepOk
        Warn = $script:StepWarn
        Seconds = $duration
    })
    $script:StepStart = $null
    $script:StepOk = 0
    $script:StepWarn = 0
}

function Write-StepSummary {
    if ($script:StepRows.Count -eq 0) { return }
    Write-Host ""
    Write-Host "Сводка шагов экспорта:" -ForegroundColor Cyan
    foreach ($row in $script:StepRows) {
        $color = if ($row.Status -eq 'WARN') { 'Yellow' } else { 'Green' }
        Write-Host ("  {0,2}. {1,-52} {2,-4} ok={3,3} warn={4,2} {5,6}s" -f `
            $row.Index, $row.Name, $row.Status, $row.Ok, $row.Warn, $row.Seconds) -ForegroundColor $color
    }
}

function Write-Step([string]$Message) {
    Complete-Step
    $script:StepIndex++
    $script:StepStart = Get-Date
    $script:StepName = $Message
    $script:StepOk = 0
    $script:StepWarn = 0
    Write-Host ""
    Write-Host ("[{0}] {1}  {2}" -f $script:StepIndex, (Get-Date).ToString('HH:mm:ss'), $Message) -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    if ($null -ne $script:StepStart) { $script:StepOk++ }
    Write-Host "    OK: $Message" -ForegroundColor Green
}

function Write-Warn2([string]$Message) {
    if ($null -ne $script:StepStart) { $script:StepWarn++ }
    Write-Host "    WARN: $Message" -ForegroundColor Yellow
}

function Resolve-FullPath([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $Path }
    $p = $Path.Trim().TrimEnd('\', '/')
    if (-not [System.IO.Path]::IsPathRooted($p)) {
        $p = Join-Path (Get-Location).Path $p
    }
    return [System.IO.Path]::GetFullPath($p)
}

function Invoke-Robo {
    param(
        [Parameter(Mandatory)][string]$From,
        [Parameter(Mandatory)][string]$To,
        [string[]]$ExcludeDirs = @(),
        [string[]]$ExcludeFiles = @(),
        # Mirror удаляет в Target файлы, которых нет в источнике. По умолчанию
        # выключен: повторный экспорт не должен стирать файлы проекта.
        [switch]$Mirror,
        # Копировать содержимое символьных ссылок. Нужно, когда источник
        # отдаёт каталог ссылкой (например `.cursor/skills`), а в Target уже
        # есть реальный каталог с локальными файлами.
        [switch]$FollowLinks
    )
    if (-not (Test-Path $From)) {
        Write-Warn2 "Источник отсутствует, skip: $From"
        return
    }
    New-Item -ItemType Directory -Path $To -Force | Out-Null

    $robo = Get-Command robocopy -ErrorAction SilentlyContinue
    if ($robo) {
        $roboArgs = @($From, $To, '/E', '/NFL', '/NDL', '/NJH', '/NJS', '/nc', '/ns', '/np')
        if ($Mirror) { $roboArgs += '/PURGE' }
        if ($ExcludeDirs.Count -gt 0) {
            $roboArgs += '/XD'
            $roboArgs += $ExcludeDirs
        }
        if ($ExcludeFiles.Count -gt 0) {
            $roboArgs += '/XF'
            $roboArgs += $ExcludeFiles
        }
        & robocopy @roboArgs | Out-Null
        $code = $LASTEXITCODE
        if ($code -ge 8) {
            throw "robocopy failed code=$code from=$From to=$To"
        }
        Write-Ok "robocopy $From -> $To (code $code)"
        return
    }

    # Linux/WSL/mac: rsync (предпочтительно) или Copy-Item
    $rsync = Get-Command rsync -ErrorAction SilentlyContinue
    if ($rsync) {
        $fromSlash = ($From.TrimEnd('/', '\') + '/')
        $toSlash = ($To.TrimEnd('/', '\') + '/')
        $args = @('-a', '--checksum')
        if ($Mirror) { $args += '--delete' }
        if ($FollowLinks) { $args += '--copy-links' }
        foreach ($d in $ExcludeDirs) {
            $args += "--exclude=$d"
            $args += "--exclude=$d/**"
        }
        foreach ($f in $ExcludeFiles) {
            $args += "--exclude=$f"
        }
        $args += @($fromSlash, $toSlash)
        & rsync @args
        if ($LASTEXITCODE -ne 0) {
            throw "rsync failed code=$LASTEXITCODE from=$From to=$To"
        }
        Write-Ok "rsync $From -> $To"
        return
    }

    throw 'robocopy or rsync is required: unsafe partial copy fallback is disabled'
}

function Test-SkipName([string]$Name, [string[]]$Patterns) {
    foreach ($p in $Patterns) { if ($Name -like $p) { return $true } }
    return $false
}

function Get-KitManifest {
    param(
        [Parameter(Mandatory)][string]$Root,
        [string[]]$Dirs = @(),
        [string[]]$RootFiles = @(),
        [string[]]$SkipDirs = @(),
        [string[]]$SkipFiles = @()
    )
    $map = @{}
    if (-not (Test-Path $Root)) { return $map }
    foreach ($f in $RootFiles) {
        $p = Join-Path $Root $f
        if (-not (Test-Path $p)) { continue }
        try {
            $item = Get-Item -LiteralPath $p -Force
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "linked manifest file is not allowed: $f"
            }
            $map[$f.ToLower()] = @{ Path = $f; Hash = (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash }
        } catch {
            throw "manifest root file cannot be read safely: $f"
        }
    }
    foreach ($dir in $Dirs) {
        $base = Join-Path $Root $dir
        if (-not (Test-Path $base)) { continue }
        Get-ChildItem -LiteralPath $base -Recurse -File -Force -ErrorAction SilentlyContinue | ForEach-Object {
            $rel = $_.FullName.Substring($base.Length).TrimStart('\', '/')
            $parts = $rel -split '[\\/]' | Where-Object { $_ }
            # .cursor/skills в образце это symlink на .agents/skills, а sync в
            # Target делает его реальным каталогом. Канон скилов - .agents,
            # поэтому дубль .cursor/skills в манифест не берём.
            if ($dir -eq '.cursor' -and $rel -match '^skills([/\\]|$)') { return }
            if ($parts | Where-Object { $SkipDirs -contains $_ }) { return }
            if (Test-SkipName $_.Name $SkipFiles) { return }
            # Битые и обычные symlink не хешируем: Get-FileHash на них падает.
            if (($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { return }
            $fullRel = (($dir -replace '\\', '/') + '/' + ($rel -replace '\\', '/'))
            try {
                $map[$fullRel.ToLower()] = @{ Path = $fullRel; Hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
            } catch {
                Write-Warn2 "манифест: пропущен нечитаемый файл $fullRel"
            }
        }
    }
    return $map
}

function Compare-KitManifests {
    param([hashtable]$Before, [hashtable]$SourceMap)
    $targetOnly = @()
    $overwritten = @()
    $added = @()
    $same = 0
    foreach ($key in $Before.Keys) {
        if (-not $SourceMap.ContainsKey($key)) {
            $targetOnly += $Before[$key].Path
        } elseif ($Before[$key].Hash -ne $SourceMap[$key].Hash) {
            $overwritten += $Before[$key].Path
        } else {
            $same++
        }
    }
    foreach ($key in $SourceMap.Keys) {
        if (-not $Before.ContainsKey($key)) { $added += $SourceMap[$key].Path }
    }
    return @{
        target_only = @($targetOnly | Sort-Object)
        overwritten = @($overwritten | Sort-Object)
        added = @($added | Sort-Object)
        same = $same
    }
}

function Get-ConflictCategory([string]$RelativePath) {
    $p = $RelativePath -replace '\\', '/'
    if ($p -match '(^|/)skills/') { return 'skill' }
    if ($p -match '(^|/)rules/') { return 'rule' }
    if ($p -match '(^|/)scripts/') { return 'script' }
    if ($p -match 'mcp|settings\.json|config\.toml') { return 'mcp' }
    if ($p -match '^\.doc/') { return 'docs' }
    return 'other'
}

function Backup-TargetOverwrites {
    param(
        [Parameter(Mandatory)][string]$TargetRoot,
        [string[]]$Paths,
        [Parameter(Mandatory)][string]$Stamp
    )
    $backupRoot = Join-Path $TargetRoot ".doc\.rebase-backup\$Stamp"
    $records = @()
    $files = @($Paths | Where-Object { $_ } | Sort-Object -Unique)
    if ($files.Count -eq 0) {
        return [pscustomobject]@{ root = $backupRoot; files = @() }
    }
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
    foreach ($relative in $files) {
        $relative = $relative -replace '\\', '/'
        $source = Join-Path $TargetRoot $relative
        if (-not (Test-Path -LiteralPath $source)) { continue }
        $item = Get-Item -LiteralPath $source -Force
        if ($item.PSIsContainer) { continue }
        $destination = Join-Path $backupRoot $relative
        $parent = Split-Path $destination -Parent
        if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
        Copy-Item -LiteralPath $source -Destination $destination -Force
        $records += [pscustomobject]@{
            path = $relative
            category = Get-ConflictCategory $relative
            backup = ((".doc/.rebase-backup/$Stamp/" + $relative) -replace '\\', '/')
        }
    }
    return [pscustomobject]@{ root = $backupRoot; files = @($records) }
}

function Write-TransferReport {
    param(
        [Parameter(Mandatory)][string]$Root,
        [Parameter(Mandatory)][string]$Source,
        [string]$ProfileName = '',
        [hashtable]$Before,
        [hashtable]$SourceMap,
        [switch]$Mirrored,
        [switch]$PreflightSkipped
    )
    $diff = if ($PreflightSkipped) {
        [pscustomobject]@{ overwritten = @(); added = @(); target_only = @(); same = 0 }
    } else {
        Compare-KitManifests -Before $Before -SourceMap $SourceMap
    }
    $targetOnly = @($diff.target_only)
    # Часть файлов kit копируется, а затем удаляется профилем (Copytrust-only
    # скилы, Core). В отчёте они отделены от реально добавленных файлов.
    $removedAfterCopy = @()
    $overwritten = @()
    foreach ($p in @($diff.overwritten)) {
        if (Test-Path (Join-Path $Root $p)) { $overwritten += $p } else { $removedAfterCopy += $p }
    }
    $added = @()
    foreach ($p in @($diff.added)) {
        if (Test-Path (Join-Path $Root $p)) { $added += $p } else { $removedAfterCopy += $p }
    }

    $archDir = Join-Path $Root '.doc\architecture'
    $tasksDir = Join-Path $Root '.doc\tasks'
    $stateDir = Join-Path $Root '.doc\harnes\state'
    $archDocs = if (Test-Path $archDir) { @(Get-ChildItem -LiteralPath $archDir -Recurse -File -Filter *.md -ErrorAction SilentlyContinue).Count } else { 0 }
    $taskDocs = if (Test-Path $tasksDir) { @(Get-ChildItem -LiteralPath $tasksDir -Recurse -File -Filter *.md -ErrorAction SilentlyContinue).Count } else { 0 }
    $taskDirs = if (Test-Path $tasksDir) { @(Get-ChildItem -LiteralPath $tasksDir -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^\d+$' }).Count } else { 0 }
    $stateDocs = if (Test-Path $stateDir) { @(Get-ChildItem -LiteralPath $stateDir -File -Filter *.md -ErrorAction SilentlyContinue).Count } else { 0 }

    $customSkills = @($targetOnly |
        Where-Object { $_ -match '^\.(cursor|codex|agents)/skills/([^/]+)/' } |
        ForEach-Object { ($_ -split '/')[2] } | Sort-Object -Unique)
    $customRules = @($targetOnly | Where-Object { $_ -match '^\.(cursor|codex|agents)/rules/' } | Sort-Object)
    $customScripts = @($targetOnly | Where-Object { $_ -match '^\.(cursor|codex|agents)/scripts/' } | Sort-Object)

    $lines = @(
        '# Отчёт переноса kit',
        '',
        "Target: ``$Root``",
        "Source: ``$Source``",
        "Профиль: ``$ProfileName``",
        "Дата: $((Get-Date).ToString('s'))",
        '',
        '## Данные проекта',
        '',
        "Документация architecture: $archDocs документов.",
        "Задачи: $taskDirs каталогов, $taskDocs документов.",
        "Состояние харнеса (``.doc/harnes/state``): $stateDocs документов.",
        "Файлов Target вне kit сохранено: $($targetOnly.Count).",
        '',
        '## Кастомные компоненты',
        '',
        "Скилы: $($customSkills.Count)$(if ($customSkills.Count) { ' (' + ($customSkills -join ', ') + ')' } else { '' }).",
        "Правила: $($customRules.Count).",
        "Скрипты: $($customScripts.Count).",
        '',
        '## Kit',
        '',
        $(if ($PreflightSkipped) {
            'Сверка kit пропущена: `-SkipPreflight` или пустой Target.'
        } else {
            "Перезаписано файлов: $($overwritten.Count).`nДобавлено файлов: $($added.Count).`nУдалено профилем после копирования: $($removedAfterCopy.Count).`nБез изменений: $($diff.same)."
        }),
        '',
        '## Сохранённые файлы Target',
        '',
        'Эти файлы не входят в kit и не удалялись. Полный список: ``.doc/.rebase-preserved.txt``.',
        '',
        $(if ($targetOnly.Count) { ($targetOnly | Select-Object -First 200 | ForEach-Object { "- ``$_``" }) -join "`n" } else { '(нет)' }),
        '',
        '## Очистка',
        '',
        $(if ($Mirrored) {
            'Запущено точное зеркало ``-MirrorKit``: перечисленные выше файлы Target удалены.'
        } else {
            'По умолчанию лишнее сохранено. Точное зеркало с удалением лишнего: флаг ``-MirrorKit``.'
        }),
        'Вручную удалить только перечисленные файлы из ``.doc/.rebase-preserved.txt``.',
        ''
    )
    $mdPath = Join-Path $Root '.doc\.rebase-report.md'
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($mdPath, ($lines -join "`n"), $utf8)
    $preservedItems = @($targetOnly)
    if ($preservedItems.Count -eq 0) { $preservedItems = @('(нет)') }
    $preservedText = (@('# Файлы Target, которых нет в образце. Экспорт их не удаляет.', '') + $preservedItems) -join "`n"
    [System.IO.File]::WriteAllText((Join-Path $Root '.doc\.rebase-preserved.txt'), $preservedText + "`n", $utf8)
    $json = @{
        target = $Root
        source = $Source
        profile = $ProfileName
        project_docs = @{ architecture = $archDocs; tasks_dirs = $taskDirs; task_docs = $taskDocs; harnes_state = $stateDocs }
        custom = @{ skills = $customSkills; rules = $customRules; scripts = $customScripts }
        kit = @{ overwritten = $overwritten; added = $added; removed_after_copy = $removedAfterCopy; unchanged = $diff.same }
        preserved = $targetOnly
        mirrored = [bool]$Mirrored
    } | ConvertTo-Json -Depth 6
    [System.IO.File]::WriteAllText((Join-Path $Root '.doc\.rebase-report.json'), $json, $utf8)

    Write-Ok "отчёт: .doc/.rebase-report.md"
    Write-Host ("    Документация проекта: architecture={0}, tasks={1}/{2} каталогов, harnes/state={3}" -f $archDocs, $taskDocs, $taskDirs, $stateDocs)
    Write-Host ("    Кастомные компоненты: skills={0}, rules={1}, scripts={2}" -f $customSkills.Count, $customRules.Count, $customScripts.Count)
    Write-Host ("    Kit: перезаписано={0}, добавлено={1}, без изменений={2}" -f $overwritten.Count, $added.Count, $diff.same)
    if ($Mirrored) {
        Write-Ok ("Точное зеркало: удалено файлов вне kit: {0}" -f $targetOnly.Count)
    } elseif ($targetOnly.Count -gt 0) {
        Write-Warn2 ("Сохранено файлов вне kit: {0}. Очистка: -MirrorKit или список .doc/.rebase-preserved.txt" -f $targetOnly.Count)
    } else {
        Write-Ok 'Файлов вне kit нет'
    }
}

function Scrub-McpJson([string]$Path) {
    if (-not (Test-Path $Path)) { return }
    $raw = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
    $changed = $false

    # Убрать живой Sourcegraph token из headers
    $new = [regex]::Replace(
        $raw,
        '("Authorization"\s*:\s*")token\s+sgp_[^"]+(")',
        '${1}token REPLACE_WITH_SOURCEGRAPH_MCP_TOKEN${2}'
    )
    if ($new -ne $raw) { $changed = $true; $raw = $new }

    # Заглушить абсолютные WSL/user Chrome paths (оставим ключи, очистим значения)
    foreach ($key in @('PLAYWRIGHT_MCP_EXECUTABLE_PATH', 'CHROME_PATH', 'LD_LIBRARY_PATH')) {
        $pat = "(`"$([regex]::Escape($key))`"\s*:\s*`")[^`"]*(`")"
        $n2 = [regex]::Replace($raw, $pat, '${1}${2}')
        if ($n2 -ne $raw) { $changed = $true; $raw = $n2 }
    }

    if ($changed) {
        $utf8 = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($Path, $raw, $utf8)
        Write-Ok "scrub secrets/paths: $Path"
    }
}

function Rewrite-SourcePaths {
    param(
        [Parameter(Mandatory)][string]$Root,
        [Parameter(Mandatory)][string]$SourceRoot,
        [Parameter(Mandatory)][string]$TargetRoot,
        [string]$SourceLeaf = '',
        [string]$TargetLeaf = ''
    )
    # Абсолютные пути образца и имя его каталога не должны оставаться в kit:
    # иначе конфиг, скил или документ укажет на чужой проект.
    # Документацию переноса и примеры в .doc не трогаем.
    $forms = @(
        $SourceRoot,
        ($SourceRoot -replace '\\', '/'),
        ($SourceRoot -replace '/', '\')
    ) | Where-Object { $_ } | Select-Object -Unique

    $skipDirs = @('node_modules', 'vendor', 'venv', '.venv', '.venv-linux', '.venv-win',
        'cache', 'memories', 'artifacts', '.git', '.state', '.data', 'plans', 'worktrees')
    $textExt = @('.md', '.mdc', '.json', '.jsonc', '.mjs', '.js', '.cjs', '.ts',
        '.sh', '.ps1', '.psm1', '.cmd', '.bat', '.toml', '.yml', '.yaml', '.txt', '.py')

    $files = New-Object System.Collections.Generic.List[string]
    foreach ($rel in @('AGENTS.md', 'mcp.index.md', 'DSH-RULES.md', '.dsh\project.patch.yml', '.codeprism.toml', '.cbmignore')) {
        $files.Add((Join-Path $Root $rel))
    }
    # .dsh kit не обходим: его файлы связаны хешами kit.manifest.json.
    foreach ($dir in @('.cursor', '.codex', '.kilo', '.agents', '.qoder', '.qwen')) {
        $base = Join-Path $Root $dir
        if (-not (Test-Path $base)) { continue }
        Get-ChildItem -Path $base -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
            $parts = $_.FullName.Substring($base.Length) -split '[\\/]' | Where-Object { $_ }
            if ($parts | Where-Object { $skipDirs -contains $_ }) { return }
            if ($textExt -notcontains $_.Extension.ToLower()) { return }
            $files.Add($_.FullName)
        }
    }

    $changed = 0
    foreach ($path in ($files | Select-Object -Unique)) {
        if (-not (Test-Path $path)) { continue }
        $raw = [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)
        $new = $raw
        foreach ($form in $forms) {
            $new = $new.Replace($form, $TargetRoot)
        }
        if ($new -ne $raw) {
            $utf8 = New-Object System.Text.UTF8Encoding($false)
            [System.IO.File]::WriteAllText($path, $new, $utf8)
            $changed++
        }
    }
    Write-Ok "path rewrite: $changed file(s) under kit dirs"
}

function Prune-ComponentRegistry {
    param([Parameter(Mandatory)][string]$Root)
    # Реестр описывает то, что реально поставлено в проект. Скилы, удалённые
    # профилем или как Copytrust-only, и пути состояния, которые создаются при
    # первом запуске, в реестре нового проекта существовать не могут.
    $relPaths = @(
        '.cursor\skills\harness-router\children\improvement\scripts\component_registry.json',
        '.codex\skills\harness-router\children\improvement\scripts\component_registry.json',
        '.agents\skills\harness-router\children\improvement\scripts\component_registry.json'
    )
    foreach ($rel in $relPaths) {
        $path = Join-Path $Root $rel
        if (-not (Test-Path $path)) { continue }
        $obj = Get-Content $path -Raw -Encoding UTF8 | ConvertFrom-Json
        if (-not $obj.components) { continue }
        $removed = @()
        $trimmed = @()
        foreach ($name in @($obj.components.PSObject.Properties.Name)) {
            $entry = $obj.components.$name
            $skillName = $null
            foreach ($f in @($entry.required_files)) {
                if ($f -match '^\.agents/skills/([^/]+)/SKILL\.md$') { $skillName = $Matches[1]; break }
            }
            if ($skillName) {
                $inCursor = Test-Path (Join-Path $Root ".cursor\skills\$skillName")
                $inAgents = Test-Path (Join-Path $Root ".agents\skills\$skillName")
                if (-not $inCursor -and -not $inAgents) {
                    $obj.components.PSObject.Properties.Remove($name)
                    $removed += $name
                    continue
                }
            }
            $dropped = 0
            foreach ($group in @('required_files', 'config_paths')) {
                if ($entry.PSObject.Properties.Name -notcontains $group) { continue }
                $kept = @()
                foreach ($item in @($entry.$group)) {
                    $full = Join-Path $Root ($item -replace '/', [System.IO.Path]::DirectorySeparatorChar)
                    if (Test-Path $full) { $kept += $item } else { $dropped++ }
                }
                $entry.$group = $kept
            }
            if ($dropped -gt 0) { $trimmed += $name }
        }
        # Зависимости на удалённые скилы ломают validate_registry.py.
        $known = @($obj.components.PSObject.Properties.Name)
        foreach ($name in $known) {
            $entry = $obj.components.$name
            if ($entry.PSObject.Properties.Name -notcontains 'skill_dependencies') { continue }
            $deps = @($entry.skill_dependencies)
            $keptDeps = @($deps | Where-Object { $known -contains $_ })
            if ($keptDeps.Count -ne $deps.Count) {
                $entry.skill_dependencies = $keptDeps
                $trimmed += "${name}:deps"
            }
        }
        $json = $obj | ConvertTo-Json -Depth 12
        $utf8 = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($path, $json, $utf8)
        $removedText = if ($removed.Count -gt 0) { $removed -join ',' } else { 'none' }
        $trimmedText = if ($trimmed.Count -gt 0) { $trimmed -join ',' } else { 'none' }
        Write-Ok "registry pruned: $rel (components removed: $removedText; paths trimmed: $trimmedText)"
    }
}

function Test-IsWindowsTargetPath([string]$Path) {
    # C:\... или \\server\share — Cursor native Windows. Не WSL /home/...
    return ($Path -match '^[A-Za-z]:\\') -or ($Path -match '^\\\\')
}

function Patch-CursorMcpForWindowsHost([string]$McpJsonPath) {
    <#
      Cursor на Windows (Open Folder C:\...) вызывает command=bash с Win-путём к .sh.
      system32\bash.exe = WSL: путь C:\... ломается → phpstan/php-deps Error.
      Переводим phpstan/php-deps на node-mcp.cmd; CBM — на .exe если есть, иначе .cmd stub.
    #>
    if (-not (Test-Path $McpJsonPath)) { return }
    $obj = Get-Content $McpJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $obj.mcpServers) { return }
    $changed = $false

    foreach ($name in @('phpstan-mcp', 'php-deps-mcp')) {
        if ($obj.mcpServers.PSObject.Properties.Name -notcontains $name) { continue }
        $s = $obj.mcpServers.$name
        $s.command = 'cmd'
        $s.args = @(
            '/c',
            '${workspaceFolder}\.tools\scripts\node-mcp.cmd',
            '${workspaceFolder}\.tools\mcp-servers\php-toolchain\server.js'
        )
        $changed = $true
    }

    if ($obj.mcpServers.PSObject.Properties.Name -contains 'codebase-memory-mcp') {
        $s = $obj.mcpServers.'codebase-memory-mcp'
        # Win-exe через cmd-обёртку (без bash+WSL path)
        $s.command = 'cmd'
        $s.args = @(
            '/c',
            '${workspaceFolder}\.agents\skills\codebase-memory-mcp\scripts\codebase-memory-mcp-launch.cmd',
            '--ui=false'
        )
        $changed = $true
    }

    if ($changed) {
        $json = $obj | ConvertTo-Json -Depth 30
        $utf8 = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($McpJsonPath, $json, $utf8)
        Write-Ok "Windows MCP launchers (phpstan/php-deps/CBM/graphify): $McpJsonPath"
    }
}

function Set-CodePrismPlaceholder($Server) {
    # Адрес CodePrism относится к образцу и не должен попасть в Target.
    # Запись остаётся, транспорт заменяется заглушкой до настройки Target.
    if ($null -eq $Server) { return }
    foreach ($key in @('url', 'serverUrl')) {
        if ($Server.PSObject.Properties.Name -contains $key) {
            $Server.$key = 'http://127.0.0.1:0/mcp'
        }
    }
}

function Disable-McpServers {
    param(
        [Parameter(Mandatory)][string]$McpJsonPath,
        [string[]]$ServerNames
    )
    if (-not (Test-Path $McpJsonPath)) { return }
    $obj = Get-Content $McpJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $obj.mcpServers) { return }
    foreach ($name in $ServerNames) {
        if ($obj.mcpServers.PSObject.Properties.Name -contains $name) {
            $obj.mcpServers.$name | Add-Member -NotePropertyName disabled -NotePropertyValue $true -Force
            if ($name -eq 'codeprism') { Set-CodePrismPlaceholder $obj.mcpServers.$name }
        }
    }
    $json = $obj | ConvertTo-Json -Depth 30
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($McpJsonPath, $json, $utf8)
    Write-Ok "disabled MCP [$($ServerNames -join ', ')] in $McpJsonPath"
}

function Merge-AgentSettingsPreserveTargetOnly {
    param(
        [Parameter(Mandatory)][string]$NewPath,
        [Parameter(Mandatory)][string]$BackupPath,
        [switch]$Qwen
    )
    # Target settings may hold local MCP servers and unrelated keys. The kit
    # copy overwrites the file, so put those back after the copy: canon wins
    # on names, local-only entries are restored.
    if (-not (Test-Path $NewPath) -or -not (Test-Path $BackupPath)) { return }
    $new = Get-Content $NewPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $old = Get-Content $BackupPath -Raw -Encoding UTF8 | ConvertFrom-Json

    foreach ($property in $old.PSObject.Properties) {
        if ($property.Name -in @('mcpServers', 'mcp')) { continue }
        if (-not ($new.PSObject.Properties.Name -contains $property.Name)) {
            $new | Add-Member -NotePropertyName $property.Name -NotePropertyValue $property.Value -Force
        }
    }

    if (-not ($new.PSObject.Properties.Name -contains 'mcpServers')) {
        $new | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) -Force
    }
    if ($old.PSObject.Properties.Name -contains 'mcpServers' -and $old.mcpServers) {
        foreach ($server in $old.mcpServers.PSObject.Properties) {
            if (-not ($new.mcpServers.PSObject.Properties.Name -contains $server.Name)) {
                $new.mcpServers | Add-Member -NotePropertyName $server.Name -NotePropertyValue $server.Value -Force
            }
        }
    }

    $newMcp = if ($new.PSObject.Properties.Name -contains 'mcp') { $new.mcp } else { [pscustomobject]@{} }
    $oldMcp = if ($old.PSObject.Properties.Name -contains 'mcp') { $old.mcp } else { [pscustomobject]@{} }
    $serverNames = @($new.mcpServers.PSObject.Properties.Name)
    if ($Qwen) {
        $excluded = @()
        if ($oldMcp.PSObject.Properties.Name -contains 'excluded') { $excluded += @($oldMcp.excluded) }
        if ($newMcp.PSObject.Properties.Name -contains 'excluded') { $excluded += @($newMcp.excluded) }
        $excluded = @($excluded | Where-Object { $serverNames -notcontains $_ } | Select-Object -Unique)
        if ($excluded.Count -gt 0) {
            $newMcp | Add-Member -NotePropertyName excluded -NotePropertyValue $excluded -Force
        }
    } else {
        $enabled = @()
        if ($oldMcp.PSObject.Properties.Name -contains 'enabledProjectMcpServers') { $enabled += @($oldMcp.enabledProjectMcpServers) }
        if ($newMcp.PSObject.Properties.Name -contains 'enabledProjectMcpServers') { $enabled += @($newMcp.enabledProjectMcpServers) }
        $enabled = @($enabled | Where-Object {
            if ($serverNames -notcontains $_) { return $false }
            $server = $new.mcpServers.$_
            $disabled = ($server.PSObject.Properties.Name -contains 'disabled') -and [bool]$server.disabled
            return -not $disabled
        } | Select-Object -Unique)
        if ($enabled.Count -gt 0) {
            $newMcp | Add-Member -NotePropertyName enabledProjectMcpServers -NotePropertyValue $enabled -Force
        }
    }
    if (@($newMcp.PSObject.Properties).Count -gt 0) {
        $new | Add-Member -NotePropertyName mcp -NotePropertyValue $newMcp -Force
    }
    $json = $new | ConvertTo-Json -Depth 30
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($NewPath, $json, $utf8)
    Write-Ok "merged Target-only settings into $NewPath"
}

function Disable-QwenMcpServers {
    param(
        [Parameter(Mandatory)][string]$McpJsonPath,
        [string[]]$ServerNames
    )
    # Qwen has no `disabled` flag: a disabled server is removed from
    # `mcpServers` and listed in `mcp.excluded`.
    if (-not (Test-Path $McpJsonPath)) { return }
    $obj = Get-Content $McpJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not ($obj.PSObject.Properties.Name -contains 'mcpServers')) { return }
    $excluded = @()
    if (($obj.PSObject.Properties.Name -contains 'mcp') -and ($obj.mcp.PSObject.Properties.Name -contains 'excluded')) {
        $excluded = @($obj.mcp.excluded)
    }
    foreach ($name in $ServerNames) {
        if ($obj.mcpServers.PSObject.Properties.Name -contains $name) {
            $obj.mcpServers.PSObject.Properties.Remove($name)
        }
        if ($excluded -notcontains $name) { $excluded += $name }
    }
    if (-not ($obj.PSObject.Properties.Name -contains 'mcp')) {
        $obj | Add-Member -NotePropertyName mcp -NotePropertyValue ([pscustomobject]@{}) -Force
    }
    $obj.mcp | Add-Member -NotePropertyName excluded -NotePropertyValue $excluded -Force
    $json = $obj | ConvertTo-Json -Depth 30
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($McpJsonPath, $json, $utf8)
    Write-Ok "disabled MCP [$($ServerNames -join ', ')] in $McpJsonPath"
}

function Protect-CodePrismViews([string]$Root) {
    foreach ($rel in @('.agents\mcp_config.json', '.agents\mcp.json', '.codex\mcp.json', '.qoder\settings.json')) {
        $path = Join-Path $Root $rel
        if (-not (Test-Path -LiteralPath $path)) { continue }
        $obj = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
        if (-not ($obj.PSObject.Properties.Name -contains 'mcpServers') -or -not $obj.mcpServers) { continue }
        if ($obj.mcpServers.PSObject.Properties.Name -notcontains 'codeprism') { continue }
        $obj.mcpServers.codeprism | Add-Member -NotePropertyName disabled -NotePropertyValue $true -Force
        Set-CodePrismPlaceholder $obj.mcpServers.codeprism
        if (($obj.PSObject.Properties.Name -contains 'mcp') -and $obj.mcp -and
            ($obj.mcp.PSObject.Properties.Name -contains 'enabledProjectMcpServers')) {
            $obj.mcp.enabledProjectMcpServers = @($obj.mcp.enabledProjectMcpServers | Where-Object { $_ -ne 'codeprism' })
        }
        [System.IO.File]::WriteAllText($path, ($obj | ConvertTo-Json -Depth 100), (New-Object System.Text.UTF8Encoding($false)))
    }
    $qwen = Join-Path $Root '.qwen\settings.json'
    if (Test-Path -LiteralPath $qwen) {
        $settings = Get-Content -LiteralPath $qwen -Raw -Encoding UTF8 | ConvertFrom-Json
        if (($settings.PSObject.Properties.Name -contains 'mcpServers') -and $settings.mcpServers -and
            ($settings.mcpServers.PSObject.Properties.Name -contains 'codeprism')) {
            Disable-QwenMcpServers -McpJsonPath $qwen -ServerNames @('codeprism')
        }
    }
    $kilo = Join-Path $Root '.kilo\kilo.jsonc'
    if (Test-Path -LiteralPath $kilo) {
        $raw = [System.IO.File]::ReadAllText($kilo)
        $header = [regex]::Match($raw, '\A(?:(?:\s*//[^\r\n]*)(?:\r?\n|$))*').Value
        $obj = $raw.Substring($header.Length) | ConvertFrom-Json
        if (($obj.PSObject.Properties.Name -contains 'mcp') -and $obj.mcp -and
            ($obj.mcp.PSObject.Properties.Name -contains 'codeprism')) {
            $obj.mcp.codeprism | Add-Member -NotePropertyName enabled -NotePropertyValue $false -Force
            Set-CodePrismPlaceholder $obj.mcp.codeprism
            [System.IO.File]::WriteAllText($kilo, ($header + ($obj | ConvertTo-Json -Depth 100) + "`n"), (New-Object System.Text.UTF8Encoding($false)))
        }
    }
}

function Assert-CodePrismTransferSafe([string]$SourceRoot, [string]$TargetRoot) {
    # Адрес CodePrism в источнике - это собственный сервер образца, а не
    # признак чужого проекта. Копирование заменяет его отключённой заглушкой.
    # Проверяем только Target: ручной DSH patch может подключаться к чужому
    # графу, его перенос не перезаписывает.
    $targetCodex = Join-Path $TargetRoot '.codex\config.toml'
    if (Test-Path -LiteralPath $targetCodex) {
        $text = [System.IO.File]::ReadAllText($targetCodex)
        $section = [regex]::Match($text, '(?ms)^\s*\[mcp_servers\.["'']?codeprism["'']?\]\s*(.*?)(?=^\s*\[|\z)').Groups[1].Value
        $hasCodePrismUrl = $section -match '(?m)^\s*(?:url|server_url)\s*='
        $hasPlaceholder = $section -match '127\.0\.0\.1:0/mcp'
        if ($hasCodePrismUrl -and -not $hasPlaceholder) {
            Write-Warn2 "CodePrism Target будет заменён отключённой заглушкой: $targetCodex"
        }
    }
    $dsh = Join-Path $TargetRoot '.dsh'
    if (Test-Path -LiteralPath $dsh -PathType Container) {
        foreach ($patch in @(Get-ChildItem -LiteralPath $dsh -File | Where-Object { $_.Extension -in @('.yml', '.yaml') })) {
            if ([System.IO.File]::ReadAllText($patch.FullName) -match '(?i)codeprism' -and [System.IO.File]::ReadAllText($patch.FullName) -notmatch 'Generated by .*generate-dsh-config\.py') {
                throw "CodePrism: existing DSH patch $($patch.FullName) may connect to another project; review it before transfer"
            }
        }
    }
}

# Kit поверх Target: sourcegraph и прочие из образца добавляются;
# серверы только у Target (laravel-boost, …) сохраняются.
function Merge-McpJsonPreserveTargetOnly {
    param(
        [Parameter(Mandatory)][string]$NewPath,
        [Parameter(Mandatory)][string]$BackupPath
    )
    if (-not (Test-Path $NewPath) -or -not (Test-Path $BackupPath)) { return }
    $newObj = Get-Content $NewPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $oldObj = Get-Content $BackupPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $newObj.mcpServers -or -not $oldObj.mcpServers) { return }

    $newNames = @($newObj.mcpServers.PSObject.Properties.Name)
    $kept = @()
    foreach ($prop in $oldObj.mcpServers.PSObject.Properties) {
        $name = $prop.Name
        if ($newNames -contains $name) { continue }
        $newObj.mcpServers | Add-Member -NotePropertyName $name -NotePropertyValue $prop.Value -Force
        $kept += $name
    }
    if ($kept.Count -eq 0) {
        Write-Ok ("MCP merge ${NewPath}: нечего сохранять (все серверы Target уже в kit или Target пуст)")
        return
    }
    $json = $newObj | ConvertTo-Json -Depth 40
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($NewPath, $json, $utf8)
    Write-Ok ("MCP merge preserved Target-only: " + ($kept -join ', ') + " → ${NewPath}")
}

function Get-TomlTopLevelMcpNames([string]$Text) {
    $names = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($m in [regex]::Matches($Text, '(?m)^\[mcp_servers\.([^\.\]]+)')) {
        [void]$names.Add($m.Groups[1].Value)
    }
    return @($names)
}

function Get-TomlMcpServerChunk([string]$Text, [string]$ServerName) {
    # Все секции [mcp_servers.NAME] и [mcp_servers.NAME.*] до следующего чужого [mcp_servers.OTHER]
    $esc = [regex]::Escape($ServerName)
    $rx = [regex]::new(
        "(?ms)(^#.*\r?\n)*^\[mcp_servers\.$esc(?:\.[^\]]+)?\].*?(?=^\[mcp_servers\.(?!$esc(?:\.|\]))|\z)",
        [System.Text.RegularExpressions.RegexOptions]::Multiline
    )
    $chunks = New-Object System.Collections.Generic.List[string]
    foreach ($m in $rx.Matches($Text)) {
        $chunks.Add($m.Value.TrimEnd() + "`n")
    }
    if ($chunks.Count -eq 0) { return '' }
    return ($chunks -join "`n")
}

function Merge-CodexTomlPreserveTargetOnly {
    param(
        [Parameter(Mandatory)][string]$NewPath,
        [Parameter(Mandatory)][string]$BackupPath
    )
    if (-not (Test-Path $NewPath) -or -not (Test-Path $BackupPath)) { return }
    $newText = [System.IO.File]::ReadAllText($NewPath, [System.Text.Encoding]::UTF8)
    $oldText = [System.IO.File]::ReadAllText($BackupPath, [System.Text.Encoding]::UTF8)
    $newNames = Get-TomlTopLevelMcpNames $newText
    $oldNames = Get-TomlTopLevelMcpNames $oldText
    $kept = @()
    $append = New-Object System.Text.StringBuilder
    foreach ($name in $oldNames) {
        if ($newNames -contains $name) { continue }
        $chunk = Get-TomlMcpServerChunk -Text $oldText -ServerName $name
        if ([string]::IsNullOrWhiteSpace($chunk)) { continue }
        [void]$append.AppendLine("")
        [void]$append.AppendLine("# --- preserved from Target (pre-rebase): $name ---")
        [void]$append.Append($chunk.TrimEnd())
        [void]$append.AppendLine("")
        $kept += $name
    }
    if ($kept.Count -eq 0) {
        Write-Ok "Codex TOML merge: нечего сохранять Target-only MCP"
        return
    }
    $out = $newText.TrimEnd() + "`n" + $append.ToString()
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($NewPath, $out, $utf8)
    Write-Ok ("Codex TOML merge preserved: " + ($kept -join ', '))
}

function Write-GitExclude([string]$RepoRoot, [switch]$IncludeDocs) {
    $gitInfo = Join-Path $RepoRoot '.git\info'
    New-Item -ItemType Directory -Path $gitInfo -Force | Out-Null
    $excludePath = Join-Path $gitInfo 'exclude'
    $docHarnessLines = @(
        '/.doc/harnes/',
        '/.doc/skil_data/',
        '/.doc/temp/',
        '/.tools/codeception/',
        '/.doc/web/',
        '/.doc/.rebase-backup/',
        '/.doc/.rebase-mcp-backup/',
        '/.doc/.rebase-conflicts.json',
        '/.doc/.rebase-conflicts.*.json',
        '/.doc/.rebase-kit.json',
        '/.doc/.rebase-report.md',
        '/.doc/.rebase-preserved.txt'
    ) -join "`n"
    $docLine = if ($IncludeDocs) { $docHarnessLines } else { '/.doc/' }
    $block = @"
# Local developer excludes (export-rebase-project.ps1 / rebase_project.md)
# Зеркала - реальные копии: исключаются рабочие среды .codex, .kilo, .qoder, .qwen, .agents.
# .antigravity, .gemini, .kilocode оставлены как legacy-защита, они не генерируются.
/.cursor/
/.codex/
/.agents/
/.kilo/
/.qoder/
/.qwen/
/.antigravity/
/.gemini/
/.dsh/
/DSH-RULES.md
$docLine
/.serena/
/.playwright-mcp/
/AGENTS.md
/php_error.log
.kilocode/
kilo.json

# Local dev tooling tree (new convention)
/.tools/

# docker-dev local overrides (legacy tools/)
/tools/docker-dev/README.md
/tools/docker-dev/compose.yaml
/tools/docker-dev/php-apache/Dockerfile
/tools/docker-dev/php-apache/apache/

# Sourcegraph local stack
/sourcegraph-local/

# Graphify code graph (generated locally)
/graphify-out/

# Local Codeception credentials
/tools/codeception/tests/Acceptance/FirstCest.php
"@
    $begin = '# >>> export-rebase-project (managed block)'
    $end = '# <<< export-rebase-project'
    $managed = "$begin`n$($block.TrimEnd())`n$end"
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    if (Test-Path $excludePath) {
        $existing = [System.IO.File]::ReadAllText($excludePath, [System.Text.Encoding]::UTF8)
        if ($existing -match [regex]::Escape($begin)) {
            $pattern = '(?s)' + [regex]::Escape($begin) + '.*?' + [regex]::Escape($end)
            $updated = [regex]::Replace($existing, $pattern, $managed)
            [System.IO.File]::WriteAllText($excludePath, $updated, $utf8)
            Write-Ok "updated managed exclude block -> $excludePath"
            return
        }
        $legacyHeader = '# Local developer excludes (export-rebase-project.ps1 / rebase_project.md)'
        if ($existing -match [regex]::Escape($legacyHeader)) {
            # Older export wrote the block without markers. Add only the lines
            # it predates and never touch the rest of the developer's file.
            $missing = @()
            if ($existing -notmatch '(?m)^/\.qoder/$') { $missing += '/.qoder/' }
            if ($existing -notmatch '(?m)^/\.qwen/$') { $missing += '/.qwen/' }
            if ($missing.Count -gt 0) {
                $insert = ($missing -join "`n")
                $existing = $existing -replace '(?m)^/\.kilo/$', "/.kilo/`n$insert"
            }
            [System.IO.File]::WriteAllText($excludePath, $existing, $utf8)
            Write-Ok "updated legacy exclude block -> $excludePath"
            return
        }
        # Existing file belongs to the developer: keep every line and append
        # the managed block once. Nothing outside the block is rewritten.
        Add-Content -Path $excludePath -Value "`n$managed" -Encoding UTF8
        Write-Ok "appended managed exclude block -> $excludePath"
        return
    }
    [System.IO.File]::WriteAllText($excludePath, $managed + "`n", $utf8)
    Write-Ok "wrote $excludePath"
}

function Set-SerenaProjectName([string]$YmlPath, [string]$Name) {
    if (-not (Test-Path $YmlPath)) { return }
    $raw = [System.IO.File]::ReadAllText($YmlPath, [System.Text.Encoding]::UTF8)
    $new = [regex]::Replace($raw, '(?m)^project_name:\s*".*"', "project_name: `"$Name`"")
    if ($new -eq $raw) {
        $new = [regex]::Replace($raw, "(?m)^project_name:\s*'.*'", "project_name: `"$Name`"")
    }
    if ($new -ne $raw) {
        $utf8 = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($YmlPath, $new, $utf8)
        Write-Ok "serena project_name=$Name"
    } else {
        Write-Warn2 "не удалось заменить project_name в $YmlPath - правьте вручную"
    }
}

function Test-TcpPortFree([int]$Port) {
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
        $listener.Stop()
        return $true
    } catch {
        return $false
    }
}

function Resolve-SerenaPort([string]$Root, [string]$SourceRoot, [int]$Requested) {
    # Serena is one unit per project. Reusing the source port makes the Target
    # client talk to the source project, so pick the project's own port.
    $sourcePort = 9121
    $canon = Join-Path $SourceRoot '.cursor\mcp.json'
    if (Test-Path $canon) {
        $raw = Get-Content $canon -Raw -Encoding UTF8
        $m = [regex]::Match($raw, '"serena"[\s\S]{0,400}?127\.0\.0\.1:(\d+)/mcp')
        if ($m.Success) { $sourcePort = [int]$m.Groups[1].Value }
    }
    $port = $Requested
    if (-not $port) {
        $sh = Join-Path $Root '.dsh\scripts\serena-shared.sh'
        if (Test-Path $sh) {
            $m = [regex]::Match((Get-Content $sh -Raw -Encoding UTF8), 'SERENA_PORT:-(\d+)')
            if ($m.Success) { $port = [int]$m.Groups[1].Value }
        }
    }
    if (-not $port) {
        for ($candidate = [Math]::Max(9121, $sourcePort + 1); $candidate -le 9199; $candidate++) {
            if (Test-TcpPortFree $candidate) { $port = $candidate; break }
        }
    }
    if (-not $port) { $port = $sourcePort }

    if ($port -ne $sourcePort) {
        $old = "http://127.0.0.1:$sourcePort/mcp"
        $new = "http://127.0.0.1:$port/mcp"
        $textExt = @('.md', '.mdc', '.json', '.jsonc', '.mjs', '.js', '.cjs', '.ts',
            '.sh', '.ps1', '.yml', '.yaml', '.toml', '.txt')
        $changed = 0
        foreach ($dir in @('.cursor', '.codex', '.kilo', '.agents', '.qoder', '.qwen', '.dsh')) {
            $base = Join-Path $Root $dir
            if (-not (Test-Path $base)) { continue }
            Get-ChildItem -Path $base -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
                if ($textExt -notcontains $_.Extension.ToLower()) { return }
                $rel = $_.FullName.Substring($base.Length)
                if ($rel -match '[\\/]tmp[\\/]') { return }
                $raw = [System.IO.File]::ReadAllText($_.FullName, [System.Text.Encoding]::UTF8)
                if ($raw.Contains($old)) {
                    $utf8 = New-Object System.Text.UTF8Encoding($false)
                    [System.IO.File]::WriteAllText($_.FullName, $raw.Replace($old, $new), $utf8)
                    $changed++
                }
            }
        }
        Write-Ok "serena port $sourcePort -> $port ($changed file(s))"
    } else {
        Write-Warn2 "serena port remains $port (same as source); pass -SerenaPort"
    }
    return $port
}

function Normalize-KitDocLinks([string]$Root, [string]$SourceRoot = '') {
    $changes = [System.Collections.Generic.List[object]]::new()
    foreach ($dir in @('harnes', 'qa', 'web')) {
        $base = Join-Path $Root ".doc/$dir"
        if (-not (Test-Path $base)) { continue }
        foreach ($file in @(Get-ChildItem -LiteralPath $base -Recurse -File -Filter '*.md')) {
            if ([IO.Path]::GetRelativePath($base, $file.FullName) -match '(^|[\\/])(archive|idea|astra_plan|plan|audit|hermes|openhands)([\\/]|$)') { continue }
            if ($SourceRoot -and -not (Test-Path (Join-Path $SourceRoot ([IO.Path]::GetRelativePath($Root, $file.FullName))))) { continue }
            $raw = [IO.File]::ReadAllText($file.FullName)
            if ($raw.StartsWith('<!-- generated')) { continue }
            $new = [regex]::Replace($raw, '(?ms)^```[^\n]*\n.*?^```[^\n]*(?:\n|$)|`+[^`\n]*`+|(?<!!)\[([^\]\r\n]+)\]\(([^)\r\n]+)\)', [Text.RegularExpressions.MatchEvaluator]{
                param($match)
                if (-not $match.Groups[2].Success) { return $match.Value }
                $href = $match.Groups[2].Value
                if ($href -match '^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|#|/)' -or $href -notmatch '\.md(?:#.*)?$') { return $match.Value }
                $relative = [Uri]::UnescapeDataString(($href -split '#', 2)[0])
                $absolute = [IO.Path]::GetFullPath((Join-Path $file.DirectoryName $relative))
                if (Test-Path -LiteralPath $absolute) { return $match.Value }
                $kitRelative = [IO.Path]::GetRelativePath($Root, $absolute).Replace('\', '/')
                if ($kitRelative -match '^\.doc/(?:harnes|qa|web)/') {
                    throw "Missing portable documentation dependency: $kitRelative"
                }
                $changes.Add(@{ file = [IO.Path]::GetRelativePath($Root, $file.FullName); excluded = $kitRelative })
                return ($match.Groups[1].Value + ' (`' + $href + '`; не входит в kit)')
            })
            if ($new -ne $raw) { [IO.File]::WriteAllText($file.FullName, $new, [Text.UTF8Encoding]::new($false)) }
        }
    }
    [IO.File]::WriteAllText((Join-Path $Root '.doc/.rebase-doc-links.json'), (ConvertTo-Json -InputObject @($changes.ToArray()) -Depth 4), [Text.UTF8Encoding]::new($false))
    Write-Ok "document links: $($changes.Count) references to excluded project content recorded"
}

function Remove-CoreOnlyNoise([string]$Root, [switch]$PreserveInstructions) {
    # Core retains the harness router and its tools, including Mirror and sync.
    $runtimeSkills = @('code', 'codebase-memory-mcp', 'codegraph', 'codeprism', 'context7',
        'git', 'graphiti', 'jdocmunch', 'mysql', 'neiroslop', 'php-deps-mcp',
        'phpstan-mcp', 'playwright', 'ponytail', 'semgrep', 'serena')
    $skillsRoot = Join-Path $Root '.agents/skills'
    foreach ($skill in @(Get-ChildItem -LiteralPath $skillsRoot -Directory)) {
        if ($skill.Name -notin ($runtimeSkills + @('harness-router'))) {
            Remove-Item -LiteralPath $skill.FullName -Recurse -Force
        }
    }
    # Local adapter references are deliberately excluded from transfer. Do not
    # leave required manifest entries pointing to files which were not copied.
    foreach ($manifest in @(Get-ChildItem -LiteralPath $skillsRoot -Recurse -File -Filter 'skill.json')) {
        $data = Get-Content -LiteralPath $manifest.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($data.resources -and $data.resources.references) {
            $data.resources.references = @($data.resources.references | Where-Object {
                $ref = [string]$_
                -not ($ref -match '(?i)(^|[\\/])[^\\/]*\.local\.' -and
                      -not (Test-Path -LiteralPath (Join-Path $manifest.DirectoryName $ref)))
            })
            [IO.File]::WriteAllText($manifest.FullName, ($data | ConvertTo-Json -Depth 100) + "`n", [Text.UTF8Encoding]::new($false))
        }
    }
    $bugSkill = Join-Path $skillsRoot 'code/children/bug-cause/SKILL.md'
    if (Test-Path $bugSkill) {
        [IO.File]::WriteAllText($bugSkill, @"
---
name: bug-cause
description: Find the root cause of a code bug; trace callers, read source, test competing hypotheses. Use for why a bug happens or unexpected code behavior.
---
# Investigate a code bug

1. Record observed behavior, expected behavior and a reproducible input. Separate evidence from assumptions.
2. Identify the current project with codebase-memory-mcp list_projects; never use another project's graph.
3. Find symbols and call paths with search_graph and trace_path. Use codegraph with the absolute current projectPath if available.
4. Read the relevant source and tests, inspect inbound callers and outbound dependencies. Use git log, git diff and git blame for history.
5. Inspect current-project documentation via jdocmunch after resolving its repository handle. Missing tracker or task documentation does not block investigation.
6. Compare hypotheses with source evidence and a scoped reproducible test. Database schema uses mysql describe_table; changes to data require explicit permission.
7. Report the confirmed cause, exact paths/lines, impact, smallest proposed correction and verification gaps. Do not claim a runtime reproduction from static reading alone.

Core does not include tracker integration or platform impersonation. Use direct git and the project's own test commands.
"@, [Text.UTF8Encoding]::new($false))
    }
    $runtimeRules = @('batch-calls', 'code-editing', 'doc-rules', 'mcp',
        'cbm-index-before-push', 'temp-dir', 'text-style', 'gates')
    $rules = Join-Path $Root '.cursor/rules'
    foreach ($file in @(Get-ChildItem -LiteralPath $rules -File -Filter '*.mdc')) {
        if ($file.BaseName -notin $runtimeRules) { Remove-Item -LiteralPath $file.FullName -Force }
    }
    foreach ($name in @('jira-task', 'bitbucket-task', 'sourcegraph', 'deepwiki', 'xdebug')) {
        $path = Join-Path $rules "mcp/$name.mdc"
        if (Test-Path $path) { Remove-Item -LiteralPath $path -Force }
    }
    $gatePath = Join-Path $rules 'gates.mdc'
    if (Test-Path $gatePath) {
        $text = [IO.File]::ReadAllText($gatePath)
        $text = [regex]::Replace($text, '(?m)^.*improvement.*\r?\n', '')
        [IO.File]::WriteAllText($gatePath, $text, [Text.UTF8Encoding]::new($false))
    }
    # Client skill directories may contain target-only user files; sync owns
    # conflict detection, so never remove those directories during pruning.
    foreach ($rel in @('.tools/codeception', '.doc/qa', '.dsh/adapters', '.dsh/scripts', '.dsh/tests')) {
        $path = Join-Path $Root $rel
        if (Test-Path $path) { Remove-Item -LiteralPath $path -Recurse -Force }
    }
    foreach ($name in @('go-task.ps1', 'task-diff.ps1')) {
        $path = Join-Path $Root ".codex/$name"
        if (Test-Path $path) { Remove-Item -LiteralPath $path -Force }
    }
    Disable-McpServers -McpJsonPath (Join-Path $Root '.cursor/mcp.json') -ServerNames @('jira-task', 'bitbucket-task')
    if (-not $PreserveInstructions) {
    [IO.File]::WriteAllText((Join-Path $Root 'AGENTS.md'), @"
# Core project instructions

Use the operational skills in .agents/skills. Read .codex/rules-index.md in Codex
before work. Project code, credentials and infrastructure need target-specific setup.
The Core profile excludes source-project task data and tracker integrations.
Do not change or publish other projects. Never push without an explicit request.
"@, [Text.UTF8Encoding]::new($false))
    }
    $docs = Join-Path $Root '.doc/harnes'
    if (Test-Path $docs) {
        foreach ($entry in @(Get-ChildItem -LiteralPath $docs -Force)) {
            if ($entry.Name -ne 'doc_rules.md') { Remove-Item -LiteralPath $entry.FullName -Recurse -Force }
        }
    }
    $rebaseDoc = Join-Path $Root '.doc/rebase_project.md'
    if (Test-Path $rebaseDoc) { Remove-Item -LiteralPath $rebaseDoc -Force }
    [IO.File]::WriteAllText((Join-Path $docs 'index.md'), "# Core runtime documentation`n`nRead doc_rules.md. Operational skill documentation lives beside each SKILL.md in .agents/skills.`n", [Text.UTF8Encoding]::new($false))
    # Core does not ship JSONdoc or tracker workflows; do not leave instructions to invoke them.
    [IO.File]::WriteAllText((Join-Path $rules 'code-editing.mdc'), @"
---
description: Safe scoped source edits and verification in the current project.
alwaysApply: false
---
# Code editing

Apply ponytail: prefer an existing implementation or standard library and the smallest complete fix. Preserve validation, access checks and error handling.
Before PHP edits read the Serena skill and initial instructions. Inspect symbols, complete relevant bodies and references; verify diagnostics after editing. For other languages use scoped file edits; do not assume PHP-only symbol tools support JavaScript or Vue.
Before writes involving SQL, access control, XSS or user data, read the CodePrism and Semgrep rules. Use only the current project's services and graph.
Read the complete relevant file and verify that each edit anchor is unique. Do not edit generated files: identify their actual source and generator in the target project first. If the generator is absent, report that rather than inventing a command.
Do not modify dependencies, lock files or generated outputs by hand. Use the target project's toolchain. Never print credentials.
After edits inspect git diff, run the relevant parser, focused tests and static analysis. Separate static evidence from runtime verification; report unavailable checks.
Canonical configuration is .cursor; operational skills are .agents/skills. Generated client views are not independently editable. Internal synchronization entry point: .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh --local-only.
"@, [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText((Join-Path $rules 'batch-calls.mdc'), @"
---
description: Batch independent read-only commands and MCP searches.
alwaysApply: false
---
# Batch independent reads

Group three or more independent read-only commands with .tools/scripts/multi-exec.sh or searches with .tools/scripts/multi-search.sh. Prefer project-scoped graph tools for code and jdocmunch for documentation before literal scans.
Do not batch dependent operations, edits, long-running services or irreversible writes. Resolve paths and handles before using their results. Never mix projects in a graph or documentation query.
"@, [Text.UTF8Encoding]::new($false))
    # Optional cross-skill links from Full must not advertise components absent from Core.
    $coreFiles = @(Get-ChildItem -LiteralPath $rules -Recurse -File -Filter '*.mdc') +
        @(Get-ChildItem -LiteralPath $skillsRoot -Recurse -File -Filter 'SKILL.md')
    foreach ($file in $coreFiles) {
        $raw = [IO.File]::ReadAllText($file.FullName)
        $lines = $raw -split "`n" | Where-Object {
            $line = $_
            $refs = [regex]::Matches($line, '(?:\.agents/skills/|\.\./skills/)([^`\s)]+/SKILL\.md)')
            -not @($refs | Where-Object { -not (Test-Path (Join-Path $skillsRoot $_.Groups[1].Value)) }).Count
        }
        [IO.File]::WriteAllText($file.FullName, (($lines -join "`n").TrimEnd() + "`n"), [Text.UTF8Encoding]::new($false))
    }
    [IO.File]::WriteAllText((Join-Path $docs 'doc_rules.md'), @"
# Project documentation

Keep one source of truth and link to it. Use the current project's documentation, not the source kit's tasks or application architecture.
Discover documentation with jdocmunch after doc_resolve_repo for the absolute current .doc path. If the index is absent or unavailable, say so and read known local files. Index creation requires permission.
Inspect the file before editing. Preserve facts and history; mark uncertain or stale information. Do not change generated documents directly: identify the project's actual canonical source and generator.
Keep temporary experiments outside durable documentation. Never copy credentials, runtime caches or another project's task history into project docs.
"@, [Text.UTF8Encoding]::new($false))
    Write-Ok 'Core: operational skills, harness tools and panel retained'
}

function Initialize-CoreRuntimeDocs([string]$Root, [string]$SourceRoot) {
    # Core omits the full harness documentation, but doctor still needs the
    # disabled-server records and an inventory of the tools actually shipped.
    $archive = Join-Path $Root '.doc/harnes/archive/mcp'
    $state = Join-Path $Root '.doc/harnes/state'
    New-Item -ItemType Directory -Force -Path $archive, $state | Out-Null
    $layout = Join-Path $SourceRoot '.doc/harnes/state/canon-paths.yaml'
    foreach ($relative in @('.doc', '.doc/harnes', '.doc/harnes/state', '.doc/harnes/state/canon-paths.yaml')) {
        $part = Get-Item -LiteralPath (Join-Path $SourceRoot $relative) -Force -ErrorAction Stop
        if (($part.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "linked canonical policy path is not allowed: $relative"
        }
    }
    if (-not (Test-Path -LiteralPath $layout -PathType Leaf)) { throw 'Core canonical path policy is missing' }
    Copy-Item -LiteralPath $layout -Destination (Join-Path $state 'canon-paths.yaml')
    $mcp = Get-Content -LiteralPath (Join-Path $Root '.cursor/mcp.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($entry in $mcp.mcpServers.PSObject.Properties) {
        if (-not $entry.Value.disabled) { continue }
        $name = $entry.Name
        if ($name -notmatch '^[a-zA-Z0-9_-]+$') { throw "Invalid MCP name: $name" }
        $skillDoc = Join-Path $Root ".agents/skills/$name/docs/mcp/$name.md"
        if (Test-Path -LiteralPath $skillDoc -PathType Leaf) { continue }
        $src = Join-Path $SourceRoot ".doc/harnes/archive/mcp/$name.md"
        if ($name -eq 'jira-task' -and -not (Test-Path -LiteralPath $src)) {
            $src = Join-Path $SourceRoot '.agents/skills/task-router/children/jira/docs/mcp/jira-task.md'
        }
        if (-not (Test-Path -LiteralPath $src -PathType Leaf)) { throw "Missing disabled MCP documentation: $name" }
        $body = [IO.File]::ReadAllText($src)
        [IO.File]::WriteAllText((Join-Path $archive "$name.md"), "# $name (disabled in Core)`n`n$body", [Text.UTF8Encoding]::new($false))
    }
    $lines = @('# Core tools inventory', '', 'Directories present in this installation:')
    $tools = Join-Path $Root '.tools'
    if (Test-Path -LiteralPath $tools) {
        foreach ($item in @(Get-ChildItem -LiteralPath $tools -Directory | Sort-Object Name)) {
            $lines += ('- `.tools/' + $item.Name + '`')
        }
    }
    [IO.File]::WriteAllText((Join-Path $state '26-tools.md'), (($lines -join "`n") + "`n"), [Text.UTF8Encoding]::new($false))
}

function Set-CorePanelProfile([string]$Root) {
    $path = Join-Path $Root '.doc/web/config/service.json'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw 'Core panel service.json is missing' }
    $config = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $config -or -not ($config.PSObject.Properties.Name -contains 'profile')) {
        throw 'Core panel service.json has no profile'
    }
    $config.profile = 'core'
    [IO.File]::WriteAllText($path, (($config | ConvertTo-Json -Depth 100) + "`n"), [Text.UTF8Encoding]::new($false))
}

function Normalize-CoreMcpLinks([string]$Root, [string]$SourceRoot) {
    # Keep the text and record links intentionally excluded by the Core profile;
    # do not mask a link that is already broken in the original source.
    $changes = [System.Collections.Generic.List[object]]::new()
    $skills = Join-Path $Root '.agents/skills'
    foreach ($doc in @(Get-ChildItem -LiteralPath $skills -Recurse -File -Filter '*.md' | Where-Object {
        $_.FullName -match '[\\/]docs[\\/]mcp[\\/][^\\/]+\.md$'
    })) {
        $sourceDoc = Join-Path $SourceRoot ([IO.Path]::GetRelativePath($Root, $doc.FullName))
        if (-not (Test-Path -LiteralPath $sourceDoc -PathType Leaf)) { continue }
        $convert = {
            param([string]$link)
            $path = ($link -split '#', 2)[0]
            if (-not $path -or $path -match '^[a-zA-Z][a-zA-Z0-9+.-]*:' -or $path.StartsWith('/')) { return $false }
            $target = [IO.Path]::GetFullPath((Join-Path $doc.DirectoryName $path))
            if (Test-Path -LiteralPath $target) { return $false }
            $rel = [IO.Path]::GetRelativePath($Root, $target).Replace('\', '/')
            if ($rel -notmatch '^(\.doc/(harnes|skil_data)/|\.cursor/rules/|\.agents/skills/)') { return $false }
            $original = Join-Path $SourceRoot $rel
            if (-not (Test-Path -LiteralPath $original)) { return $false }
            $changes.Add(@{ file = [IO.Path]::GetRelativePath($Root, $doc.FullName).Replace('\', '/'); excluded = $rel; original = $link })
            return $true
        }
        $raw = [IO.File]::ReadAllText($doc.FullName)
        $new = [regex]::Replace($raw, '(?m)^related:\s*\[([^\]]*)\]', [Text.RegularExpressions.MatchEvaluator]{
            param($match)
            $kept = @($match.Groups[1].Value -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not (& $convert $_) })
            return 'related: [' + ($kept -join ', ') + ']'
        })
        $new = [regex]::Replace($new, '(?ms)^```[^\n]*\n.*?^```[^\n]*(?:\n|$)|`+[^`\n]*`+|(?<!!)\[([^\]\r\n]+)\]\(([^)\r\n]+)\)', [Text.RegularExpressions.MatchEvaluator]{
            param($match)
            if (-not $match.Groups[2].Success -or -not (& $convert $match.Groups[2].Value)) { return $match.Value }
            return ($match.Groups[1].Value + ' (`' + $match.Groups[2].Value + '`; не входит в Core)')
        })
        if ($new -ne $raw) { [IO.File]::WriteAllText($doc.FullName, $new, [Text.UTF8Encoding]::new($false)) }
    }
    [IO.File]::WriteAllText((Join-Path $Root '.doc/.rebase-core-links.json'), (ConvertTo-Json -InputObject @($changes.ToArray()) -Depth 4), [Text.UTF8Encoding]::new($false))
    Write-Ok "Core MCP documentation: $($changes.Count) excluded references recorded"
}

function Write-NextSteps([string]$Root, [string]$ProfileName, [string]$Name, [string]$SourceName, [int]$SerenaPort = 9121) {
    if ($ProfileName -eq 'Core') {
        [IO.File]::WriteAllText((Join-Path $Root 'EXPORT_NEXT_STEPS.md'), @"
# Core runtime setup

Canonical skills: .agents/skills. Canonical rules and MCP: .cursor.
Configure the new project's MCP credentials, PHP container and database before use.
Project graphs, documentation indexes, caches and credentials were not imported.
Synchronization has already run locally. Repeat it after editing project configuration:

bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh --local-only

Core includes operational code skills, harness tools and the web panel.
Source-project task data, QA corpus and tracker integrations are excluded.
Full harness documentation is available in the Full kit.
"@, [Text.UTF8Encoding]::new($false))
        return
    }

    $path = Join-Path $Root 'EXPORT_NEXT_STEPS.md'
    $template = @'
# После export-rebase-project

Целевой проект: `__ROOT__`
Serena project_name: `__NAME__`
Профиль: `__PROFILE__`

Экспорт переносит среду агента, а не приложение. Ниже полный порядок запуска
на новом проекте: секреты, пути, индексы, панель, тесты и проверка.

## 0. Что уже сделано

- Скопированы `.cursor/`, `.codex/`, `.qoder/`, `.qwen/`, `.serena/project.yml`, `.agents/`, DSH kit, стандарты `.doc/` и QA-контур.
- Из `.doc/skil_data` перенесены только `*.example.*`; рабочие данные создаются на Target.
- Документация харнеса из `.doc/architecture` перенесена вместе с JSON-каноном, где он есть. Ссылки на исключённые задачи и контент приложения помечены; список: `.doc/.rebase-doc-links.json`.
- Абсолютные пути образца заменены на `__ROOT__` в конфигах и лаунчерах.
- `.serena/project.yml` получил `project_name: "__NAME__"`.
- `mcp.env` созданы из примеров без секретов. Git меняется только при явных флагах `-InitGit` и/или `-ManageGitExclude`.
- Из реестра компонентов убраны скилы, которых нет в этом проекте, и runtime-пути.
- Файлы Target, которых нет в образце, не удаляются. Отчёт: `.doc/.rebase-report.md` и `.doc/.rebase-report.json`, список: `.doc/.rebase-preserved.txt`.
- Отчёт показывает, сколько в проекте документации, задач и кастомных скилов, какие файлы kit перезаписаны.
- Точное зеркало kit с удалением лишнего включается отдельным флагом `-MirrorKit`.
- Повторный перенос обновлённого kit выполняется той же командой из репозитория-образца; файлы проекта сохраняются, отчёт перезаписывается.
- Не копировались: задачи, контент архитектуры Copytrust, `.codegraph/`, venv (`.cursor/tools/codeprism-ai/venv`), `.doc/qa/tmp-runs`, `sourcegraph-local`.
- `.tools/` переносится безопасным набором: `.tools/scripts`, `docker-dev/compose.yaml`, `docker-dev/php-apache`, `php85-scan`, `codeception/codeception.yml`, `codeception/composer.json`, `codeception/composer.lock`, `codeception/scripts`, `codeception/tests/_envs`; без `.env`, `dump.sql`, `vendor`, `_output`, `__pycache__`.

## 0.1. MCP: что проверить до работы

| Сервер | Что должно быть | Если не так |
|---|---|---|
| `codebase-memory-mcp` | проект Target в `list_projects`, граф готов | `index_repository(repo_path="__ROOT__", mode="fast")` |
| `codegraph` | `.codegraph/` построен, `pendingChanges` пуст | `codegraph init --yes __ROOT__` |
| `codeprism` | отдельный сервер проекта, ответ `get_graph_stats` подтверждает корень и готовый индекс | раздел 4.3 |
| `serena` | порт `__SERENA_PORT__`, project `__NAME__` | раздел 4.5 |
| `jdocmunch` | repo `local/__NAME__`, индекс собран | раздел 4.4 |
| `mysql` | выключен, если проект не на MySQL | раздел 2 |

Вопросы, которые агент обязан задать до правок и запусков:

1. Имя PHP-контейнера и путь к PHP-обвязкам.
2. Какая БД и порт, если включать mysql.
3. Есть ли доступ к Jira и какую учётную запись брать.
4. Нужен ли Sourcegraph и какой репозиторий.
5. Какой стенд и URL для тестов, есть ли браузер и chromedriver.
6. Какой провайдер Qwen задан в `~/.qwen/settings.json`.
7. Какой порт Serena закреплён за проектом: `__SERENA_PORT__`.

## 1. Первые 10 минут

1. Открыть этот каталог как корень workspace: `__ROOT__`. Не открывать родительскую папку.
2. Reload Window и проверить, что Settings -> MCP видит серверы.
3. Выполнить синхронизацию представлений:

   ```bash
   bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh
   ```

   Синк пересобирает `.codex`, `.kilo`, `.agents`, `.qoder` и `.qwen` из канона.
   Скопированные `.qoder` и `.qwen` до синка могут содержать пути и настройки образца.

4. Qoder: `.qoder/settings.json` запускает stdio MCP через `.cursor/mcp.env`;
   для Qoder IDE пользовательские коннекторы хранятся в `~/.qoder/settings.json`.
5. Qwen Code: `.qwen/rules` и `.qwen/settings.json` генерируются из канона,
   `.agents/skills` читается нативно, `AGENTS.md` тоже. Путь и провайдер задаются
   в `~/.qwen/settings.json` внутри `qwen`; секреты в проект не копируются.
6. Заполнить секреты из раздела 2.
7. Прогнать smoke MCP:

   ```bash
   node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs
   ```

   Ожидаемо: все включённые серверы OK. Допустимые отклонения до настройки:
   `sourcegraph`, `xdebug`, `bitbucket-task` и `deepwiki` SKIP (выключены в каноне),
   `jira-task` FAIL до подъёма Docker-стенда, `mysql` SKIP если relay уже занят,
   `codeprism` SKIP до настройки отдельной службы,
   `codebase-memory-mcp` DEGRADED до `index_repository` (раздел 4.1).

## 1a. Мастер настройки проекта

Скрипт запускается **в корне Target**, не в репозитории-образце. Экспорт уже скопировал его в `.agents/skills/harness-router/children/project-setup/scripts/onboard-project.py`.

Сначала проверка без изменений:

```bash
python3 .agents/skills/harness-router/children/project-setup/scripts/onboard-project.py --root . --check
```

Первичная настройка, с индексами:

```bash
python3 .agents/skills/harness-router/children/project-setup/scripts/onboard-project.py --root . --yes \
  --php-container <container> \
  --mysql disable --mysql-database <db> --mysql-port <port> \
  --serena-port __SERENA_PORT__ --web-port <free-port>
```

Повторный запуск после очередного экспорта, когда индексы уже построены:

```bash
python3 .agents/skills/harness-router/children/project-setup/scripts/onboard-project.py --root . --yes --skip-indexes \
  --php-container <container> \
  --mysql disable --mysql-database <db> --mysql-port <port> \
  --serena-port __SERENA_PORT__
```

После повторного экспорта вернуть проектный `AGENTS.md`, если он был заменён версией образца.

Флаги: `--mysql keep|disable|set`, `--mysql-database`, `--mysql-port`,
`--reindex-project-docs` (медленный индекс `.dsh`, 15-20 мин),
`--add-harness-to-git` (по умолчанию харнес в git не добавляется),
`--include-harness`, `--include-docs`, `--exclude-docs`, `--add-docs-to-git`,
`--skip-indexes`. Отчёт: `.doc/onboard-report.md` и `.doc/onboard-report.json`.
Скрипт не коммитит и не удаляет файлы проекта.

## 2. Секреты

| Файл | Ключи | Откуда взять |
|---|---|---|
| `.cursor/mcp.env` | `MYSQL_*`, `DOCKER_PHP_CONTAINER`, `NODE_BIN`, `PHP_BIN` | `.env` своего `.tools/docker-dev` |
| `.codex/mcp.env` | те же | тот же файл |
| `.kilo/mcp.env` | те же | тот же файл; создан из примера, не из образца |
| `.doc/skil_data/jira/config.env` | `JIRA_*` | доступ к Jira под своей учётной записью |


Проверка, что секретов образца нет:

```bash
grep -RIn "sgp_\|JIRA_API_TOKEN=." .cursor/mcp.env .codex/mcp.env .kilo/mcp.env .doc/skil_data/jira/config.env
```

Ожидаемо: только пустые значения и комментарии.

## 3. Имена продукта

Экспорт заменяет абсолютные пути образца и имя его каталога во всех файлах kit
(`.cursor`, `.codex`, `.kilo`, `.agents`, `.qoder`, `.qwen`, `AGENTS.md`, `mcp.index.md`). Остальные
продуктовые строки нужно заменить вручную:

```bash
grep -rIn "__SOURCE_LEAF__\|copytrust-dev-php-apache-1\|repo:\^\|CT-" \
  .cursor .codex .kilo .agents .qoder .qwen .dsh AGENTS.md mcp.index.md
```

Заменить:

- имя Docker-контейнера PHP;
- фильтр `repo:` под свой `repos.conf`;
- префикс задач `CT-`;
- имя БД и порт стенда в `.cursor/mcp.env` и `.codex/mcp.env`;
- URL стенда и S3 в `.doc/architecture/index.md` после заполнения архитектуры.

После замены повторить `bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh`.

## 4. Индексы и графы

Порядок важен: сначала индексы, потом smoke MCP.

### 4.1. Codebase Memory (CBM)

```
index_repository(repo_path="__ROOT__", mode="fast")
index_status(project="...")
```

Имя проекта взять из `list_projects`. Индекс строится на Target, из образца он не переносится.

### 4.2. CodeGraph

```bash
codegraph init --yes __ROOT__
codegraph status --json
```

`.codegraph/` не копируется. Ожидаемо: `fileCount`, `nodeCount` и `edgeCount` больше нуля, `pendingChanges` пуст.

### 4.3. CodePrism

CodePrism после переноса отключен. Вместо адреса образца записана заглушка
`http://127.0.0.1:0/mcp`: включайте сервер только после проверки, что он
обслуживает Target. Адрес образца нельзя включать в Target: он
может обслуживать чужой проект. Один процесс обслуживает один проект; несколько
редакторов подключаются к нему. Ниже порядок для Linux или WSL с работающим
`systemctl --user`. Нативная служба Windows этим скриптом не создаётся.

1. Войдите в корень Target и выберите отдельный свободный порт. Например, 9202
   подходит только если порт свободен и не закреплён за другой службой. Проверьте
   свои настройки DSH, глобальные клиентские конфигурации и запущенные процессы.
   Старые stdio-процессы именно Target могут обращаться к той же базе; согласуйте
   и остановите их до запуска новой службы. Другие проекты не останавливайте.

```bash
PROJECT="$(pwd -P)"
PORT=9202
systemctl --user list-units --all 'mcp-codeprism*'
ss -ltnp
ps -eo pid,ppid,args | grep '[c]odeprism_serve.py'
```

2. Проверьте `.codeprism.toml`: файл скопирован из образца, если в Target его
   не было. Языки и исключения должны подходить Target. Не копируйте чужую базу
   или виртуальное окружение. Если venv уже существует, проверьте его и не
   пересоздавайте без решения владельца. Для отсутствующего venv:

```bash
mkdir -p "$PROJECT/.cursor/tools/codeprism-ai"
uv venv "$PROJECT/.cursor/tools/codeprism-ai/venv"
uv pip install --python "$PROJECT/.cursor/tools/codeprism-ai/venv/bin/python" 'codeprism-ai==0.1.11'
```

3. Создайте unit в каталоге пользовательского systemd. Скрипт проверяет свободный
   порт и имеющиеся unit в указанном каталоге, не перезаписывает другой unit и
   печатает точное имя службы. Проверьте выведенный путь и содержимое unit до
   запуска: `WorkingDirectory`, Python, сервер, корень и порт должны относиться
   к Target. При занятом порте выберите другой и повторите регистрацию.

```bash
mkdir -p "$HOME/.config/systemd/user"
python3 "$PROJECT/.cursor/mcp-stack/add-codeprism.py" "$PROJECT" "$PORT" \
  --output-dir "$HOME/.config/systemd/user"
```

4. После проверки выполните выведенные скриптом команды `systemctl --user
   daemon-reload` и `systemctl --user enable --now <имя-unit>`. Проверьте
   состояние и журнал этого unit. Сервер начинает фоновую индексацию при запуске;
   `CODEPRISM_NO_AUTO_INDEX=1` отключает также наблюдатель файлов.

```bash
systemctl --user status '<имя-unit>' --no-pager
journalctl --user -u '<имя-unit>' -n 100 --no-pager
```

5. До включения клиентов подключитесь отдельным MCP-клиентом к
   `http://127.0.0.1:<PORT>/mcp` и вызовите `get_graph_stats(path=".")`.
   Дождитесь `index_status = ready`; `project_path` после `realpath` должен
   точно совпасть с `PROJECT`. Открытый порт и список инструментов не доказывают
   принадлежность графа. При ошибке или чужом пути не включайте CodePrism.

```bash
"$PROJECT/.cursor/tools/codeprism-ai/venv/bin/python" - "$PROJECT" "$PORT" <<'PY'
import asyncio
from pathlib import Path
import sys
from fastmcp import Client

async def main():
    async with Client(f'http://127.0.0.1:{int(sys.argv[2])}/mcp') as client:
        result = await client.call_tool('get_graph_stats', {'path': '.'})
        data = result.structured_content or result.data
        if result.is_error or not isinstance(data, dict):
            raise RuntimeError('CodePrism вернул ошибку')
        if Path(data['project_path']).resolve() != Path(sys.argv[1]).resolve():
            raise RuntimeError('CodePrism обслуживает другой проект')
        if data.get('index_status') != 'ready':
            raise RuntimeError('индекс не готов; повторите проверку позже')
        print('CodePrism: проект и готовность индекса подтверждены')

asyncio.run(asyncio.wait_for(main(), timeout=30))
PY
```

6. Только после проверки измените запись `codeprism` в каноне `.cursor/mcp.json`:
   укажите `type: "http"`, URL `http://127.0.0.1:<PORT>/mcp` и снимите
   `disabled`. Сохраните остальные параметры. Затем синхронизируйте используемые
   клиентские представления из канона и проверьте через каждый клиент тот же
   `project_path`. Stdio-мост Codex проверяет корень и читает URL из канона;
   `CODEPRISM_TARGET` сам по себе не выбирает граф сервера.

   Перед общим `sync-agent-views.sh` проверьте его побочные эффекты: скрипт
   обновляет представления Codex и может изменить глобальную конфигурацию Gemini.
   Нестандартные DSH и глобальные конфигурации проверьте отдельно. Полная
   синхронизация и доступ Windows-клиента к WSL не подтверждаются одним наличием
   URL. После включения комплексная проверка: `bash .cursor/mcp-stack/verify.sh "$PROJECT"`.

Сервер доступен на loopback без аутентификации и предназначен для доверенных
локальных процессов. При отключении сначала отключите клиентов, затем выполните
`systemctl --user disable --now <имя-unit>` для службы Target. База при остановке
не удаляется. Инструкция не исправляет ограничения самого переноса kit: некоторые
существующие настройки Codex или DSH останавливают перенос до записи.

### 4.4. jDocMunch

```bash
bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --index
bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --repo
```

Первый запуск загружает модель 25-60 с. Индекс лежит в `~/.doc-index/local/<name>.json`.

### 4.5. Serena

Serena обслуживает один проект на юнит:

```bash
bash .cursor/mcp-stack/add-serena.sh "__ROOT__" __SERENA_PORT__
bash .cursor/mcp-stack/verify.sh "__ROOT__"
```

Порт `__SERENA_PORT__` уже записан в клиентские конфиги. После регистрации проверить,
что ни один клиент не смотрит на порт образца, и сделать Reload Window.

## 5. Codex

1. Проверить, что `.codex/config.toml` содержит пути `__ROOT__`, а не каталог образца.
2. Добавить trust на новый путь и обновить `.codex/global-trust.snippet.toml`.
3. Перезапустить Codex и проверить MCP.

## 6. Панель документации

```bash
cd .doc/web
./install.sh --check
./install.sh --project
./verify.sh
./start.sh
```

Панель слушает порт 8077, другой порт задаётся `WEB_PANEL_PORT`. `install.sh --project` создаёт `state/`, `ADAPTERS.local.md` и `.env` с путями Target. Windows: `install.ps1 -Check`, затем `install.ps1 -Project`.

## 7. QA, браузер и тесты

- `.tools/codeception/vendor` скопирован, если экспорт шёл без `-SkipRuntimeDeps`.
- Свой `dump.sql` и БД стенда нужны обязательно: дамп Copytrust не переносится.
- Chrome и chromedriver: `.doc/qa/browser-setup.md`.
- Приложение берётся из git целевого проекта. В `.tools/` переносятся только конфиги и скрипты; `.env`, дамп MySQL, `vendor` и `_output` создаются на месте.
- Первый прогон: `bash .agents/skills/task-router/children/testing-router/children/browser-verify/scripts/start-chromedriver-wsl.sh`, затем `codecept run`.

## 8. Git

- По умолчанию экспорт не создаёт Git и не меняет `.git/info/exclude`; `.gitignore` проекта не копируется и не перезаписывается.
- С `-ManageGitExclude` локальный блок exclude скрывает харнес; с дополнительным `-IncludeDocs` документация `.doc` не исключается этим блоком.
- Без `-ManageGitExclude` проверьте правила текущего проекта: переносимые файлы могут появиться в `git status`. Не добавляйте их в индекс без проверки состава и секретов.
- Только документация без харнеса: `--include-docs` и не передавать `--include-harness`.
- Добавить харнес: `onboard-project.py --add-harness-to-git` (стейджинг без коммита).
- Добавить документацию: `onboard-project.py --include-docs --add-docs-to-git` (архитектура, задачи, manifest, archviz).
- Скрыть документацию: `--exclude-docs`.
- Коммит не создавать до `git status` и проверки, что в индекс не попали секреты и лишние runtime-файлы.

## 9. Хост-инструменты

| Инструмент | Зачем | Проверка |
|---|---|---|
| Node 20+, npm, npx | MCP на Node | `node -v`, `npx -v` |
| uv, uvx | serena, semgrep, git, codeprism | `uv --version` |
| Docker Desktop | стенд, MySQL, Jira | `docker ps` |
| codebase-memory-mcp | CBM | `codebase-memory-mcp --version` |
| codegraph | граф кода | `codegraph status` |
| Chrome и chromedriver | Codeception, Playwright | `.doc/qa/browser-setup.md` |
| Python 3.12 | скрипты `.doc`, content-extractor | `python3 --version` |

## 10. Финальный чеклист

```bash
bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh
python3 .agents/skills/harness-router/children/environment-sync/tests/test_sync_views.py
python3 .agents/skills/harness-router/children/improvement/scripts/validate_registry.py
python3 .agents/skills/harness-router/children/improvement/scripts/validate_rules.py \
  --rules-dir .cursor/rules --skills-dir .agents/skills
node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs
```

Ожидаемо:

- sync заканчивается строкой `All Agent Views ... Successfully Synced`;
- `test_sync_views.py` печатает `21/21 tests passed`;
- `validate_registry.py` возвращает `status: passed`;
- `validate_rules.py` не содержит `severity: error`, warnings допустимы;
- MCP smoke: 14 OK, разрешённые SKIP, `jira-task` зелёный только после стенда.

## 11. Частые ошибки

| Симптом | Причина | Решение |
|---|---|---|
| `jira-task` FAIL или Loading | нет Docker-контейнера или неверное имя | поднять стенд, поправить имя контейнера в `.cursor/mcp.json` |
| `serena` Loading | первый запуск `uvx` | подождать, затем Reload Window |
| `mysql` не подключается | занят `127.0.0.1:3306` или неверный `MYSQL_PORT` | освободить порт, сверить `.env` docker-dev |
| `phpstan` или `php-deps` Error на Windows | `bash` из WSL ломает путь `C:\...` | открыть через WSL Remote или перейти на `node-mcp.cmd` |
| `codeprism` не стартует | venv не создан, он не копируется | команды из раздела 4.3 |
| `codegraph` пустой | индекс не построен | `codegraph init --yes __ROOT__` |
| `jdocmunch` не находит документы | индекс не собран | `bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --index` |
| `validate_rules.py` ругается на `login-as-user` | скил Copytrust-only удалён | warning допустим, error лечится обновлением ссылки в скиле |
| панель не открывается | нет `state/`, `.env` или порт занят | `install.sh --project`, затем `verify.sh` |
| пути указывают на старый проект | правка сделана после экспорта | повторить `sync-agent-views.sh` и проверить `grep -R` по старым путям |

## 12. Что не скопировано намеренно

| Путь | Причина |
|---|---|
| `.doc/tasks/{N}/`, `.doc/tasks/index.md` | задачи другого продукта |
| `.doc/architecture/*` кроме `index.md` | архитектура другого продукта |
| `.codegraph/` | локальный индекс, строится на Target |
| `.cursor/tools/codeprism-ai/venv` | Python venv с абсолютными путями |
| `.doc/qa/tmp-runs` | артефакты прогонов образца |
| `.doc/skil_data/task-doc/runs`, `work`, `state` | прогоны и состояние образца |
| живые `mcp.env`, `config.env`, SG-токен, `mcp.token` | секреты |
| `.doc/web/state`, `ADAPTERS.local.md`, `actions.local.json` | состояние панели |
| корневой `node_modules/` приложения | не нужен MCP |

## 13. Канон

- `.doc/rebase_project.md` - полная процедура, Day0, День 1, ошибки П-1 - П-20.
- `.doc/harnes/state/14-project-migration.md` - краткая карта переноса.
- `.doc/harnes/mcp/{server}.md` - настройка каждого MCP.
- `.doc/harnes/doc_rules.md` - правила записи документации.
- `.agents/skills/harness-router/children/new-project/SKILL.md` - экспорт kit, этап 0 и подтверждение.
- `.agents/skills/harness-router/children/project-setup/SKILL.md` - настройка MCP, портов, индексов и git.
'@
    $content = $template.Replace('__ROOT__', $Root).Replace('__NAME__', $Name).Replace('__PROFILE__', $ProfileName).Replace('__SOURCE_LEAF__', $SourceName).Replace('__SERENA_PORT__', "$SerenaPort")
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($path, $content, $utf8)
    Write-Ok "wrote EXPORT_NEXT_STEPS.md"
}

# --- main ---

$scriptDir = $PSScriptRoot
if (-not $Source) {
    # Скрипт лежит в .doc/ рядом с rebase_project.md → корень репо = родитель
    $Source = Resolve-FullPath (Join-Path $scriptDir '..\..\..\..\..\..')
} else {
    $Source = Resolve-FullPath $Source
}
$Target = Resolve-FullPath $Target
$targetHadAgents = Test-Path (Join-Path $Target 'AGENTS.md')
$pathComparison = if ([IO.Path]::DirectorySeparatorChar -eq '\') { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
$sourcePrefix = $Source.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
$targetPrefix = $Target.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
if ($Source.Equals($Target, $pathComparison) -or $sourcePrefix.StartsWith($targetPrefix, $pathComparison) -or $targetPrefix.StartsWith($sourcePrefix, $pathComparison)) {
    throw 'Source and Target must not overlap'
}
foreach ($rootPath in @($Source, $Target)) {
    $ancestor = $rootPath
    while ($ancestor) {
        if ((Test-Path -LiteralPath $ancestor) -and ((Get-Item -LiteralPath $ancestor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Linked Source/Target ancestor is not supported: $ancestor"
        }
        $ancestor = Split-Path $ancestor -Parent
    }
}

# The legacy Core pruning pass removes components and cannot distinguish prior
# kit ownership from user content. Until receipt-aware update is integrated,
# reject targets containing a harness before creating backups or writing files.
if ($Profile -eq 'Core') {
    $existingCore = @(@('.agents/skills', '.agents/mcp_config.json', '.cursor/rules', '.cursor/mcp.json',
        '.codex/config.toml', '.kilo/kilo.jsonc', '.qoder/skills', '.qoder/rules', '.qoder/settings.json',
        '.qwen/rules', '.qwen/settings.json', '.doc/harnes', '.doc/web', '.doc/skil_data/mirror', '.dsh') | Where-Object {
        Test-Path -LiteralPath (Join-Path $Target $_)
    })
    if ($existingCore.Count -gt 0) {
        throw ('Core legacy transfer cannot safely update an existing harness; no files changed. ' +
            'Use a clean target until receipt-aware update is available. Existing paths: ' + ($existingCore -join ', '))
    }

    # Validate policy as data using the installed trusted reader before any
    # Target write. Never import or execute a policy reader from Source.
    $readerDir = Join-Path $PSScriptRoot '../../harness-core/scripts'
    $readerFile = Join-Path $readerDir 'canon_paths.py'
    $preflightPython = Get-Command python3 -ErrorAction SilentlyContinue
    if (-not $preflightPython) { $preflightPython = Get-Command python -ErrorAction SilentlyContinue }
    if (-not $preflightPython -or -not (Test-Path -LiteralPath $readerFile -PathType Leaf)) {
        throw 'Core source policy preflight requires Python and the installed trusted policy reader; no files changed.'
    }
    $probe = 'import sys; sys.dont_write_bytecode=True; sys.path.insert(0,sys.argv[1]); from pathlib import Path; from canon_paths import load_preliminary_policies; load_preliminary_policies(Path(sys.argv[2]))'
    $policyOutput = (& $preflightPython.Source -c $probe $readerDir $Source 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) {
        throw "Core source policy preflight failed; no Target files changed. $policyOutput"
    }
}

if (-not $ProjectName) {
    $ProjectName = Split-Path $Target -Leaf
}

Write-Host "Source: $Source" -ForegroundColor DarkCyan
Write-Host "Target: $Target" -ForegroundColor DarkCyan
Write-Host "Profile: $Profile | ProjectName: $ProjectName" -ForegroundColor DarkCyan

if (-not (Test-Path (Join-Path $Source '.cursor\mcp.json'))) {
    throw "Не похоже на корень образца (нет .cursor/mcp.json): $Source"
}
if (-not (Test-Path (Join-Path $Source '.doc\rebase_project.md'))) {
    throw "Нет .doc/rebase_project.md в источнике: $Source"
}
Assert-CodePrismTransferSafe -SourceRoot $Source -TargetRoot $Target

$kitScanDirs = @(
    '.cursor', '.codex', '.agents', '.kilo', '.qoder', '.qwen', '.serena', '.dsh',
    '.doc\web', '.doc\harnes', '.doc\qa', '.doc\codeception',
    '.tools\scripts', '.tools\mcp-servers', '.tools\docker-dev\php-apache',
    '.tools\php85-scan', '.tools\codeception\scripts', '.tools\codeception\tests\_envs'
)
$kitRootFiles = @('AGENTS.md', 'mcp.index.md', 'kilo.json', '.codeprism.toml', '.cbmignore', 'DSH-RULES.md', '.doc/harnes/state/canon-paths.yaml',
    '.tools/docker-dev/compose.yaml', '.tools/codeception/codeception.yml',
    '.tools/codeception/composer.json', '.tools/codeception/composer.lock', '.tools/codeception/README.md')
$portableSupportDocs = @('auditskil777.md')
$archSource = Join-Path $Source '.doc/architecture'
if (Test-Path $archSource) {
    foreach ($file in @(Get-ChildItem -LiteralPath $archSource -File)) {
        if ($file.Name -like 'deepseek-harness-*' -or $file.BaseName -in @('local-embeddings', 'local-dev-resources', 'sourcegraph-local')) {
            if ($file.Extension -in @('.md', '.json')) { $portableSupportDocs += "architecture/$($file.Name)" }
        }
    }
}
$kitRootFiles += @($portableSupportDocs | ForEach-Object { ".doc/$_" })

$kitSkipDirs = @('node_modules', 'vendor', 'artifacts', 'memories', 'cache', '.state', 'skil_data', '.data',
    'venv', '.venv', '.venv-linux', '.venv-win', '__pycache__', 'imd', 'logs', 'output', '_output',
    'screen', '.pytest_cache', 'tmp-runs', 'runs', 'work', 'registry.snapshots', 'out', 'state',
    'plans', 'worktrees', 'repos-mirror', 'backups', 'upstream', 'team-memory')
$kitSkipFiles = @('mcp.env', '.env', 'config.env', 'out_copytrust.json', 'dump.sql', 'composer.lock',
    '.bearer_token', 'agent-manager.json', 'kilo-permissions.fragment.jsonc', 'package-lock.json',
    'registry.json', 'quarantine.json', 'run.log', 'ADAPTERS.local.md', 'actions.local.json',
    'prices.local.json', '*.local.md', '*.local.json', '*.local.yaml', '*.local.yml', '*.log', '*.fail.png', '*.fail.html', '*.token',
    'scheduled_tasks.json', 'project.local.yml', '*.bak', '*.bak-*')

Write-Step "Этап 0: исследование Target"
$preflightSkipped = $false
$beforeManifest = @{}
$sourceManifest = @{}
$overwrittenPreview = @()
$previewTargetOnly = @()
$previewAdded = @()
$backupTargetAll = @()
$conflictStamp = (Get-Date).ToString('yyyyMMdd-HHmmss-fff') + '-' + ([guid]::NewGuid().ToString('N').Substring(0,8))
$targetExists = Test-Path $Target
$targetKitDirs = @('.cursor', '.codex', '.agents', '.kilo', '.qoder', '.qwen', '.dsh', '.serena', '.doc') |
    Where-Object { Test-Path (Join-Path $Target $_) }
if (-not $targetExists) {
    $preflightSkipped = $true
    Write-Host "    Target не существует: перезаписи не будет" -ForegroundColor DarkGray
} elseif (@($targetKitDirs).Count -eq 0 -and @($kitRootFiles | Where-Object { Test-Path (Join-Path $Target $_) }).Count -eq 0) {
    $preflightSkipped = $true
    Write-Host "    В Target нет каталогов kit: перезаписи не будет" -ForegroundColor DarkGray
} elseif ($SkipPreflight) {
    Write-Warn2 "сверка пропущена (-SkipPreflight); точное число перезаписей неизвестно"
    if (-not $SkipBackup) {
        Write-Warn2 "для бэкапа строится отдельный список файлов Target"
        $dangerManifest = Get-KitManifest -Root $Target -Dirs $kitScanDirs -RootFiles $kitRootFiles -SkipDirs $kitSkipDirs -SkipFiles $kitSkipFiles
        $backupTargetAll = @($dangerManifest.Keys | ForEach-Object { $dangerManifest[$_].Path })
        $overwrittenPreview = @($backupTargetAll)
    }
    if (-not $Yes -and -not $UpdateMode) {
        $answer = Read-Host "Target уже содержит kit. Продолжить? [y/N]"
        if ($answer -notmatch '^[yY]') { Write-Host "Отменено пользователем." -ForegroundColor Yellow; exit 1 }
    }
} else {
    $sourceManifest = Get-KitManifest -Root $Source -Dirs $kitScanDirs -RootFiles $kitRootFiles -SkipDirs $kitSkipDirs -SkipFiles $kitSkipFiles
    if (-not $sourceManifest.ContainsKey('mcp.index.md')) {
        $srcMcpIndex = Join-Path $Source '.doc\mcp.index.md'
        if (Test-Path $srcMcpIndex) {
            $sourceManifest['mcp.index.md'] = @{ Path = 'mcp.index.md'; Hash = (Get-FileHash -LiteralPath $srcMcpIndex -Algorithm SHA256).Hash }
        }
    }
    $beforeManifest = Get-KitManifest -Root $Target -Dirs $kitScanDirs -RootFiles $kitRootFiles -SkipDirs $kitSkipDirs -SkipFiles $kitSkipFiles
    $preview = Compare-KitManifests -Before $beforeManifest -SourceMap $sourceManifest
    $overwrittenPreview = @($preview.overwritten)
    $previewTargetOnly = @($preview.target_only)
    $previewAdded = @($preview.added)
    $backupTargetAll = @($beforeManifest.Keys | ForEach-Object { $beforeManifest[$_].Path })
    Write-Host ("    перезапишется: {0}, добавится: {1}, сохранится вне kit: {2}" -f $preview.overwritten.Count, $preview.added.Count, $preview.target_only.Count)
    if ($CleanMode) {
        Write-Warn2 ("clean: будет удалено файлов вне kit: {0}, перезаписано: {1}" -f $preview.target_only.Count, $preview.overwritten.Count)
    } elseif ($UpdateMode) {
        Write-Ok ("update: kit-файлы будут обновлены, локальные дополнения сохранены")
    } elseif ($preview.overwritten.Count -gt 0) {
        Write-Host "    Файлы под перезапись (первые 30):" -ForegroundColor Yellow
        $preview.overwritten | Select-Object -First 30 | ForEach-Object { Write-Host "      - $_" -ForegroundColor Yellow }
        if (-not $Yes) {
            $answer = Read-Host "Перезаписать $($preview.overwritten.Count) файл(ов)? [y/N]"
            if ($answer -notmatch '^[yY]') { Write-Host "Отменено пользователем." -ForegroundColor Yellow; exit 1 }
        } else {
            Write-Ok "подтверждено флагом -Yes"
        }
    } else {
        Write-Ok "перезаписывать нечего, только добавление"
    }
    if ($preview.target_only.Count -gt 0 -and -not $CleanMode) {
        Write-Host "    Сохранятся вне kit (первые 10):" -ForegroundColor DarkGray
        $preview.target_only | Select-Object -First 10 | ForEach-Object { Write-Host "      - $_" -ForegroundColor DarkGray }
    }
}

if ($MigrateMode -and (Test-Path (Join-Path $Target '.doc\.rebase-kit.json'))) {
    Write-Warn2 "в Target уже есть маркер kit; для повторного обновления используйте -Mode update"
}
if ($CleanMode -and -not $Yes) {
    $answer = Read-Host "Очистить kit-компоненты Target и установить только kit? Бэкап будет сохранен. [y/N]"
    if ($answer -notmatch '^[yY]') { Write-Host "Отменено пользователем." -ForegroundColor Yellow; exit 1 }
}
if ($UpdateMode) {
    $marker = Join-Path $Target '.doc\.rebase-kit.json'
    if (-not (Test-Path $marker)) {
        Write-Warn2 "нет .doc/.rebase-kit.json: проект не помечен как kit, обновление продолжится"
    } else {
        Write-Ok "update: найден маркер kit, разбор конфликтов отключен"
    }
}

Write-Step "Создание целевого каталога"
New-Item -ItemType Directory -Path $Target -Force | Out-Null
Write-Ok $Target

if (-not $SkipBackup) {
    Write-Step "Бэкап перезаписываемых файлов"
    # Back up the actual mutable domains, including local-only files and docs/state.
    $backupMap = Get-KitManifest -Root $Target -Dirs $kitScanDirs -RootFiles $kitRootFiles -SkipDirs @('node_modules', 'vendor', '__pycache__', '.git', 'cache', 'memories', '.rebase-backup')
    $backupPaths = @($backupMap.Keys | ForEach-Object { $backupMap[$_].Path })
    $conflictBackup = Backup-TargetOverwrites -TargetRoot $Target -Paths @($backupPaths) -Stamp $conflictStamp
    $backupCount = @($conflictBackup.files).Count
    $overwrittenPaths = @($overwrittenPreview)
    $overwrittenRecords = if ($preflightSkipped) {
        @()
    } else {
        @($conflictBackup.files | Where-Object { $overwrittenPaths -contains $_.path })
    }
    New-Item -ItemType Directory -Path (Join-Path $Target '.doc') -Force | Out-Null
    $conflictReport = [ordered]@{
        schema = 1
        mode = $Mode
        timestamp = $conflictStamp
        backup_scope = 'all-mutable-domains'
        backup_dir = if ($backupCount -gt 0) { ".doc/.rebase-backup/$conflictStamp" } else { '' }
        backup_files = @($conflictBackup.files)
        overwritten = @($overwrittenRecords)
        target_only = @($previewTargetOnly)
        added = @($previewAdded)
        counts = [ordered]@{
            overwritten = @($overwrittenRecords).Count
            backup_files = $backupCount
            target_only = @($previewTargetOnly).Count
            added = @($previewAdded).Count
        }
    }
    $conflictPath = Join-Path $Target '.doc\.rebase-conflicts.json'
    if (Test-Path $conflictPath) {
        try {
            $previous = [System.IO.File]::ReadAllText($conflictPath, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
            if ($previous.timestamp) {
                $archive = Join-Path $Target (".doc\.rebase-conflicts." + $previous.timestamp + ".json")
                if (-not (Test-Path $archive)) { Copy-Item $conflictPath $archive -Force }
            }
        } catch {
            Write-Warn2 "не удалось сохранить предыдущий .rebase-conflicts.json"
        }
    }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText(
        $conflictPath,
        ($conflictReport | ConvertTo-Json -Depth 6),
        $utf8
    )
    if ($backupCount -gt 0) {
        Write-Ok ("бэкап {0} файлов → {1}" -f $backupCount, $conflictReport.backup_dir)
    } else {
        Write-Ok "перезаписываемых файлов нет, бэкап пуст"
    }
} else {
    Write-Warn2 "бэкап перезаписываемых файлов отключен (-SkipBackup)"
}

if ($CleanMode) {
    $sourcegraphDir = Join-Path $Target 'sourcegraph-local'
    if (Test-Path $sourcegraphDir) {
        $sourcegraphBackup = Join-Path $Target ".doc\.rebase-backup\$conflictStamp\sourcegraph-local"
        New-Item -ItemType Directory -Path (Split-Path $sourcegraphBackup -Parent) -Force | Out-Null
        Move-Item -LiteralPath $sourcegraphDir -Destination $sourcegraphBackup -Force
        Write-Ok "clean: sourcegraph-local перемещен в бэкап"
    }
    if (-not $IncludeKilo) {
        $kiloDir = Join-Path $Target '.kilo'
        if (Test-Path $kiloDir) {
            Remove-Item -LiteralPath $kiloDir -Recurse -Force
            Write-Ok "clean: удален .kilo"
        }
    }
}

if (-not $SkipSiblingConfig) {
    $sibling = Join-Path (Split-Path $Target -Parent) '.config'
    if (-not (Test-Path $sibling)) {
        New-Item -ItemType Directory -Path $sibling -Force | Out-Null
        $readme = Join-Path $sibling 'README.txt'
        @"
Sibling config for Docker PHP mount (../../../.config from .tools/docker-dev).
Put here: prepend.php, .env, .secrets.env for the NEW project.
Do not copy production secrets from Copytrust blindly.
"@ | Set-Content -Path $readme -Encoding UTF8
        Write-Ok "created sibling $sibling"
    } else {
        Write-Ok "sibling .config already exists: $sibling"
    }
}

if ($InitGit -and -not $SkipGitInit) {
    $gitDir = Join-Path $Target '.git'
    if (-not (Test-Path $gitDir)) {
        Write-Step "git init"
        Push-Location $Target
        try {
            git init | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "git init failed with exit code $LASTEXITCODE" }
            Write-Ok 'git init'
        } finally {
            Pop-Location
        }
    }
}

if ($ManageGitExclude -and -not $SkipExclude) {
    Write-Step "git exclude"
    if (Test-Path (Join-Path $Target '.git')) {
        Write-GitExclude -RepoRoot $Target -IncludeDocs:$IncludeDocs
    } else {
        Write-Warn2 'нет .git - exclude пропущен (используйте -InitGit или инициализируйте git)'
    }
}

Write-Step "AGENTS.md"
if ((Test-Path (Join-Path $Source 'AGENTS.md')) -and (-not (Test-Path (Join-Path $Target 'AGENTS.md')))) {
    Copy-Item (Join-Path $Source 'AGENTS.md') (Join-Path $Target 'AGENTS.md') -Force
    Write-Ok 'AGENTS.md'
}

New-Item -ItemType Directory -Path (Join-Path $Target '.doc') -Force | Out-Null
[IO.File]::WriteAllText((Join-Path $Target '.doc/.rebase-kit.json'), (@{status='pending';profile=$Profile;mode=$Mode;started=(Get-Date).ToString('o')} | ConvertTo-Json), [Text.UTF8Encoding]::new($false))

Write-Step "Копирование .cursor / .codex"
# Бэкап MCP Target до перезаписи (для merge sourcegraph + preserve boost)
$mcpBackupDir = Join-Path $Target '.doc\.rebase-mcp-backup'
$cursorMcpBak = Join-Path $mcpBackupDir 'cursor.mcp.json'
$codexMcpBak = Join-Path $mcpBackupDir 'codex.mcp.json'
$codexTomlBak = Join-Path $mcpBackupDir 'codex.config.toml'
$qoderSettingsBak = Join-Path $mcpBackupDir 'qoder.settings.json'
$qwenSettingsBak = Join-Path $mcpBackupDir 'qwen.settings.json'
if (-not $SkipMcpMerge) {
    New-Item -ItemType Directory -Path $mcpBackupDir -Force | Out-Null
    foreach ($oldBackup in @($cursorMcpBak, $codexMcpBak, $codexTomlBak, $qoderSettingsBak, $qwenSettingsBak)) {
        if (Test-Path $oldBackup) { Remove-Item -LiteralPath $oldBackup -Force }
    }
    $srcCursorMcp = Join-Path $Target '.cursor\mcp.json'
    $srcCodexMcp = Join-Path $Target '.codex\mcp.json'
    $srcCodexToml = Join-Path $Target '.codex\config.toml'
    if (Test-Path $srcCursorMcp) {
        Copy-Item $srcCursorMcp $cursorMcpBak -Force
        Write-Ok "backup Target .cursor/mcp.json → .doc/.rebase-mcp-backup/"
    }
    if (Test-Path $srcCodexMcp) {
        Copy-Item $srcCodexMcp $codexMcpBak -Force
        Write-Ok "backup Target .codex/mcp.json"
    }
    if (Test-Path $srcCodexToml) {
        Copy-Item $srcCodexToml $codexTomlBak -Force
        Write-Ok "backup Target .codex/config.toml"
    }
    $srcQoderSettings = Join-Path $Target '.qoder\settings.json'
    if (Test-Path $srcQoderSettings) {
        Copy-Item $srcQoderSettings $qoderSettingsBak -Force
        Write-Ok "backup Target .qoder/settings.json"
    }
    $srcQwenSettings = Join-Path $Target '.qwen\settings.json'
    if (Test-Path $srcQwenSettings) {
        Copy-Item $srcQwenSettings $qwenSettingsBak -Force
        Write-Ok "backup Target .qwen/settings.json"
    }
}

$xd = @('node_modules', 'vendor', 'artifacts', 'memories', 'cache', '.state', 'skil_data', '.data', 'venv', '__pycache__')
$xf = $kitSkipFiles + @('package-lock.json', 'composer.lock')
foreach ($root in @('.cursor', '.codex', '.agents', '.qoder', '.qwen')) {
    $rootExcludes = @($xf)
    $rootDirs = @($xd)
    if ($root -ne '.cursor') { $rootExcludes += @('mcp.json', 'mcp_config.json') }
    if ($root -eq '.agents') { $rootExcludes += @('skills.json') }
    if ($root -eq '.codex') { $rootExcludes += @('config.toml') }
    if ($root -in @('.qoder', '.qwen')) {
        $rootExcludes += @('settings.json')
        # Generated views must be built from the target canon, not copied from
        # the source profile. Existing target views remain untouched for sync
        # preflight to detect and report conflicts.
        $rootDirs += @('rules', 'skills')
    }
    Invoke-Robo -From (Join-Path $Source $root) -To (Join-Path $Target $root) -ExcludeDirs $rootDirs -ExcludeFiles $rootExcludes -Mirror:$EffectiveMirror -FollowLinks
    if ($root -eq '.cursor') {
        Disable-McpServers -McpJsonPath (Join-Path $Target '.cursor\mcp.json') -ServerNames @('codeprism')
    } else {
        Protect-CodePrismViews -Root $Target
    }
}

# MCP servers live in the local tooling tree, not inside agent kits. Sources
# are copied here; node_modules comes with -CopyRuntimeDeps.
Write-Step "Копирование .tools/mcp-servers"
Invoke-Robo -From (Join-Path $Source '.tools\mcp-servers') -To (Join-Path $Target '.tools\mcp-servers') -ExcludeDirs @('node_modules') -Mirror:$EffectiveMirror

# MCP-конфиги ссылаются на обёртки .tools/scripts (node-mcp, run-with-mcp-env,
# mysql-mcp-proxy). Без них phpstan, php-deps и mysql на Target не стартуют.
Write-Step "Копирование .tools/scripts"
Invoke-Robo -From (Join-Path $Source '.tools\scripts') -To (Join-Path $Target '.tools\scripts') -Mirror:$EffectiveMirror

# MCP index configs live in the project root, outside kit dirs. A project may
# already have its own file; never overwrite it.
foreach ($cfg in @('.codeprism.toml', '.cbmignore')) {
    $srcCfg = Join-Path $Source $cfg
    $dstCfg = Join-Path $Target $cfg
    if ((Test-Path $srcCfg) -and -not (Test-Path $dstCfg)) {
        Copy-Item $srcCfg $dstCfg -Force
        Write-Ok "copied $cfg"
    }
}

if ($CopyRuntimeDeps) {
    Write-Step "Runtime deps: php-toolchain node_modules + tools/vendor (+ codeception)"
    $nmSrc = Join-Path $Source '.tools\mcp-servers\php-toolchain\node_modules'
    $nmDst = Join-Path $Target '.tools\mcp-servers\php-toolchain\node_modules'
    if (Test-Path $nmSrc) {
        Invoke-Robo -From $nmSrc -To $nmDst -Mirror:$EffectiveMirror
    } else {
        Write-Warn2 "нет .tools/mcp-servers/php-toolchain/node_modules - потом npm install или -RunSetup"
    }
    New-Item -ItemType Directory -Path (Join-Path $Target '.tools\mcp-servers\php-toolchain') -Force | Out-Null
    foreach ($lock in @('package-lock.json', 'package.json')) {
        $lf = Join-Path $Source ".tools\mcp-servers\php-toolchain\$lock"
        if (Test-Path $lf) {
            Copy-Item $lf (Join-Path $Target ".tools\mcp-servers\php-toolchain\$lock") -Force
        }
    }
    foreach ($kit in @('.cursor', '.codex')) {
        $vendSrc = Join-Path $Source "$kit\tools\vendor"
        $vendDst = Join-Path $Target "$kit\tools\vendor"
        if (Test-Path $vendSrc) {
            Invoke-Robo -From $vendSrc -To $vendDst -Mirror:$EffectiveMirror
        } else {
            Write-Warn2 "нет $kit/tools/vendor - phpstan/phpda через setup.ps1 / composer"
        }
        foreach ($lock in @('composer.lock', 'composer.json', 'composer.phar')) {
            $lf = Join-Path $Source "$kit\tools\$lock"
            if (Test-Path $lf) {
                $td = Join-Path $Target "$kit\tools"
                New-Item -ItemType Directory -Path $td -Force | Out-Null
                Copy-Item $lf (Join-Path $td $lock) -Force
            }
        }
    }
    if ($Profile -eq 'Full') {
        $cvSrc = Join-Path $Source '.tools\codeception\vendor'
        $cvDst = Join-Path $Target '.tools\codeception\vendor'
        if (Test-Path $cvSrc) {
            Invoke-Robo -From $cvSrc -To $cvDst -Mirror:$EffectiveMirror
            $cl = Join-Path $Source '.tools\codeception\composer.lock'
            if (Test-Path $cl) {
                Copy-Item $cl (Join-Path $Target '.tools\codeception\composer.lock') -Force
            }
        } else {
            Write-Warn2 'нет .tools/codeception/vendor - composer install в .tools/codeception'
        }
    }
} else {
    Write-Warn2 'SkipRuntimeDeps: phpstan-mcp / codeception потребуют setup.ps1 / composer / npm'
}

Write-Step "Копирование .serena"
Invoke-Robo -From (Join-Path $Source '.serena') -To (Join-Path $Target '.serena') `
    -ExcludeDirs @('memories', 'cache') -ExcludeFiles @('project.local.yml') -Mirror:$EffectiveMirror
Set-SerenaProjectName -YmlPath (Join-Path $Target '.serena\project.yml') -Name $ProjectName

Write-Step "Копирование .doc (стандарты + инфра)"
$docTarget = Join-Path $Target '.doc'
New-Item -ItemType Directory -Path $docTarget -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $docTarget 'harnes') -Force | Out-Null
Write-Ok 'scaffold .doc/harnes (canon docs)'

$docFiles = @(
    'rebase_project.md', 'mcp.index.md',
    'harnes/doc_rules.md', 'harnes/index.md', 'harnes/tests.md', 'harnes/testaudit.md',
    'harnes/jsondoc.md', 'harnes/readmy.md', 'harnes/readmy_doc.md',
    'harnes/skill-format.md', 'harnes/component-docs.md', 'harnes/component-install.md',
    'harnes/state/13-agent-migration.md', 'harnes/state/14-project-migration.md'
)
if ($Profile -eq 'Core') { $docFiles = @('mcp.index.md', 'harnes/doc_rules.md') } else { $docFiles += $portableSupportDocs }
foreach ($f in $docFiles) {
    $src = Join-Path $Source ".doc\$f"
    if (Test-Path $src) {
        $dst = Join-Path $docTarget $f
        New-Item -ItemType Directory -Path (Split-Path -Parent $dst) -Force | Out-Null
        Copy-Item $src $dst -Force
        Write-Ok ".doc/$f"
    }
}
# удобная копия шпаргалки CBM/SG в корень Target
$mcpIndex = Join-Path $Source '.doc\mcp.index.md'
if (Test-Path $mcpIndex) {
    Copy-Item $mcpIndex (Join-Path $Target 'mcp.index.md') -Force
    Write-Ok 'mcp.index.md (корень Target)'
}

$docDirs = if ($Profile -eq 'Full') { @('harnes', 'web') } else { @('web') }
$docXd = @('node_modules', '.venv', '.venv-linux', '.venv-win', '__pycache__', 'cache', 'imd', 'vendor', 'logs', 'output', '_output', 'screen', '.pytest_cache', 'tmp-runs')
$docXf = @('.env', 'config.env', 'out_copytrust.json', 'dump.sql', 'composer.lock', 'mcp.env', '.bearer_token', '*.local.md', '*.local.json', '*.local.yaml', '*.local.yml')
foreach ($d in $docDirs) {
    $extraXd = @()
    $extraXf = @()
    $xfForDir = $docXf
    if ($d -eq 'web') {
        # панель и сервис: код переносим, состояние и локальный адаптер - нет
        $xfForDir = @('ADAPTERS.local.md', 'actions.local.json', 'prices.local.json', '*.local.md', '*.local.yaml', '*.local.yml', '*.log', '.env')
        $extraXd = @('state')
        $extraXf = @()
    }
    Invoke-Robo -From (Join-Path $Source ".doc\$d") -To (Join-Path $docTarget $d) `
        -ExcludeDirs ($docXd + $extraXd) -ExcludeFiles ($xfForDir + $extraXf) -Mirror:$EffectiveMirror
}

Write-Step "Копирование DSH kit (.dsh)"
$dshKit = Join-Path $Source '.agents\skills\harness-router\children\new-project\scripts\copy-dsh-kit.ps1'
if (Test-Path $dshKit) {
    & $dshKit -Source $Source -Target $Target -PreserveLocal:(-not $EffectiveMirror)
    if ($LASTEXITCODE -ne 0) { throw "DSH kit copy failed (exit $LASTEXITCODE)" }
    & $dshKit -Source $Source -Target $Target -Check -PreserveLocal:(-not $EffectiveMirror)
    if ($LASTEXITCODE -ne 0) { throw "DSH kit check failed (exit $LASTEXITCODE)" }
} else {
    throw "DSH kit helper not found: $dshKit"
}

if (-not $SkipTools) {
    Write-Step "Копирование .tools (без секретов, vendor и данных)"
    $toolsSrc = Join-Path $Source '.tools'
    if (-not (Test-Path $toolsSrc)) {
        Write-Warn2 'source .tools не найден'
    } else {
        $toolsDst = Join-Path $Target '.tools'
        New-Item -ItemType Directory -Path $toolsDst -Force | Out-Null
        $toolFiles = @('docker-dev/compose.yaml')
        $toolDirs = @('docker-dev/php-apache', 'php85-scan')
        if ($Profile -eq 'Full') {
            $toolFiles += @(
                'codeception/codeception.yml',
                'codeception/composer.json',
                'codeception/composer.lock',
                'codeception/README.md'
            )
            $toolDirs += @('codeception/tests/_envs', 'codeception/scripts')
        }
        foreach ($rel in $toolFiles) {
            $from = Join-Path $toolsSrc $rel
            if (-not (Test-Path $from)) { continue }
            $to = Join-Path $toolsDst $rel
            New-Item -ItemType Directory -Path (Split-Path $to -Parent) -Force | Out-Null
            Copy-Item $from $to -Force
            Write-Ok "tools/$rel"
        }
        foreach ($rel in $toolDirs) {
            $from = Join-Path $toolsSrc $rel
            if (-not (Test-Path $from)) { continue }
            Get-ChildItem -Path $from -Recurse -File -Force -ErrorAction SilentlyContinue | Where-Object {
                $_.FullName -notmatch '[\\/]__pycache__[\\/]|[\\/]vendor[\\/]|[\\/]_output[\\/]|[\\/]dump\.sql$|[\\/]\.env$'
            } | ForEach-Object {
                $srcFile = $_
                $relative = $srcFile.FullName.Substring($toolsSrc.Length).TrimStart('\', '/')
                $destFile = Join-Path $toolsDst $relative
                $destDir = Split-Path $destFile -Parent
                if (-not (Test-Path $destDir)) {
                    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
                }
                Copy-Item $srcFile.FullName $destFile -Force
            }
            Write-Ok "tools/$rel"
        }
        Write-Ok 'tools subset copied'
    }
}

# Only distributable examples, never state, audit history, screenshots or cached graphs.
if ($Profile -eq 'Full') {
    $examplesRoot = Join-Path $Source '.doc/skil_data'
    if (Test-Path $examplesRoot) {
        Get-ChildItem -LiteralPath $examplesRoot -Recurse -File -Filter '*.example.*' | ForEach-Object {
            $relative = $_.FullName.Substring($examplesRoot.Length).TrimStart('\', '/')
            $exampleTarget = Join-Path (Join-Path $Target '.doc/skil_data') $relative
            if (-not (Test-Path $exampleTarget)) {
                New-Item -ItemType Directory -Path (Split-Path $exampleTarget -Parent) -Force | Out-Null
                Copy-Item -LiteralPath $_.FullName -Destination $exampleTarget
            }
        }
    }
}

# kaiten research (один файл, без runtime)
$kaitenSrc = Join-Path $Source '.doc\kaiten\doc.md'
if (Test-Path $kaitenSrc) {
    $kaitenDst = Join-Path $docTarget 'kaiten'
    New-Item -ItemType Directory -Path $kaitenDst -Force | Out-Null
    Copy-Item $kaitenSrc (Join-Path $kaitenDst 'doc.md') -Force
    Write-Ok '.doc/kaiten/doc.md'
}


# каркас
@(
    '.doc\architecture\_map',
    '.doc\tasks',
    '.doc\tasks\_map',
    '.doc\qa\reports',
    '.doc\skil_data\yadisk-screenshot\imd'
) | ForEach-Object {
    New-Item -ItemType Directory -Path (Join-Path $Target $_) -Force | Out-Null
}
Write-Ok 'scaffold architecture/_map, tasks/_map, qa/reports, mcpyandex/imd'

# Минимальный architecture/index.md (каркас, не контент Copytrust)
$archIndex = Join-Path $Target '.doc\architecture\index.md'
# A project may keep architecture docs under a differently named directory
# (`archiecture`, `docs/arch`, ...). Do not plant an empty stub in that case.
$existingArch = Get-ChildItem (Join-Path $Target '.doc') -Directory -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -ne 'architecture' -and
        $_.Name -like '*archit*' -and
        (Get-ChildItem $_.FullName -Filter '*.md' -File -ErrorAction SilentlyContinue | Select-Object -First 1)
    } | Select-Object -First 1
if (-not (Test-Path $archIndex) -and -not $existingArch) {
    $stub = @"
# Architecture index

<!-- meta
type: index
status: draft
updated: $((Get-Date).ToString('yyyy-MM-dd'))
related: [../doc_rules.md]
tags: [architecture, index]
-->

---

## Суть

Оглавление архитектуры проекта ``$ProjectName``. Заполнить через skill project-doc / map-project.ps1.

---

## Разделы

(пусто - создать документы по Index Gate)

---

## Связи

- [doc_rules.md](../doc_rules.md)

---

## Известные проблемы и ограничения

(нет)

---

## История изменений

- $((Get-Date).ToString('yyyy-MM-dd')): каркас после export-rebase-project.ps1
"@
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($archIndex, $stub, $utf8)
    Write-Ok 'created .doc/architecture/index.md stub'
}

# yadisk-fetch переносится вместе с .agents/skills/yadisk-screenshot/scripts.

if ($IncludeKilo) {
    Write-Step "Kilo (опционально)"
    Invoke-Robo -From (Join-Path $Source '.kilo') -To (Join-Path $Target '.kilo') -ExcludeDirs @('node_modules', 'plans', 'worktrees') -ExcludeFiles @('agent-manager.json', 'kilo-permissions.fragment.jsonc', 'mcp.env') -Mirror:$EffectiveMirror
    # permissions fragment содержит живые alwaysAllow-маппинги исходника -
    # на Target регенерируется sync-agent-views.sh, не копируется.
    # .kilocode удален как legacy-каталог старого Kilo Code, копировать нечего.
    $kj = Join-Path $Source 'kilo.json'
    if (Test-Path $kj) { Copy-Item $kj (Join-Path $Target 'kilo.json') -Force }
    Scrub-McpJson -Path (Join-Path $Target '.kilo\kilo.jsonc')
    Protect-CodePrismViews -Root $Target
}

if (-not $SkipMcpMerge) {
    foreach ($pair in @(@($codexTomlBak, '.codex/config.toml'), @($qoderSettingsBak, '.qoder/settings.json'), @($qwenSettingsBak, '.qwen/settings.json'))) {
        if (Test-Path $pair[0]) { Copy-Item -LiteralPath $pair[0] -Destination (Join-Path $Target $pair[1]) -Force }
    }
}

Write-Step "Секреты: mcp.env из example (пустые/шаблонные)"
foreach ($kit in @('.cursor', '.codex')) {
    $ex = Join-Path $Target "$kit\mcp.env.example"
    $mcpEnvPath = Join-Path $Target "$kit\mcp.env"
    if ((Test-Path $ex) -and -not (Test-Path $mcpEnvPath)) {
        Copy-Item $ex $mcpEnvPath -Force
        Write-Ok "created $kit/mcp.env from example"
    }
}
# Graphiti: имя группы графа равно имени нового проекта. Иначе проект либо
# останется на плейсхолдере примера, либо запишет память в чужой граф.
$graphitiSlug = (Split-Path $Target -Leaf)
if ($graphitiSlug) { $graphitiSlug = $graphitiSlug.ToLower() -replace '[^a-z0-9_.-]', '-' }
foreach ($kit in @('.cursor', '.codex')) {
    $mcpEnvPath = Join-Path $Target "$kit\mcp.env"
    if (-not (Test-Path $mcpEnvPath)) { continue }
    $envRaw = [System.IO.File]::ReadAllText($mcpEnvPath, [System.Text.Encoding]::UTF8)
    if ($envRaw -notmatch '(?m)^#?\s*GRAPHITI_GROUP_ID=') { continue }
    $envNew = [regex]::Replace($envRaw, '(?m)^#?\s*GRAPHITI_GROUP_ID=.*$', "GRAPHITI_GROUP_ID=$graphitiSlug")
    $utf8Env = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($mcpEnvPath, $envNew, $utf8Env)
    Write-Ok "$kit/mcp.env: GRAPHITI_GROUP_ID=$graphitiSlug"
}
# .kilo/mcp.env на образце содержит живой токен, поэтому он не копируется:
# берём уже очищенный пример из .cursor, чтобы Kilo-среда стартовала без секретов.
$kiloEnv = Join-Path $Target '.kilo\mcp.env'
$cursorEnv = Join-Path $Target '.cursor\mcp.env'
if ((Test-Path (Join-Path $Target '.kilo')) -and -not (Test-Path $kiloEnv) -and (Test-Path $cursorEnv)) {
    Copy-Item $cursorEnv $kiloEnv -Force
    Write-Ok 'created .kilo/mcp.env from .cursor/mcp.env (без секретов)'
}

if ($Profile -eq 'Full') {
    $jex = Join-Path $Target '.doc\skil_data\jira\config.example.env'
    $jenv = Join-Path $Target '.doc\skil_data\jira\config.env'
    if ((Test-Path $jex) -and -not (Test-Path $jenv)) {
        Copy-Item $jex $jenv -Force
        Write-Ok 'created .doc/skil_data/jira/config.env from example (заполните JIRA_*)'
    }
}

Write-Step "Scrub mcp.json (токены / chrome paths)"
Scrub-McpJson -Path (Join-Path $Target '.cursor\mcp.json')
Scrub-McpJson -Path (Join-Path $Target '.codex\mcp.json')
# antigravity_mcp_config.json инлайнит SG-токен из канона - чистим тем же scrub
Scrub-McpJson -Path (Join-Path $Target '.doc\synh_harnes\antigravity_mcp_config.json')
Scrub-McpJson -Path (Join-Path $Target '.qoder\settings.json')
Scrub-McpJson -Path (Join-Path $Target '.qwen\settings.json')

if (Test-IsWindowsTargetPath $Target) {
    Write-Step "Windows host: patch Cursor MCP launchers (bash+WSL path break)"
    Patch-CursorMcpForWindowsHost -McpJsonPath (Join-Path $Target '.cursor\mcp.json')
}

if (-not $SkipMcpMerge) {
    Write-Step "Merge MCP: kit (sourcegraph/graphify/…) + Target-only (boost/…)"
    if (Test-Path $cursorMcpBak) {
        Merge-McpJsonPreserveTargetOnly -NewPath (Join-Path $Target '.cursor\mcp.json') -BackupPath $cursorMcpBak
    }
    if (Test-Path $codexMcpBak) {
        Merge-McpJsonPreserveTargetOnly -NewPath (Join-Path $Target '.codex\mcp.json') -BackupPath $codexMcpBak
    }
    if (Test-Path $codexTomlBak) {
        Merge-CodexTomlPreserveTargetOnly -NewPath (Join-Path $Target '.codex\config.toml') -BackupPath $codexTomlBak
    }
    if (Test-Path $qoderSettingsBak) {
        Merge-AgentSettingsPreserveTargetOnly -NewPath (Join-Path $Target '.qoder\settings.json') -BackupPath $qoderSettingsBak
    }
    if (Test-Path $qwenSettingsBak) {
        Merge-AgentSettingsPreserveTargetOnly -NewPath (Join-Path $Target '.qwen\settings.json') -BackupPath $qwenSettingsBak -Qwen
    }
} else {
    Write-Warn2 'SkipMcpMerge: Target-only MCP (boost/…) не восстановлены'
}

# Merge may restore CodePrism from the previous Target when the kit lacks it.
Disable-McpServers -McpJsonPath (Join-Path $Target '.cursor\mcp.json') -ServerNames @('codeprism')
Protect-CodePrismViews -Root $Target
Write-Warn2 'CodePrism отключён в каноне Target: синхронизируйте представления; до включения проверьте принадлежность отдельного сервера этому проекту'

Write-Step "Перезапись абсолютных путей Source -> Target"
Rewrite-SourcePaths -Root $Target -SourceRoot $Source -TargetRoot $Target `
    -SourceLeaf (Split-Path $Source -Leaf) -TargetLeaf $ProjectName

$targetSerenaPort = Resolve-SerenaPort -Root $Target -SourceRoot $Source -Requested $SerenaPort

# Copytrust-only skills не нужны на чужом проекте (даже в Full)
foreach ($kit in @('.cursor', '.codex', '.agents', '.qoder', '.qwen')) {
    foreach ($s in @('login-as-user')) {
        $p = Join-Path $Target "$kit\skills\$s"
        if (Test-Path $p) {
            Remove-Item $p -Recurse -Force
            Write-Ok "removed Copytrust-only skill $kit/skills/$s"
        }
    }
}

if ($Profile -eq 'Full') { Normalize-KitDocLinks -Root $Target -SourceRoot $Source }

if ($Profile -eq 'Core') {
    Write-Step "Профиль Core: вырезать task/jira skills"
    Remove-CoreOnlyNoise -Root $Target -PreserveInstructions:$targetHadAgents
    Set-CorePanelProfile -Root $Target
    Initialize-CoreRuntimeDocs -Root $Target -SourceRoot $Source
    Normalize-CoreMcpLinks -Root $Target -SourceRoot $Source
    $toml = Join-Path $Target '.codex\config.toml'
    if (Test-Path $toml) {
        $t = [System.IO.File]::ReadAllText($toml, [System.Text.Encoding]::UTF8)
        $t2 = [regex]::Replace($t, '(?ms)(\[mcp_servers\.jira-task\][^\[]*?)^\s*enabled\s*=\s*true', '${1}enabled = false', 'Multiline')
        $t2 = [regex]::Replace($t2, '(?ms)(\[mcp_servers\.bitbucket-task\][^\[]*?)^\s*enabled\s*=\s*true', '${1}enabled = false', 'Multiline')
        if ($t2 -ne $t) {
            $utf8 = New-Object System.Text.UTF8Encoding($false)
            [System.IO.File]::WriteAllText($toml, $t2, $utf8)
            Write-Ok 'Core: disabled jira/bitbucket in config.toml'
        }
    }
    # Core: jira/bitbucket в Cursor mcp.json тоже
    Disable-McpServers -McpJsonPath (Join-Path $Target '.cursor\mcp.json') -ServerNames @('jira-task', 'bitbucket-task')
    Disable-McpServers -McpJsonPath (Join-Path $Target '.codex\mcp.json') -ServerNames @('jira-task', 'bitbucket-task')
    Disable-McpServers -McpJsonPath (Join-Path $Target '.qoder\settings.json') -ServerNames @('jira-task', 'bitbucket-task')
    Disable-QwenMcpServers -McpJsonPath (Join-Path $Target '.qwen\settings.json') -ServerNames @('jira-task', 'bitbucket-task')
}

Write-Step "Реестр компонентов: убрать удалённые скилы и runtime-пути"
Prune-ComponentRegistry -Root $Target

if ($RunSetup) {
    Write-Step "setup.ps1 (Cursor + Codex)"
    foreach ($kit in @('.cursor', '.codex')) {
        $setup = Join-Path $Target "$kit\setup.ps1"
        if (Test-Path $setup) {
            Push-Location $Target
            try {
                & powershell -NoProfile -ExecutionPolicy Bypass -File $setup
                Write-Ok "ran $kit/setup.ps1"
            } catch {
                Write-Warn2 "$kit/setup.ps1: $($_.Exception.Message)"
            } finally {
                Pop-Location
            }
        }
    }

    $install = Join-Path $Target '.doc\web\install.ps1'
    if (Test-Path $install) {
        Write-Step "service check (copytrust-tools)"
        $ps = Get-Command pwsh -ErrorAction SilentlyContinue
        if (-not $ps) { $ps = Get-Command powershell -ErrorAction SilentlyContinue }
        if ($ps) {
            Push-Location $Target
            try {
                & $ps.Source -NoProfile -ExecutionPolicy Bypass -File $install -Check
                if ($LASTEXITCODE -eq 0) {
                    & $ps.Source -NoProfile -ExecutionPolicy Bypass -File $install -Project $Target
                } else {
                    Write-Warn2 "service: prerequisites missing, install skipped"
                }
            } catch {
                Write-Warn2 "service: $($_.Exception.Message)"
            } finally {
                Pop-Location
            }
        } else {
            Write-Warn2 "service: pwsh/powershell not found"
        }
    }
}

Write-Step 'Синхронизация сред из канона Target'
$nativeCodexConfig = Join-Path $Target '.codex/config.toml'
if (-not (Test-Path -LiteralPath $nativeCodexConfig)) {
    [IO.File]::WriteAllText($nativeCodexConfig, "approval_policy = `"on-request`"`n", [Text.UTF8Encoding]::new($false))
}
$syncScript = Join-Path $Target '.agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh'
$bash = Get-Command bash -ErrorAction SilentlyContinue
if (-not $bash -or -not (Test-Path -LiteralPath $syncScript)) { throw 'Target synchronization requires bash and sync-agent-views.sh' }
$oldNoPrompt = $env:HARNESS_SYNC_NO_PROMPT
$env:HARNESS_SYNC_NO_PROMPT = '1'
Push-Location $Target
try {
    & $bash.Source $syncScript --local-only
    if ($LASTEXITCODE -ne 0) { throw "Target synchronization failed (exit $LASTEXITCODE)" }
} finally {
    Pop-Location
    $env:HARNESS_SYNC_NO_PROMPT = $oldNoPrompt
}

if ($Profile -eq 'Core') {
    # Generate a new graph from the trusted source tool, never copy the
    # source project's mirror data. Existing mirror state is blocked above.
    $mirrorSource = Join-Path $Source '.agents/skills/harness-router/children/mirror/scripts/harness_mirror.py'
    $python = Get-Command python3 -ErrorAction SilentlyContinue
    if (-not $python) { $python = Get-Command python -ErrorAction SilentlyContinue }
    if (-not $python -or -not (Test-Path -LiteralPath $mirrorSource -PathType Leaf)) {
        throw 'Core mirror generation requires Python and the source mirror script'
    }
    & $python.Source $mirrorSource --root $Target rebuild
    if ($LASTEXITCODE -ne 0) { throw "Core mirror generation failed (exit $LASTEXITCODE)" }
}

Write-Step "Отчёт переноса"
$kitMarker = [ordered]@{
    schema = 1
    status = 'pending'
    mode = $Mode
    source = $Source
    profile = $Profile
    project_name = $ProjectName
    installed_at = (Get-Date).ToString('s')
    kit_manifest = '.doc/skil_data/harness-core/kit-manifest.json'
    conflicts = '.doc/.rebase-conflicts.json'
}
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText(
    (Join-Path $Target '.doc\.rebase-kit.json'),
    ($kitMarker | ConvertTo-Json -Depth 4),
    $utf8
)

$python = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python -ErrorAction SilentlyContinue }
if (-not $python) { throw 'Python is required to generate the Codex MCP configuration' }
$codexGenerator = Join-Path $Target '.agents\skills\harness-router\children\environment-sync\scripts\generate-codex-mcp.py'
$codexConfig = Join-Path $Target '.codex\config.toml'
if (-not (Test-Path -LiteralPath $codexGenerator -PathType Leaf)) { throw 'Codex MCP generator is missing in Target' }
Write-Step 'Сборка Codex MCP из канона Target'
& $python.Source $codexGenerator --root $Target --config $codexConfig
if ($LASTEXITCODE -ne 0) { throw 'Codex MCP generation failed' }
& $python.Source $codexGenerator --root $Target --config $codexConfig --check
if ($LASTEXITCODE -ne 0) { throw 'Codex MCP verification failed' }
if ($python) {
    $scanner = Join-Path $Source '.agents\skills\harness-router\children\add-skill\scripts\scan_local_skills.py'
    if (Test-Path $scanner) {
        $baseline = Join-Path $Target '.doc\skil_data\harness-core\kit-manifest.json'
        & $python.Source $scanner --root $Source --baseline $baseline --write-baseline | Out-Null
        Write-Ok "манифест пакета записан"
    }
}

Write-TransferReport -Root $Target -Source $Source -ProfileName $Profile -Before $beforeManifest -SourceMap $sourceManifest -Mirrored:$EffectiveMirror -PreflightSkipped:$preflightSkipped

if ($MigrateMode -and -not $SkipReview) {
    $reviewScript = Join-Path $Target '.agents\skills\harness-router\children\migration-review\scripts\review_migration.py'
    if (Test-Path $reviewScript) {
        if ($python) {
            Write-Step "Анализ локальных компонентов после переноса"
            $reviewArgs = @($reviewScript, '--root', $Target)
            if (-not $Yes) { $reviewArgs += '--interactive' } else { $reviewArgs += '--report-only' }
            & $python.Source @reviewArgs
        } else {
            Write-Warn2 "python не найден, анализ локальных компонентов пропущен"
        }
    }
}

Write-NextSteps -Root $Target -ProfileName $Profile -Name $ProjectName -SourceName (Split-Path $Source -Leaf) -SerenaPort $targetSerenaPort

Write-Step "Аудит must-файлов"
$must = @(
    'AGENTS.md',
    '.codeprism.toml',
    '.cursor\mcp.json', '.cursor\setup.ps1', '.cursor\rules\text-style.mdc',
    '.agents\skills\task-router\children\gototask\scripts\gototask.ps1',
    '.agents\skills\task-router\children\gototask\config.json',
    '.agents\skills\task-router\children\task-diff\scripts\task-diff.ps1',
    '.agents\skills\ponytail\SKILL.md',
    '.agents\skills\ponytail\skill.json',
    '.agents\rules\doc-rules.md',
    '.agents\mcp_config.json',
    '.qoder\rules\doc-rules.md',
    '.qoder\settings.json',
    '.qoder\skills\ponytail\SKILL.md',
    '.qwen\rules\doc-rules.md',
    '.qwen\settings.json',
    '.qwen\skills\rule-code-editing\SKILL.md',
    '.tools\scripts\php-docker.cmd', '.tools\scripts\node-mcp.sh',
    '.tools\scripts\node-mcp.cmd',
    '.tools\mcp-servers\php-toolchain\server.js',
    '.codex\config.toml', '.codex\rules-index.md', '.codex\go-task.ps1', '.codex\task-diff.ps1',
    '.agents\skills\prepare-plan\assets\plan.template.md', '.agents\skills.json',
    '.tools\scripts\run-with-mcp-env.sh', '.codex\lib\kit-root.ps1',
    '.doc\harnes\doc_rules.md', '.doc\harnes\tests.md', '.doc\harnes\testaudit.md', '.doc\harnes\jsondoc.md', '.doc\harnes\readmy.md', '.doc\harnes\readmy_doc.md', '.doc\harnes\skill-format.md', '.doc\harnes\component-docs.md', '.doc\harnes\component-install.md', '.doc\rebase_project.md',
    '.agents\skills\harness-router\children\project-setup\scripts\onboard-project.py',
    '.agents\skills\harness-router\children\project-setup\SKILL.md',
    '.agents\skills\harness-router\children\new-project\SKILL.md',
    '.agents\skills\harness-router\children\new-project\scripts\rebase_project.ps1',
    '.agents\skills\harness-router\children\new-project\scripts\rebase_project_gi.ps1',
    '.doc\mcp.index.md',
    '.agents\skills\documentation-router\children\task-doc\scripts\schemas',
    '.agents\skills\jdocmunch\scripts\jdocmunch-mcp.sh', '.agents\skills\codegraph\scripts\codegraph-mcp.sh',
    '.agents\skills\codeprism\scripts\codeprism-mcp.sh',
    '.agents\skills\documentation-router\children\project-doc\scripts\map-project.ps1', '.agents\skills\documentation-router\children\project-doc\scripts\build-tasks-index.ps1',
    '.agents\skills\harness-router\children\new-project\scripts\export-rebase-project.ps1',
    '.tools\scripts\node-mcp.cmd', '.agents\skills\codebase-memory-mcp\scripts\codebase-memory-mcp-launch.cmd',
    '.doc\harnes\index.md',
    '.doc\harnes\state\13-agent-migration.md',
    '.doc\harnes\state\14-project-migration.md',
    '.dsh\skills\dsh-router\SKILL.md',
    '.dsh\skills\dsh-router\README.md',
    '.dsh\skills\dsh-router\skill.json',
    '.dsh\kit.manifest.json',
    '.dsh\adapters\prepare-plan-digest.md',
    '.dsh\scripts\run-ps1.sh',
    '.dsh\scripts\smoke.sh',
    '.dsh\models.overlay.json',
    '.agents\skills\yadisk-screenshot\scripts\yadisk-fetch.ps1',
    '.doc\web\README.md',
    '.doc\web\router.php',
    '.doc\web\docker-compose.yml',
    '.doc\web\start.sh',
    '.doc\web\stop.sh',
    '.doc\web\app\lib.php',
    '.doc\web\app\harness.php',
    '.doc\web\app\jobs.php',
    '.doc\web\app\pricing.php',
    '.doc\web\app\providers.php',
    '.doc\web\config\prices.json',
    '.doc\web\config\prices.local.example.json',
    '.doc\web\public\index.php',
    '.doc\web\public\assets\app.js',
    '.doc\web\public\assets\style.css',
    '.doc\web\config\actions.json',
    '.doc\web\config\actions.schema.json',
    '.doc\web\config\service.json',
    '.doc\web\bin\build-actions.py',
    '.doc\web\bin\job-runner.php',
    '.doc\web\bin\selfcheck.py',
    '.doc\web\install.sh',
    '.doc\web\install.ps1',
    '.doc\web\verify.sh',
    '.doc\web\ADAPTERS.example.md',
    '.doc\web\Dockerfile.tools',
    '.doc\web\compose.tools.yml',
    '.agents\skills\task-router\children\analytics\README.md',
    '.agents\skills\task-router\children\analytics\scripts\task-analytics.py',
    '.agents\skills\task-router\children\analytics\scripts\lib\db.py',
    '.agents\skills\task-router\children\analytics\scripts\lib\facts.py',
    '.agents\skills\task-router\children\analytics\scripts\lib\attribute.py',
    '.agents\skills\task-router\children\analytics\scripts\lib\metrics.py',
    '.agents\skills\task-router\children\analytics\scripts\lib\compliance.py',
    '.agents\skills\task-router\children\analytics\scripts\lib\slices.py',
    '.agents\skills\task-router\children\analytics\scripts\lib\corpus.py',
    '.agents\skills\task-router\children\analytics\scripts\lib\render.py',
    '.agents\skills\task-router\children\analytics\assets\config\thresholds.json',
    '.agents\skills\task-router\children\analytics\assets\config\required-calls.json',
    '.agents\skills\task-router\children\analytics\assets\config\slices.json',
    '.agents\skills\task-router\children\analytics\assets\schemas\analysis.schema.json',
    '.doc\architecture\index.md',
    '.serena\project.yml',
    'EXPORT_NEXT_STEPS.md'
)
if ($Profile -eq 'Core') {
    $must = @('AGENTS.md', '.cursor/mcp.json', '.codex/config.toml', '.codex/rules-index.md',
        '.agents/skills/ponytail/SKILL.md', '.agents/skills/serena/SKILL.md', '.agents/skills/code/SKILL.md',
        '.agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh',
        '.agents/skills/harness-router/children/mirror/SKILL.md',
        '.agents/skills/harness-router/children/mirror/scripts/harness_mirror.py', '.doc/web/router.php',
        '.agents/skills.json', '.doc/harnes/doc_rules.md', '.doc/harnes/state/canon-paths.yaml', '.serena/project.yml', 'EXPORT_NEXT_STEPS.md')
}
if ($Profile -eq 'Full') {
    $must += @('.agents\skills\task-router\children\jira\scripts\server.php')
    if (-not $SkipTools) {
        $must += @('.tools\codeception\codeception.yml', '.tools\codeception\composer.json')
    }
}
if ($CopyRuntimeDeps) {
    $must += @(
        '.tools\mcp-servers\php-toolchain\node_modules\@modelcontextprotocol\sdk\package.json',
        '.cursor\tools\vendor\bin\phpstan',
        '.codex\tools\vendor\bin\phpstan'
    )
    if ($Profile -eq 'Full') {
        $must += @('.tools\codeception\vendor\autoload.php')
    }
}
$missing = @()
foreach ($rel in $must) {
    if ($Profile -eq 'Core' -and $rel -match 'gototask|task-diff|task-doc|task-code-review|prepare-task-test|browser-verify|test-task|task-intake|login-as-user|jira-report|go-task|analytics') { continue }
    $full = Join-Path $Target $rel
    if (-not (Test-Path $full)) {
        $missing += $rel
        Write-Host "    MISSING: $rel" -ForegroundColor Red
    }
}
# запрещённое
$forbidden = @()
if (Test-Path (Join-Path $Target '.doc\tasks\index.md')) { $forbidden += '.doc/tasks/index.md (чужой индекс?)' }
$taskDirs = @(Get-ChildItem (Join-Path $Target '.doc\tasks') -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^\d+$' })
if ($taskDirs.Count -gt 0) { $forbidden += ('.doc/tasks/{N}/ count=' + $taskDirs.Count) }
if (Test-Path (Join-Path $Target '.agents\skills\login-as-user')) { $forbidden += 'login-as-user still present' }
if (Test-Path (Join-Path $Target '.cursor\tools\codeprism-ai\venv')) { $forbidden += '.cursor/tools/codeprism-ai/venv (venv не копируется, создаётся на Target)' }
if (Test-Path (Join-Path $Target '.doc\qa\tmp-runs')) { $forbidden += '.doc/qa/tmp-runs (артефакты прогонов)' }
if (Test-Path (Join-Path $Target '.doc\skil_data\task-doc\runs')) { $forbidden += '.doc/skil_data/task-doc/runs (прогоны образца)' }
# stale source paths: конфиг должен ссылаться на Target, а не на образец
$sourceForms = @($Source, ($Source -replace '\\', '/'), ($Source -replace '/', '\')) | Where-Object { $_ }
foreach ($rel in @('.cursor\mcp.json', '.codex\config.toml', '.codex\mcp.json', '.kilo\kilo.jsonc', '.agents\mcp.json', 'AGENTS.md', 'mcp.index.md')) {
    $p = Join-Path $Target $rel
    if (-not (Test-Path $p)) { continue }
    $txt = [System.IO.File]::ReadAllText($p, [System.Text.Encoding]::UTF8)
    foreach ($form in $sourceForms) {
        if ($txt.Contains($form)) { $forbidden += "$rel содержит путь Source"; break }
    }
}
$mustFail = $false
if ($missing.Count -eq 0 -and $forbidden.Count -eq 0) {
    Write-Ok 'must-check PASS'
} else {
    $mustFail = $true
    if ($missing.Count -gt 0) { Write-Warn2 ("must missing: " + ($missing -join ', ')) }
    if ($forbidden.Count -gt 0) { Write-Warn2 ("forbidden present: " + ($forbidden -join ', ')) }
}

# exclude smoke
if (Test-Path (Join-Path $Target '.git')) {
    Push-Location $Target
    try {
        $ig = git check-ignore -v .cursor/mcp.json 2>$null
        if ($ig) { Write-Ok "git check-ignore: $ig" } else { Write-Warn2 'git check-ignore не сработал для .cursor/mcp.json' }
    } finally { Pop-Location }
}

Complete-Step
Write-StepSummary
Write-Host ""
Write-Host "Откройте в Cursor: $Target" -ForegroundColor Green
Write-Host "Дальше: $Target\EXPORT_NEXT_STEPS.md" -ForegroundColor Green
if ($Profile -eq 'Full') { Write-Host "Канон: $Target\.doc\rebase_project.md" -ForegroundColor Green }
Write-Host ""

$kitMarker['status'] = if ($mustFail) { 'failed' } else { 'passed' }
[IO.File]::WriteAllText((Join-Path $Target '.doc/.rebase-kit.json'), ($kitMarker | ConvertTo-Json -Depth 4), [Text.UTF8Encoding]::new($false))

if ($mustFail) {
    Write-Host ""
    Write-Host "EXPORT_REBASE_DONE_WITH_WARNINGS target=$Target profile=$Profile project=$ProjectName" -ForegroundColor Yellow
    exit 2
}

# маркер для агента Cursor
Write-Host "EXPORT_REBASE_DONE target=$Target profile=$Profile project=$ProjectName"

<#
.SYNOPSIS
    Собирает .doc/tasks/index.md — индекс задач: номер, название, затронутые файлы.
    Два раздела: Задачи → файлы, Файлы → задачи (для поиска при doc-verify).

.DESCRIPTION
    Источники на задачу:
      - task.md  → title (# Issue #N: ...)
      - diff.files.md → блок ## All files (если есть)
      - doc.md   → backtick-пути к коду (доп. к diff, без дублей)
      - наличие doc.md / plan.md

    Запуск из корня репо:
      powershell .agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1

.PARAMETER OutPath
    Куда писать (по умолчанию .doc/tasks/index.md)

.PARAMETER AlsoTsv
    Дополнительно писать .doc/tasks/_map/file-to-tasks.tsv (для скриптов)

.EXAMPLE
    powershell .agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1
    powershell .agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1 -AlsoTsv
#>

param(
    [string]$OutPath = '',
    [switch]$AlsoTsv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_lib.ps1')

$projectRoot = (Get-Location).Path
$tasksRoot = Join-Path $projectRoot '.doc/tasks'
if (-not $OutPath) {
    $OutPath = Join-Path $tasksRoot 'index.md'
}

function Get-TaskTitle([string]$TaskMdPath, [string]$Id) {
    $text = Read-TextFile -Path $TaskMdPath
    if (-not $text) { return "задача #$Id" }
    $m = [regex]::Match($text, '(?m)^#\s+Issue\s+#?\d+:\s*(.+)$')
    if ($m.Success) {
        $t = $m.Groups[1].Value.Trim()
        # обрезать длинные хвосты
        if ($t.Length -gt 120) { $t = $t.Substring(0, 117) + '...' }
        return $t
    }
    $m2 = [regex]::Match($text, '(?m)^#\s+(.+)$')
    if ($m2.Success) { return $m2.Groups[1].Value.Trim() }
    return "задача #$Id"
}

function Get-FilesFromDiffFiles([string]$DiffFilesPath) {
    $text = Read-TextFile -Path $DiffFilesPath
    if (-not $text) { return @() }
    $files = New-Object System.Collections.Generic.List[string]
    $inAll = $false
    foreach ($line in ($text -split "`r?`n")) {
        if ($line -match '^##\s+All files\s*$') { $inAll = $true; continue }
        if ($inAll -and $line -match '^##\s+') { break }
        if (-not $inAll) { continue }
        $p = $line.Trim()
        if (-not $p) { continue }
        if ($p -match '^[`*\-\|]') { continue }
        if ($p -match '^[a-zA-Z0-9_./\\-]+\.[a-zA-Z0-9]+$') {
            $files.Add((Normalize-RelativePath $p))
        }
    }
    return @($files | Sort-Object -Unique)
}

function Get-FilesFromDocMd([string]$DocPath) {
    if (-not (Test-Path -LiteralPath $DocPath)) { return @() }
    return @(Get-DocCodeRefs -Path $DocPath | Where-Object {
        $_ -and $_ -notmatch '^\.doc/' -and $_ -notmatch '\.md$'
    })
}

$taskDirs = @(Get-ChildItem -Path $tasksRoot -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^\d+$' } |
    Sort-Object { [int]$_.Name })

$tasks = @()
$fileToTasks = @{}  # path -> list of @{id; title}

foreach ($dir in $taskDirs) {
    $id = $dir.Name
    $taskMd = Join-Path $dir.FullName 'task.md'
    $docMd = Join-Path $dir.FullName 'doc.md'
    $planMd = Join-Path $dir.FullName 'plan.md'
    $diffFiles = Join-Path $dir.FullName 'diff.files.md'

    $title = if (Test-Path -LiteralPath $taskMd) {
        Get-TaskTitle -TaskMdPath $taskMd -Id $id
    } else {
        "задача #$id (нет task.md)"
    }

    $files = New-Object System.Collections.Generic.HashSet[string]
    foreach ($f in @(Get-FilesFromDiffFiles -DiffFilesPath $diffFiles)) {
        [void]$files.Add($f)
    }
    # doc.md backticks — дополнение, если diff пуст или для полноты
    foreach ($f in @(Get-FilesFromDocMd -DocPath $docMd)) {
        [void]$files.Add($f)
    }

    $fileList = @($files | Sort-Object)
    $entry = [ordered]@{
        id       = $id
        title    = $title
        hasTask  = [bool](Test-Path -LiteralPath $taskMd)
        hasDoc   = [bool](Test-Path -LiteralPath $docMd)
        hasPlan  = [bool](Test-Path -LiteralPath $planMd)
        hasDiff  = [bool](Test-Path -LiteralPath $diffFiles)
        files    = $fileList
        fileCount = $fileList.Count
    }
    $tasks += [PSCustomObject]$entry

    foreach ($fp in $fileList) {
        if (-not $fileToTasks.ContainsKey($fp)) {
            $fileToTasks[$fp] = New-Object System.Collections.Generic.List[object]
        }
        $fileToTasks[$fp].Add([PSCustomObject]@{ id = $id; title = $title })
    }
}

$genDate = Get-Date -Format 'yyyy-MM-dd HH:mm'
$sb = New-Object System.Text.StringBuilder

[void]$sb.AppendLine('# Индекс задач CopyTrust')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('<!-- meta')
[void]$sb.AppendLine('type: index')
[void]$sb.AppendLine('status: actual')
[void]$sb.AppendLine("updated: $(Get-Date -Format 'yyyy-MM-dd')")
[void]$sb.AppendLine('tags: [tasks, index, files]')
[void]$sb.AppendLine('-->')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('---')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('## Суть')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('Реестр задач `.doc/tasks/{N}/`: номер, название, наличие `task.md`/`doc.md`,')
[void]$sb.AppendLine('затронутые файлы кода. Для поиска «какой task трогал этот файл» и')
[void]$sb.AppendLine('для **doc-verify V6** (`find-related-tasks.ps1`).')
[void]$sb.AppendLine('')
[void]$sb.AppendLine("> **Сгенерировано:** $genDate скриптом [``build-tasks-index.ps1``](../../.agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1). **Не править руками** — пересобери скриптом.")
[void]$sb.AppendLine('')
[void]$sb.AppendLine('Скрипт: [`.agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1`](../../.agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1)')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('```powershell')
[void]$sb.AppendLine('powershell -ExecutionPolicy Bypass -File .agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1 -AlsoTsv')
[void]$sb.AppendLine('```')
[void]$sb.AppendLine('')
[void]$sb.AppendLine("| Метрика | Значение |")
[void]$sb.AppendLine("|---|---|")
[void]$sb.AppendLine("| Задач в `.doc/tasks/` | $($tasks.Count) |")
[void]$sb.AppendLine("| С `doc.md` | $((@($tasks | Where-Object hasDoc)).Count) |")
[void]$sb.AppendLine("| С `diff.files.md` | $((@($tasks | Where-Object hasDiff)).Count) |")
[void]$sb.AppendLine("| Уникальных путей кода | $($fileToTasks.Count) |")
[void]$sb.AppendLine('')
[void]$sb.AppendLine('---')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('## 1. Задачи → файлы')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('| # | Название | Артефакты | Файлов |')
[void]$sb.AppendLine('|---|---|---|---|')

foreach ($t in $tasks) {
    $arts = @()
    if ($t.hasTask) { $arts += "[task](./$($t.id)/task.md)" }
    if ($t.hasDoc) { $arts += "[doc](./$($t.id)/doc.md)" }
    if ($t.hasPlan) { $arts += "[plan](./$($t.id)/plan.md)" }
    if ($t.hasDiff) { $arts += "[diff.files](./$($t.id)/diff.files.md)" }
    $artStr = if ($arts.Count) { $arts -join ' · ' } else { '—' }
    $titleEsc = ($t.title -replace '\|', '/')
    $taskCell = if ($t.hasTask) { "[#$($t.id)](./$($t.id)/task.md)" } else { "#$($t.id)" }
    [void]$sb.AppendLine("| $taskCell | $titleEsc | $artStr | $($t.fileCount) |")
}

[void]$sb.AppendLine('')
[void]$sb.AppendLine('### Детали по задачам (файлы)')
[void]$sb.AppendLine('')

foreach ($t in $tasks) {
    if ($t.fileCount -eq 0) { continue }
    [void]$sb.AppendLine("#### #$($t.id) — $($t.title)")
    [void]$sb.AppendLine('')
    if ($t.hasDoc) {
        [void]$sb.AppendLine("- Документация: [doc.md](./$($t.id)/doc.md)")
    }
    foreach ($f in $t.files) {
        [void]$sb.AppendLine("- ``$f``")
    }
    [void]$sb.AppendLine('')
}

[void]$sb.AppendLine('---')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('## 2. Файлы → задачи')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('Поиск: Ctrl+F по пути файла. Ссылки ведут на `task.md`, при его отсутствии на `doc.md`.')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('| Файл | Задачи |')
[void]$sb.AppendLine('|---|---|')

foreach ($fp in ($fileToTasks.Keys | Sort-Object)) {
    $seen = @{}
    $uniq = New-Object System.Collections.Generic.List[string]
    foreach ($x in ($fileToTasks[$fp] | Sort-Object { [int]$_.id })) {
        if ($seen.ContainsKey($x.id)) { continue }
        $seen[$x.id] = $true
        $id = $x.id
        $hasTask = Test-Path (Join-Path $tasksRoot "$id/task.md")
        $hasDoc = Test-Path (Join-Path $tasksRoot "$id/doc.md")
        if ($hasTask -and $hasDoc) {
            $uniq.Add("[#$id](./$id/task.md) ([doc](./$id/doc.md))")
        } elseif ($hasTask) {
            $uniq.Add("[#$id](./$id/task.md)")
        } elseif ($hasDoc) {
            $uniq.Add("[#$id](./$id/doc.md) (doc)")
        } else {
            $uniq.Add("#$id")
        }
    }
    [void]$sb.AppendLine("| ``$fp`` | $($uniq -join ', ') |")
}

[void]$sb.AppendLine('')
[void]$sb.AppendLine('---')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('## Связи')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('- [architecture/index.md](../architecture/index.md) — оглавление архитектуры')
[void]$sb.AppendLine('- [doc_rules.md](../harnes/doc_rules.md) — правила документации')
[void]$sb.AppendLine('- [`.codex/skills/documentation-router/children/doc-verify/SKILL.md`](../../.codex/skills/documentation-router/children/doc-verify/SKILL.md) — сверка docs, V6 задачи')
[void]$sb.AppendLine('- [`.agents/skills/documentation-router/children/doc-verify/scripts/find-related-tasks.ps1`](../../.agents/skills/documentation-router/children/doc-verify/scripts/find-related-tasks.ps1) — поиск задач для arch-doc')
[void]$sb.AppendLine('- [`.agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1`](../../.agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1) — этот индекс')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('#tasks #index #files')
[void]$sb.AppendLine('')

Write-Utf8File -Path $OutPath -Content $sb.ToString()
Write-Host "OK: $OutPath ($($tasks.Count) tasks, $($fileToTasks.Count) files)" -ForegroundColor Green

if ($AlsoTsv) {
    $mapDir = Join-Path $tasksRoot '_map'
    if (-not (Test-Path $mapDir)) {
        New-Item -ItemType Directory -Path $mapDir -Force | Out-Null
    }
    $tsvPath = Join-Path $mapDir 'file-to-tasks.tsv'
    $tsv = New-Object System.Collections.Generic.List[string]
    $tsv.Add("path`ttask_ids`ttitles")
    foreach ($fp in ($fileToTasks.Keys | Sort-Object)) {
        $ids = @($fileToTasks[$fp] | ForEach-Object { $_.id } | Sort-Object { [int]$_ } -Unique)
        $titles = @($fileToTasks[$fp] | Sort-Object { [int]$_.id } | ForEach-Object {
            "$($_.id):$($_.title -replace '`t', ' ')"
        } | Sort-Object -Unique)
        $tsv.Add("$fp`t$($ids -join ',')`t$($titles -join ' | ')")
    }
    Write-Utf8File -Path $tsvPath -Content (($tsv.ToArray()) -join "`r`n")
    Write-Host "OK: $tsvPath" -ForegroundColor Green
}

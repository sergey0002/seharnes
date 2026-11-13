<#
.SYNOPSIS
    Ищет задачи (.doc/tasks/{N}/), связанные с architecture-документом.
    Для шага V6 скила doc-verify.

.PARAMETER Doc
    Имя документа: orders.md или путь .doc/architecture/orders.md

.PARAMETER Limit
    Сколько задач вывести (по score), по умолчанию 8.

.PARAMETER Json
    Вывести JSON вместо текста.

.EXAMPLE
    powershell .agents/skills/documentation-router/children/doc-verify/scripts/find-related-tasks.ps1 -Doc orders.md
    powershell .agents/skills/documentation-router/children/doc-verify/scripts/find-related-tasks.ps1 -Doc payments.md -Limit 12
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Doc,
    [int]$Limit = 8,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\..\project-doc\scripts\_lib.ps1')

$projectRoot = (Get-Location).Path
$docName = Split-Path -Leaf (Normalize-RelativePath ($Doc -replace '^(\.doc/)?architecture/', ''))
$docStem = [IO.Path]::GetFileNameWithoutExtension($docName)
$archJsonPath = Join-Path $projectRoot ".doc/architecture/$docStem.json"
$archMdPath = Join-Path $projectRoot ".doc/architecture/$docStem.md"

if (-not (Test-Path -LiteralPath $archJsonPath) -and -not (Test-Path -LiteralPath $archMdPath)) {
    Write-Host "Документ не найден: .doc/architecture/$docStem" -ForegroundColor Red
    exit 1
}

# --- JSONdoc Fast Path (через jsondoc.py related legacy-v1) ---
$cliPath = Join-Path $projectRoot ".agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py"
$python = Get-Command python3 -ErrorAction SilentlyContinue

if ($python -and (Test-Path -LiteralPath $cliPath) -and (Test-Path -LiteralPath $archJsonPath)) {
    try {
        $jsonOut = & python3 $cliPath --root $projectRoot related --arch $docStem --profile legacy-v1 --limit $Limit 2>$null
        if ($LASTEXITCODE -eq 0 -and $jsonOut) {
            $parsed = $jsonOut | ConvertFrom-Json
            if ($parsed.status -eq 'ok' -and $parsed.data) {
                if ($Json) {
                    $payload = @($parsed.data | ForEach-Object {
                        [ordered]@{
                            id       = [string]$_.id
                            score    = [int]$_.score
                            reasons  = @($_.reasons)
                            hasDoc   = [bool]$_.hasDoc
                            hasTask  = [bool]$_.hasTask
                            taskPath = [string]$_.taskPath
                            docPath  = if ($_.docPath) { [string]$_.docPath } else { $null }
                            alreadyInArch = [bool]$_.alreadyInArch
                        }
                    })
                    $payload | ConvertTo-Json -Depth 5
                    exit 0
                }

                Write-Host ""
                Write-Host "  Связанные задачи для $docStem (top $Limit / candidates $($parsed.counts.matched)) [JSONdoc]:" -ForegroundColor Cyan
                Write-Host ""
                if ($parsed.data.Count -eq 0) {
                    Write-Host "  (не найдено)" -ForegroundColor Yellow
                    Write-Host ""
                    exit 0
                }
                foreach ($e in $parsed.data) {
                    $id = $e.id
                    $flags = @()
                    if ($e.hasDoc) { $flags += 'doc.md' } else { $flags += 'no-doc' }
                    if ($e.alreadyInArch) { $flags += 'in-arch' }
                    $why = ($e.reasons -join '; ')
                    Write-Host ("  #{0,-5} score={1,-3} [{2}]  {3}" -f $id, $e.score, ($flags -join ','), $why) -ForegroundColor White
                    Write-Host "         .doc/tasks/$id/task.md$(if ($e.hasDoc) { " | doc.md" } else { '' })" -ForegroundColor DarkGray
                }
                Write-Host ""
                Write-Host "  В doc-verify V6: ## Связанные задачи (score≥20) + П-N при баге; см. .doc/tasks/index.md" -ForegroundColor DarkGray
                Write-Host ""
                exit 0
            }
        }
    } catch {
        # Fall back to legacy file scan
    }
}

$archPath = if (Test-Path -LiteralPath $archMdPath) { $archMdPath } else { $archJsonPath }
$tasksRoot = Join-Path $projectRoot '.doc/tasks'

$codeRefs = @(Get-DocCodeRefs -Path $archPath)
$codeSet = @{}
foreach ($r in $codeRefs) {
    $codeSet[(Normalize-RelativePath $r).ToLowerInvariant()] = $true
    $bn = (Split-Path -Leaf $r).ToLowerInvariant()
    if ($bn) { $codeSet["basename:$bn"] = $true }
}

# Уже проставленные task id в самом arch
$archText = Read-TextFile -Path $archPath
$already = @{}
foreach ($m in [regex]::Matches($archText, '\.\./tasks/(\d+)/')) {
    $already[$m.Groups[1].Value] = $true
}

$scores = @{}  # id -> @{ score; reasons; hasDoc; hasTask }

function Add-Score([string]$Id, [int]$Points, [string]$Reason) {
    if (-not $scores.ContainsKey($Id)) {
        $scores[$Id] = @{
            score   = 0
            reasons = New-Object System.Collections.Generic.List[string]
            hasDoc  = (Test-Path (Join-Path $tasksRoot "$Id/doc.md"))
            hasTask = (Test-Path (Join-Path $tasksRoot "$Id/task.md"))
        }
    }
    $scores[$Id].score += $Points
    if ($Reason -and -not $scores[$Id].reasons.Contains($Reason)) {
        $scores[$Id].reasons.Add($Reason)
    }
}

if (-not (Test-Path $tasksRoot)) {
    Write-Host "Нет папки .doc/tasks" -ForegroundColor Red
    exit 1
}

# Ускорение: индекс файл→задачи (.doc/tasks/_map/file-to-tasks.tsv)
$tsvPath = Join-Path $tasksRoot '_map/file-to-tasks.tsv'
if (Test-Path -LiteralPath $tsvPath) {
    $tsvHits = 0
    foreach ($line in (Get-Content $tsvPath -Encoding UTF8 | Select-Object -Skip 1)) {
        if (-not $line.Trim()) { continue }
        $parts = $line -split "`t", 3
        if ($parts.Count -lt 2) { continue }
        $p = (Normalize-RelativePath $parts[0]).ToLowerInvariant()
        $bn = (Split-Path -Leaf $p).ToLowerInvariant()
        $match = $codeSet.ContainsKey($p) -or ($bn -and $codeSet.ContainsKey("basename:$bn"))
        if (-not $match) { continue }
        $ids = @($parts[1] -split ',' | Where-Object { $_ -match '^\d+$' })
        foreach ($id in $ids) {
            Add-Score $id 40 "index-file→task ($($parts[0]))"
            $tsvHits++
        }
    }
    if ($tsvHits -gt 0) {
        Write-Host "  index TSV: +score для $tsvHits совпадений path↔task (см. tasks/index.md)" -ForegroundColor DarkGray
    }
} else {
    Write-Host "  (нет tasks/_map/file-to-tasks.tsv — запусти build-tasks-index.ps1 -AlsoTsv)" -ForegroundColor DarkYellow
}

$taskDirs = @(Get-ChildItem -Path $tasksRoot -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^\d+$' })

foreach ($dir in $taskDirs) {
    $id = $dir.Name
    $filesToScan = @(
        'doc.md', 'plan.md', 'diff.files.md', 'task.md'
    ) | ForEach-Object { Join-Path $dir.FullName $_ } |
        Where-Object { Test-Path -LiteralPath $_ }

    $hitArchLink = $false
    $hitStem = $false
    $pathHits = 0

    foreach ($f in $filesToScan) {
        $text = Read-TextFile -Path $f
        if (-not $text) { continue }
        $base = Split-Path -Leaf $f

        if ($text -match [regex]::Escape("architecture/$docName") -or
            $text -match [regex]::Escape("architecture/$docStem.md") -or
            $text -match "\]\(\./$docName" -or
            $text -match "\]\(\.\./\.\./architecture/$docName") {
            $hitArchLink = $true
        }

        # Упоминание имени файла как ссылки/якоря
        if ($text -match [regex]::Escape($docName) -or
            $text -match "$docStem\.md#") {
            $hitStem = $true
        }

        # Пересечение путей кода (только diff.files.md и doc.md — экономия)
        if ($base -in @('diff.files.md', 'doc.md') -and $codeSet.Count -gt 0) {
            foreach ($m in [regex]::Matches($text, '(?m)[`\s]([a-zA-Z0-9_./\\-]+\.(?:php|vue|js|ts|tpl|sql))')) {
                $p = (Normalize-RelativePath $m.Groups[1].Value).ToLowerInvariant()
                $bn = (Split-Path -Leaf $p).ToLowerInvariant()
                if ($codeSet.ContainsKey($p) -or $codeSet.ContainsKey("basename:$bn")) {
                    $pathHits++
                    if ($pathHits -ge 5) { break }
                }
            }
        }
    }

    if ($hitArchLink) { Add-Score $id 50 "link→architecture/$docName" }
    if ($hitStem -and -not $hitArchLink) { Add-Score $id 20 "mention $docName" }
    if ($pathHits -gt 0) { Add-Score $id ([Math]::Min(30, $pathHits * 6)) "code-overlap x$pathHits" }
    if ($already.ContainsKey($id)) { Add-Score $id 10 "already-in-arch" }
}

$ranked = @(
    $scores.GetEnumerator() |
        Sort-Object { -$_.Value.score }, { [int]$_.Name } |
        Select-Object -First $Limit
)

if ($Json) {
    $payload = @(
        $ranked | ForEach-Object {
            [ordered]@{
                id       = $_.Name
                score    = $_.Value.score
                reasons  = @($_.Value.reasons)
                hasDoc   = [bool]$_.Value.hasDoc
                hasTask  = [bool]$_.Value.hasTask
                taskPath = ".doc/tasks/$($_.Name)/task.md"
                docPath  = if ($_.Value.hasDoc) { ".doc/tasks/$($_.Name)/doc.md" } else { $null }
                alreadyInArch = [bool]$already.ContainsKey($_.Name)
            }
        }
    )
    $payload | ConvertTo-Json -Depth 5
    exit 0
}

Write-Host ""
Write-Host "  Связанные задачи для $docName (top $Limit / candidates $($scores.Count)):" -ForegroundColor Cyan
Write-Host "  code-refs in arch: $($codeRefs.Count) | already linked in arch: $($already.Count)" -ForegroundColor DarkGray
Write-Host ""

if ($ranked.Count -eq 0) {
    Write-Host "  (не найдено)" -ForegroundColor Yellow
    Write-Host ""
    exit 0
}

foreach ($e in $ranked) {
    $id = $e.Name
    $v = $e.Value
    $flags = @()
    if ($v.hasDoc) { $flags += 'doc.md' } else { $flags += 'no-doc' }
    if ($already.ContainsKey($id)) { $flags += 'in-arch' }
    $why = ($v.reasons -join '; ')
    Write-Host ("  #{0,-5} score={1,-3} [{2}]  {3}" -f $id, $v.score, ($flags -join ','), $why) -ForegroundColor White
    Write-Host "         .doc/tasks/$id/task.md$(if ($v.hasDoc) { " | doc.md" } else { '' })" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "  В doc-verify V6: ## Связанные задачи (score≥20) + П-N при баге; см. .doc/tasks/index.md" -ForegroundColor DarkGray
Write-Host ""

<#
.SYNOPSIS
    Очередь сверки architecture/*.md с кодом: статус, батч документов, init/reset.

.DESCRIPTION
    Реестр: .doc/architecture/_map/verify-registry.tsv
    По умолчанию порция = 1 документ (полная сверка с кодом).

    Запускай из корня проекта.
    Скинь вывод в чат и напиши: "продолжи сверку документации"

.PARAMETER Count
    Сколько документов выдать (по умолчанию 1).

.PARAMETER Skip
    Пропустить первые N pending (параллельные агенты).

.PARAMETER Status
    Только прогресс-бар, без выдачи батча.

.PARAMETER Init
    Пересобрать очередь по текущим architecture/*.md.
    Уже verified/skipped сохраняются, новые файлы = pending.
    Удалённые из папки - строка убирается.

.PARAMETER Reset
    Все документы снова pending (полная повторная сверка).

.PARAMETER ResetStale
    Пометить pending те docs, у которых код из backtick-ссылок
    менялся после meta.updated (логика как sync-docs).

.PARAMETER Section
    Выдать конкретный файл (имя или путь architecture/foo.md),
    даже если уже verified (для ручной пересверки).

.EXAMPLE
    powershell .agents/skills/documentation-router/children/doc-verify/scripts/get-verify-batch.ps1 -Init
    powershell .agents/skills/documentation-router/children/doc-verify/scripts/get-verify-batch.ps1 -Status
    powershell .agents/skills/documentation-router/children/doc-verify/scripts/get-verify-batch.ps1 -Count 1
    powershell .agents/skills/documentation-router/children/doc-verify/scripts/get-verify-batch.ps1 -Section payments.md
    powershell .agents/skills/documentation-router/children/doc-verify/scripts/get-verify-batch.ps1 -ResetStale
#>

param(
    [int]$Count = 1,
    [int]$Skip = 0,
    [switch]$Status,
    [switch]$Init,
    [switch]$Reset,
    [switch]$ResetStale,
    [string]$Section = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\..\project-doc\scripts\_lib.ps1')

function Get-VerifyRegistryPath {
    $projectRoot = (Get-Location).Path
    return (Join-Path $projectRoot '.doc\architecture\_map\verify-registry.tsv')
}

function Get-VerifySkipNames {
    # Навигация / приоритеты - не сверяем с кодом как бизнес-доки
    return @('index.md', '_priority.md')
}

function Read-VerifyRegistry([string]$Path) {
    $rows = @()
    if (-not (Test-Path $Path)) { return $rows }
    $lines = Get-Content $Path -ErrorAction SilentlyContinue
    if (-not $lines -or $lines.Count -lt 2) { return $rows }
    $header = $lines[0] -split "`t"
    foreach ($line in $lines | Select-Object -Skip 1) {
        if (-not $line.Trim()) { continue }
        $parts = $line -split "`t", $header.Count
        $obj = [ordered]@{}
        for ($i = 0; $i -lt $header.Count; $i++) {
            $obj[$header[$i]] = if ($i -lt $parts.Count) { $parts[$i] } else { '' }
        }
        $rows += [PSCustomObject]$obj
    }
    return $rows
}

function Write-VerifyRegistry([string]$Path, $Rows) {
    $header = "path`tstatus`tverified_at`tissues_found`tcode_refs`tnotes"
    $body = [System.Collections.Generic.List[string]]::new()
    foreach ($row in @($Rows | Sort-Object path)) {
        $p = [string]$row.path
        $s = if ($row.status) { [string]$row.status } else { 'pending' }
        $v = if ($row.verified_at) { [string]$row.verified_at } else { '' }
        $i = if ($null -ne $row.issues_found -and "$($row.issues_found)" -ne '') { [string]$row.issues_found } else { '' }
        $c = if ($null -ne $row.code_refs -and "$($row.code_refs)" -ne '') { [string]$row.code_refs } else { '' }
        $n = if ($row.notes) { [string]$row.notes } else { '' }
        $body.Add("$p`t$s`t$v`t$i`t$c`t$n")
    }
    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.Add($header)
    foreach ($l in $body) { $lines.Add($l) }
    Write-Utf8File -Path $Path -Content (($lines.ToArray()) -join "`r`n")
}

function Get-ArchDocRelativeName([System.IO.FileInfo]$File) {
    $projectRoot = (Get-Location).Path
    $archDir = Join-Path $projectRoot '.doc\architecture'
    $rel = $File.FullName.Substring($archDir.Length).TrimStart('\', '/')
    return Normalize-RelativePath $rel
}

function New-VerifyRow([string]$RelPath, [string]$Status = 'pending') {
    return [PSCustomObject]@{
        path         = $RelPath
        status       = $Status
        verified_at  = ''
        issues_found = ''
        code_refs    = ''
        notes        = ''
    }
}

function Sync-VerifyRegistry {
    param(
        [string]$RegistryPath,
        [switch]$ForceReset
    )

    $skipNames = Get-VerifySkipNames
    $docs = @(Get-ArchitectureDocs | Where-Object { $_.Name -notin $skipNames })
    $existing = @{}
    foreach ($r in @(Read-VerifyRegistry -Path $RegistryPath)) {
        $existing[$r.path] = $r
    }

    $rows = @()
    foreach ($doc in $docs) {
        $rel = Get-ArchDocRelativeName $doc
        $full = $doc.FullName
        $codeRefs = @(Get-DocCodeRefs -Path $full)
        $refsCount = $codeRefs.Count

        if ($ForceReset) {
            $row = New-VerifyRow -RelPath $rel -Status 'pending'
            $row.code_refs = [string]$refsCount
            $rows += $row
            continue
        }

        if ($existing.ContainsKey($rel)) {
            $old = $existing[$rel]
            $status = if ($old.status) { $old.status } else { 'pending' }
            $rows += [PSCustomObject]@{
                path         = $rel
                status       = $status
                verified_at  = if ($old.verified_at) { $old.verified_at } else { '' }
                issues_found = if ($null -ne $old.issues_found) { $old.issues_found } else { '' }
                code_refs    = [string]$refsCount
                notes        = if ($old.notes) { $old.notes } else { '' }
            }
        } else {
            $row = New-VerifyRow -RelPath $rel -Status 'pending'
            $row.code_refs = [string]$refsCount
            $rows += $row
        }
    }

    Write-VerifyRegistry -Path $RegistryPath -Rows $rows
    return $rows
}

function Test-DocStaleByGit {
    param(
        [Parameter(Mandatory)][string]$DocFullPath,
        [Parameter(Mandatory)][datetime]$UpdatedDate
    )
    if (-not (Test-GitAvailable)) { return $false }
    $refs = @(Get-DocCodeRefs -Path $DocFullPath)
    if ($refs.Count -eq 0) { return $false }
    $since = $UpdatedDate.ToString('yyyy-MM-dd')
    foreach ($ref in $refs) {
        $full = ConvertTo-FullPath -RelativePath $ref
        if (-not (Test-Path -LiteralPath $full)) { continue }
        $log = git log -1 --since="$since" --pretty=format:%H -- $ref 2>$null
        if ($log) { return $true }
    }
    return $false
}

$registryPath = Get-VerifyRegistryPath
$mapDir = Split-Path -Parent $registryPath
if (-not (Test-Path $mapDir)) {
    New-Item -ItemType Directory -Path $mapDir -Force | Out-Null
}

if ($Init -or $Reset -or -not (Test-Path $registryPath)) {
    $force = [bool]$Reset
    $null = Sync-VerifyRegistry -RegistryPath $registryPath -ForceReset:$force
    if ($Reset) {
        Write-Host "Очередь сверки сброшена: все pending." -ForegroundColor Yellow
    } elseif ($Init -or -not (Test-Path $registryPath)) {
        Write-Host "Очередь сверки инициализирована / синхронизирована." -ForegroundColor Green
    }
}

$all = @(Read-VerifyRegistry -Path $registryPath)
if ($all.Count -eq 0) {
    $all = @(Sync-VerifyRegistry -RegistryPath $registryPath)
}

if ($ResetStale) {
    $projectRoot = (Get-Location).Path
    $archDir = Join-Path $projectRoot '.doc\architecture'
    $staleCount = 0
    $updated = @()
    foreach ($row in $all) {
        $docPath = Join-Path $archDir ($row.path -replace '/', [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $docPath)) {
            $updated += $row
            continue
        }
        $meta = Get-DocMeta -Path $docPath
        $isStale = $false
        if ($meta -and $meta.updated -match '^\d{4}-\d{2}-\d{2}$') {
            try {
                $upd = [datetime]::ParseExact($meta.updated, 'yyyy-MM-dd', $null)
                $isStale = Test-DocStaleByGit -DocFullPath $docPath -UpdatedDate $upd
            } catch { $isStale = $false }
        }
        if ($isStale -and $row.status -eq 'verified') {
            $row.status = 'pending'
            $row.notes = 'reset_stale'
            $staleCount++
        }
        $updated += $row
    }
    Write-VerifyRegistry -Path $registryPath -Rows $updated
    $all = $updated
    Write-Host "ResetStale: возвращено в pending: $staleCount" -ForegroundColor Yellow
}

# Перечитать после maintenance
$all = @(Read-VerifyRegistry -Path $registryPath)

$stats = @{
    total     = $all.Count
    verified  = @($all | Where-Object { $_.status -eq 'verified' }).Count
    pending   = @($all | Where-Object { $_.status -eq 'pending' }).Count
    skipped   = @($all | Where-Object { $_.status -eq 'skipped' }).Count
}
$denom = $stats.verified + $stats.pending
$pct = if ($denom -gt 0) { [math]::Round(($stats.verified / $denom) * 100, 1) } else { 0 }

function Write-VerifyStatusBar {
    param($Pct, $Stats, $Denom)
    $bar_len = 30
    $filled = [math]::Floor($Pct / 100 * $bar_len)
    $empty = $bar_len - $filled
    $bar = ('█' * $filled) + ('░' * $empty)
    Write-Host ""
    Write-Host "  Прогресс сверки docs <-> код:" -ForegroundColor Cyan
    Write-Host "  $bar $Pct% ($($Stats.verified)/$Denom)" -ForegroundColor Green
    Write-Host "  verified: $($Stats.verified) | pending: $($Stats.pending) | skipped: $($Stats.skipped) | total: $($Stats.total)" -ForegroundColor DarkGray
    Write-Host ""
}

# Init/Reset/ResetStale без явного -Count / -Section: только статус
$maintenanceExit = ($Init -or $Reset -or $ResetStale) -and
    -not $Section -and
    -not $PSBoundParameters.ContainsKey('Count')

if ($Status -or $maintenanceExit) {
    Write-VerifyStatusBar -Pct $pct -Stats $stats -Denom $denom
    exit 0
}

# Конкретный Section
if ($Section) {
    $secNorm = Normalize-RelativePath ($Section -replace '^(\.doc/)?architecture/', '')
    $match = @($all | Where-Object {
        $_.path -eq $secNorm -or $_.path -eq (Split-Path -Leaf $secNorm) -or
        (Split-Path -Leaf $_.path) -eq (Split-Path -Leaf $secNorm)
    } | Select-Object -First 1)
    if (-not $match) {
        Write-Host "Документ не найден в очереди: $Section" -ForegroundColor Red
        Write-Host "Сначала: powershell .agents/skills/documentation-router/children/doc-verify/scripts/get-verify-batch.ps1 -Init"
        exit 1
    }
    $batch = @($match)
} else {
    $pending = @($all | Where-Object { $_.status -eq 'pending' } | Sort-Object @{
        Expression = {
            $n = 0
            # Сначала docs с меньшим числом code-refs (быстрее порция)
            if ([int]::TryParse([string]$_.code_refs, [ref]$n)) { $n } else { 99999 }
        }
    }, path)

    if ($pending.Count -eq 0) {
        Write-Host "Все документы сверены с кодом." -ForegroundColor Green
        Write-Host "Повторно: -Reset | -ResetStale | -Section payments.md"
        exit 0
    }

    if ($Skip -gt 0 -and $Skip -lt $pending.Count) {
        $pending = @($pending | Select-Object -Skip $Skip)
    }
    $batch = @($pending | Select-Object -First $Count)
}

Write-Host ""
Write-Host "  === Очередь сверки ($($batch.Count) док.) ===" -ForegroundColor Cyan
Write-Host "  Прогресс: $pct% ($($stats.verified)/$denom), pending: $($stats.pending)" -ForegroundColor DarkGray
Write-Host ""

$projectRoot = (Get-Location).Path
$archDir = Join-Path $projectRoot '.doc\architecture'
$outLines = @()

foreach ($item in $batch) {
    $docFull = Join-Path $archDir ($item.path -replace '/', [IO.Path]::DirectorySeparatorChar)
    $meta = if (Test-Path -LiteralPath $docFull) { Get-DocMeta -Path $docFull } else { $null }
    $h1 = if (Test-Path -LiteralPath $docFull) { Get-DocFirstHeading -Path $docFull } else { $item.path }
    $refs = if (Test-Path -LiteralPath $docFull) { @(Get-DocCodeRefs -Path $docFull) } else { @() }
    $upd = if ($meta -and $meta.updated) { $meta.updated } else { '?' }
    $relDoc = Normalize-RelativePath ('.doc/architecture/' + $item.path)

    Write-Host "  - $($item.path)  [$($item.status)]  refs=$($refs.Count)  updated=$upd" -ForegroundColor White
    Write-Host "    H1: $h1" -ForegroundColor DarkGray
    if ($refs.Count -gt 0) {
        $preview = ($refs | Select-Object -First 8) -join ', '
        if ($refs.Count -gt 8) { $preview += ", ... (+$($refs.Count - 8))" }
        Write-Host "    code: $preview" -ForegroundColor DarkGray
    }
    $outLines += $relDoc
}

$outPath = Join-Path $projectRoot '.doc\architecture\_map\current-verify-batch.txt'
Write-Utf8File -Path $outPath -Content (($outLines -join "`r`n") + "`r`n")

Write-Host ""
Write-Host "  Список: .doc/architecture/_map/current-verify-batch.txt" -ForegroundColor DarkGray
Write-Host "  После сверки: mark-verify-done.ps1 -Path `"$($batch[0].path)`" -Issues N" -ForegroundColor DarkGray
Write-Host ""

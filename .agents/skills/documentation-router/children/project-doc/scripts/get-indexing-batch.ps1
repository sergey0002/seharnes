<#
.SYNOPSIS
    Выдает батч неиндексированных файлов из реестра для обработки агентом.
    Сортирует по директориям, чтобы файлы одного модуля попадали в один батч.

    Автоматически:
    - исключает явный шум (plugins/, *.min.js, *.bundle.js)
    - приоритизирует файлы из hot-files.txt (90 дней по git)
.PARAMETER Count
    Количество файлов в батче (по умолчанию 10).
.PARAMETER Skip
    Пропустить первые N файлов (для параллельных агентов).
.PARAMETER Kind
    Фильтр по типу: php, js, vue, css, tpl, sql, config.
    Если указан — выдаёт только файлы этого типа.
.PARAMETER Status
    Показать только статистику, не выдавать батч.
.PARAMETER NoHotPriority
    Отключить приоритезацию по hot-files.txt (по умолчанию hot файлы идут первыми).
#>

param(
    [int]$Count = 10,
    [int]$Skip = 0,
    [string]$Kind = '',
    [switch]$Status,
    [switch]$NoHotPriority
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_lib.ps1')

function Read-TsvRows([string]$Path) {
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

$registryPath = Get-RegistryFilePath
$all = @(Read-TsvRows -Path $registryPath)

if ($all.Count -eq 0) {
    Write-Host "Реестр пуст или не найден. Сначала запустите map-project.ps1." -ForegroundColor Red
    exit 1
}

# Статистика
$stats = @{
    total = $all.Count
    indexed = @($all | Where-Object { $_.status -eq 'indexed' }).Count
    not_indexed = @($all | Where-Object { $_.status -eq 'not_indexed' }).Count
    noise = @($all | Where-Object { $_.status -eq 'noise' }).Count
}
$pct = if ($stats.total -gt 0) { [math]::Round(($stats.indexed / ($stats.indexed + $stats.not_indexed)) * 100, 1) } else { 0 }

if ($Status) {
    $bar_len = 30
    $filled = [math]::Floor($pct / 100 * $bar_len)
    $empty = $bar_len - $filled
    $bar = ('█' * $filled) + ('░' * $empty)
    Write-Host ""
    Write-Host "  📊 Прогресс индексации:" -ForegroundColor Cyan
    Write-Host "  $bar $pct% ($($stats.indexed)/$($stats.indexed + $stats.not_indexed))" -ForegroundColor Green
    Write-Host "  indexed: $($stats.indexed) | pending: $($stats.not_indexed) | noise: $($stats.noise)" -ForegroundColor DarkGray
    Write-Host ""
    exit 0
}

# Фильтрация
$pending = @($all | Where-Object { $_.status -eq 'not_indexed' -and $_.kind -ne 'other' })
if ($Kind) {
    $pending = @($pending | Where-Object { $_.kind -eq $Kind })
}

# Авто-фильтр шума: plugins/, *.min.js, *.bundle.js, vendor/
$noisePatterns = @(
    '(^|/)scripts/plugins/',
    '(^|/)admin/scripts/plugins/',
    '\.min\.(js|css)$',
    '\.bundle\.js$',
    '(^|/)vendor/',
    '(^|/)node_modules/'
)
$autoNoise = @()
$pending = @($pending | Where-Object {
    $p = $_.path
    $isNoise = $false
    foreach ($pat in $noisePatterns) {
        if ($p -match $pat) { $isNoise = $true; break }
    }
    if ($isNoise) { $autoNoise += $p; return $false }
    return $true
})

if ($autoNoise.Count -gt 0) {
    Write-Host "  🔇 Авто-фильтр шума: $($autoNoise.Count) файлов исключено из батча" -ForegroundColor DarkYellow
    Write-Host "     (помети их через mark-noise.ps1 чтобы убрать из очереди навсегда)" -ForegroundColor DarkGray
}

if ($pending.Count -eq 0) {
    Write-Host "Все файлы проиндексированы! 🎉" -ForegroundColor Green
    exit 0
}

# Приоритизация по hot-files.txt (наиболее активные в git за 90 дней)
$hotMap = @{}
if (-not $NoHotPriority) {
    $hotPath = Join-Path (Get-Location).Path '.doc\architecture\_map\hot-files.txt'
    if (Test-Path $hotPath) {
        $hotLines = Get-Content $hotPath -ErrorAction SilentlyContinue
        $rank = 0
        foreach ($line in $hotLines) {
            $rank++
            if ($line -match '^\s*\d+\s+(.+)$') {
                $hotPath2 = $matches[1].Trim() -replace '\\', '/'
                if (-not $hotMap.ContainsKey($hotPath2)) { $hotMap[$hotPath2] = $rank }
            }
        }
    }
}

# Сортировка: сначала hot (по rank), потом по директории (модуль вместе)
$pending = @($pending | Sort-Object @{
    Expression = { if ($hotMap.ContainsKey($_.path)) { $hotMap[$_.path] } else { 99999 } }
}, @{
    Expression = { ($_.path -replace '[^/]+$', '') }
})

# Skip + Take
if ($Skip -gt 0 -and $Skip -lt $pending.Count) {
    $pending = @($pending | Select-Object -Skip $Skip)
}
$batch = @($pending | Select-Object -First $Count)

Write-Host ""
Write-Host "  === Очередь индексации ($($batch.Count) из $($pending.Count) ожидающих) ===" -ForegroundColor Cyan
Write-Host "  Покрытие: $pct% ($($stats.indexed)/$($stats.indexed + $stats.not_indexed))" -ForegroundColor DarkGray
Write-Host ""
foreach ($item in $batch) {
    $dir = ($item.path -replace '[^/]+$', '').TrimEnd('/')
    $hotMark = if ($hotMap.ContainsKey($item.path)) { ' 🔥' } else { '' }
    Write-Host "  - $($item.path) [$($item.kind)] ($dir)$hotMark" -ForegroundColor White
}

$outPath = Join-Path (Get-Location).Path '.doc\architecture\_map\current-batch.txt'
$paths = $batch | ForEach-Object { $_.path }
Write-Utf8File -Path $outPath -Content ($paths -join "`r`n")

Write-Host ""
Write-Host "  Список сохранен в .doc\architecture\_map\current-batch.txt" -ForegroundColor DarkGray
Write-Host ""

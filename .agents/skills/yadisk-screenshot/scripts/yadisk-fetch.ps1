<#
.SYNOPSIS
    Скачивает файл (обычно скриншот) по публичной ссылке Яндекс.Диска
    и сохраняет в .doc/skil_data/yadisk-screenshot/imd/.

.DESCRIPTION
    Имя файла детерминированно по SHA256-хешу нормализованного URL —
    повторный запуск с той же ссылкой не качает заново, а возвращает
    путь к уже существующему файлу. Используется публичный API
    Яндекс.Диска (cloud-api.yandex.net) — авторизация не нужна.

    Финальный путь к файлу выводится в stdout (Write-Output),
    статус идёт в Host/stderr.

.PARAMETER Url
    Публичная ссылка на ресурс Яндекс.Диска. Примеры:
    - https://disk.yandex.ru/i/HUpAFmr_sBwddQ
    - https://disk.yandex.ru/d/...
    - yadi.sk/i/...

.PARAMETER OutputDir
    Папка для сохранения. По умолчанию: <script>/imd

.PARAMETER NamePrefix
    Префикс имени файла. По умолчанию: yadisk
    Итоговое имя: <prefix>_<sha256[0..11]>.<ext>

.PARAMETER Force
    Перекачать, даже если файл с таким хешем уже есть.

.PARAMETER Quiet
    Не выводить статус, только итоговый путь.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .agents/skills/yadisk-screenshot/scripts/yadisk-fetch.ps1 -Url "https://disk.yandex.ru/i/HUpAFmr_sBwddQ"

.EXAMPLE
    $img = & powershell -NoProfile -ExecutionPolicy Bypass -File .agents/skills/yadisk-screenshot/scripts/yadisk-fetch.ps1 -Url $link -Quiet
    # $img содержит абсолютный путь к скачанному файлу
    # При повторном вызове с тем же $link возвращает тот же путь без сетевых запросов.

.OUTPUTS
    System.String — абсолютный путь к скачанному файлу.

.NOTES
    Exit codes:
      0 — успех (включая cache hit)
      1 — ошибка API (не удалось получить download href)
      2 — ошибка скачивания файла
      3 — неверные аргументы
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Url,

    [string]$OutputDir = '',

    [string]$NamePrefix = 'yadisk',

    [switch]$Force,

    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
    $OutputDir = Join-Path $scriptDir 'imd'
}

function Write-Status {
    param([string]$Message, [string]$Color = 'Cyan')
    if (-not $Quiet) {
        Write-Host $Message -ForegroundColor $Color
    }
}

function Write-ErrLine {
    param([string]$Message)
    [Console]::Error.WriteLine($Message)
}

function Get-UrlHash {
    param([string]$RawUrl)
    $normalized = $RawUrl.Trim().TrimEnd('/')
    try {
        $uri = [uri]$normalized
        $uriHost = $uri.Host.ToLowerInvariant()
        $scheme = $uri.Scheme.ToLowerInvariant()
        $normalized = "${scheme}://${uriHost}$($uri.AbsolutePath)$($uri.Query)"
        $normalized = $normalized.TrimEnd('/')
    } catch {
        # Если не удалось распарсить как URI — оставляем trim+trimEnd
    }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($normalized)
        $hashBytes = $sha.ComputeHash($bytes)
        $hex = ($hashBytes | ForEach-Object { $_.ToString('x2') }) -join ''
        return $hex.Substring(0, 12)
    } finally {
        $sha.Dispose()
    }
}

if ([string]::IsNullOrWhiteSpace($Url)) {
    Write-ErrLine "ERROR: параметр -Url пустой"
    exit 3
}

if ($Url -notmatch '^https?://(disk\.yandex\.|yadi\.sk/)') {
    Write-ErrLine "ERROR: ссылка не похожа на Яндекс.Диск: $Url"
    exit 3
}

if (-not (Test-Path -LiteralPath $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    Write-Status "Создана папка: $OutputDir" 'DarkGray'
}

$urlHash = Get-UrlHash -RawUrl $Url
Write-Status "→ URL hash: $urlHash" 'DarkGray'

if (-not $Force) {
    $cached = Get-ChildItem -LiteralPath $OutputDir -Filter "${NamePrefix}_${urlHash}.*" -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cached) {
        $sizeKb = [math]::Round($cached.Length / 1024, 1)
        Write-Status "✓ Уже скачано ранее: $($cached.Name) ($sizeKb KB)" 'Green'
        Write-Output $cached.FullName
        exit 0
    }
}

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls11 -bor [Net.SecurityProtocolType]::Tls

$publicKey = [uri]::EscapeDataString($Url)
$apiBase   = 'https://cloud-api.yandex.net/v1/disk/public/resources'

Write-Status "→ Запрос метаданных Яндекс.Диска..." 'Cyan'
$origName = $null
try {
    $info = Invoke-RestMethod -Uri "$apiBase`?public_key=$publicKey" -Method Get -TimeoutSec 30
    $origName = $info.name
    Write-Status "  имя на Диске: $origName" 'DarkGray'
    if ($info.size) {
        $sizeKb = [math]::Round($info.size / 1024, 1)
        Write-Status "  размер:      $sizeKb KB" 'DarkGray'
    }
} catch {
    Write-Status "  метаданные недоступны, продолжаем без них ($($_.Exception.Message))" 'Yellow'
}

Write-Status "→ Получение прямой ссылки на скачивание..." 'Cyan'
$downloadUrl = $null
try {
    $dl = Invoke-RestMethod -Uri "$apiBase/download?public_key=$publicKey" -Method Get -TimeoutSec 30
    $downloadUrl = $dl.href
} catch {
    Write-ErrLine "ERROR: API Яндекс.Диска не вернул ссылку на скачивание: $($_.Exception.Message)"
    exit 1
}

if ([string]::IsNullOrWhiteSpace($downloadUrl)) {
    Write-ErrLine "ERROR: пустой href в ответе API"
    exit 1
}

$ext = if ($origName) { [System.IO.Path]::GetExtension($origName) } else { '' }
if ([string]::IsNullOrEmpty($ext)) { $ext = '.png' }

$fileName = "${NamePrefix}_${urlHash}${ext}"
$outputPath = Join-Path $OutputDir $fileName

Write-Status "→ Скачивание -> $fileName" 'Cyan'
try {
    $oldProgress = $ProgressPreference
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $downloadUrl -OutFile $outputPath -UseBasicParsing -TimeoutSec 120
    $ProgressPreference = $oldProgress
} catch {
    Write-ErrLine "ERROR: не удалось скачать файл: $($_.Exception.Message)"
    exit 2
}

if (-not (Test-Path -LiteralPath $outputPath)) {
    Write-ErrLine "ERROR: файл не появился по пути $outputPath"
    exit 2
}

$item = Get-Item -LiteralPath $outputPath
$absPath = $item.FullName
$sizeKb = [math]::Round($item.Length / 1024, 1)

Write-Status "✓ Скачано ($sizeKb KB)" 'Green'
Write-Output $absPath
exit 0

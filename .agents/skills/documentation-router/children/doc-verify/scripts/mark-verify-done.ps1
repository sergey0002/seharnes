<#
.SYNOPSIS
    Помечает architecture-документ как сверенный (или skipped) в verify-registry.tsv.

.PARAMETER Path
    Имя файла или относительный путь: payments.md / orders.md

.PARAMETER Issues
    Сколько несоответствий исправлено (число). 0 = расхождений не было.

.PARAMETER Skip
    Пропустить документ без сверки (status=skipped).

.PARAMETER Notes
    Короткая заметка в реестр.

.EXAMPLE
    powershell .agents/skills/documentation-router/children/doc-verify/scripts/mark-verify-done.ps1 -Path payments.md -Issues 2
    powershell .agents/skills/documentation-router/children/doc-verify/scripts/mark-verify-done.ps1 -Path index.md -Skip -Notes "nav only"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Path,
    [int]$Issues = 0,
    [switch]$Skip,
    [string]$Notes = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\..\project-doc\scripts\_lib.ps1')

function Get-VerifyRegistryPath {
    $projectRoot = (Get-Location).Path
    return (Join-Path $projectRoot '.doc\architecture\_map\verify-registry.tsv')
}

$registryPath = Get-VerifyRegistryPath
if (-not (Test-Path $registryPath)) {
    Write-Host "Реестр не найден. Сначала: get-verify-batch.ps1 -Init" -ForegroundColor Red
    exit 1
}

$target = Normalize-RelativePath ($Path -replace '^(\.doc/)?architecture/', '')
$leaf = Split-Path -Leaf $target

$lines = Get-Content $registryPath -Encoding UTF8
$header = $lines[0]
$found = $false
$newLines = @($header)

foreach ($line in $lines | Select-Object -Skip 1) {
    if (-not $line.Trim()) { continue }
    $parts = $line -split "`t", 6
    while ($parts.Count -lt 6) { $parts += '' }
    $rowPath = $parts[0]
    if ($rowPath -eq $target -or $rowPath -eq $leaf -or (Split-Path -Leaf $rowPath) -eq $leaf) {
        $found = $true
        $parts[1] = if ($Skip) { 'skipped' } else { 'verified' }
        $parts[2] = (Get-Date -Format 'yyyy-MM-dd')
        $parts[3] = if ($Skip) { '' } else { [string]$Issues }
        if ($Notes) { $parts[5] = $Notes }
        Write-Host "OK: $rowPath -> $($parts[1]) (issues=$($parts[3]))" -ForegroundColor Green
    }
    $newLines += ($parts -join "`t")
}

if (-not $found) {
    Write-Host "Не найден в реестре: $Path" -ForegroundColor Red
    exit 1
}

Write-Utf8File -Path $registryPath -Content ($newLines -join "`r`n")

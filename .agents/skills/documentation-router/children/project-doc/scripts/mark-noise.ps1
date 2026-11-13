<#
.SYNOPSIS
    Помечает файлы как "шум" (noise) в реестре, чтобы исключить их из очереди индексации.
#>

param(
    [Parameter(Mandatory=$true)]
    [string[]]$Paths
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_lib.ps1')

$registryPath = Get-RegistryFilePath
$content = Get-Content $registryPath -Encoding UTF8
$newContent = $content | ForEach-Object {
    $line = $_
    foreach ($p in $Paths) {
        $pNorm = Normalize-RelativePath $p
        if ($line -match "^$([regex]::Escape($pNorm))`t") {
            $parts = $line -split "`t"
            $parts[2] = 'noise'
            $line = $parts -join "`t"
            Write-Host "✅ Исключен из очереди: $pNorm" -ForegroundColor Yellow
        }
    }
    $line
}
Write-Utf8File -Path $registryPath -Content ($newContent -join "`r`n")

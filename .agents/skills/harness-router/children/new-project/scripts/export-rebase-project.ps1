<#
.SYNOPSIS
    Совместимость: делегирует в ../rebase_project.ps1 (канон рядом с rebase_project.md).
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Target,

    [string]$Source = '',

    [ValidateSet('Full', 'Core')]
    [string]$Profile = 'Full',

    [ValidateSet('migrate', 'clean', 'update')]
    [string]$Mode = 'migrate',

    [string]$ProjectName = '',

    [switch]$IncludeKilo,
    [switch]$SkipTools,
    [switch]$SkipRuntimeDeps,
    [switch]$SkipGitInit,
    [switch]$SkipExclude,
    [switch]$RunSetup,
    [switch]$SkipMcpMerge,
    [switch]$SkipSiblingConfig,
    [switch]$SkipBackup,
    [switch]$SkipReview,
    [switch]$MirrorKit,
    [switch]$Yes
)

$ErrorActionPreference = 'Stop'
$canon = Join-Path $PSScriptRoot 'rebase_project.ps1'
if (-not (Test-Path $canon)) {
    throw "Не найден канон скрипта: $canon"
}
& $canon @PSBoundParameters

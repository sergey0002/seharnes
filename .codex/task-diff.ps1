# Wrapper for Codex — run task-diff without reading SKILL.md source.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File .codex/task-diff.ps1 -TaskNumber 1627
param(
    [Parameter(Mandatory = $true)]
    [string] $TaskNumber,
    [ValidateSet('inspect', 'generate')]
    [string] $Action = 'generate',
    [string] $ReleaseBranch,
    [string] $TaskBranch,
    [string] $ForkCommit,
    [string] $LegacyTaskNumber,
    [ValidateSet('full', 'ahead')]
    [string] $Mode = 'full',
    [switch] $StrictMatch,
    [switch] $NoIncludeUnnumbered,
    [switch] $NoReleaseBase,
    [switch] $AheadOnly,
    [switch] $SkipFetch,
    [switch] $AllowNoBranch
)

$scriptCandidates = @(
    (Join-Path $PSScriptRoot 'skills/task-router/children/task-diff/scripts/task-diff.ps1'),
    (Join-Path $PSScriptRoot '../.agents/skills/task-router/children/task-diff/scripts/task-diff.ps1')
)
$script = $scriptCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $script) {
    Write-Error "task-diff.ps1 not found. Tried: $($scriptCandidates -join ', ')"
    exit 1
}

$params = @{
    TaskNumber = $TaskNumber
    Action     = $Action
}
if ($ReleaseBranch) { $params.ReleaseBranch = $ReleaseBranch }
if ($TaskBranch) { $params.TaskBranch = $TaskBranch }
if ($ForkCommit) { $params.ForkCommit = $ForkCommit }
if ($StrictMatch) { $params.StrictMatch = $true }
if ($SkipFetch) { $params.SkipFetch = $true }

& $script @params
exit $LASTEXITCODE

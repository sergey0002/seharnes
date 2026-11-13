# Wrapper: one command for Codex — no need to read gototask.ps1 source.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File .codex/go-task.ps1 -TaskNumber 1627
param(
    [Parameter(Mandatory = $true)]
    [string] $TaskNumber,
    [ValidateSet('inspect', 'export-task', 'checkout', 'create-branch', 'merge-release', 'sync')]
    [string] $Action = 'inspect',
    [string] $ReleaseBranch,
    [string] $TaskBranch,
    [ValidateSet('discard', 'stash', 'keep')]
    [string] $LocalChanges = 'keep',
    [switch] $ConfirmCreateBranch,
    [switch] $ConfirmDiscard,
    [switch] $ConfirmMerge
)

$scriptCandidates = @(
    (Join-Path $PSScriptRoot 'skills/task-router/children/gototask/scripts/gototask.ps1'),
    (Join-Path $PSScriptRoot '../.agents/skills/task-router/children/gototask/scripts/gototask.ps1')
)
$script = $scriptCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $script) {
    Write-Error "gototask.ps1 not found. Tried: $($scriptCandidates -join ', ')"
    exit 1
}

$params = @{
    TaskNumber   = $TaskNumber
    Action       = $Action
    LocalChanges = $LocalChanges
}
if ($ReleaseBranch) { $params.ReleaseBranch = $ReleaseBranch }
if ($TaskBranch) { $params.TaskBranch = $TaskBranch }
if ($ConfirmCreateBranch) { $params.ConfirmCreateBranch = $true }
if ($ConfirmDiscard) { $params.ConfirmDiscard = $true }
if ($ConfirmMerge) { $params.ConfirmMerge = $true }

& $script @params
exit $LASTEXITCODE

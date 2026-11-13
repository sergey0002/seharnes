param(
    [Parameter(Mandatory = $true)]
    [string]$TaskNumber,

    [string]$RepoPath = (Get-Location).Path,

    [string]$ConfigPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $ConfigPath) {
    $ConfigPath = Join-Path $RepoPath ".cursor/skills/task-router/children/gototask/config.json"
}

$config = Get-Content $ConfigPath -Raw | ConvertFrom-Json
$candidates = @($config.releaseBranch) + @($config.releaseBranchFallbacks)

Push-Location $RepoPath
try {
    git fetch origin 2>&1 | Out-Null

    $remoteHeads = git ls-remote --heads origin 2>&1 |
        ForEach-Object {
            if ($_ -match 'refs/heads/(.+)$') { $Matches[1] }
        } |
        Where-Object { $_ }

    $exactBranches = @(
        "features/#$TaskNumber",
        "bugfixes/#$TaskNumber"
    )

    $foundExact = @()
    foreach ($branch in $exactBranches) {
        if ($remoteHeads -contains $branch) {
            $foundExact += $branch
        }
    }

    $variantPattern = [regex]::Escape("#$TaskNumber")
    $foundVariants = $remoteHeads |
        Where-Object { $_ -match $variantPattern -and $_ -notin $exactBranches }

    $releaseBranch = $null
    foreach ($candidate in $candidates) {
        if ($remoteHeads -contains $candidate) {
            $releaseBranch = $candidate
            break
        }
    }

    [PSCustomObject]@{
        taskNumber = $TaskNumber
        releaseBranch = $releaseBranch
        releaseBranchCandidates = $candidates
        exactBranches = $foundExact
        variantBranches = @($foundVariants)
        branchExists = ($foundExact.Count -gt 0)
    } | ConvertTo-Json -Depth 4
}
finally {
    Pop-Location
}

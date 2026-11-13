# Rebuild diff.md / diff.files.md for all numeric task folders under .doc/tasks.
# Uses task-diff in mode=full: commits by Jira + Bitbucket legacy numbers from task.md.
# One git fetch at start; per-task -SkipFetch -AllowNoBranch (branch deleted → git log --all).
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .codex/rebuild-all-task-diffs.ps1
#   powershell ... -File .codex/rebuild-all-task-diffs.ps1 -Only "2108,2426"
#   powershell ... -File .codex/rebuild-all-task-diffs.ps1 -Limit 5

param(
    [string] $RepoPath = "",
    [string] $Only = "",
    [int] $Limit = 0,
    [switch] $NoFetch
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = if ($RepoPath) { $RepoPath } else { (Get-Location).Path }
if (-not (Test-Path (Join-Path $repo ".git"))) {
    throw "Not a git repo: $repo"
}

$wrapper = Join-Path $repo ".codex/task-diff.ps1"
if (-not (Test-Path $wrapper)) {
    throw "Missing $wrapper"
}

$tasksRoot = Join-Path $repo ".doc/tasks"
$reportDir = Join-Path $tasksRoot "_map"
if (-not (Test-Path $reportDir)) {
    New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
}
$reportPath = Join-Path $reportDir "diff-rebuild-report.md"
$jsonlPath = Join-Path $reportDir "diff-rebuild-report.jsonl"

$onlySet = @{}
if ($Only) {
    foreach ($p in ($Only -split '[,;\s]+' | Where-Object { $_ })) {
        $onlySet[$p] = $true
    }
}

$taskNums = @(
    Get-ChildItem -Path $tasksRoot -Directory |
        Where-Object { $_.Name -match '^\d+$' } |
        ForEach-Object { $_.Name } |
        Sort-Object { [int]$_ }
)
if ($onlySet.Count -gt 0) {
    $taskNums = @($taskNums | Where-Object { $onlySet.ContainsKey($_) })
}
if ($Limit -gt 0 -and $taskNums.Count -gt $Limit) {
    $taskNums = @($taskNums | Select-Object -First $Limit)
}

Write-Host "Tasks to rebuild: $($taskNums.Count)"

if (-not $NoFetch.IsPresent) {
    Write-Host "git fetch origin ..."
    Push-Location $repo
    try {
        $fetchOut = git fetch origin 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "git fetch failed (will use existing remote-tracking refs): $($fetchOut | Out-String)"
        }
    } finally {
        Pop-Location
    }
}

if (Test-Path $jsonlPath) { Remove-Item $jsonlPath -Force }

$ok = 0
$fail = 0
$zero = 0
$noBranch = 0
$rows = New-Object System.Collections.Generic.List[string]
$rows.Add("# Diff rebuild report")
$rows.Add("")
$rows.Add("| Generated | $((Get-Date).ToUniversalTime().ToString('dd.MM.yyyy HH:mm')) UTC |")
$rows.Add("| Tasks | $($taskNums.Count) |")
$rows.Add("")
$rows.Add("| Task | ok | commits | files | branch | legacy | search | error |")
$rows.Add("| --- | --- | ---: | ---: | --- | --- | --- | --- |")

$i = 0
foreach ($n in $taskNums) {
    $i++
    Write-Host "[$i/$($taskNums.Count)] task $n ..."
    $err = ""
    $commitCount = 0
    $fileCount = 0
    $taskBranch = ""
    $legacy = ""
    $searchSource = ""
    $noBranchFb = $false
    $succeeded = $false

    try {
        $out = & powershell -NoProfile -ExecutionPolicy Bypass -File $wrapper `
            -TaskNumber $n `
            -Mode full `
            -SkipFetch `
            -AllowNoBranch 2>&1
        $text = ($out | ForEach-Object { "$_" }) -join "`n"
        if ($LASTEXITCODE -ne 0) {
            throw "exit ${LASTEXITCODE}: $text"
        }
        # Last JSON object in output (ConvertTo-Json from task-diff)
        $jsonStart = $text.LastIndexOf('{')
        if ($jsonStart -lt 0) { throw "No JSON in output" }
        $jsonText = $text.Substring($jsonStart)
        $obj = $jsonText | ConvertFrom-Json
        if (-not $obj.ok) { throw "ok=false" }
        $succeeded = $true
        $commitCount = [int]$obj.commitCount
        $fileCount = [int]$obj.fileCount
        $taskBranch = [string]$obj.taskBranch
        $legacy = [string]$obj.legacyTaskNumber
        $searchSource = [string]$obj.searchSource
        $noBranchFb = [bool]$obj.noBranchFallback
        if ($noBranchFb) { $noBranch++ }
        if ($commitCount -eq 0) { $zero++ } else { $ok++ }
        Add-Content -Path $jsonlPath -Value ($jsonText.Trim()) -Encoding UTF8
    } catch {
        $fail++
        $err = ($_ | Out-String).Trim() -replace '\|', '/' -replace "`r?`n", " "
        if ($err.Length -gt 120) { $err = $err.Substring(0, 117) + "..." }
        $lineObj = @{
            ok = $false
            taskNumber = $n
            error = "$_"
        } | ConvertTo-Json -Compress
        Add-Content -Path $jsonlPath -Value $lineObj -Encoding UTF8
    }

    $okMark = if ($succeeded) { "yes" } else { "no" }
    $branchCell = if ($taskBranch) { $taskBranch } else { "_none_" }
    $legacyCell = if ($legacy) { $legacy } else { "-" }
    $searchCell = if ($searchSource) { $searchSource } else { "-" }
    $rows.Add("| $n | $okMark | $commitCount | $fileCount | ``$branchCell`` | $legacyCell | $searchCell | $err |")
}

$rows.Add("")
$rows.Add("## Summary")
$rows.Add("")
$rows.Add("- ok with commits: $ok")
$rows.Add("- ok but 0 commits: $zero")
$rows.Add("- failed: $fail")
$rows.Add("- no-branch fallback (--all): $noBranch")
$rows.Add("")
$rows.Add("JSONL: ``.doc/tasks/_map/diff-rebuild-report.jsonl``")

$utf8Bom = New-Object System.Text.UTF8Encoding $true
[System.IO.File]::WriteAllText($reportPath, ($rows -Join "`n"), $utf8Bom)

Write-Host ""
Write-Host "Done. ok+commits=$ok zero=$zero fail=$fail noBranch=$noBranch"
Write-Host "Report: $reportPath"

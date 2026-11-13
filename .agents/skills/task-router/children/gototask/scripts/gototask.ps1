param(
    [Parameter(Mandatory = $true)]
    [string]$TaskNumber,

    [ValidateSet("inspect", "export-task", "checkout", "create-branch", "merge-release", "sync")]
    [string]$Action = "inspect",

    [string]$RepoPath = "",
    [string]$ConfigPath = "",
    [string]$ReleaseBranch = "",
    [string]$TaskBranch = "",
    [ValidateSet("discard", "stash", "keep")]
    [string]$LocalChanges = "keep",
    [switch]$SkipTaskExport,

    # Explicit human consent. Apply refuses to act on a pending question, and
    # destructive actions require their own switch so an agent cannot discard
    # work just by passing -LocalChanges discard.
    [switch]$ConfirmCreateBranch,
    [switch]$ConfirmDiscard,
    [switch]$ConfirmMerge
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Json([object]$Data) {
    $Data | ConvertTo-Json -Depth 8
}

function Get-RepoRoot {
    param([string]$StartPath)
    $path = if ($StartPath) { $StartPath } else { (Get-Location).Path }
    if (Test-Path (Join-Path $path ".git")) { return (Resolve-Path $path).Path }
    $parent = Split-Path $path -Parent
    if (-not $parent -or $parent -eq $path) { throw "Git repo not found from: $StartPath" }
    return Get-RepoRoot -StartPath $parent
}

function Invoke-Git {
    param([string]$Repo, [string[]]$GitArgs)
    Push-Location $Repo
    try {
        $old = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        $raw = & git @GitArgs 2>&1
        $ec = $LASTEXITCODE
        $ErrorActionPreference = $old

        $lines = @($raw | ForEach-Object {
            if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.ToString() } else { "$_" }
        }) | Where-Object {
            $_ -notmatch '^\*\* WARNING: connection is not using a post-quantum'
            $_ -notmatch '^\*\* This session may be vulnerable'
            $_ -notmatch '^\*\* The server may need to be upgraded'
        }

        if ($ec -ne 0) { throw ($lines -join "`n").Trim() }
        return ($lines -join "`n").Trim()
    } finally {
        Pop-Location
    }
}

function Get-RemoteHeads([string]$Repo) {
    $raw = Invoke-Git $Repo @("ls-remote", "--heads", "origin")
    @($raw -split "`r?`n") |
        ForEach-Object { $_.Trim() } |
        ForEach-Object { if ($_ -match 'refs/heads/(.+)$') { $Matches[1] } } |
        Where-Object { $_ }
}

function Get-ReleaseBranches([string[]]$Heads) {
    $Heads | Where-Object { $_ -match '^(release|releases)/' } |
        Sort-Object {
            $v = $_ -replace '^(release|releases)/', ''
            try { [version]$v } catch { [version]"0.0.0" }
        } -Descending
}

function Get-BackportTarget {
    # Backport task branches carry a target-release suffix:
    #   bugfixes/#N_for5606     -> 5.6.0.6
    #   bugfixes/#N_for_5.6.0.6 -> 5.6.0.6
    # Returns the dotted version, or $null when the branch is not a backport.
    param([string]$Branch)
    if (-not $Branch) { return $null }
    if ($Branch -match '_for_(\d+\.\d+(?:\.\d+){0,2})$') {
        return $Matches[1]
    }
    if ($Branch -match '_for(\d{3,5})$') {
        $digits = $Matches[1]
        if ($digits.Length -lt 3) { return $null }
        return (($digits.ToCharArray()) -join '.')
    }
    return $null
}

function Resolve-ReleaseBranchFromVersion {
    param(
        [string[]]$Heads,
        [string[]]$ReleaseBranches,
        [string]$Version
    )
    if (-not $Version) { return $null }
    $v = $Version.Trim()
    if (-not $v) { return $null }

    foreach ($candidate in @("releases/$v", "release/$v")) {
        if ($Heads -contains $candidate) { return $candidate }
    }

    $escaped = [regex]::Escape($v)
    $match = @($ReleaseBranches | Where-Object { $_ -match "/$escaped`$" })
    if ($match.Count -gt 0) { return $match[0] }
    return $null
}

function Get-DefaultReleaseBranch {
    param(
        [string[]]$Heads,
        [string[]]$ReleaseBranches,
        [object]$Config,
        [string]$JiraVersion
    )

    if ($JiraVersion) {
        foreach ($version in ($JiraVersion -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })) {
            $fromJira = Resolve-ReleaseBranchFromVersion -Heads $Heads -ReleaseBranches $ReleaseBranches -Version $version
            if ($fromJira) {
                return @{ branch = $fromJira; source = "jira"; jiraVersion = $version }
            }
        }
    }

    foreach ($candidate in @($Config.releaseBranch) + @($Config.releaseBranchFallbacks)) {
        if ($Heads -contains $candidate) {
            return @{ branch = $candidate; source = "config"; jiraVersion = $JiraVersion }
        }
    }

    return @{ branch = $null; source = $null; jiraVersion = $JiraVersion }
}

function Test-LegacyBranch([string]$Branch, [string[]]$Legacy) {
    foreach ($ln in $Legacy) {
        if (-not $ln) { continue }
        $esc = [regex]::Escape($ln)
        if ($Branch -match "(^|[/#_-])$esc([^0-9]|$)") { return $true }
    }
    return $false
}

function Get-TaskBranches([string[]]$Heads, [string]$Num, [string[]]$Legacy = @()) {
    $exact = @("features/#$Num", "bugfixes/#$Num")
    $jiraExact = @($exact | Where-Object { $Heads -contains $_ })

    # Imported Bitbucket tasks kept the original issue number in branch names
    # (features/#1642 for Jira CT-2533), so those refs count as exact matches.
    $legacyPatterns = @()
    foreach ($ln in $Legacy) {
        if (-not $ln) { continue }
        $legacyPatterns += @("features/#$ln", "bugfixes/#$ln", "features/$ln", "bugfixes/$ln")
    }
    $legacyExact = @($legacyPatterns | Select-Object -Unique | Where-Object {
        $Heads -contains $_ -and $_ -notin $jiraExact
    })

    $pattern = [regex]::Escape("#$Num")
    $variants = @($Heads | Where-Object {
        ($_ -match $pattern -or (Test-LegacyBranch $_ $Legacy)) -and
        $_ -notin $jiraExact -and
        $_ -notin $legacyExact
    })

    return @{
        exact = @($jiraExact + $legacyExact)
        jiraExact = $jiraExact
        legacyExact = $legacyExact
        variants = $variants
    }
}

function Get-BranchPrefix([string]$Title, [string]$Kind) {
    if ($Kind -eq "bug") { return "bugfixes" }
    if ($Kind -in @("enhancement", "task", "proposal")) { return "features" }
    if ($Kind -match '^(?i)(баг|bug)$') { return "bugfixes" }
    if ($Title) {
        $t = $Title.ToLowerInvariant()
        # oshibka / dorabotka without cyrillic literals (encoding-safe)
        if ($t -match '\u043E\u0448\u0438\u0431\u043A\u0430') { return "bugfixes" }
        if ($t -match '\u0434\u043E\u0440\u0430\u0431\u043E\u0442\u043A\u0430') { return "features" }
    }
    return $null
}

function Export-TaskMd([string]$Repo, [string]$Num) {
    $server = Join-Path $Repo ".agents/skills/task-router/children/jira/scripts/server.php"
    if (-not (Test-Path $server)) { throw "Not found: $server" }

    $php = Get-Command php -ErrorAction SilentlyContinue
    if ($php) {
        $out = & php $server $Num 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0) { return @{ ok = $true; method = "php"; output = $out.Trim() } }
    }

    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if ($docker) {
        $out = & docker exec copytrust-dev-php-apache-1 php /var/www/html/.agents/skills/task-router/children/jira/scripts/server.php $Num 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0) { return @{ ok = $true; method = "docker"; output = $out.Trim() } }
        return @{ ok = $false; method = "docker"; output = $out.Trim() }
    }

    throw "PHP and Docker unavailable for task export"
}

# JSONdoc dual output: PHP exporter leaves tracker.json next to task.md.
# Ingest must never fail the export itself (plan .doc/harnes/jsondoc.md 19.2 / 9.5).
function Invoke-JsondocTrackerIngest([string]$Repo, [string]$Num) {
    try {
        $tracker = Join-Path $Repo ".doc/tasks/$Num/_jsondoc/work/tracker.json"
        $cli = Join-Path $Repo ".agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py"
        if (-not (Test-Path $tracker)) { return @{ status = "skipped"; reason = "tracker_not_found" } }
        if (-not (Test-Path $cli)) { return @{ status = "skipped"; reason = "jsondoc_not_found" } }
        $python = Get-Command python3 -ErrorAction SilentlyContinue
        if (-not $python) { return @{ status = "skipped"; reason = "python3_not_found" } }
        $old = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            & $python.Source $cli --root $Repo ingest-tracker --task $Num --input $tracker 2>&1 | Out-Null
            $code = $LASTEXITCODE
        } finally { $ErrorActionPreference = $old }
        if ($code -ne 0) { return @{ status = "failed"; reason = "ingest_failed"; exitCode = $code } }
        return @{ status = "success"; exitCode = 0 }
    } catch {
        return @{ status = "failed"; reason = "ingest_exception" }
    }
}

function Read-TaskInfo([string]$Repo, [string]$Num) {
    $path = Join-Path $Repo ".doc/tasks/$Num/task.md"
    if (-not (Test-Path $path)) { return $null }
    $content = Get-Content $path -Raw -Encoding UTF8
    $title = $null
    if ($content -match '(?m)^#\s+Issue\s+#\d+:\s*(.+)$') { $title = $Matches[1].Trim() }
    $kind = $null
    if ($content -match '(?m)^\|\s*Kind\s*\|\s*(\S+)\s*\|') { $kind = $Matches[1].Trim() }
    $version = $null
    if ($content -match '(?m)^\|\s*Version\s*\|\s*(.+?)\s*\|') {
        $version = $Matches[1].Trim()
        if (-not $version) { $version = $null }
    }
    $bitbucket = New-Object System.Collections.Generic.List[string]
    if ($content -match '(?m)^\|\s*Bitbucket\s*\|\s*(.+?)\s*\|') {
        foreach ($part in ($Matches[1] -split '[,\s]+')) {
            if ($part -match '^\d+$') { $bitbucket.Add($part) }
        }
    }
    foreach ($m in [regex]::Matches($content, '(?i)Imported[ \t]+from[ \t]+<?https?://(?:www\.)?bitbucket\.org/[^\s/]+/[^\s/]+/issues/(\d+)')) {
        $bitbucket.Add($m.Groups[1].Value)
    }
    return @{
        path = $path
        title = $title
        kind = $kind
        version = $version
        bitbucket = @($bitbucket | Select-Object -Unique)
        prefix = $(Get-BranchPrefix $title $kind)
    }
}

function Test-DirtyWorkingTree([string]$Repo) {
    $s = Invoke-Git $Repo @("status", "--porcelain")
    return [bool]$s
}

function Invoke-HandleLocalChanges([string]$Repo, [string]$Action, [string]$Num) {
    if (-not (Test-DirtyWorkingTree $Repo)) { return @{ handled = $false; action = "none" } }
    switch ($Action) {
        "discard" {
            if (-not $ConfirmDiscard) {
                return @{
                    handled = $false
                    action = "blocked"
                    needsUserInput = @("discard_requires_confirm")
                }
            }
            Invoke-Git $Repo @("reset", "--hard", "HEAD") | Out-Null
            Invoke-Git $Repo @("clean", "-fd") | Out-Null
            return @{ handled = $true; action = "discarded" }
        }
        "stash" {
            Invoke-Git $Repo @("stash", "push", "-u", "-m", "gototask: before #$Num") | Out-Null
            return @{ handled = $true; action = "stashed" }
        }
        default { return @{ handled = $false; action = "kept" } }
    }
}

function Test-LocalBranch([string]$Repo, [string]$Branch) {
    Push-Location $Repo
    try {
        $old = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & git show-ref --verify --quiet "refs/heads/$Branch"
        $ec = $LASTEXITCODE
        $ErrorActionPreference = $old
        return ($ec -eq 0)
    } finally { Pop-Location }
}

function Get-LocalAheadCount([string]$Repo, [string]$Branch) {
    # Commits that exist locally but not on the upstream branch. Non-zero means
    # resetting the branch would destroy work.
    Push-Location $Repo
    try {
        $old = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & git rev-parse --abbrev-ref "$Branch@{u}" 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { $ErrorActionPreference = $old; return -1 }
        $count = (& git rev-list --count "$Branch@{u}..$Branch" 2>&1 | Out-String).Trim()
        $ErrorActionPreference = $old
        if ($count -match '^\d+$') { return [int]$count }
        return -1
    } finally { Pop-Location }
}

# Checkout by SHA. An existing local branch is never reset: it is checked out and
# fast-forwarded. Resetting (`checkout -B`) is reserved for branches that do not
# exist locally yet.
function Invoke-CheckoutBySha([string]$Repo, [string]$Branch, [string]$Sha) {
    if (Test-LocalBranch $Repo $Branch) {
        $ahead = Get-LocalAheadCount $Repo $Branch
        if ($ahead -gt 0) {
            throw "Local branch $Branch is $ahead commit(s) ahead of upstream; merge or push it instead of resetting"
        }
        Invoke-Git $Repo @("checkout", $Branch) | Out-Null
        Push-Location $Repo
        try {
            $old = $ErrorActionPreference
            $ErrorActionPreference = 'Continue'
            & git merge --ff-only $Sha 2>&1 | Out-Null
            $ec = $LASTEXITCODE
            $ErrorActionPreference = $old
        } finally { Pop-Location }
        if ($ec -ne 0) { throw "fast-forward of $Branch to $Sha failed (exit $ec)" }
        return
    }
    Push-Location $Repo
    try {
        $old = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & git checkout -b $Branch $Sha 2>&1 | Out-Null
        $ec = $LASTEXITCODE
        $ErrorActionPreference = $old
        if ($ec -ne 0) { throw "checkout -b failed for $Branch at $Sha (exit $ec)" }
    } finally { Pop-Location }
}

function Get-MergeConflicts([string]$Repo) {
    $conflicts = Invoke-Git $Repo @("diff", "--name-only", "--diff-filter=U")
    if (-not $conflicts) { return @() }
    return @($conflicts -split "`n" | Where-Object { $_ })
}

# --- main ---

$repo = Get-RepoRoot -StartPath $(if ($RepoPath) { $RepoPath } else { (Get-Location).Path })
if (-not $ConfigPath) { $ConfigPath = Join-Path $repo ".cursor/skills/task-router/children/gototask/config.json" }
$config = Get-Content $ConfigPath -Raw | ConvertFrom-Json

# Network access is not guaranteed. `git ls-remote` reaching the server can fail
# with "Connection closed" and previously aborted the whole inspect run, so a
# transient outage looked like a broken task. Fall back to the local
# remote-tracking refs and record the degraded state instead of failing.
$originState = "ok"
try {
    Invoke-Git $repo @("fetch", "origin") 2>$null | Out-Null
} catch {
    $originState = "fetch_failed"
}
try {
    $heads = @(Get-RemoteHeads $repo)
} catch {
    $heads = @()
    if ($originState -eq "ok") { $originState = "ls_remote_failed" }
    try {
        $localRefs = Invoke-Git $repo @("for-each-ref", "--format=%(refname)", "--", "refs/remotes/origin")
    } catch {
        $localRefs = ""
    }
    foreach ($ref in @($localRefs -split "`r?`n" | Where-Object { $_ })) {
        $name = $ref -replace "^refs/remotes/origin/", ""
        if ($name) { $heads += $name }
    }
}
$releaseBranches = @(Get-ReleaseBranches $heads)

$taskExport = $null
$jsondocIngest = @{ status = "skipped"; reason = "task_export_skipped" }
$taskInfo = $null
if (-not $SkipTaskExport) {
    try {
        $taskExport = Export-TaskMd $repo $TaskNumber
        if ($taskExport.ok) { $jsondocIngest = Invoke-JsondocTrackerIngest $repo $TaskNumber }
        else { $jsondocIngest = @{ status = "skipped"; reason = "task_export_failed" } }
        $taskInfo = Read-TaskInfo $repo $TaskNumber
    } catch {
        $taskExport = @{ ok = $false; error = $_.Exception.Message }
        $jsondocIngest = @{ status = "skipped"; reason = "task_export_failed" }
        $taskInfo = Read-TaskInfo $repo $TaskNumber
    }
} else {
    $taskInfo = Read-TaskInfo $repo $TaskNumber
}

$legacyNums = if ($taskInfo -and $taskInfo.bitbucket) { @($taskInfo.bitbucket) } else { @() }
$branches = Get-TaskBranches $heads $TaskNumber $legacyNums

$suggestedPrefix = if ($taskInfo -and $taskInfo.prefix) { $taskInfo.prefix } else { $null }
$suggestedBranch = if ($suggestedPrefix) { "$suggestedPrefix/#$TaskNumber" } else { $null }

$taskTitle = if ($taskInfo) { $taskInfo.title } else { $null }
if ($taskExport -and $taskExport.ok -and $taskExport.output -match '(?m)^Title:\s*(.+)$') {
    $taskTitle = $Matches[1].Trim()
    if (-not $suggestedPrefix) {
        $suggestedPrefix = Get-BranchPrefix $taskTitle $(if ($taskInfo) { $taskInfo.kind })
        $suggestedBranch = if ($suggestedPrefix) { "$suggestedPrefix/#$TaskNumber" } else { $null }
    }
}

$jiraVersion = if ($taskInfo) { $taskInfo.version } else { $null }
$defaultReleaseInfo = Get-DefaultReleaseBranch -Heads $heads -ReleaseBranches $releaseBranches -Config $config -JiraVersion $jiraVersion
$defaultRelease = $defaultReleaseInfo.branch

# Backport suffix overrides the Jira Fix Version release. A branch named
# bugfixes/#N_for5606 or bugfixes/#N_for_5.6.0.6 must merge with 5.6.0.6, not
# with whatever Fix Version says (5.7 / 4.0 (новдиз) never map to a branch).
$backportBranchName = $TaskBranch
if (-not $backportBranchName) {
    if ($branches.exact.Count -eq 1) { $backportBranchName = $branches.exact[0] }
    elseif ($branches.variants.Count -eq 1) { $backportBranchName = $branches.variants[0] }
}
if ($backportBranchName) {
    $backportVersion = Get-BackportTarget -Branch $backportBranchName
    if ($backportVersion) {
        $backportRelease = Resolve-ReleaseBranchFromVersion -Heads $heads -ReleaseBranches $releaseBranches -Version $backportVersion
        if ($backportRelease) {
            $defaultReleaseInfo = @{ branch = $backportRelease; source = "backport_suffix"; jiraVersion = $jiraVersion }
            $defaultRelease = $backportRelease
        }
    }
}

$result = @{
    action = $Action
    taskNumber = $TaskNumber
    repoPath = $repo
    taskExport = $taskExport
    jsondocIngest = $jsondocIngest
    task = @{
        path = if ($taskInfo) { $taskInfo.path } else { $null }
        title = $taskTitle
        kind = if ($taskInfo) { $taskInfo.kind } else { $null }
        jiraVersion = $jiraVersion
        bitbucket = @($legacyNums)
        suggestedPrefix = $suggestedPrefix
        suggestedBranch = $suggestedBranch
    }
    releaseBranches = $releaseBranches
    defaultReleaseBranch = $defaultRelease
    defaultReleaseSource = $defaultReleaseInfo.source
    taskBranches = $branches
    legacyNumbers = @($legacyNums)
    branchExists = ($branches.exact.Count -gt 0)
    branchExistsLocally = $false
    localAheadCount = 0
    hasLocalChanges = (Test-DirtyWorkingTree $repo)
    originState = $originState
    currentBranch = Invoke-Git $repo @("branch", "--show-current")
    needsUserInput = @()
    recommendedAction = $null
}

# Local (unpushed) branch state. `branchExists` only reflects origin; without
# this an already checked-out task branch looks missing and create-branch loops.
$localBranchName = $TaskBranch
if (-not $localBranchName) {
    if ($branches.exact.Count -eq 1) { $localBranchName = $branches.exact[0] }
    elseif ($suggestedBranch) { $localBranchName = $suggestedBranch }
}
if ($localBranchName -and (Test-LocalBranch $repo $localBranchName)) {
    $result.branchExistsLocally = $true
    $result.localAheadCount = Get-LocalAheadCount $repo $localBranchName
}

if ($branches.exact.Count -gt 1) {
    $result.needsUserInput += "select_task_branch"
} elseif ($branches.exact.Count -eq 0 -and $branches.variants.Count -gt 0) {
    $result.needsUserInput += "select_task_branch"
}

# Release from Jira Fix Version only. Ask only if missing / not on origin.
if (-not $defaultRelease -or $defaultReleaseInfo.source -ne "jira") {
    $result.needsUserInput += "select_release_branch"
}

if ($result.hasLocalChanges -and $LocalChanges -eq "keep") {
    $result.needsUserInput += "local_changes"
}

# A failed Jira export silently leaves a stale task.md. Surface it instead of
# letting the report claim "task.md обновлён".
if ($taskExport -and ($taskExport.ok -eq $false)) {
    $result.needsUserInput += "task_export_failed"
    $result.taskExport = $taskExport
}

if (-not $result.branchExists -and -not $branches.variants.Count) {
    if (-not $suggestedPrefix) { $result.needsUserInput += "select_branch_prefix" }
    $result.needsUserInput += "confirm_create_branch"
    if ($suggestedBranch -and ($result.needsUserInput -notcontains "select_branch_prefix")) {
        $result.recommendedAction = "create-branch"
    }
} elseif ($result.branchExists -or $branches.variants.Count -gt 0) {
    # Existing task branch: always merge release (no confirm_merge_release).
    if ($result.needsUserInput -notcontains "select_task_branch") {
        $result.recommendedAction = "merge-release"
    }
}

if ($Action -eq "inspect") {
    Write-Json $result
    exit 0
}

if ($Action -eq "export-task") {
    Write-Json @{ action = $Action; taskExport = $taskExport; jsondocIngest = $jsondocIngest; task = $result.task }
    exit 0
}

# Consent gate: never apply while a question is open. The caller must either
# resolve the question or pass the matching -Confirm* switch.
$blockers = @($result.needsUserInput)
if ($Action -eq "create-branch" -and -not $ConfirmCreateBranch -and $blockers.Count -gt 0) {
    Write-Json @{
        ok = $false
        action = $Action
        error = "apply_blocked_pending_user_input"
        needsUserInput = $blockers
    }
    exit 3
}
if ($Action -eq "merge-release" -and -not $ConfirmMerge -and $blockers.Count -gt 0) {
    Write-Json @{
        ok = $false
        action = $Action
        error = "apply_blocked_pending_user_input"
        needsUserInput = $blockers
    }
    exit 3
}
if ($LocalChanges -eq "discard" -and -not $ConfirmDiscard) {
    Write-Json @{
        ok = $false
        action = $Action
        error = "discard_requires_confirm"
        needsUserInput = @("local_changes")
    }
    exit 3
}

$branch = $TaskBranch
if (-not $branch) {
    if ($branches.exact.Count -eq 1) { $branch = $branches.exact[0] }
    elseif ($suggestedBranch) { $branch = $suggestedBranch }
    else { throw "TaskBranch required" }
}

$release = $ReleaseBranch
if (-not $release) {
    if ($defaultRelease) { $release = $defaultRelease }
    else { throw "ReleaseBranch required" }
}

$localResult = Invoke-HandleLocalChanges $repo $LocalChanges $TaskNumber

# Fetch branch objects explicitly — needed when origin.fetch refspec is narrowed
# (ls-remote still returns live tip, but git fetch origin may not download that branch).
function Invoke-FetchRemoteBranch([string]$Repo, [string]$Branch) {
    Push-Location $Repo
    try {
        $old = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & git fetch origin "refs/heads/${Branch}" 2>&1 | Out-Null
        $ec = $LASTEXITCODE
        $ErrorActionPreference = $old
        if ($ec -ne 0) { throw "fetch failed for origin/$Branch (exit $ec)" }
    } finally { Pop-Location }
}

function Test-LocalCommit([string]$Repo, [string]$Sha) {
    Push-Location $Repo
    try {
        $old = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & git cat-file -e "${Sha}^{commit}" 2>&1 | Out-Null
        return ($LASTEXITCODE -eq 0)
    } finally {
        $ErrorActionPreference = $old
        Pop-Location
    }
}

# Helper: resolve remote branch to SHA via ls-remote (safe for # in names)
function Get-RemoteBranchSha([string]$Repo, [string]$Branch) {
    Push-Location $Repo
    try {
        $old = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        $lines = & git ls-remote origin "refs/heads/$Branch" 2>&1
        $ErrorActionPreference = $old
        $escaped = [regex]::Escape($Branch)
        $line = @($lines) | Where-Object { $_ -match "refs/heads/$escaped`$" } | Select-Object -First 1
        if (-not $line) { throw "Remote branch not found: $Branch" }
        return ($line -split "\s+")[0].Trim()
    } finally { Pop-Location }
}

# Checkout by SHA with -B (create-or-reset) — safe for any branch name including #
function Invoke-CheckoutBranch([string]$Repo, [string]$Branch) {
    Invoke-FetchRemoteBranch $Repo $Branch
    $sha = Get-RemoteBranchSha $Repo $Branch
    if (-not (Test-LocalCommit $Repo $sha)) {
        throw "Branch commit $sha not available locally after fetch (branch: $Branch)"
    }
    Invoke-CheckoutBySha $Repo $Branch $sha
}

function Invoke-CheckoutReleaseBranch([string]$Repo, [string]$Branch) {
    Invoke-CheckoutBranch $Repo $Branch
}

# After apply: best-effort refresh of the codegraph index (no LLM).
function Invoke-CodegraphIndexSync([string]$Repo) {
    if ($env:CODEGRAPH_AUTO_UPDATE -eq '0') {
        return @{ ok = $false; skipped = $true; reason = "disabled by CODEGRAPH_AUTO_UPDATE=0" }
    }
    $cli = Get-Command codegraph -ErrorAction SilentlyContinue
    if (-not $cli) {
        return @{ ok = $false; skipped = $true; reason = "codegraph not found" }
    }
    $db = Join-Path $Repo ".codegraph/codegraph.db"
    if (-not (Test-Path $db)) {
        return @{ ok = $false; skipped = $true; reason = "codegraph index not built; run codegraph init" }
    }
    $job = $null
    try {
        $job = Start-Job -ScriptBlock {
            param($CliPath, $Root)
            & $CliPath sync $Root 2>&1
            exit $LASTEXITCODE
        } -ArgumentList $cli.Source, $Repo
        $done = Wait-Job $job -Timeout 60
        if (-not $done) {
            Stop-Job $job -ErrorAction SilentlyContinue
            return @{ ok = $false; skipped = $false; timeout = $true; reason = "codegraph sync exceeded 60s" }
        }
        $state = $job.State
        $raw = Receive-Job $job -ErrorAction SilentlyContinue
        $text = (@($raw | ForEach-Object { "$_" }) -join "`n").Trim()
        return @{ ok = ($state -eq 'Completed'); skipped = $false; output = $text }
    } catch {
        return @{ ok = $false; skipped = $false; error = $_.Exception.Message }
    } finally {
        if ($job) { Remove-Job $job -Force -ErrorAction SilentlyContinue }
    }
}

function Write-ApplyJson([hashtable]$Data) {
    $Data.codegraphIndex = Invoke-CodegraphIndexSync $repo
    Write-Json $Data
}

switch ($Action) {
    "checkout" {
        if ($heads -notcontains $branch) { throw "Branch not on origin: $branch" }
        Invoke-CheckoutBranch $repo $branch
        Write-ApplyJson @{
            ok = $true; action = $Action; branch = $branch
            localChanges = $localResult
            currentBranch = (Invoke-Git $repo @("branch", "--show-current"))
            head = (Invoke-Git $repo @("log", "-1", "--oneline"))
        }
    }
    "create-branch" {
        if ($heads -notcontains $release) { throw "Release branch not on origin: $release" }
        Invoke-CheckoutReleaseBranch $repo $release
        # create new branch from current HEAD
        Invoke-Git $repo @("checkout", "-b", $branch) | Out-Null
        Write-ApplyJson @{
            ok = $true; action = $Action; branch = $branch; releaseBranch = $release
            created = $true; localChanges = $localResult
            currentBranch = (Invoke-Git $repo @("branch", "--show-current"))
            head = (Invoke-Git $repo @("log", "-1", "--oneline"))
        }
    }
    "merge-release" {
        if ($heads -notcontains $branch) { throw "Task branch not on origin: $branch" }
        if ($heads -notcontains $release) { throw "Release branch not on origin: $release" }

        # switch to task branch
        Invoke-CheckoutBranch $repo $branch

        # resolve release SHA and merge by SHA (avoids any ref resolution issues with # in names)
        Invoke-FetchRemoteBranch $repo $release
        $releaseSha = Get-RemoteBranchSha $repo $release
        if (-not (Test-LocalCommit $repo $releaseSha)) {
            throw "Release commit $releaseSha not available locally after fetch (branch: $release)"
        }

        $mergeOut = ""
        Push-Location $repo
        $old = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        $rawMerge = & git merge $releaseSha --no-edit -m "gototask: merge $release into $branch" 2>&1
        $mergeEc = $LASTEXITCODE
        $ErrorActionPreference = $old
        Pop-Location
        $mergeOut = ($rawMerge | Out-String).Trim()
        try {
            if ($mergeEc -ne 0) { throw "merge exit $mergeEc" }
            $merged = $true
            $conflicts = @()
        } catch {
            $merged = $false
            $conflicts = @(Get-MergeConflicts $repo)
        }

        Write-ApplyJson @{
            ok = $merged
            action = $Action
            branch = $branch
            releaseBranch = $release
            merged = $merged
            mergeOutput = $mergeOut
            conflicts = $conflicts
            localChanges = $localResult
            currentBranch = (Invoke-Git $repo @("branch", "--show-current"))
            head = (Invoke-Git $repo @("log", "-1", "--oneline"))
            needsConflictResolution = ($conflicts.Count -gt 0)
        }
        if (-not $merged) { exit 2 }
    }
    "sync" {
        if ($heads -notcontains $branch) { throw "Branch not on origin: $branch" }
        Invoke-CheckoutBranch $repo $branch
        Write-ApplyJson @{
            ok = $true; action = $Action; branch = $branch
            localChanges = $localResult
            currentBranch = (Invoke-Git $repo @("branch", "--show-current"))
            head = (Invoke-Git $repo @("log", "-1", "--oneline"))
        }
    }
    default { throw "Unknown action: $Action" }
}

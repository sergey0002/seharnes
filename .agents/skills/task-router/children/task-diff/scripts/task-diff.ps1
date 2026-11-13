param(
    [Parameter(Mandatory = $true)]
    [string]$TaskNumber,

    [ValidateSet("inspect", "generate")]
    [string]$Action = "generate",

    [string]$RepoPath = "",
    [string]$ConfigPath = "",
    [string]$ReleaseBranch = "",
    [string]$TaskBranch = "",
    [string]$ForkCommit = "",
    [switch]$UseRemoteTip,
    [switch]$StrictMatch,
    [switch]$SkipFetch,

    # Documented in SKILL.md but previously absent, which silently made
    # `-Mode ahead` behave like a full diff.
    [ValidateSet("full", "ahead")]
    [string]$Mode = "full",
    [switch]$AheadOnly,
    [switch]$NoReleaseBase
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# UTF-8 for git output and file writes on Windows
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
if ($Host.Name -eq "ConsoleHost") {
    try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch {}
}
try { chcp 65001 | Out-Null } catch {}

function Write-Json([object]$Data) {
    $Data | ConvertTo-Json -Depth 8
}

function Write-Utf8File([string]$Path, [string]$Content) {
    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($true))
}

function Get-RepoRoot {
    param([string]$StartPath)
    $path = if ($StartPath) { $StartPath } else { (Get-Location).Path }
    if (Test-Path (Join-Path $path ".git")) { return (Resolve-Path $path).Path }
    $parent = Split-Path $path -Parent
    if (-not $parent -or $parent -eq $path) { throw "Git repo not found from: $StartPath" }
    return Get-RepoRoot -StartPath $parent
}

function Invoke-GitRaw {
    param([string]$Repo, [string[]]$GitArgs)
    Push-Location $Repo
    try {
        $old = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $allArgs = @("-c", "core.quotepath=false", "-c", "i18n.logOutputEncoding=utf-8", "-c", "i18n.commitEncoding=utf-8") + $GitArgs
        $out = & git @allArgs 2>&1
        $ec = $LASTEXITCODE
        $ErrorActionPreference = $old
        $lines = @($out | ForEach-Object { "$_" }) | Where-Object {
            $_ -notmatch '^\*\* WARNING: connection is not using a post-quantum'
            $_ -notmatch '^\*\* This session may be vulnerable'
            $_ -notmatch '^\*\* The server may need to be upgraded'
        }
        $text = ($lines -join "`n")
        return @{ exitCode = $ec; output = $text.Trim() }
    } finally {
        Pop-Location
    }
}

function Invoke-Git {
    param([string]$Repo, [string[]]$GitArgs)
    $r = Invoke-GitRaw $Repo $GitArgs
    if ($r.exitCode -ne 0) { throw $r.output }
    return $r.output
}

function Test-GitRemoteTransportFailure([string]$Text) {
    if (-not $Text) { return $false }
    return [bool]($Text -match "REMOTE HOST IDENTIFICATION HAS CHANGED|Host key verification failed|Permission denied \(publickey\)|Could not read from remote repository|Could not resolve hostname|Connection timed out|Connection refused|Network is unreachable|unable to authenticate|Failed to connect|ssh: Could not|Operation not permitted")
}

function Get-OriginHostKeyHint([string]$Text) {
    if ($Text -match "REMOTE HOST IDENTIFICATION HAS CHANGED|Host key verification failed") {
        return "ssh-keygen -R gitverse.ru; ssh-keyscan -t rsa,ed25519 gitverse.ru >> ~/.ssh/known_hosts"
    }
    return $null
}

function Get-RemoteHeads([string]$Repo) {
    $raw = Invoke-Git $Repo @("ls-remote", "--heads", "origin")
    @($raw -split "`r?`n") |
        ForEach-Object { $_.Trim() } |
        ForEach-Object { if ($_ -match "refs/heads/(.+)$") { $Matches[1] } } |
        Where-Object { $_ }
}

function Get-LocalHeads([string]$Repo) {
    $raw = Invoke-Git $Repo @("for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes/origin", "refs/remotes/bitbucket")
    $names = New-Object System.Collections.Generic.HashSet[string]
    foreach ($line in @($raw -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })) {
        $name = $null
        if ($line -match "^refs/heads/(.+)$") {
            $name = $Matches[1]
        } elseif ($line -match "^refs/remotes/origin/(.+)$") {
            $name = $Matches[1]
        } elseif ($line -match "^refs/remotes/bitbucket/(.+)$") {
            $name = $Matches[1]
        }
        if ($name -and $name -ne "HEAD") { [void]$names.Add($name) }
    }
    return @($names)
}

function Get-GitCommitIfExists([string]$Repo, [string]$Ref) {
    $r = Invoke-GitRaw $Repo @("rev-parse", "--verify", "--quiet", "${Ref}^{commit}")
    if ($r.exitCode -eq 0 -and $r.output) { return $r.output.Trim() }
    return $null
}

function Resolve-LocalBranchRef([string]$Repo, [string]$Branch) {
    foreach ($candidate in @(
        "refs/heads/$Branch",
        "refs/remotes/origin/$Branch",
        "refs/remotes/bitbucket/$Branch"
    )) {
        if (Get-GitCommitIfExists $Repo $candidate) { return $candidate }
    }
    return $null
}

function Sync-Origin {
    param(
        [string]$Repo,
        [bool]$SkipFetch
    )

    $state = @{
        ok = $false
        mode = "local-fallback"
        error = $null
        hint = $null
    }

    if ($SkipFetch) {
        $state.mode = "skipped"
        return $state
    }

    $fetch = Invoke-GitRaw $Repo @("fetch", "origin")
    if ($fetch.exitCode -eq 0) {
        $state.ok = $true
        $state.mode = "fetched"
        return $state
    }

    $state.error = $fetch.output
    $state.hint = Get-OriginHostKeyHint $fetch.output
    if (-not (Test-GitRemoteTransportFailure $fetch.output)) {
        # Unknown fetch error: still try ls-remote before giving up on origin.
        $headsProbe = Invoke-GitRaw $Repo @("ls-remote", "--heads", "origin")
        if ($headsProbe.exitCode -eq 0) {
            $state.ok = $true
            $state.mode = "ls-remote"
            $state.error = $fetch.output
            return $state
        }
        $state.error = (@($fetch.output, $headsProbe.output) | Where-Object { $_ }) -join "`n"
        $state.hint = Get-OriginHostKeyHint $state.error
    }
    return $state
}

function Get-AvailableHeads {
    param(
        [string]$Repo,
        [hashtable]$OriginState
    )

    if ($OriginState.ok) {
        try {
            return @(Get-RemoteHeads $Repo)
        } catch {
            $OriginState.ok = $false
            $OriginState.mode = "local-fallback"
            $OriginState.error = "$_"
            $OriginState.hint = Get-OriginHostKeyHint "$_"
        }
    }
    return @(Get-LocalHeads $Repo)
}

function Get-ReleaseBranches([string[]]$Heads) {
    $Heads | Where-Object { $_ -match "^(release|releases)/" } |
        Sort-Object {
            $v = $_ -replace "^(release|releases)/", ""
            try { [version]$v } catch { [version]"0.0.0" }
        } -Descending
}

function Get-TaskBranches([string[]]$Heads, [string]$Num, [string[]]$Legacy = @()) {
    $exact = @("features/#$Num", "bugfixes/#$Num")
    $jiraExact = @($exact | Where-Object { $Heads -contains $_ })

    # Imported Bitbucket tasks kept the original issue number in branch names,
    # so refs like features/#1642 belong to Jira CT-2533.
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

function Test-LegacyBranch([string]$Branch, [string[]]$Legacy) {
    foreach ($ln in $Legacy) {
        if (-not $ln) { continue }
        $esc = [regex]::Escape($ln)
        if ($Branch -match "(^|[/#_-])$esc([^0-9]|$)") { return $true }
    }
    return $false
}

function Get-RemoteBranchSha([string]$Repo, [string]$Branch) {
    $r = Invoke-GitRaw $Repo @("ls-remote", "origin", "refs/heads/$Branch")
    if ($r.exitCode -ne 0) { throw $r.output }
    $escaped = [regex]::Escape($Branch)
    $line = @($r.output -split "`r?`n") | Where-Object { $_ -match "refs/heads/$escaped`$" } | Select-Object -First 1
    if (-not $line) { throw "Remote branch not found: $Branch" }
    return ($line -split "\s+")[0].Trim()
}

function Resolve-ReleaseFromBranchSuffix([string]$Branch, [string[]]$Heads) {
    if ($Branch -match "_for_([\d.]+)$") {
        $ver = $Matches[1]
    } elseif ($Branch -match "_for(\d+)$") {
        $digits = $Matches[1]
        if ($digits.Length -ge 4) {
            $ver = "$($digits[0]).$($digits[1]).$($digits[2]).$($digits.Substring(3))"
        } else {
            return $null
        }
    } else {
        return $null
    }

    foreach ($candidate in @("release/$ver", "releases/$ver")) {
        if ($Heads -contains $candidate) { return $candidate }
    }
    return $null
}

function Read-TaskTitle([string]$Repo, [string]$Num) {
    $path = Join-Path $Repo ".doc/tasks/$Num/task.md"
    if (-not (Test-Path $path)) { return $null }
    $content = Get-Content $path -Raw -Encoding UTF8
    if ($content -match "(?m)^#\s+Issue\s+#\d+:\s*(.+)$") { return $Matches[1].Trim() }
    return $null
}

function Read-TaskBitbucketIssues([string]$Repo, [string]$Num) {
    $path = Join-Path $Repo ".doc/tasks/$Num/task.md"
    if (-not (Test-Path $path)) { return @() }
    $content = Get-Content $path -Raw -Encoding UTF8
    $found = New-Object System.Collections.Generic.List[string]
    if ($content -match '(?m)^\|\s*Bitbucket\s*\|\s*(.+?)\s*\|') {
        foreach ($part in ($Matches[1] -split '[,\s]+')) {
            if ($part -match '^\d+$') { $found.Add($part) }
        }
    }
    foreach ($m in [regex]::Matches($content, '(?i)Imported[ \t]+from[ \t]+<?https?://(?:www\.)?bitbucket\.org/[^\s/]+/[^\s/]+/issues/(\d+)')) {
        $found.Add($m.Groups[1].Value)
    }
    return @($found | Select-Object -Unique)
}

function Resolve-TaskBranch {
    param(
        [string]$Num,
        [string]$Explicit,
        [hashtable]$Branches,
        [string]$CurrentBranch
    )

    if ($Explicit) { return $Explicit }

    $pattern = [regex]::Escape("#$Num")
    if ($CurrentBranch -match $pattern) { return $CurrentBranch }

    if ($Branches.exact.Count -eq 1) { return $Branches.exact[0] }
    if ($Branches.exact.Count -gt 1) { return $null }

    if ($Branches.variants.Count -eq 1 -and $Branches.exact.Count -eq 0) {
        return $Branches.variants[0]
    }

    return $null
}

function Resolve-ReleaseBranch {
    param(
        [string]$Explicit,
        [string]$TaskBranch,
        [string[]]$Heads,
        [object]$Config
    )

    if ($Explicit) { return $Explicit }

    $fromSuffix = Resolve-ReleaseFromBranchSuffix $TaskBranch $Heads
    if ($fromSuffix) { return $fromSuffix }

    foreach ($c in @($Config.releaseBranch) + @($Config.releaseBranchFallbacks)) {
        if ($Heads -contains $c) { return $c }
    }

    $releases = @(Get-ReleaseBranches $Heads)
    if ($releases.Count -gt 0) { return $releases[0] }

    return $null
}

function Ensure-BranchAvailable {
    param(
        [string]$Repo,
        [string]$Branch,
        [string]$Label,
        [hashtable]$OriginState
    )

    if ($OriginState.ok) {
        $localRef = "refs/tmp/task-diff/$Label"
        $r = Invoke-GitRaw $Repo @("fetch", "origin", "refs/heads/${Branch}:${localRef}")
        if ($r.exitCode -eq 0) { return $localRef }

        $OriginState.ok = $false
        $OriginState.mode = "local-fallback"
        $OriginState.error = $r.output
        $OriginState.hint = Get-OriginHostKeyHint $r.output
    }

    $resolved = Resolve-LocalBranchRef $Repo $Branch
    if ($resolved) { return $resolved }

    $detail = if ($OriginState.error) { $OriginState.error } else { "origin was not queried (SkipFetch or previous failure)" }
    throw "Branch not available locally and origin fetch failed: $Branch. $detail"
}

function Test-IsTaskCommit([string]$Subject, [string]$Num, [bool]$Strict, [string[]]$Legacy = @()) {
    if (Test-IsNumberedCommit $Subject $Num $Strict) { return $true }
    foreach ($ln in $Legacy) {
        if ($ln -and (Test-IsNumberedCommit $Subject $ln $Strict)) { return $true }
    }
    return $false
}

function Test-IsNumberedCommit([string]$Subject, [string]$Num, [bool]$Strict) {
    $s = $Subject.Trim()
    $escaped = [regex]::Escape($Num)
    # Commit subjects in this repo also use the `CT-2622` form. Without this
    # alternative those commits vanished from the task diff.
    if ($Strict) {
        return $s -match "^(#|CT-)?$escaped(\s| -|:|$)"
    } else {
        # Subjects are "2379 ...", "#2379 ...", "CT-2379 ...", a merge message
        # that names the branch, or an imported tracker URL such as
        # ".../issues/597" / ".../browse/CT-597". The last form used to be
        # missed, so legacy tasks got an empty diff.
        if ($s -match "(^|[\s#'])(#|CT-)?$escaped(\b|$)") { return $true }
        return $s -match "(issues|browse|pull)/(CT-)?$escaped(\b|$)"
    }
}

function Get-ReleaseVersionCommit {
    param([string]$Repo, [string]$ReleaseRef, [string]$ReleaseBranch)

    if ($ReleaseBranch -notmatch "/([\d.]+)$") { return $null }
    $ver = $Matches[1]
    $verEsc = [regex]::Escape($ver)
    $raw = Invoke-Git $Repo @("log", $ReleaseRef, "--format=%H %s", "--max-count=2000")
    foreach ($line in @($raw -split "`r?`n" | Where-Object { $_ })) {
        if ($line -match "^([0-9a-f]{40})\s+.+\s+$verEsc`$") { return $Matches[1] }
    }
    return $null
}

function Get-TaskCommitEntries {
    param([string]$Repo, [string]$Range, [string]$Num, [bool]$Strict, [string[]]$Legacy = @())

    # A merged task branch has no commits in release..HEAD. Search all refs,
    # then keep only commits that are actually in the task tip.
    $logArgs = @("log", "--no-merges", "--reverse", "--format=%H%x1f%h%x1f%an%x1f%ae%x1f%ai%x1f%s")
    if ($Range) { $logArgs += $Range } else { $logArgs += "--all" }
    $raw = Invoke-Git $Repo $logArgs

    $sep = [string][char]0x1f
    $entries = @()
    foreach ($line in @($raw -split "`r?`n" | Where-Object { $_ })) {
        $parts = $line -split [regex]::Escape($sep), 6
        if ($parts.Count -lt 6) { continue }
        if (-not (Test-IsTaskCommit $parts[5] $Num $Strict $Legacy)) { continue }

        $sha = $parts[0]
        $patch = (Invoke-GitRaw $Repo @("show", "--format=", "--no-color", "--no-renames", $sha)).output
        $stat = (Invoke-GitRaw $Repo @("show", "--format=", "--stat", "--no-color", $sha)).output

        $names = (Invoke-GitRaw $Repo @("show", "--format=", "--name-only", "--no-renames", $sha)).output
        $files = @($names -split "`r?`n" | Where-Object { $_ }) | Sort-Object -Unique

        $entries += [PSCustomObject]@{
            Sha = $sha
            ShortSha = $parts[1]
            Author = $parts[2]
            Email = $parts[3]
            Date = $parts[4]
            Subject = $parts[5]
            Stat = $stat
            Patch = $patch
            Files = $files
        }
    }
    return $entries
}

function Format-CommitDate([string]$GitDate) {
    if ($GitDate -match "^(\d{4})-(\d{2})-(\d{2}) (\d{2}:\d{2}:\d{2}) (.+)$") {
        return "$($Matches[3]).$($Matches[2]).$($Matches[1]) $($Matches[4]) $($Matches[5])"
    }
    return $GitDate
}

function Build-FilesMarkdown {
    param(
        [string]$Num,
        [string]$Title,
        [string]$TaskBranch,
        [object[]]$CommitEntries,
        [string[]]$UncommittedFiles
    )

    $now = (Get-Date).ToUniversalTime().ToString("dd.MM.yyyy HH:mm") + " UTC"
    $allFiles = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)

    foreach ($c in $CommitEntries) {
        foreach ($f in $c.Files) { [void]$allFiles.Add($f) }
    }
    foreach ($f in $UncommittedFiles) { [void]$allFiles.Add($f) }

    $sorted = @($allFiles | Sort-Object)
    $lines = New-Object System.Collections.Generic.List[string]

    $lines.Add("# Files Issue #$Num")
    if ($Title) { $lines.Add("**$Title**") }
    $lines.Add("")
    $lines.Add("| Field | Value |")
    $lines.Add("| --- | --- |")
    $lines.Add("| Generated | $now |")
    $lines.Add('| Task branch | `' + $TaskBranch + '` |')
    $lines.Add("| Task commits | $(@($CommitEntries).Count) |")
    $lines.Add("| Unique files | $(@($sorted).Count) |")
    $lines.Add("")
    $lines.Add("> Flat list for agent: all paths touched by task commits and uncommitted changes.")
    $lines.Add("")

    $lines.Add("## All files")
    $lines.Add("")
    if (@($sorted).Count -eq 0) {
        $lines.Add("_None._")
    } else {
        foreach ($f in $sorted) { $lines.Add($f) }
    }
    $lines.Add("")

    if ($CommitEntries.Count -gt 0) {
        $lines.Add("## By commit")
        $lines.Add("")
        foreach ($c in $CommitEntries) {
            $d = Format-CommitDate $c.Date
            $lines.Add("### ``$($c.ShortSha)`` | $d | $($c.Author)")
            $lines.Add("")
            if (@($c.Files).Count -eq 0) {
                $lines.Add("_No files._")
            } else {
                foreach ($f in $c.Files) { $lines.Add($f) }
            }
            $lines.Add("")
        }
    }

    if (@($UncommittedFiles).Count -gt 0) {
        $localNow = (Get-Date).ToString("dd.MM.yyyy HH:mm:ss K")
        $lines.Add("## Uncommitted")
        $lines.Add("")
        $lines.Add("### (working tree) | $localNow")
        $lines.Add("")
        foreach ($f in $UncommittedFiles) { $lines.Add($f) }
    }

    return ($lines -join "`n")
}

function Build-DiffMarkdown {
    param(
        [string]$Num,
        [string]$Title,
        [string]$TaskBranch,
        [string]$ReleaseBranch,
        [string]$MergeBase,
        [string]$TaskTip,
        [object[]]$CommitEntries,
        [string]$UncommittedDiff,
        [bool]$HasUncommitted,
        [string]$BranchMode = "branch",
        [string[]]$LegacyNumbers = @()
    )

    $now = (Get-Date).ToUniversalTime().ToString("dd.MM.yyyy HH:mm") + " UTC"
    $lines = New-Object System.Collections.Generic.List[string]

    $lines.Add("# Diff Issue #$Num")
    if ($Title) { $lines.Add("**$Title**") }
    $lines.Add("")
    $lines.Add("| Field | Value |")
    $lines.Add("| --- | --- |")
    $lines.Add("| Generated | $now |")
    $lines.Add('| Branch mode | `' + $BranchMode + '` |')
    $lines.Add('| Task branch | `' + $TaskBranch + '` |')
    if (@($LegacyNumbers).Count -gt 0) {
        $lines.Add('| Legacy numbers | `' + (@($LegacyNumbers) -join ', ') + '` |')
    }
    $lines.Add('| Release base | `' + $ReleaseBranch + '` |')
    $mbShort = if ($MergeBase) { $MergeBase.Substring(0, [Math]::Min(10, $MergeBase.Length)) } else { "-" }
    $ttShort = if ($TaskTip) { $TaskTip.Substring(0, [Math]::Min(10, $TaskTip.Length)) } else { "-" }
    $lines.Add('| Merge-base | `' + $mbShort + '` |')
    $lines.Add('| Task tip | `' + $ttShort + '` |')
    $lines.Add("| Task commits | $($CommitEntries.Count) |")
    $uncomm = if ($HasUncommitted) { "yes" } else { "no" }
    $lines.Add("| Uncommitted changes | $uncomm |")
    $lines.Add("")
    $matchNote = if ($BranchMode -eq "any-ref") {
        "Task branch not found. Only commits whose **subject mentions** ``$Num`` anywhere in local refs."
    } elseif ($StrictMatch) {
        "Only commits whose **subject starts with** ``$Num`` or ``#$Num``."
    } else {
        "Only commits whose **subject mentions** ``$Num`` or ``#$Num`` (in range from merge-base / fork)."
    }
    if (@($LegacyNumbers).Count -gt 0) {
        $matchNote = $matchNote + " Legacy Bitbucket numbers also accepted: " + (@($LegacyNumbers) -join ', ') + "."
    }
    $lines.Add("> $matchNote")
    $lines.Add("> Each section below: commit id, date/time, author, then diff.")
    $lines.Add("")

    if ($CommitEntries.Count -gt 0) {
        $lines.Add("## Commits (index)")
        $lines.Add("")
        foreach ($c in $CommitEntries) {
            $d = Format-CommitDate $c.Date
            $lines.Add("- ``$($c.ShortSha)`` | $d | $($c.Author) | $($c.Subject)")
        }
        $lines.Add("")
    }

    $lines.Add("## Committed changes")
    $lines.Add("")

    if ($CommitEntries.Count -eq 0) {
        $lines.Add("_No task commits found in range._")
    } else {
        foreach ($c in $CommitEntries) {
            $d = Format-CommitDate $c.Date
            $lines.Add("### ``$($c.ShortSha)`` | $d | $($c.Author)")
            $lines.Add("")
            $lines.Add("**Commit:** ``$($c.Sha)``")
            $lines.Add("**Author:** $($c.Author) <$($c.Email)>")
            $lines.Add("**Date:** $d")
            $lines.Add("**Message:** $($c.Subject)")
            $lines.Add("")

            if ($c.Stat) {
                $lines.Add("**Files:**")
                $lines.Add("")
                $lines.Add('```')
                $lines.Add($c.Stat)
                $lines.Add('```')
                $lines.Add("")
            }

            if ($c.Patch) {
                $lines.Add("**Diff:**")
                $lines.Add("")
                $lines.Add('```diff')
                $lines.Add($c.Patch)
                $lines.Add('```')
            } else {
                $lines.Add("_Empty patch (merge/rename only)._")
            }
            $lines.Add("")
        }
    }

    $lines.Add("## Uncommitted changes")
    $lines.Add("")
    if ($HasUncommitted -and $UncommittedDiff) {
        $localNow = (Get-Date).ToString("dd.MM.yyyy HH:mm:ss K")
        $lines.Add("### (working tree) | $localNow | local uncommitted")
        $lines.Add("")
        $lines.Add('```diff')
        $lines.Add($UncommittedDiff)
        $lines.Add('```')
    } else {
        $lines.Add("_None._")
    }

    return ($lines -join "`n")
}

# --- main ---

$repo = Get-RepoRoot -StartPath $(if ($RepoPath) { $RepoPath } else { (Get-Location).Path })
if (-not $ConfigPath) {
    foreach ($candidate in @(
        (Join-Path $repo ".cursor/skills/task-router/children/gototask/config.json"),
        (Join-Path $repo ".codex/skills/task-router/children/gototask/config.json")
    )) {
        if (Test-Path $candidate) {
            $ConfigPath = $candidate
            break
        }
    }
}
if (-not $ConfigPath -or -not (Test-Path $ConfigPath)) {
    throw "gototask config.json not found"
}
$config = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json

$originState = Sync-Origin -Repo $repo -SkipFetch $SkipFetch.IsPresent
$heads = @(Get-AvailableHeads -Repo $repo -OriginState $originState)
$currentBranch = Invoke-Git $repo @("branch", "--show-current")
$taskTitle = Read-TaskTitle $repo $TaskNumber
$legacyNumbers = @(Read-TaskBitbucketIssues $repo $TaskNumber)
$branches = Get-TaskBranches $heads $TaskNumber $legacyNumbers

$taskBranch = Resolve-TaskBranch -Num $TaskNumber -Explicit $TaskBranch -Branches $branches -CurrentBranch $currentBranch

$inspect = @{
    action = $Action
    taskNumber = $TaskNumber
    repoPath = $repo
    currentBranch = $currentBranch
    taskTitle = $taskTitle
    legacyNumbers = @($legacyNumbers)
    taskBranches = $branches
    releaseBranches = @(Get-ReleaseBranches $heads)
    resolvedTaskBranch = $taskBranch
    branchMode = $(if ($taskBranch) { "branch" } else { "any-ref" })
    resolvedReleaseBranch = Resolve-ReleaseBranch -Explicit $ReleaseBranch -TaskBranch $taskBranch -Heads $heads -Config $config
    originSync = $originState.mode
    originError = $originState.error
    originHint = $originState.hint
    needsUserInput = @()
}

if (-not $taskBranch) {
    if ($branches.exact.Count -gt 1 -or ($branches.variants.Count -gt 0 -and $branches.exact.Count -eq 0)) {
        $inspect.needsUserInput += "select_task_branch"
    } else {
        $inspect.needsUserInput += "task_branch_not_found"
    }
}

if ($Action -eq "inspect") {
    Write-Json $inspect
    exit 0
}

# -Mode ahead narrows the diff to commits that are only on the task branch.
# -NoReleaseBase drops the (possibly distant) release merge-base and diffs
# against the task branch fork point instead. Both switches were documented in
# SKILL.md but had no effect before.
$aheadMode = $AheadOnly -or ($Mode -eq "ahead")

$branchMode = "branch"
$alreadyInRelease = $null
$collectUncommitted = $false

if (-not $taskBranch) {
    if ($aheadMode) {
        throw "Ahead mode requires a resolved task branch for #$TaskNumber. Run -Action inspect or pass -TaskBranch."
    }

    # Old and already merged tasks may have no branch ref at all. Their commits
    # still exist in release history, so fall back to a subject search over all
    # local refs and mark the result explicitly instead of failing.
    $branchMode = "any-ref"
    $releaseBranch = Resolve-ReleaseBranch -Explicit $ReleaseBranch -TaskBranch "" -Heads $heads -Config $config
    $releaseRef = $null
    if ($releaseBranch) {
        try {
            $releaseRef = Ensure-BranchAvailable -Repo $repo -Branch $releaseBranch -Label "release" -OriginState $originState
        } catch {
            $releaseBranch = $null
        }
    }
    $taskRef = $null
    $taskTip = ""
    $mergeBase = ""
    $commitEntries = @(Get-TaskCommitEntries $repo "" $TaskNumber $StrictMatch $legacyNumbers)
    if ($releaseRef) {
        $alreadyInRelease = @($commitEntries | Where-Object {
            (Invoke-GitRaw $repo @("merge-base", "--is-ancestor", $_.Sha, $releaseRef)).exitCode -eq 0
        }).Count
    }
} else {
    $collectUncommitted = ($currentBranch -eq $taskBranch)
    $releaseBranch = Resolve-ReleaseBranch -Explicit $ReleaseBranch -TaskBranch $taskBranch -Heads $heads -Config $config
    if (-not $releaseBranch) {
        throw "Release branch not resolved. Pass -ReleaseBranch."
    }

    $releaseRef = Ensure-BranchAvailable -Repo $repo -Branch $releaseBranch -Label "release" -OriginState $originState

    if ($currentBranch -eq $taskBranch) {
        $taskRef = "HEAD"
        $taskTip = Invoke-Git $repo @("rev-parse", "HEAD")
    } else {
        $taskRef = Ensure-BranchAvailable -Repo $repo -Branch $taskBranch -Label "task" -OriginState $originState
        $taskTip = Invoke-Git $repo @("rev-parse", $taskRef)
    }

    if ($ForkCommit) {
        $forkSha = (Invoke-GitRaw $repo @("rev-parse", "--verify", $ForkCommit)).output.Trim()
        if (-not $forkSha) { throw "Fork commit not found: $ForkCommit" }
        $mergeBase = $forkSha
    } elseif ($NoReleaseBase) {
        # Fork point from the upstream remote-tracking ref; falls back to the
        # release merge-base when the task branch is not published yet.
        $upstreamRef = "refs/remotes/origin/$taskBranch"
        $hasUpstream = (Invoke-GitRaw $repo @("rev-parse", "--verify", "--quiet", $upstreamRef)).output.Trim()
        if ($hasUpstream) {
            $mergeBase = Invoke-Git $repo @("merge-base", $upstreamRef, $taskRef)
        } else {
            $mergeBase = Invoke-Git $repo @("merge-base", $releaseRef, $taskRef)
        }
    } else {
        $mergeBase = Invoke-Git $repo @("merge-base", $releaseRef, $taskRef)
    }

    $commitRange = "$mergeBase..$taskRef"
    $commitEntries = @(Get-TaskCommitEntries $repo $commitRange $TaskNumber $StrictMatch $legacyNumbers)

    # Release may already contain merged task PRs — merge-base moves forward and hides earlier task commits.
    # In `ahead` mode we deliberately keep the plain merge-base: the caller asked
    # only for commits that are not yet in the release.
    if (-not $ForkCommit -and -not $aheadMode) {
        $releaseVersion = Get-ReleaseVersionCommit $repo $releaseRef $releaseBranch
        if ($releaseVersion) {
            $versionEntries = @(Get-TaskCommitEntries $repo "$releaseVersion..$taskRef" $TaskNumber $StrictMatch $legacyNumbers)
            if ($versionEntries.Count -gt $commitEntries.Count) {
                $mergeBase = $releaseVersion
                $commitRange = "$mergeBase..$taskRef"
                $commitEntries = $versionEntries
            }
        }
        # Still empty: the task is fully merged into the release, so release..HEAD
        # has no task commits. Collect ancestors of the task tip from all refs.
        if ($commitEntries.Count -eq 0) {
            $allEntries = @(Get-TaskCommitEntries $repo "" $TaskNumber $StrictMatch $legacyNumbers)
            $commitEntries = @($allEntries | Where-Object {
                (Invoke-GitRaw $repo @("merge-base", "--is-ancestor", $_.Sha, $taskRef)).exitCode -eq 0
            })
        }
    }
}

$uncommittedDiff = ""
if ($aheadMode) {
    # `ahead` answers "what is not on the release yet", so working-tree noise
    # must not be mixed into the result.
    $uncommittedDiff = ""
}
$uncommittedFiles = @()
$hasUncommitted = $false
if ($collectUncommitted) {
    $uncommittedDiff = (Invoke-GitRaw $repo @("diff", "HEAD")).output
    $hasUncommitted = [bool]$uncommittedDiff
    $uncommittedNames = (Invoke-GitRaw $repo @("diff", "--name-only", "HEAD")).output
    $uncommittedFiles = @($uncommittedNames -split "`r?`n" | Where-Object { $_ })

    # Untracked files. The old filter kept only sql/migrations and tests, so a
    # brand-new source file never reached the diff and looked like it did not
    # exist. Keep task-relevant paths while excluding local agent noise.
    $untrackedRaw = (Invoke-GitRaw $repo @("ls-files", "--others", "--exclude-standard")).output
    $untrackedCandidates = @($untrackedRaw -split "`r?`n" | Where-Object { $_ })
    $untrackedIgnore = '^(\.doc/\.jira/|\.doc/tasks/|\.doc/qa/|node_modules/|\.idea/|vendor/)'
    $relevantUntracked = @($untrackedCandidates | Where-Object {
        $_ -notmatch $untrackedIgnore
    })
    $skippedUntracked = @($untrackedCandidates | Where-Object { $_ -match $untrackedIgnore })
    foreach ($uf in $relevantUntracked) {
        if ($uncommittedFiles -notcontains $uf) {
            $uncommittedFiles += $uf
        }
        $ufDiff = (Invoke-GitRaw $repo @("diff", "--no-index", "--", "/dev/null", $uf)).output
        if ($ufDiff) {
            if ($uncommittedDiff) { $uncommittedDiff += "`n" }
            $uncommittedDiff += $ufDiff
        }
    }
    $hasUncommitted = [bool]($uncommittedDiff -or ($uncommittedFiles.Count -gt 0))
}

$branchDisplay = if ($taskBranch) { $taskBranch } else { "any-ref" }

$markdown = Build-DiffMarkdown `
    -Num $TaskNumber `
    -Title $taskTitle `
    -TaskBranch $branchDisplay `
    -ReleaseBranch $releaseBranch `
    -MergeBase $mergeBase `
    -TaskTip $taskTip `
    -CommitEntries $commitEntries `
    -UncommittedDiff $uncommittedDiff `
    -HasUncommitted $hasUncommitted `
    -BranchMode $branchMode `
    -LegacyNumbers $legacyNumbers

$outDir = Join-Path $repo ".doc/tasks/$TaskNumber"
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir -Force | Out-Null }
$outPath = Join-Path $outDir "diff.md"
$filesPath = Join-Path $outDir "diff.files.md"
Write-Utf8File $outPath $markdown

$filesMarkdown = Build-FilesMarkdown `
    -Num $TaskNumber `
    -Title $taskTitle `
    -TaskBranch $branchDisplay `
    -CommitEntries $commitEntries `
    -UncommittedFiles $uncommittedFiles
Write-Utf8File $filesPath $filesMarkdown

$uniqueFileCount = @(
    @($commitEntries | ForEach-Object { $_.Files })
    @($uncommittedFiles)
) | ForEach-Object { $_ } | Where-Object { $_ } | Sort-Object -Unique

Write-Json @{
    ok = $true
    action = "generate"
    taskNumber = $TaskNumber
    path = $outPath
    filesPath = $filesPath
    taskBranch = $branchDisplay
    branchMode = $branchMode
    legacyNumbers = @($legacyNumbers)
    releaseBranch = $releaseBranch
    mergeBase = $mergeBase
    commitCount = $commitEntries.Count
    fileCount = (@($uniqueFileCount)).Count
    alreadyInRelease = $alreadyInRelease
    aheadOfRelease = $(if ($null -ne $alreadyInRelease) { $commitEntries.Count - $alreadyInRelease } else { $null })
    commits = @($commitEntries | ForEach-Object { $_.ShortSha })
    hasUncommitted = $hasUncommitted
    originSync = $originState.mode
    originError = $originState.error
    originHint = $originState.hint
    diffBytes = [System.Text.Encoding]::UTF8.GetByteCount($markdown)
    filesBytes = [System.Text.Encoding]::UTF8.GetByteCount($filesMarkdown)
}

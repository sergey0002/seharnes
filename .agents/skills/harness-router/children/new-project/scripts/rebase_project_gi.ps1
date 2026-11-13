#Requires -Version 5.1
<#
.SYNOPSIS
  Локальный git exclude (+ опционально skip-worktree) для AI-kit.

.DESCRIPTION
  Канон: .doc/rebase_project.md (секция local exclude).
  Запуск из корня проекта (где .git), либо укажите -RepoRoot.

  Не коммитится: пишет только .git/info/exclude и флаги index.

.EXAMPLE
  cd C:\laragon\www\myproject
  powershell -NoProfile -ExecutionPolicy Bypass -File .doc\rebase_project_gi.ps1

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .doc\rebase_project_gi.ps1 -RepoRoot "C:\laragon\www\myproject" -Force
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = '',
    [switch]$Force,
    [switch]$NoSkipWorktree
)

$ErrorActionPreference = 'Stop'

function Write-Ok([string]$m) { Write-Host "    OK: $m" -ForegroundColor Green }
function Write-Warn2([string]$m) { Write-Host "    WARN: $m" -ForegroundColor Yellow }
function Write-Step([string]$m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Write-Fail([string]$m) { Write-Host "    FAIL: $m" -ForegroundColor Red }

function Resolve-RepoRoot {
    param([string]$Explicit)
    if ($Explicit) {
        $r = [System.IO.Path]::GetFullPath($Explicit)
        if (-not (Test-Path (Join-Path $r '.git'))) {
            throw "Нет .git в -RepoRoot: $r"
        }
        return $r
    }
    # скрипт лежит в .doc/ → родитель часто корень репо
    $scriptDir = $PSScriptRoot
    if ($scriptDir) {
        $parent = Split-Path -Parent $scriptDir
        if ((Split-Path -Leaf $scriptDir) -eq '.doc' -and (Test-Path (Join-Path $parent '.git'))) {
            return $parent
        }
    }
    $cwd = (Get-Location).Path
    if (Test-Path (Join-Path $cwd '.git')) { return $cwd }
    throw "Не найден корень git. cd в корень проекта (где .git) или укажите -RepoRoot. cwd=$cwd"
}

function Get-ExcludeBlock {
    return @"
# Local developer excludes (rebase_project_gi.ps1 / rebase_project.md)
# Зеркала - реальные копии: исключаются все 7 сред, не только часть.
/.cursor/
/.codex/
/.agents/
/.kilo/
/.qoder/
/.qwen/
/.antigravity/
/.gemini/
/.doc/
/.serena/
/.playwright-mcp/
/AGENTS.md
/php_error.log
.kilocode/
kilo.json

# Local dev tooling tree (new convention)
/.tools/

# docker-dev local overrides (legacy tools/)
/tools/docker-dev/README.md
/tools/docker-dev/compose.yaml
/tools/docker-dev/php-apache/Dockerfile
/tools/docker-dev/php-apache/apache/

# Sourcegraph local stack
/sourcegraph-local/

# Local Codeception credentials
/tools/codeception/tests/Acceptance/FirstCest.php
"@
}

function Write-GitExcludeLocal {
    param([string]$Root, [switch]$ForceRewrite)
    $gitInfo = Join-Path $Root '.git\info'
    New-Item -ItemType Directory -Path $gitInfo -Force | Out-Null
    $excludePath = Join-Path $gitInfo 'exclude'
    $block = Get-ExcludeBlock
    $marker = 'rebase_project_gi.ps1'

    if ((Test-Path $excludePath) -and -not $ForceRewrite) {
        $existing = Get-Content $excludePath -Raw -ErrorAction SilentlyContinue
        if ($existing -and ($existing -match [regex]::Escape($marker) -or $existing -match 'export-rebase-project')) {
            # Never rewrite the developer's exclude file. Only add lines that a
            # older block predates.
            $missing = @()
            if ($existing -notmatch '(?m)^/\.qoder/$') { $missing += '/.qoder/' }
            if ($existing -notmatch '(?m)^/\.qwen/$') { $missing += '/.qwen/' }
            if ($missing.Count -gt 0) {
                $insert = ($missing -join "`n")
                $updated = $existing -replace '(?m)^/\.kilo/$', "/.kilo/`n$insert"
                if ($updated -ne $existing) {
                    $utf8 = New-Object System.Text.UTF8Encoding($false)
                    [System.IO.File]::WriteAllText($excludePath, $updated, $utf8)
                    Write-Ok "added $($missing -join ', ') to existing exclude -> $excludePath"
                    return $excludePath
                }
            }
            Write-Ok "exclude уже есть (маркер) -> $excludePath  (-Force чтобы перезаписать)"
            return $excludePath
        }
        if ($existing -and $existing.Trim().Length -gt 0) {
            Add-Content -Path $excludePath -Value "`n$block" -Encoding UTF8
            Write-Ok "appended exclude block -> $excludePath"
            return $excludePath
        }
    }

    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($excludePath, $block.TrimStart() + "`n", $utf8)
    Write-Ok "wrote $excludePath"
    return $excludePath
}

function Set-SkipWorktreeLocal {
    param([string]$Root)
    $files = @(
        'docker-dev/compose.yaml',
        'docker-dev/README.md',
        'docker-dev/php-apache/Dockerfile',
        'codeception/tests/Acceptance/FirstCest.php'
    )
    Push-Location $Root
    try {
        foreach ($suffix in $files) {
            $rel = "tools/$suffix"
            $full = Join-Path $Root ($rel -replace '/', [IO.Path]::DirectorySeparatorChar)
            if (-not (Test-Path -LiteralPath $full)) {
                $rel = ".tools/$suffix"
                $full = Join-Path $Root ($rel -replace '/', [IO.Path]::DirectorySeparatorChar)
            }
            if (-not (Test-Path -LiteralPath $full)) {
                Write-Warn2 "skip-worktree: нет файла tools/$suffix и .tools/$suffix"
                continue
            }
            $tracked = & git ls-files -- "$rel" 2>$null
            if (-not $tracked) {
                if ($rel.StartsWith('.tools/')) {
                    continue
                }
                Write-Warn2 "skip-worktree: не в index (untracked) $rel"
                continue
            }
            & git update-index --skip-worktree -- "$rel"
            if ($LASTEXITCODE -eq 0) {
                Write-Ok "skip-worktree $rel"
            } else {
                Write-Warn2 "skip-worktree failed: $rel"
            }
        }
    } finally {
        Pop-Location
    }
}

function Test-ExcludeSmoke {
    param([string]$Root)
    Push-Location $Root
    try {
        $probes = @('.cursor/mcp.json', '.doc/harnes/doc_rules.md', 'AGENTS.md', 'sourcegraph-local/README.md')
        $ok = 0
        foreach ($p in $probes) {
            if (-not (Test-Path -LiteralPath (Join-Path $Root ($p -replace '/', [IO.Path]::DirectorySeparatorChar)))) {
                Write-Warn2 "smoke skip (нет на диске): $p"
                continue
            }
            $out = & git check-ignore -v -- "$p" 2>$null
            if ($out) {
                Write-Ok "check-ignore: $out"
                $ok++
            } else {
                Write-Fail "не игнорируется: $p"
            }
        }
        Write-Host ""
        Write-Host "skip-worktree (ожидается S в начале):" -ForegroundColor Cyan
        & git ls-files -v 2>$null | Where-Object { $_ -match '^[a-zS] ' -and $_ -match '\.?tools/(docker-dev|codeception)' }
        return $ok
    } finally {
        Pop-Location
    }
}

# --- main ---
$root = Resolve-RepoRoot -Explicit $RepoRoot
Write-Step "RepoRoot: $root"

Write-Step ".git/info/exclude"
$null = Write-GitExcludeLocal -Root $root -ForceRewrite:$Force

if (-not $NoSkipWorktree) {
    Write-Step "skip-worktree (локальные оверрайды)"
    Set-SkipWorktreeLocal -Root $root
} else {
    Write-Warn2 'NoSkipWorktree: флаги не ставились'
}

Write-Step "проверка"
$n = Test-ExcludeSmoke -Root $root

Write-Host ""
Write-Host "REBASE_GI_DONE root=$root exclude_hits=$n" -ForegroundColor Green
Write-Host "Канон: .doc\rebase_project.md (локальный git exclude)"
exit 0

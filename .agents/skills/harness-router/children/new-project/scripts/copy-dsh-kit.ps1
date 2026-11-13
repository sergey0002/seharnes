<#
.SYNOPSIS
    Копирует DSH kit (.dsh) из образца в Target при переносе проекта.

.DESCRIPTION
    Переносит только переносимую часть DSH: skills, adapters, scripts, tests и
    models.overlay.json. Сгенерированные project.patch.yml и DSH-RULES.md не
    копируются: их заново создаёт sync-agent-views.sh на Target из .cursor.

    Kit в git не хранится, поэтому переносится копированием, как .cursor и .codex.

.PARAMETER Source
    Корень проекта-образца.

.PARAMETER Target
    Корень нового проекта.

.PARAMETER Check
    Ничего не писать. Сравнить состав и содержимое kit на Target с Source.

.EXAMPLE
    pwsh -NoProfile -File .agents/skills/harness-router/children/new-project/scripts/copy-dsh-kit.ps1 -Source . -Target ..\newproject

.EXAMPLE
    pwsh -NoProfile -File .agents/skills/harness-router/children/new-project/scripts/copy-dsh-kit.ps1 -Source . -Target ..\newproject -Check
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Source,

    [Parameter(Mandatory = $true)]
    [string]$Target,

    [switch]$Check,
    [switch]$PreserveLocal
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-FullPath([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { throw 'dsh-kit: empty path' }
    $p = $Path.Trim()
    if (-not [System.IO.Path]::IsPathRooted($p)) {
        $p = Join-Path (Get-Location).Path $p
    }
    return [System.IO.Path]::GetFullPath($p)
}

$sourceRoot = Resolve-FullPath $Source
$targetRoot = Resolve-FullPath $Target
foreach ($root in @($sourceRoot, $targetRoot)) {
    $ancestor = $root
    while ($ancestor) {
        if ((Test-Path -LiteralPath $ancestor) -and ((Get-Item -LiteralPath $ancestor -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
            throw "dsh-kit: linked root or ancestor not supported: $ancestor"
        }
        $ancestor = Split-Path -Path $ancestor -Parent
    }
    if (Test-Path -LiteralPath $root) {
        $resolved = (Resolve-Path -LiteralPath $root).ProviderPath
        if ($root -eq $sourceRoot) { $sourceRoot = $resolved } else { $targetRoot = $resolved }
    }
}
$comparison = if ([System.IO.Path]::DirectorySeparatorChar -eq '\') { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
$sourcePrefix = $sourceRoot.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
$targetPrefix = $targetRoot.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
if ($sourceRoot.Equals($targetRoot, $comparison) -or $sourcePrefix.StartsWith($targetPrefix, $comparison) -or $targetPrefix.StartsWith($sourcePrefix, $comparison)) {
    throw 'dsh-kit: Source and Target must not overlap'
}
$srcDsh = Join-Path $sourceRoot '.dsh'
$dstDsh = Join-Path $targetRoot '.dsh'

if (-not (Test-Path -LiteralPath $srcDsh -PathType Container)) {
    Write-Host "dsh-kit: source .dsh not found: $srcDsh"
    exit 2
}

$kitDirs = @('skills', 'adapters', 'scripts', 'tests')
$kitFiles = @('models.overlay.json', 'kit.manifest.json')
function Assert-NoLinks([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { throw "dsh-kit: link not supported: $Path" }
    if ($item.PSIsContainer) {
        foreach ($child in @(Get-ChildItem -LiteralPath $Path -Force)) { Assert-NoLinks $child.FullName }
    }
}

foreach ($name in $kitDirs) {
    if (-not (Test-Path -LiteralPath (Join-Path $srcDsh $name) -PathType Container)) { throw "dsh-kit: missing source directory .dsh/$name" }
}
foreach ($name in $kitFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $srcDsh $name) -PathType Leaf)) { throw "dsh-kit: missing source file .dsh/$name" }
}
foreach ($root in @($srcDsh, $dstDsh)) {
    if ((Test-Path -LiteralPath $root) -and ((Get-Item -LiteralPath $root -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint)) { throw "dsh-kit: link not supported: $root" }
    foreach ($name in ($kitDirs + $kitFiles)) { Assert-NoLinks (Join-Path $root $name) }
}

$manifest = Get-Content -LiteralPath (Join-Path $srcDsh 'kit.manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $manifest.files -or @($manifest.files).Count -eq 0) { throw 'dsh-kit: empty source manifest' }
foreach ($rel in $manifest.files) {
    if ($rel -notmatch '^\.dsh/(skills|adapters|scripts|tests)/[^\\]+$|^\.dsh/(models\.overlay\.json|kit\.manifest\.json)$' -or $rel -match '(^|/)\.\.?(/|$)') { throw "dsh-kit: invalid manifest path: $rel" }
    if (-not (Test-Path -LiteralPath (Join-Path $sourceRoot $rel) -PathType Leaf)) { throw "dsh-kit: missing source manifest file: $rel" }
}

function Get-KitFiles([string]$Root, [bool]$ExcludeCache) {
    $map = [System.Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
    foreach ($name in $kitDirs) {
        $dir = Join-Path $Root $name
        if (-not (Test-Path -LiteralPath $dir -PathType Container)) { continue }
        foreach ($file in @(Get-ChildItem -LiteralPath $dir -Recurse -File -Force)) {
            $rel = $file.FullName.Substring($Root.Length).TrimStart('\', '/') -replace '\\', '/'
            if ($rel -match '^skills/[^/]+/SKILL\.md$' -and
                [System.IO.File]::ReadAllText($file.FullName).Contains('<!-- generated discovery wrapper; do not edit -->')) { continue }
            if ($ExcludeCache -and $rel -match '(^|/)(__pycache__|\.pytest_cache)(/|$)') { continue }
            $map.Add($rel, $file.FullName)
        }
    }
    foreach ($name in $kitFiles) {
        $file = Join-Path $Root $name
        if (Test-Path -LiteralPath $file -PathType Leaf) { $map.Add($name, $file) }
    }
    return ,$map
}

$sourceFiles = Get-KitFiles $srcDsh $true
if (-not $Check) {
    New-Item -ItemType Directory -Path $dstDsh -Force | Out-Null
    foreach ($name in $kitDirs) {
        $dest = Join-Path $dstDsh $name
        if ((Test-Path -LiteralPath $dest) -and -not $PreserveLocal) { Remove-Item -LiteralPath $dest -Recurse -Force }
        New-Item -ItemType Directory -Path $dest -Force | Out-Null
    }
    foreach ($rel in $sourceFiles.Keys) {
        $dest = Join-Path $dstDsh $rel
        New-Item -ItemType Directory -Path (Split-Path $dest -Parent) -Force | Out-Null
        Copy-Item -LiteralPath $sourceFiles[$rel] -Destination $dest -Force
    }
}
$targetFiles = Get-KitFiles $dstDsh $false
$differences = @()
foreach ($name in $kitDirs) {
    if (-not (Test-Path -LiteralPath (Join-Path $dstDsh $name) -PathType Container)) { $differences += "missing directory: $name" }
}
foreach ($rel in $sourceFiles.Keys) {
    if (-not $targetFiles.ContainsKey($rel)) { $differences += "missing: $rel" }
    elseif ((Get-FileHash -LiteralPath $sourceFiles[$rel] -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $targetFiles[$rel] -Algorithm SHA256).Hash) { $differences += "changed: $rel" }
}
foreach ($rel in $targetFiles.Keys) {
    if (-not $PreserveLocal -and -not $sourceFiles.ContainsKey($rel)) { $differences += "extra: $rel" }
}
if ($differences.Count -gt 0) {
    $differences | Sort-Object | ForEach-Object { Write-Host "dsh-kit: $_" }
    exit 1
}
Write-Host "dsh-kit: ok ($targetRoot)"
exit 0

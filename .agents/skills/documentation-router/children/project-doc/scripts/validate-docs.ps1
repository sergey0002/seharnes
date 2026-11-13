<#
.SYNOPSIS
    Валидация архитектурной документации: meta, обязательные секции, ссылки.
#>

param(
    [switch]$Fix,
    [string]$Path = '',
    [string]$Mask = '*.md'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_lib.ps1')

$projectRoot = (Get-Location).Path
$archDir = Join-Path $projectRoot '.doc\architecture'
$errors = [System.Collections.Generic.List[string]]::new()
$warnings = [System.Collections.Generic.List[string]]::new()
$ok = [System.Collections.Generic.List[string]]::new()
$fixed = [System.Collections.Generic.List[string]]::new()
$validStatuses = @('actual', 'outdated', 'draft', 'frozen')
$validTypes = @('architecture', 'rules', 'api', 'model', 'flow', 'config', 'index')

function Get-TargetDocs {
    if (-not $Path) {
        return @(Get-ChildItem -Path $archDir -Filter $Mask -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch '\\_map\\' -and $_.Name -notmatch '^_' })
    }

    $resolved = @()
    $candidate = Join-Path $projectRoot $Path
    $wildcard = ($Path -match '[\*\?\[\]]')
    if ($wildcard) {
        $resolved = @(Get-ChildItem -Path $candidate -File -ErrorAction SilentlyContinue)
    } elseif (Test-Path $candidate -PathType Container) {
        $resolved = @(Get-ChildItem -Path $candidate -Filter $Mask -Recurse -File -ErrorAction SilentlyContinue)
    } elseif (Test-Path $candidate -PathType Leaf) {
        $resolved = @((Get-Item -LiteralPath $candidate -ErrorAction Stop))
    } else {
        throw "Path not found: $Path"
    }

    return @($resolved | Where-Object {
        $full = ($_.FullName -replace '\\', '/')
        $_.Extension -ieq '.md' -and
        $full -notmatch '/_map/' -and
        $_.Name -notmatch '^_' -and
        $full -notmatch '/(_jsondoc|test-runs|vendor|screenshots|backups?|attachments)/' -and
        $_.Name -notmatch '^(task|diff|diff\.files|test|report|ask|audit|plan|plan-stage\d+|readme)\.md$'
    } | Sort-Object FullName -Unique)
}

$docs = @(Get-TargetDocs)

foreach ($doc in $docs) {
    $rel = Get-RelativePath -FullPath $doc.FullName
    $content = Read-TextFile -Path $doc.FullName
    if (-not $content) {
        $errors.Add("  ❌ $rel — пустой файл")
        continue
    }

    $docErrors = @()
    $docWarns = @()
    $isGeneratedTaskView = ($rel -match '(^|/)tasks/\d+/doc\.md$') -and
        ($content -match '(?m)^<!-- generated from task:')
    if (-not $isGeneratedTaskView) {
        $meta = Get-DocMeta -Path $doc.FullName
        if (-not $meta) {
            $docErrors += 'нет блока <!-- meta -->'
        } else {
            foreach ($field in @('type','status','updated')) {
                if (-not $meta.PSObject.Properties.Name.Contains($field) -or -not $meta.$field) {
                    $docErrors += "meta: нет поля '${field}:'"
                }
            }
            if ($meta.status -and $meta.status -notin $validStatuses) {
                $docWarns += "meta: неизвестный status $($meta.status)"
            }
            if ($meta.type -and $meta.type -notin $validTypes) {
                $docWarns += "meta: неизвестный type $($meta.type)"
            }
            if ($meta.updated -and $meta.updated -notmatch '^\d{4}-\d{2}-\d{2}$') {
                $docErrors += 'meta: updated не YYYY-MM-DD'
            }
        }

        $required = if ($doc.Name -ieq 'index.md' -or ($meta -and $meta.type -eq 'index')) {
            @('## Суть', '## Связи')
        } else {
            @('## Суть', '## Связи', '## Известные проблемы и ограничения', '## История изменений')
        }

        foreach ($section in $required) {
            if ($content -notmatch [regex]::Escape($section)) {
                $docErrors += "нет секции '$section'"
            }
        }
    }

    $linkScan = [regex]::Replace($content, '(?ms)^\s*```.*?^\s*```', '')
    $linkScan = [regex]::Replace($linkScan, '`[^`]*`', '')
    $linkMatches = [regex]::Matches($linkScan, '\[([^\]]+)\]\(([^)]+)\)')
    foreach ($m in $linkMatches) {
        $href = $m.Groups[2].Value
        if ($href -match '^(\.\.?/|\./).*\.md') {
            $hrefClean = $href -replace '#.*$', ''
            $target = [System.IO.Path]::GetFullPath((Join-Path $doc.DirectoryName $hrefClean))
            if (-not (Test-Path $target)) {
                $docErrors += "сломанная ссылка: $href"
            }
        }
    }

    if ($docErrors.Count -eq 0 -and $docWarns.Count -eq 0) {
        $ok.Add("  ✅ $rel")
    } else {
        foreach ($e in $docErrors) { $errors.Add("  ❌ $rel — $e") }
        foreach ($w in $docWarns) { $warnings.Add("  ⚠️  $rel — $w") }
    }
}

Write-Host ''
Write-Host '═══════════════════════════════════════' -ForegroundColor Cyan
Write-Host '  РЕЗУЛЬТАТЫ ВАЛИДАЦИИ' -ForegroundColor Cyan
Write-Host '═══════════════════════════════════════' -ForegroundColor Cyan
Write-Host ''
if ($fixed.Count -gt 0) { $fixed | ForEach-Object { Write-Host $_ -ForegroundColor Yellow } }
if ($errors.Count -gt 0) { Write-Host "❌ Ошибки ($($errors.Count))" -ForegroundColor Red; $errors | ForEach-Object { Write-Host $_ -ForegroundColor Red } }
if ($warnings.Count -gt 0) { Write-Host "⚠️  Предупреждения ($($warnings.Count))" -ForegroundColor Yellow; $warnings | ForEach-Object { Write-Host $_ -ForegroundColor Yellow } }
if ($ok.Count -gt 0) { Write-Host "✅ OK ($($ok.Count))" -ForegroundColor Green; $ok | ForEach-Object { Write-Host $_ -ForegroundColor Green } }
Write-Host ''
Write-Host "Итого: $($docs.Count) файлов | ❌ $($errors.Count) | ⚠️ $($warnings.Count) | ✅ $($ok.Count)" -ForegroundColor Cyan
exit $(if ($errors.Count -gt 0) { 1 } else { 0 })

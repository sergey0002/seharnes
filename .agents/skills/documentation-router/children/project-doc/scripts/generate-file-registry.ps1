<#
.SYNOPSIS
    Генерирует persistent registry покрытия файлов документацией.
#>

param([switch]$Quiet)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_lib.ps1')

function Escape-Tsv([string]$Value) {
    if ($null -eq $Value) { return '' }
    return ($Value -replace "`t", ' ' -replace "`r?`n", ' ').Trim()
}

function Read-TsvMap([string]$Path) {
    $map = @{}
    if (-not (Test-Path $Path)) { return $map }
    $rows = Get-Content $Path -ErrorAction SilentlyContinue
    if (-not $rows -or $rows.Count -lt 2) { return $map }
    $header = $rows[0] -split "`t"
    foreach ($line in $rows | Select-Object -Skip 1) {
        if (-not $line.Trim()) { continue }
        $parts = $line -split "`t", $header.Count
        $obj = [ordered]@{}
        for ($i = 0; $i -lt $header.Count; $i++) {
            $obj[$header[$i]] = if ($i -lt $parts.Count) { $parts[$i] } else { '' }
        }
        $pathKey = Normalize-RelativePath $obj['path']
        if ($pathKey) { $map[$pathKey] = [PSCustomObject]$obj }
    }
    return $map
}

$tracked = @(
    (Get-ProjectFiles -Extensions @('php','phtml','tpl','vue','js','ts','css','scss','sass','less','sql')) +
    (Get-ProjectFiles -Include @('composer.json','package.json','phpunit.xml','webpack.config.js','webpack.config.ts','.env.example'))
) | Sort-Object -Unique

# Safety Gate: не разрушать существующий реестр, если в текущей директории
# найдено подозрительно мало файлов по сравнению с тем, что уже есть в реестре.
# Это защищает от запуска вне git-репозитория проекта.
$existingPreview = Read-TsvMap -Path (Get-RegistryFilePath)
if ($existingPreview.Count -gt 100) {
    $threshold = [math]::Floor($existingPreview.Count * 0.5)
    if ($tracked.Count -lt $threshold) {
        Write-Host "⚠️  Safety Gate: найдено $($tracked.Count) файлов в текущей директории," -ForegroundColor Yellow
        Write-Host "   но в реестре уже $($existingPreview.Count) записей." -ForegroundColor Yellow
        Write-Host "   Похоже, скрипт запущен вне корня проекта или git недоступен." -ForegroundColor Yellow
        Write-Host "   Реестр не будет обновлён, чтобы не разрушить существующие данные." -ForegroundColor Yellow
        Write-Host "" -ForegroundColor Yellow
        Write-Host "   Если это намеренно — переименуйте/удалите file-registry.tsv и запустите снова." -ForegroundColor DarkGray
        exit 0
    }
}

$basenameToPath = @{}
$basenameCounts = @{}
foreach ($path in $tracked) {
    $bn = Split-Path -Leaf $path
    $basenameToPath[$bn] = $path
    if (-not $basenameCounts.ContainsKey($bn)) { $basenameCounts[$bn] = 0 }
    $basenameCounts[$bn]++
}

$docs = Get-ArchitectureDocs
$refMap = @{}
$domainMap = @{}
foreach ($doc in $docs) {
    $docName = Split-Path -Leaf $doc.FullName
    $businessKey = Get-DocBusinessKey -Path $doc.FullName
    foreach ($ref in (Get-DocCodeRefs -Path $doc.FullName)) {
        $resolved = $null
        if ($tracked -contains $ref) {
            $resolved = $ref
        } else {
            $bn = Split-Path -Leaf $ref
            if ($basenameCounts.ContainsKey($bn) -and $basenameCounts[$bn] -eq 1) {
                $resolved = $basenameToPath[$bn]
            }
        }

        if (-not $resolved) { continue }
        if (-not $refMap.ContainsKey($resolved)) {
            $refMap[$resolved] = [System.Collections.Generic.HashSet[string]]::new()
            $domainMap[$resolved] = [System.Collections.Generic.HashSet[string]]::new()
        }
        $null = $refMap[$resolved].Add($docName)
        if ($businessKey) { $null = $domainMap[$resolved].Add($businessKey) }
    }
}

$existing = Read-TsvMap -Path (Get-RegistryFilePath)
$today = Get-Date -Format 'yyyy-MM-dd'
$lines = [System.Collections.Generic.List[string]]::new()
$header = "path`tkind`tstatus`tdomain`tdoc_refs`tfirst_indexed`tlast_checked`tsource"
$lines.Add($header)

$indexedCount = 0
foreach ($path in $tracked) {
    $prev = if ($existing.ContainsKey($path)) { $existing[$path] } else { $null }
    $docsRef = @()
    if ($refMap.ContainsKey($path)) { $docsRef = @($refMap[$path] | Sort-Object) }
    $domains = @()
    if ($domainMap.ContainsKey($path)) { $domains = @($domainMap[$path] | Sort-Object) }


    $status = 'not_indexed'
    if ($docsRef.Count -gt 0) {
        $status = 'indexed'
    } elseif ($prev -and $prev.status -in @('manual','noise')) {
        $status = $prev.status
    }

    if ($status -eq 'indexed') { $indexedCount++ }

    $lines.Add((@(
        (Escape-Tsv $path),
        (Escape-Tsv (Get-FileKind -Path $path)),
        (Escape-Tsv $status),
        (Escape-Tsv $(if ($domains.Count -gt 0) { $domains[0] } elseif ($prev) { $prev.domain } else { '' })),
        (Escape-Tsv $(if ($docsRef.Count -gt 0) { $docsRef -join ';' } elseif ($prev) { $prev.doc_refs } else { '' })),
        (Escape-Tsv $(if ($prev -and $prev.first_indexed) { $prev.first_indexed } elseif ($status -eq 'indexed') { $today } else { '' })),
        (Escape-Tsv $today),
        (Escape-Tsv $(if ($prev -and $prev.source) { $prev.source } elseif ($docsRef.Count -gt 0) { 'merged' } else { 'map' }))
    ) -join "`t"))
}

$deletedCount = 0
foreach ($path in @($existing.Keys | Sort-Object)) {
    if ($tracked -contains $path) { continue }
    $prev = $existing[$path]
    $lines.Add((@(
        (Escape-Tsv $path),
        (Escape-Tsv $prev.kind),
        (Escape-Tsv 'deleted'),
        (Escape-Tsv $prev.domain),
        (Escape-Tsv $prev.doc_refs),
        (Escape-Tsv $prev.first_indexed),
        (Escape-Tsv $today),
        (Escape-Tsv $prev.source)
    ) -join "`t"))
    $deletedCount++
}

Write-Utf8File -Path (Get-RegistryFilePath) -Content ($lines -join "`r`n")
if (-not $Quiet) {
    $pct = if ($tracked.Count -gt 0) { [math]::Round(($indexedCount / $tracked.Count) * 100, 1) } else { 0 }
    Write-Host "✅ file-registry: .doc\architecture\_map\file-registry.tsv" -ForegroundColor Green
    Write-Host "   Покрытие: $indexedCount/$($tracked.Count) ($pct%)" -ForegroundColor Cyan
    if ($deletedCount -gt 0) { Write-Host "   Удаленных файлов (в истории): $deletedCount" -ForegroundColor Yellow }
}

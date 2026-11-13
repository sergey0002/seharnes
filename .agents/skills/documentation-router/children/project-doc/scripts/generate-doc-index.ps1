<#
.SYNOPSIS
    Генерирует лёгкий индекс architecture-документов для агентов.
#>

param([switch]$Quiet)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_lib.ps1')

function Escape-Tsv([string]$Value) {
    if ($null -eq $Value) { return '' }
    return ($Value -replace "`t", ' ' -replace "`r?`n", ' ').Trim()
}

$docs = Get-ArchitectureDocs
$out = Get-DocIndexFilePath
$lines = [System.Collections.Generic.List[string]]::new()
$header = "doc_path`th1`ttype`tstatus`ttags`trelated`tlast_updated`tbusiness_key"
$lines.Add($header)

foreach ($doc in $docs) {
    $meta = Get-DocMeta -Path $doc.FullName
    $rel = Get-RelativePath -FullPath $doc.FullName
    if ($rel -match '\.json$') { $rel = $rel -replace '\.json$', '.md' }
    $h1 = Get-DocFirstHeading -Path $doc.FullName
    $lines.Add((@(
        (Escape-Tsv $rel),
        (Escape-Tsv $h1),
        (Escape-Tsv $(if ($meta) { $meta.type } else { '' })),
        (Escape-Tsv $(if ($meta) { $meta.status } else { '' })),
        (Escape-Tsv $(if ($meta -and $meta.tags) { @($meta.tags) -join ';' } else { '' })),
        (Escape-Tsv $(if ($meta -and $meta.related) { @($meta.related) -join ';' } else { '' })),
        (Escape-Tsv $(if ($meta) { $meta.updated } else { '' })),
        (Escape-Tsv (Get-DocBusinessKey -Path $doc.FullName))
    ) -join "`t"))
}

Write-Utf8File -Path $out -Content ($lines -join "`r`n")
if (-not $Quiet) {
    Write-Host "✅ doc-index: .doc\architecture\_map\doc-index.tsv ($($docs.Count) docs)" -ForegroundColor Green
}

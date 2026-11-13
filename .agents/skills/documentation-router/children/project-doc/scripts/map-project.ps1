<#
.SYNOPSIS
    Builds project map for documentation and refreshes derived indexing artifacts.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_lib.ps1')

$projectRoot = (Get-Location).Path
$out = Join-Path $projectRoot (Join-Path '.doc' (Join-Path 'architecture' '_map'))
New-Item -ItemType Directory -Path $out -Force | Out-Null

function Get-FileScope([string]$RelativePath) {
    if ($RelativePath -match '^(scripts/plugins|admin/scripts/plugins|vendor|node_modules|dompdf)/' -or
        $RelativePath -match '\.min\.(js|css)$' -or
        $RelativePath -match '/phone-codes/') {
        return 'vendor'
    }
    return 'app'
}

function Get-FileStats {
    param(
        [Parameter(Mandatory)][string]$RelativePath,
        [string]$ClassPattern = '',
        [string]$FunctionPattern = ''
    )

    $text = Read-TextFile -Path (Join-Path $projectRoot $RelativePath)
    $lines = @()
    if ($text) {
        $lines = @($text -split "`r?`n")
        if ($lines.Count -gt 1 -and $lines[$lines.Count - 1] -eq '' -and $text.EndsWith("`n")) {
            $lines = @($lines[0..($lines.Count - 2)])
        }
    }

    $classes = 0
    $functions = 0
    foreach ($line in $lines) {
        if ($ClassPattern -and $line -match $ClassPattern) { $classes++ }
        if ($FunctionPattern -and $line -match $FunctionPattern) { $functions++ }
    }

    return [PSCustomObject]@{
        Path = $RelativePath
        Scope = Get-FileScope $RelativePath
        Loc = $lines.Count
        Classes = $classes
        Functions = $functions
    }
}

Write-Host 'Building project map...' -ForegroundColor Cyan
$allFiles = Get-ProjectFiles
$dirs = $allFiles | ForEach-Object { Split-Path $_ -Parent } | Where-Object { $_ -and ($_ -split '/').Count -le 6 } | Sort-Object -Unique
Write-Utf8File -Path (Join-Path $out 'tree.txt') -Content ($dirs -join "`r`n")

$phpFiles = @(Get-ProjectFiles -Extensions @('php'))
$vueFiles = @(Get-ProjectFiles -Extensions @('vue'))
$jsFiles  = @(Get-ProjectFiles -Extensions @('js','ts'))
$tplFiles = @(Get-ProjectFiles -Extensions @('tpl','phtml'))
$cssFiles = @(Get-ProjectFiles -Extensions @('css','scss','sass','less'))
$sqlFiles = @(Get-ProjectFiles -Extensions @('sql'))

$phpClassPattern = '^\s*(?:abstract\s+|final\s+)?(?:class|interface|trait)\s+[A-Za-z_]'
$phpFunctionPattern = '^\s*(?:(?:public|protected|private|static|abstract|final)\s+)*function\s+&?\s*[A-Za-z_]'
$jsClassPattern = '^\s*(?:export\s+)?(?:default\s+)?class\s+[A-Za-z_$]'
$jsFunctionPattern = '^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\b|^\s*(?:export\s+)?(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=\s*(?:async\s*)?(?:function\b|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)'
$cssClassPattern = '^\s*\.[A-Za-z_-]'

$phpStats = @($phpFiles | ForEach-Object {
    Get-FileStats -RelativePath $_ -ClassPattern $phpClassPattern -FunctionPattern $phpFunctionPattern
})
$phpMetrics = @($phpStats | Sort-Object Scope, @{Expression = { $_.Loc }; Descending = $true} | ForEach-Object {
    "$($_.Loc)`t$($_.Classes)`t$($_.Functions)`t$($_.Scope)`t$($_.Path)"
})
Write-Utf8File -Path (Join-Path $out 'php-metrics.txt') -Content ("loc`tclasses`tfunctions`tscope`tpath`r`n" + ($phpMetrics -join "`r`n"))

$procedural = @($phpStats | Where-Object { $_.Classes -eq 0 } | Sort-Object Scope, @{Expression = { $_.Loc }; Descending = $true} | ForEach-Object {
    "$($_.Loc)`t$($_.Scope)`t$($_.Path)"
})
Write-Utf8File -Path (Join-Path $out 'procedural-php-files.txt') -Content ("loc`tscope`tpath`r`n" + ($procedural -join "`r`n"))

$jsStats = @($jsFiles | ForEach-Object {
    Get-FileStats -RelativePath $_ -ClassPattern $jsClassPattern -FunctionPattern $jsFunctionPattern
})
$jsMetrics = @($jsStats | Sort-Object Scope, @{Expression = { $_.Loc }; Descending = $true} | ForEach-Object {
    "$($_.Loc)`t$($_.Functions)`t$($_.Scope)`t$($_.Path)"
})
Write-Utf8File -Path (Join-Path $out 'js-metrics.txt') -Content ("loc`tfunctions`tscope`tpath`r`n" + ($jsMetrics -join "`r`n"))

$tplMetrics = @($tplFiles | ForEach-Object {
    Get-FileStats -RelativePath $_
} | Sort-Object Scope, @{Expression = { $_.Loc }; Descending = $true} | ForEach-Object {
    "$($_.Loc)`t$($_.Scope)`t$($_.Path)"
})
Write-Utf8File -Path (Join-Path $out 'tpl-metrics.txt') -Content ("loc`tscope`tpath`r`n" + ($tplMetrics -join "`r`n"))

$cssMetrics = @($cssFiles | ForEach-Object {
    Get-FileStats -RelativePath $_ -ClassPattern $cssClassPattern
} | Sort-Object Scope, @{Expression = { $_.Loc }; Descending = $true} | ForEach-Object {
    "$($_.Loc)`t$($_.Classes)`t$($_.Scope)`t$($_.Path)"
})
Write-Utf8File -Path (Join-Path $out 'css-metrics.txt') -Content ("loc`tclasses`tscope`tpath`r`n" + ($cssMetrics -join "`r`n"))

Write-Utf8File -Path (Join-Path $out 'js-files.txt') -Content (($jsFiles | Sort-Object) -join "`r`n")
Write-Utf8File -Path (Join-Path $out 'vue-files.txt') -Content (($vueFiles | Sort-Object) -join "`r`n")
Write-Utf8File -Path (Join-Path $out 'tpl-files.txt') -Content (($tplFiles | Sort-Object) -join "`r`n")
Write-Utf8File -Path (Join-Path $out 'css-files.txt') -Content (($cssFiles | Sort-Object) -join "`r`n")

$routeFiles = Get-ProjectFiles -Include @('routes.php','web.php','api.php','m_router.php','router.js','router.ts')
$configFiles = Get-ProjectFiles -Include @('.env.example','config.php','webpack.config.js','webpack.config.ts','composer.json','package.json','phpunit.xml')

if (Test-GitAvailable) {
    $since = (Get-Date).AddDays(-90).ToString('yyyy-MM-dd')
    $hot = git log --since=$since --name-only --pretty=format: 2>$null |
        Where-Object { $_ -match '\.(php|vue|js|ts)$' -and -not (Test-StrictExcluded $_) } |
        Group-Object | Sort-Object Count -Descending | Select-Object -First 50 |
        ForEach-Object { "$($_.Count.ToString().PadLeft(4))  $($_.Name)" }
    Write-Utf8File -Path (Join-Path $out 'hot-files.txt') -Content ($hot -join "`r`n")
} else {
    Write-Utf8File -Path (Join-Path $out 'hot-files.txt') -Content 'git unavailable'
}

& (Join-Path $PSScriptRoot 'generate-doc-index.ps1') -Quiet
& (Join-Path $PSScriptRoot 'generate-file-registry.ps1') -Quiet

Write-Host 'Map done: .doc/architecture/_map/' -ForegroundColor Green
Write-Host ("  PHP files: $($phpFiles.Count)")
Write-Host ("  Vue components: $($vueFiles.Count)")
Write-Host ("  JS/TS files: $($jsFiles.Count)")
Write-Host ("  TPL files: $($tplFiles.Count)")
Write-Host ("  CSS files: $($cssFiles.Count)")
Write-Host ("  SQL files: $($sqlFiles.Count)")
Write-Host ("  Procedural PHP (0 classes): $($procedural.Count)")

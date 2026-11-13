<#
.SYNOPSIS
    Общая библиотека для docscripts: фильтрация файлов проекта, meta-парсинг,
    state/registry helpers и служебные функции для incremental documentation.
#>

$Script:StrictExcludeDirs = @(
    'vendor', 'node_modules', 'cache', 'templates_c', 'dist',
    'backups', 'uploads', 'img', 'imgp', 'pageImages', 'mailing',
    'tests/cache', 'bin', 'obj', 'build', '.doc', '.agents', '.cursor'
)

$Script:FallbackExcludeDirs = $Script:StrictExcludeDirs + @('_map', '.vs')

function Set-DocConsoleEncoding {
    try {
        $utf8 = New-Object System.Text.UTF8Encoding($false)
        [Console]::OutputEncoding = $utf8
        $script:OutputEncoding = $utf8
        $global:OutputEncoding = $utf8
    } catch { }
}

function Normalize-RelativePath {
    param([AllowNull()][string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return '' }
    return ($Path.Trim() -replace '\\', '/').TrimStart('/')
}

function Get-RelativePath {
    param([Parameter(Mandatory)][string]$FullPath)
    $projectRoot = (Get-Location).Path
    return Normalize-RelativePath ($FullPath.Replace($projectRoot, '').TrimStart('\','/'))
}

function Read-TextFile {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path $Path)) { return $null }
    try {
        return [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
    } catch {
        return Get-Content $Path -Raw -ErrorAction SilentlyContinue
    }
}

function Write-Utf8File {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Content
    )
    $dir = Split-Path -Parent $Path
    if ($dir) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $utf8)
}

function Read-JsonFile {
    param([Parameter(Mandatory)][string]$Path)
    $raw = Read-TextFile -Path $Path
    if (-not $raw) { return $null }
    try { return $raw | ConvertFrom-Json } catch { return $null }
}

function Write-JsonFile {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)]$Object
    )
    $json = $Object | ConvertTo-Json -Depth 20
    Write-Utf8File -Path $Path -Content $json
}

function Convert-MetaList {
    param([AllowNull()][string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return @() }
    $trimmed = $Value.Trim()
    if ($trimmed.StartsWith('[') -and $trimmed.EndsWith(']')) {
        $trimmed = $trimmed.Substring(1, $trimmed.Length - 2)
    }
    if (-not $trimmed) { return @() }
    return @(
        $trimmed -split ',' |
            ForEach-Object { $_.Trim().Trim('"','''') } |
            Where-Object { $_ }
    )
}

function Get-DocMeta {
    param([Parameter(Mandatory)][string]$Path)
    if ($Path -match '\.json$') {
        $jsonObj = Read-JsonFile -Path $Path
        if ($jsonObj) {
            $meta = [ordered]@{
                type = if ($jsonObj.metadata -and $jsonObj.metadata.doc_type) { $jsonObj.metadata.doc_type } else { 'architecture' }
                status = if ($jsonObj.metadata -and $jsonObj.metadata.source_status) { $jsonObj.metadata.source_status } elseif ($jsonObj.metadata -and $jsonObj.metadata.status) { $jsonObj.metadata.status } else { '' }
                tags = @()
                related = @()
                updated = if ($jsonObj.metadata -and $jsonObj.metadata.updated_at) { ($jsonObj.metadata.updated_at -split 'T')[0] } else { '' }
            }
            if ($jsonObj.relations) {
                $meta.related = @($jsonObj.relations | ForEach-Object {
                    if ($_.target -and $_.target.document_id) {
                        $t = $_.target.document_id -replace '^architecture:', '' -replace '^arch:', ''
                        if ($t -notmatch '\.md$') { "$t.md" } else { $t }
                    }
                } | Where-Object { $_ })
            }
            if ($jsonObj.tags) {
                $meta.tags = @($jsonObj.tags | ForEach-Object {
                    if ($_.tag_id) { $_.tag_id }
                } | Where-Object { $_ })
            }
            if ((-not $meta.related -or $meta.related.Count -eq 0 -or -not $meta.tags -or $meta.tags.Count -eq 0) -and $jsonObj.sections -and $jsonObj.sections.Count -gt 0) {
                $sec0 = $jsonObj.sections[0].body_markdown
                if ($sec0 -match '<!-- meta(.*?)-->') {
                    $mBlock = $matches[1] -split "`r?`n"
                    foreach ($line in $mBlock) {
                        $trimmed = $line.Trim()
                        if ($trimmed -match '^tags:\s*(.*)$' -and (-not $meta.tags -or $meta.tags.Count -eq 0)) {
                            $meta.tags = @(Convert-MetaList $matches[1].Trim())
                        }
                        if ($trimmed -match '^related:\s*(.*)$' -and (-not $meta.related -or $meta.related.Count -eq 0)) {
                            $meta.related = @(Convert-MetaList $matches[1].Trim())
                        }
                        if ($trimmed -match '^status:\s*(.*)$' -and -not $meta.status) {
                            $meta.status = $matches[1].Trim()
                        }
                        if ($trimmed -match '^updated:\s*(.*)$' -and -not $meta.updated) {
                            $meta.updated = $matches[1].Trim()
                        }
                    }
                }
            }
            return [PSCustomObject]$meta
        }
        return $null
    }

    $content = Read-TextFile -Path $Path
    if (-not $content) { return $null }
    $match = [regex]::Match($content, '<!-- meta(.*?)-->', [System.Text.RegularExpressions.RegexOptions]::Singleline)
    if (-not $match.Success) { return $null }

    $meta = [ordered]@{
        type = ''
        status = ''
        tags = @()
        related = @()
        updated = ''
    }
    $body = $match.Groups[1].Value -split "`r?`n"
    foreach ($line in $body) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }
        if ($trimmed -match '^([A-Za-z0-9_.-]+):\s*(.*)$') {
            $key = $matches[1]
            $value = $matches[2].Trim()
            switch ($key) {
                'tags'    { $meta[$key] = @(Convert-MetaList $value) }
                'related' { $meta[$key] = @(Convert-MetaList $value) }
                default   { $meta[$key] = $value }
            }
        }
    }
    return [PSCustomObject]$meta
}

function Get-DocFirstHeading {
    param([Parameter(Mandatory)][string]$Path)
    if ($Path -match '\.json$') {
        $jsonObj = Read-JsonFile -Path $Path
        if ($jsonObj -and $jsonObj.metadata -and $jsonObj.metadata.title) {
            return $jsonObj.metadata.title.Trim()
        }
    }
    $lines = Get-Content $Path -ErrorAction SilentlyContinue
    $h1 = $lines | Select-String '^# ' | Select-Object -First 1
    if ($h1) { return $h1.Line.Trim().TrimStart('#').Trim() }
    return [System.IO.Path]::GetFileNameWithoutExtension($Path)
}

function Get-DocBusinessKey {
    param([Parameter(Mandatory)][string]$Path)
    return ([System.IO.Path]::GetFileNameWithoutExtension($Path)).ToLowerInvariant()
}

function Get-DocCodeRefs {
    param([Parameter(Mandatory)][string]$Path)
    if ($Path -match '\.json$') {
        $jsonObj = Read-JsonFile -Path $Path
        if ($jsonObj -and $jsonObj.sections) {
            $allSec = ($jsonObj.sections | ForEach-Object { $_.body_markdown }) -join "`n"
            return @(
                [regex]::Matches($allSec, '`([a-zA-Z0-9_./\\& -]+\.(?:php|phtml|vue|js|ts|tpl|css|scss|sass|less|sql|json|yml|yaml|xml|md))(?:\:\d+)?`') |
                    ForEach-Object { Normalize-RelativePath ($_.Groups[1].Value) } |
                    Where-Object { $_ } |
                    Sort-Object -Unique
            )
        }
    }
    $content = Read-TextFile -Path $Path
    if (-not $content) { return @() }
    return @(
        [regex]::Matches($content, '`([a-zA-Z0-9_./\\& -]+\.(?:php|phtml|vue|js|ts|tpl|css|scss|sass|less|sql|json|yml|yaml|xml|md))(?:\:\d+)?`') |
            ForEach-Object { Normalize-RelativePath ($_.Groups[1].Value) } |
            Where-Object { $_ } |
            Sort-Object -Unique
    )
}

function Get-ArchitectureDocs {
    $projectRoot = (Get-Location).Path
    $archDir = Join-Path $projectRoot '.doc\architecture'
    $jsonItems = @(Get-ChildItem -Path $archDir -Filter '*.json' -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch '\\_jsondoc\\' -and $_.FullName -notmatch '\\_map\\' -and $_.Name -notmatch '^_' -and $_.Name -ne 'index.json' })
    if ($jsonItems.Count -gt 0) {
        $navItems = @(Get-ChildItem -Path $archDir -Filter '*.md' -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -eq 'index.md' -or $_.Name -eq '_priority.md' })
        return @($jsonItems + $navItems | Sort-Object FullName)
    }
    return @(Get-ChildItem -Path $archDir -Filter '*.md' -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch '\\_map\\' -and $_.Name -notmatch '^_' } |
        Sort-Object FullName)
}

function Get-RegistryFilePath {
    $projectRoot = (Get-Location).Path
    return (Join-Path $projectRoot '.doc\architecture\_map\file-registry.tsv')
}

function Get-DocIndexFilePath {
    $projectRoot = (Get-Location).Path
    return (Join-Path $projectRoot '.doc\architecture\_map\doc-index.tsv')
}

function Get-FileKind {
    param([Parameter(Mandatory)][string]$Path)
    $ext = [System.IO.Path]::GetExtension($Path).TrimStart('.').ToLowerInvariant()
    switch ($ext) {
        'php'   { return 'php' }
        'phtml' { return 'tpl' }
        'tpl'   { return 'tpl' }
        'vue'   { return 'vue' }
        'js'    { return 'js' }
        'ts'    { return 'ts' }
        'css'   { return 'css' }
        'scss'  { return 'css' }
        'sass'  { return 'css' }
        'less'  { return 'css' }
        'sql'   { return 'sql' }
        'json'  { return 'config' }
        'yml'   { return 'config' }
        'yaml'  { return 'config' }
        'xml'   { return 'config' }
        default { if ($ext) { return $ext } else { return 'other' } }
    }
}

function Test-GitAvailable {
    try {
        $null = git rev-parse --is-inside-work-tree 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Test-StrictExcluded {
    param([Parameter(Mandatory)][string]$RelativePath)
    $normalized = Normalize-RelativePath $RelativePath

    if ($normalized -match '^\.[^/]+(/|$)') {
        return $true
    }

    foreach ($d in $Script:StrictExcludeDirs) {
        if ($normalized -eq $d -or $normalized -like "$d/*" -or $normalized -like "*/$d/*") {
            return $true
        }
    }

    return $false
}

function Get-ProjectFiles {
    [CmdletBinding()]
    param(
        [string[]]$Extensions = @(),
        [string]$Pattern = '',
        [string[]]$Include = @()
    )

    $projectRoot = (Get-Location).Path
    $files = @()

    if (Test-GitAvailable) {
        $gitFiles = git ls-files --cached --others --exclude-standard 2>$null
        if ($LASTEXITCODE -eq 0 -and $gitFiles) {
            $files = @($gitFiles | Where-Object { $_ })
        }
    }

    if (-not $files) {
        $files = Get-ChildItem -LiteralPath $projectRoot -Recurse -File -ErrorAction SilentlyContinue |
            ForEach-Object {
                $rel = Normalize-RelativePath ($_.FullName.Substring($projectRoot.Length).TrimStart('\','/'))
                $skip = $false
                foreach ($d in $Script:FallbackExcludeDirs) {
                    if ($rel -eq $d -or $rel -like "$d/*" -or $rel -like "*/$d/*") {
                        $skip = $true
                        break
                    }
                }
                if (-not $skip) { $rel }
            } | Where-Object { $_ }
    }

    $files = $files | ForEach-Object { Normalize-RelativePath $_ } | Where-Object { -not (Test-StrictExcluded $_) }

    if ($Extensions -and $Extensions.Count -gt 0) {
        $extPattern = '\.(?:' + (($Extensions | ForEach-Object { [regex]::Escape($_) }) -join '|') + ')$'
        $files = $files | Where-Object { $_ -imatch $extPattern }
    }

    if ($Include -and $Include.Count -gt 0) {
        $files = $files | Where-Object {
            $name = Split-Path -Leaf $_
            $match = $false
            foreach ($inc in $Include) {
                if ($name -ieq $inc -or $name -ilike $inc) { $match = $true; break }
            }
            $match
        }
    }

    if ($Pattern) {
        $files = $files | Where-Object { $_ -imatch [regex]::Escape($Pattern) }
    }

    return @($files | Sort-Object -Unique)
}

function ConvertTo-FullPath {
    param([Parameter(Mandatory)][string]$RelativePath)
    $projectRoot = (Get-Location).Path
    return (Join-Path $projectRoot ((Normalize-RelativePath $RelativePath) -replace '/', '\\'))
}

function Test-YesAnswer {
    param([AllowNull()][string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return $false }
    $t = $Text.Trim().ToLowerInvariant()
    $yesDa = -join @([char]0x0434, [char]0x0430)
    $yesD  = [char]0x0434
    return ($t -in @('yes', 'y', 'da', 'd')) -or ($Text.Trim() -eq $yesDa) -or ($Text.Trim() -eq $yesD)
}

function Test-PathMatchesAny {
    param(
        [Parameter(Mandatory)][string]$Path,
        [string[]]$Patterns = @(),
        [string[]]$Aliases = @()
    )

    $normalized = Normalize-RelativePath $Path
    foreach ($pattern in @($Patterns | Where-Object { $_ })) {
        $p = Normalize-RelativePath $pattern
        if (-not $p) { continue }
        if ($normalized -like "*$p*" -or $normalized -imatch [regex]::Escape($p)) { return $true }
    }
    foreach ($alias in @($Aliases | Where-Object { $_ })) {
        if ($normalized -imatch [regex]::Escape($alias)) { return $true }
    }
    return $false
}

Set-DocConsoleEncoding

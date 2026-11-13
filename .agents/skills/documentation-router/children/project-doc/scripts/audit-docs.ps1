<#
.SYNOPSIS
    Аудит документации: gaps, устаревшие документы, сломанные ссылки.
    Уважает .gitignore (через git ls-files) и strict-фильтр.

.DESCRIPTION
    Запускай из корня проекта: powershell .agents/skills/documentation-router/children/project-doc/scripts/audit-docs.ps1
    Скинь вывод в чат и напиши: "проанализируй аудит"

.EXAMPLE
    cd C:\projects\copytrust\testdeploydocker
    powershell .agents/skills/documentation-router/children/project-doc/scripts/audit-docs.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "SilentlyContinue"

. (Join-Path $PSScriptRoot "_lib.ps1")

$ProjectRoot = (Get-Location).Path
$ArchDir = Join-Path $ProjectRoot ".doc\architecture"

Write-Host "🔍 Аудит документации..." -ForegroundColor Cyan
Write-Host ""

$report = [System.Collections.Generic.List[string]]::new()
$report.Add("=== АУДИТ ДОКУМЕНТАЦИИ ===")
$report.Add("=== Дата: $(Get-Date -Format 'yyyy-MM-dd HH:mm') ===")
$report.Add("")

# ─── Собираем все упоминания файлов проекта в архитектурных .md ─────
# Алгоритм: ищем backtick-кавычки с путями, накапливаем как набор:
#  - полные относительные пути (например: app/Services/PaymentService.php)
#  - только basename как fallback (например: PaymentService.php)
# Поиск активного файла считается успешным если ЛИБО найден полный relpath
# (forward или backslash), ЛИБО найден basename и других файлов с таким же
# именем в карте нет (нет коллизии).
$archDocs = Get-ChildItem -Path $ArchDir -Filter "*.md" -Recurse |
    Where-Object { $_.Name -notmatch "^_" -and $_.FullName -notmatch "\\_map\\" }

$archRawText = ($archDocs | ForEach-Object { Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue }) -join "`n"

# Извлекаем все упомянутые относительные пути (с / или \)
$mentionedRelPaths = @{}
foreach ($m in [regex]::Matches($archRawText, '`([a-zA-Z][a-zA-Z0-9/\\_.-]+\.(?:php|vue|js|ts|sql))(?::\d+)?`')) {
    $p = $m.Groups[1].Value -replace '\\', '/'
    $mentionedRelPaths[$p] = $true
}
# Множество basename → счётчик упоминаний
$mentionedBasenames = @{}
foreach ($p in $mentionedRelPaths.Keys) {
    $bn = Split-Path -Leaf $p
    if (-not $mentionedBasenames.ContainsKey($bn)) { $mentionedBasenames[$bn] = 0 }
    $mentionedBasenames[$bn]++
}

function Test-FileMentionedInDocs {
    <#
    Возвращает $true если файл "$relPath" задокументирован.
    Проверка по полному пути (надёжно) с двойным fallback на basename
    с учётом коллизий из карты файлов проекта.
    #>
    param(
        [string]$RelPath,
        [hashtable]$AllBasenamesInProject
    )
    $norm = $RelPath -replace '\\', '/'
    # 1) Точное совпадение по полному пути
    if ($mentionedRelPaths.ContainsKey($norm)) { return $true }
    # 2) Совпадение по подстроке (для случаев когда упомянут хвост пути)
    foreach ($mp in $mentionedRelPaths.Keys) {
        if ($mp -ieq $norm -or $norm.EndsWith("/" + $mp) -or $mp.EndsWith("/" + $norm)) {
            return $true
        }
    }
    # 3) По basename — только если в проекте нет коллизий
    $bn = Split-Path -Leaf $norm
    if ($AllBasenamesInProject[$bn] -eq 1 -and $mentionedBasenames.ContainsKey($bn)) {
        return $true
    }
    return $false
}

# ─── 1. Активные файлы без упоминания в документации ────────────
$report.Add("--- Активные файлы без упоминания в документации (90 дней) ---")
$report.Add("")
if (Test-GitAvailable) {
    $since = (Get-Date).AddDays(-90).ToString("yyyy-MM-dd")

    # Карта всех файлов проекта для определения коллизий basename
    $allProjFiles = Get-ProjectFiles -Extensions @("php","vue","js","ts")
    $basenameCounts = @{}
    foreach ($f in $allProjFiles) {
        $bn = Split-Path -Leaf $f
        if (-not $basenameCounts.ContainsKey($bn)) { $basenameCounts[$bn] = 0 }
        $basenameCounts[$bn]++
    }

    # Активные файлы за 90 дней
    $activeFiles = git log --since=$since --name-only --pretty=format: 2>$null |
        Where-Object {
            $_ -match "\.(php|vue|js|ts)$" -and
            -not (Test-StrictExcluded $_) -and
            $_ -notmatch "(^|/)(vendor|node_modules)/"
        }

    # Счётчик изменений по каждому файлу
    $changeCounts = @{}
    foreach ($f in $activeFiles) {
        if (-not $changeCounts.ContainsKey($f)) { $changeCounts[$f] = 0 }
        $changeCounts[$f]++
    }

    $missing = $changeCounts.Keys |
        Where-Object {
            $rel = $_
            # Файл существует физически
            (Test-Path (ConvertTo-FullPath $rel)) -and
            # И не упомянут в документации (точная проверка)
            (-not (Test-FileMentionedInDocs -RelPath $rel -AllBasenamesInProject $basenameCounts))
        } |
        ForEach-Object {
            [PSCustomObject]@{ File = $_; Changes = $changeCounts[$_] }
        }

    $missing | Sort-Object Changes -Descending | Select-Object -First 30 |
        ForEach-Object { $report.Add("  [$($_.Changes.ToString().PadLeft(3)) изм.] $($_.File)") }

    if (-not $missing) { $report.Add("  (всё задокументировано или активных файлов нет)") }
} else {
    $report.Add("  git недоступен")
}
$report.Add("")

# ─── 2. Устаревшие документы (>60 дней без обновления) ──────────
$report.Add("--- Документы не обновлявшиеся более 60 дней ---")
$report.Add("")
foreach ($d in $archDocs) {
    $content = Get-Content $d.FullName -ErrorAction SilentlyContinue
    $updatedLine = $content | Select-String -Pattern "updated:\s*(\d{4}-\d{2}-\d{2})" | Select-Object -First 1
    $rel = $d.FullName.Replace($ProjectRoot, "").TrimStart("\")
    if (-not $updatedLine) {
        $report.Add("  ❓ $rel — нет поля updated в meta")
    } else {
        $dateStr = $updatedLine.Matches[0].Groups[1].Value
        try {
            $docDate = [datetime]::ParseExact($dateStr, "yyyy-MM-dd", $null)
            $days = [int]((Get-Date) - $docDate).TotalDays
            if ($days -gt 60) {
                $report.Add("  📅 $rel ($days дней без обновлений, последнее: $dateStr)")
            }
        } catch { }
    }
}
$report.Add("")

# ─── 3. Сломанные ссылки ────────────────────────────────────────
$report.Add("--- Сломанные ссылки в документации ---")
$report.Add("")
foreach ($d in $archDocs) {
    $docDir = $d.DirectoryName
    $rel = $d.FullName.Replace($ProjectRoot, "").TrimStart("\")
    $content = Get-Content $d.FullName -ErrorAction SilentlyContinue
    if (-not $content) { continue }
    $linkMatches = [regex]::Matches(($content -join "`n"), '\((\./|\.\./)[^)#]+\.md')
    foreach ($m in $linkMatches) {
        $linkRaw = $m.Value.TrimStart("(")
        $target = Join-Path $docDir $linkRaw
        $target = [System.IO.Path]::GetFullPath($target)
        if (-not (Test-Path $target)) {
            $report.Add("  ❌ $rel")
            $report.Add("     → $linkRaw (файл не найден)")
        }
    }
}
$report.Add("")

# ─── 4. Документы без meta-блока ────────────────────────────────
$report.Add("--- Документы без блока <!-- meta --> ---")
$report.Add("")
foreach ($d in $archDocs) {
    $content = Get-Content $d.FullName -Raw -ErrorAction SilentlyContinue
    $rel = $d.FullName.Replace($ProjectRoot, "").TrimStart("\")
    if ($content -and $content -notmatch "<!-- meta") {
        $report.Add("  📋 $rel")
    }
}
$report.Add("")

# ─── 5. Изолированные документы (никто не ссылается) ────────────
$report.Add("--- Изолированные документы (никто не ссылается, кроме index.md) ---")
$report.Add("")
$nonIndexDocs = $archDocs | Where-Object { $_.Name -ne "index.md" }
foreach ($doc in $nonIndexDocs) {
    $basename = $doc.Name
    $mentioned = $false
    foreach ($other in $archDocs) {
        if ($other.Name -eq $basename) { continue }
        $c = Get-Content $other.FullName -Raw -ErrorAction SilentlyContinue
        if ($c -and ($c -match [regex]::Escape($basename))) { $mentioned = $true; break }
    }
    if (-not $mentioned) {
        $rel = $doc.FullName.Replace($ProjectRoot, "").TrimStart("\")
        $report.Add("  🔗 $rel")
    }
}
$report.Add("")

# ─── 6. Топ кандидатов на документирование (30 дней) ────────────
$report.Add("--- Топ-20 активных файлов за 30 дней (кандидаты на документирование) ---")
$report.Add("")
if (Test-GitAvailable) {
    $since30 = (Get-Date).AddDays(-30).ToString("yyyy-MM-dd")
    git log --since=$since30 --name-only --pretty=format: 2>$null |
        Where-Object {
            $_ -match "\.(php|vue|js)$" -and
            -not (Test-StrictExcluded $_) -and
            $_ -notmatch "(^|/)(vendor|node_modules)/"
        } |
        Group-Object | Sort-Object Count -Descending | Select-Object -First 20 |
        ForEach-Object { $report.Add("  [$($_.Count.ToString().PadLeft(3)) изм.] $($_.Name)") }
} else {
    $report.Add("  git недоступен")
}
$report.Add("")
$report.Add("=== КОНЕЦ АУДИТА ===")

$report | Write-Output

Write-Host ""
Write-Host "Скинь вывод в чат и напиши: 'проанализируй аудит'" -ForegroundColor Cyan

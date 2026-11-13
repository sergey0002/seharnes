<#
.SYNOPSIS
    Находит устаревшие архитектурные документы: код изменился после
    последнего обновления документа (поле updated: в meta-блоке).

.DESCRIPTION
    Для каждого .md в .doc/architecture/:
    - Извлекает дату updated: из meta-блока
    - Находит все упомянутые файлы проекта (в backtick-кавычках)
    - Проверяет git log: были ли эти файлы изменены после updated
    - Выводит отчёт: какие документы нужно обновить и почему

    Запускай из корня проекта.
    Скинь вывод в чат и напиши: "обнови устаревшие документы"

.PARAMETER Days
    Дополнительный порог: показывать только если файл изменялся
    в последние N дней (по умолчанию 0 = показывать все).

.PARAMETER Section
    Проверять только конкретный документ (имя файла без пути).

.EXAMPLE
    powershell .agents/skills/documentation-router/children/project-doc/scripts/sync-docs.ps1
    powershell .agents/skills/documentation-router/children/project-doc/scripts/sync-docs.ps1 -Days 30
    powershell .agents/skills/documentation-router/children/project-doc/scripts/sync-docs.ps1 -Section payments.md
#>

param(
    [int]$Days = 0,
    [string]$Section = ""
)

$ProjectRoot = (Get-Location).Path
$ArchDir = Join-Path $ProjectRoot ".doc\architecture"

Write-Host "🔄 Проверка актуальности документации..." -ForegroundColor Cyan
Write-Host ""

$stale   = [System.Collections.Generic.List[PSCustomObject]]::new()
$current = [System.Collections.Generic.List[string]]::new()
$noMeta  = [System.Collections.Generic.List[string]]::new()
$gitAvailable = $true

try { git log --oneline -1 2>$null | Out-Null } catch { $gitAvailable = $false }

$docs = Get-ChildItem -Path $ArchDir -Filter "*.md" -Recurse |
    Where-Object {
        $_.Name -notmatch "^_" -and $_.FullName -notmatch "\\_map\\" -and
        (-not $Section -or $_.Name -eq $Section)
    }

foreach ($doc in $docs) {
    $rel = $doc.FullName.Replace($ProjectRoot, "").TrimStart("\")
    $content = Get-Content $doc.FullName -Raw -ErrorAction SilentlyContinue
    if (-not $content) { continue }

    # Извлекаем дату из meta
    $updMatch = [regex]::Match($content, "updated:\s*(\d{4}-\d{2}-\d{2})")
    if (-not $updMatch.Success) {
        $noMeta.Add($rel)
        continue
    }

    $updatedStr = $updMatch.Groups[1].Value
    try {
        $updatedDate = [datetime]::ParseExact($updatedStr, "yyyy-MM-dd", $null)
    } catch {
        $noMeta.Add("$rel (неверный формат даты: $updatedStr)")
        continue
    }

    # Извлекаем упомянутые файлы проекта из backtick-кода
    $codeRefs = [regex]::Matches($content, '`([a-zA-Z][a-zA-Z0-9/_.-]+\.(php|vue|js|ts|sql)(?::\d+)?)`') |
        ForEach-Object { $_.Groups[1].Value -replace ":\d+$", "" } |
        Sort-Object -Unique

    if ($codeRefs.Count -eq 0) {
        $current.Add("  ✅ $rel (нет ссылок на код)")
        continue
    }

    $changedFiles = @()

    if ($gitAvailable) {
        foreach ($ref in $codeRefs) {
            # Проверяем git log с даты updated
            $since = $updatedDate.ToString("yyyy-MM-dd")
            $sinceArg = if ($Days -gt 0) {
                "--since=" + (Get-Date).AddDays(-$Days).ToString("yyyy-MM-dd")
            } else {
                "--since=$since"
            }

            $changes = git log $sinceArg --oneline -- $ref 2>$null
            if ($changes) {
                $changeCount = @($changes).Count
                $lastChange = git log $sinceArg --format="%ad %s" --date=short -- $ref 2>$null |
                    Select-Object -First 1
                $changedFiles += [PSCustomObject]@{
                    File    = $ref
                    Count   = $changeCount
                    Last    = $lastChange
                }
            }
        }
    }

    if ($changedFiles.Count -gt 0) {
        $stale.Add([PSCustomObject]@{
            Doc          = $rel
            UpdatedDate  = $updatedStr
            ChangedFiles = $changedFiles
            TotalChanges = ($changedFiles | Measure-Object Count -Sum).Sum
        })
    } else {
        $daysSince = [int]((Get-Date) - $updatedDate).TotalDays
        $current.Add("  ✅ $rel (обновлён: $updatedStr, ${daysSince}д назад)")
    }
}

# ─── Отчёт ─────────────────────────────────────────────────────
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  СИНХРОНИЗАЦИЯ ДОКУМЕНТАЦИИ С КОДОМ" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

if (-not $gitAvailable) {
    Write-Host "⚠️  git недоступен — показываю только структуру." -ForegroundColor Yellow
    Write-Host ""
}

if ($stale.Count -gt 0) {
    $stale = $stale | Sort-Object TotalChanges -Descending
    Write-Host "🔴 Требуют обновления ($($stale.Count)):" -ForegroundColor Red
    Write-Host ""
    foreach ($s in $stale) {
        Write-Host "  📄 $($s.Doc)" -ForegroundColor Red
        Write-Host "     Последнее обновление: $($s.UpdatedDate)"
        Write-Host "     Изменения в коде после этой даты:"
        foreach ($cf in ($s.ChangedFiles | Sort-Object Count -Descending)) {
            Write-Host "       [$($cf.Count) изм.]  $($cf.File)" -ForegroundColor Yellow
            if ($cf.Last) { Write-Host "              → $($cf.Last)" -ForegroundColor Gray }
        }
        Write-Host ""
    }
}

if ($noMeta.Count -gt 0) {
    Write-Host "⚠️  Нет даты updated в meta ($($noMeta.Count)):" -ForegroundColor Yellow
    $noMeta | ForEach-Object { Write-Host "  $_" }
    Write-Host ""
}

if ($current.Count -gt 0) {
    Write-Host "✅ Актуальны ($($current.Count)):" -ForegroundColor Green
    $current | ForEach-Object { Write-Host $_ }
    Write-Host ""
}

Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Итого: $($docs.Count) документов | 🔴 $($stale.Count) устаревших | ✅ $($current.Count) актуальных" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

if ($stale.Count -gt 0) {
    Write-Host "Скинь вывод в чат и напиши: 'обнови устаревшие документы'" -ForegroundColor Cyan
    Write-Host "Агент прочитает изменившиеся файлы и обновит только затронутые секции." -ForegroundColor Gray
}

exit $(if ($stale.Count -gt 0) { 1 } else { 0 })

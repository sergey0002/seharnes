#Requires -Version 5.1
# multi-search.ps1 - тонкая Windows-обертка: форвардинг в multi-search.sh под WSL/Git-Bash,
# либо прямой rg при их отсутствии. Путь один для всех сред: .cursor/scripts/.
param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Sh = Join-Path $ScriptDir 'multi-search.sh'
$Bash = $null
foreach ($c in @('bash','wsl')) {
  try { $b = (Get-Command $c -ErrorAction Stop).Source; if ($b) { $Bash = $b; break } } catch {}
}
if ($Bash) { & $Bash $Sh @Args; exit $LASTEXITCODE }
$Rg = $null
try { $Rg = (Get-Command rg -ErrorAction Stop).Source } catch {}
if (-not $Rg) { Write-Error 'rg not found and no bash/wsl fallback; install ripgrep'; exit 2 }
Write-Error 'direct rg fallback: only single-pattern search supported, use WSL for full features'
exit 2

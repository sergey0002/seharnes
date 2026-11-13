#Requires -Version 5.1
# multi-exec.ps1 - тонкая Windows-обертка: форвардинг в multi-exec.sh под WSL/Git-Bash.
param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Sh = Join-Path $ScriptDir 'multi-exec.sh'
$Bash = $null
foreach ($c in @('bash','wsl')) {
  try { $b = (Get-Command $c -ErrorAction Stop).Source; if ($b) { $Bash = $b; break } } catch {}
}
if (-not $Bash) { Write-Error 'bash or wsl required for multi-exec.sh'; exit 2 }
& $Bash $Sh @Args; exit $LASTEXITCODE

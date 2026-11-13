param(
    [switch]$Check,
    [string]$Project = ''
)

$ErrorActionPreference = 'Stop'
$bash = Get-Command bash -ErrorAction SilentlyContinue
if (-not $bash) {
    Write-Error 'bash not found: install the service on Linux/WSL or add bash to PATH'
    exit 1
}

$script = Join-Path $PSScriptRoot 'install.sh'
$args = @()
if ($Check) { $args += '--check' }
if ($Project) { $args += @('--project', $Project) }
if (-not $Check -and -not $Project) { $args += '--help' }

& $bash.Source $script @args
exit $LASTEXITCODE

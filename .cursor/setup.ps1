# One-time setup after copying .cursor into a project.
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$repoRoot = Resolve-Path (Join-Path $here "..")
$toolchain = Join-Path $repoRoot ".tools\mcp-servers\php-toolchain"
$phpTools = Join-Path $here "tools"
$dockerEnv = Join-Path $repoRoot "tools\docker-dev\.env"
$phpDockerCmd = Join-Path $here "scripts\php-docker.cmd"

function Find-PhpExe {
    if ($env:PHP_BIN -and (Test-Path $env:PHP_BIN)) { return $env:PHP_BIN }
    if ($env:LARAGON_ROOT) {
        $phpRoot = Join-Path $env:LARAGON_ROOT "bin\php"
        if (Test-Path $phpRoot) {
            $latest = Get-ChildItem $phpRoot -Directory -Filter "php-*" | Sort-Object Name -Descending | Select-Object -First 1
            if ($latest) {
                $exe = Join-Path $latest.FullName "php.exe"
                if (Test-Path $exe) { return $exe }
            }
        }
    }
    $cmd = Get-Command php -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Find-ComposerExe {
    $cmd = Get-Command composer -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Read-DotEnv($path) {
    $map = @{}
    if (-not (Test-Path $path)) { return $map }
    foreach ($line in Get-Content $path -Encoding UTF8) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith("#")) { continue }
        $i = $t.IndexOf("=")
        if ($i -lt 1) { continue }
        $map[$t.Substring(0, $i).Trim()] = $t.Substring($i + 1).Trim()
    }
    return $map
}

function Sync-McpEnvFromDocker($docker) {
    $mcpEnvPath = Join-Path $here "mcp.env"
    if (Test-Path $mcpEnvPath) {
        $lines = Get-Content $mcpEnvPath -Encoding UTF8
    } else {
        $lines = Get-Content (Join-Path $here "mcp.env.example") -Encoding UTF8
    }

    $updates = @{
        MYSQL_HOST = "127.0.0.1"
        MYSQL_PORT = if ($docker["MYSQL_PORT"]) { $docker["MYSQL_PORT"] } else { "3306" }
        MYSQL_USER = if ($docker["MYSQL_USER"]) { $docker["MYSQL_USER"] } else { "root" }
        MYSQL_PASSWORD = if ($docker["MYSQL_PASSWORD"]) { $docker["MYSQL_PASSWORD"] } else { "" }
        MYSQL_DATABASE = if ($docker["MYSQL_DATABASE"]) { $docker["MYSQL_DATABASE"] } else { "" }
    }

    if (-not (Find-PhpExe) -and (Test-Path $phpDockerCmd)) {
        $updates["PHP_BIN"] = (Resolve-Path $phpDockerCmd).Path
        $project = if ($docker["COMPOSE_PROJECT_NAME"]) { $docker["COMPOSE_PROJECT_NAME"] } else { "copytrust-dev" }
        $updates["DOCKER_PHP_CONTAINER"] = "${project}-php-apache-1"
    }

    $out = New-Object System.Collections.Generic.List[string]
    $written = @{}
    foreach ($line in $lines) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=') {
            $key = $Matches[1]
            if ($updates.ContainsKey($key)) {
                $out.Add("$key=$($updates[$key])")
                $written[$key] = $true
                continue
            }
        }
        $out.Add($line)
    }
    foreach ($kv in $updates.GetEnumerator()) {
        if (-not $written[$kv.Key]) { $out.Add("$($kv.Key)=$($kv.Value)") }
    }
    Set-Content -Path $mcpEnvPath -Value $out -Encoding UTF8
    Write-Host "Synced mcp.env (MySQL port $($updates.MYSQL_PORT), database '$($updates.MYSQL_DATABASE)')."
}

function Install-ToolsViaDocker {
    if (Test-Path (Join-Path $phpTools "vendor\bin\phpstan")) { return $true }
    $container = "copytrust-dev-php-apache-1"
    $running = docker ps --filter "name=$container" --format "{{.Names}}" 2>$null
    if (-not $running) { return $false }

    Write-Host "Installing PHPStan/phpda via Docker ($container)..."
    $cmd = "export COMPOSER_HOME=/tmp/composer && mkdir -p `$COMPOSER_HOME && cd /var/www/html/.cursor/tools && (test -f composer.phar || curl -sS https://getcomposer.org/installer | php) && php composer.phar install --no-interaction --ignore-platform-reqs"
    docker exec $container bash -c $cmd
    return (Test-Path (Join-Path $phpTools "vendor\bin\phpstan"))
}

if (-not (Test-Path (Join-Path $here "mcp.env"))) {
    Copy-Item (Join-Path $here "mcp.env.example") (Join-Path $here "mcp.env")
    Write-Host "Created mcp.env from example."
}

$docker = Read-DotEnv $dockerEnv
if ($docker.Count -gt 0) {
    Sync-McpEnvFromDocker $docker
} else {
    Write-Host "No .tools/docker-dev/.env - edit .cursor/mcp.env manually (MYSQL_*)."
}

if (Test-Path (Join-Path $toolchain "package.json")) {
    Push-Location $toolchain
    if (-not (Test-Path "node_modules")) {
        npm install --omit=dev
        Write-Host "Installed php-toolchain (Node) dependencies."
    } else {
        Write-Host "php-toolchain node_modules OK."
    }
    Pop-Location
}

$composerJson = Join-Path $phpTools "composer.json"
if (Test-Path $composerJson) {
    if (-not (Test-Path (Join-Path $phpTools "vendor\bin\phpstan"))) {
        $composer = Find-ComposerExe
        if ($composer) {
            Push-Location $phpTools
            Write-Host "Installing PHPStan and phpda into .cursor/tools/vendor ..."
            & $composer install --no-interaction --ignore-platform-req=php
            Pop-Location
        } else {
            Install-ToolsViaDocker | Out-Null
        }
    }
    if (Test-Path (Join-Path $phpTools "vendor\bin\phpstan")) {
        Write-Host "OK: .cursor/tools/vendor/bin/phpstan"
    } else {
        Write-Warning "PHPStan not in .cursor/tools. Ensure docker compose up -d php-apache, then re-run setup.ps1"
    }
}

Write-Host 'Done. Fully restart Cursor, then check Settings / MCP.'

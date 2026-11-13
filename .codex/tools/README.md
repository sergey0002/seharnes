# Bundled PHP CLIs for MCP

Local `vendor/` for **phpstan-mcp** and **php-deps-mcp** (no need to install these in every project).

## Install (once per copied `.codex` folder)

From project root, with PHP and Composer on PATH:

```powershell
.\.codex\\setup.ps1
```

Or manually:

```powershell
cd .codex\\tools
composer install --no-interaction
cd ..\..
```

If `phpda` fails platform checks on PHP 8+:

```powershell
composer install --no-interaction --ignore-platform-req=php
```

## Layout

```text
.codex/tools/
  composer.json
  vendor/bin/phpstan
  vendor/bin/phpda
```

Analysis still runs against **your project** (`${workspaceFolder}`); only the binaries live here.


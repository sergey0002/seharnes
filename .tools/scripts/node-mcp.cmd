@echo off
REM Windows launcher for phpstan-mcp / php-deps-mcp (Cursor native on C:\...).
REM Prefer this over bash+node-mcp.sh: system32\bash.exe is WSL and breaks Win paths.
setlocal
set "NODE=%ProgramFiles%\nodejs\node.exe"
if not exist "%NODE%" set "NODE=%LocalAppData%\Programs\node\node.exe"
if not exist "%NODE%" set "NODE=node"
if defined NODE_BIN if exist "%NODE_BIN%" set "NODE=%NODE_BIN%"
"%NODE%" %*

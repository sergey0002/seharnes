@echo off
REM Windows launcher for codebase-memory-mcp (avoid bash+WSL path breakage).
setlocal
set "EXE=%LocalAppData%\Programs\codebase-memory-mcp\codebase-memory-mcp.exe"
if not exist "%EXE%" (
  echo codebase-memory-mcp: exe not found at %EXE% >&2
  echo Install CBM or use WSL Cursor remote. See .cursor/codebase-memory-mcp.md >&2
  exit /b 127
)
"%EXE%" %*

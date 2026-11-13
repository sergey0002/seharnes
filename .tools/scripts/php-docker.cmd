@echo off
setlocal
set "NODE=%ProgramFiles%\nodejs\node.exe"
if not exist "%NODE%" set "NODE=node"
"%NODE%" "%~dp0php-docker.js" %*

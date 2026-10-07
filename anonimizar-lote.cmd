@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-lote\Scripts\python.exe" (
  echo Execute instalar-lote.cmd primeiro.
  exit /b 1
)
".venv-lote\Scripts\python.exe" scripts\lote_local\anonimizar.py %*
exit /b %errorlevel%

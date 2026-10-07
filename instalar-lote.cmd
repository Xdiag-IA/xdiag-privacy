@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Instale Python 3.10 a 3.12 com a opcao Add Python to PATH e tente novamente.
  exit /b 1
)
python -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,12) else 1)"
if errorlevel 1 (
  echo Este perfil requer Python 3.10, 3.11 ou 3.12 no comando python.
  exit /b 1
)
if not exist ".venv-lote\Scripts\python.exe" python -m venv .venv-lote
if errorlevel 1 exit /b 1
".venv-lote\Scripts\python.exe" -m pip install --upgrade "pip>=25,<27"
if errorlevel 1 exit /b 1
".venv-lote\Scripts\python.exe" -m pip install torch==2.5.1+cpu --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple
if errorlevel 1 exit /b 1
".venv-lote\Scripts\python.exe" -m pip install -r requirements-lote.txt
if errorlevel 1 exit /b 1
".venv-lote\Scripts\python.exe" scripts\lote_local\preparar_modelo.py
if errorlevel 1 exit /b 1
".venv-lote\Scripts\python.exe" scripts\lote_local\preparar_ocr.py
if errorlevel 1 exit /b 1
echo Pronto. Execute anonimizar-lote.cmd --entrada "PASTA DOS DOCUMENTOS" --saida "PASTA DOS RESULTADOS".

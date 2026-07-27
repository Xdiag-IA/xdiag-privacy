<#
.SYNOPSIS
  Prova que o runtime empacotado roda o backend fora do Docker.

.DESCRIPTION
  Este e o teste que decide o plano do instalador. Ele nao verifica so "o
  Python abre": ele copia o runtime para um caminho com espaco e acento (o
  caso real de %LOCALAPPDATA% de um usuario chamado "Jose Antonio"), sobe o
  uvicorn de la, e processa um documento do corpus de verdade.

  Se passar, empacotar e encanamento conhecido. Se falhar, falha aqui, barato.

.PARAMETER Mock
  XDIAG_MOCK=1: valida o encanamento (Python relocavel, FastAPI, uvicorn,
  rotas) em segundos, sem baixar os ~2,2GB de modelo.

.PARAMETER SkipRelocate
  Roda direto de build/runtime, sem copiar. Util para iterar rapido; nao
  prova relocabilidade.

.PARAMETER Document
  Documento a processar. Por padrao, um laudo do corpus de teste.
#>
[CmdletBinding()]
param(
    [switch]$Mock,
    [switch]$SkipRelocate,
    [string]$Document
)

$ErrorActionPreference = "Stop"

$DesktopDir = Split-Path -Parent $PSScriptRoot
$RepoDir = Split-Path -Parent $DesktopDir
$BuildDir = Join-Path $DesktopDir "build"
$RuntimeDir = Join-Path $BuildDir "runtime"

if (-not $Document) {
    $Document = Join-Path $RepoDir "tests\corpus\laudo_us_abdome_02.png"
}

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "    $msg" -ForegroundColor Green }
function Write-Bad($msg) { Write-Host "    $msg" -ForegroundColor Red }

function Get-FreePort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    $port = $listener.LocalEndpoint.Port
    $listener.Stop()
    return $port
}

if (-not (Test-Path (Join-Path $RuntimeDir "python\python.exe"))) {
    throw "runtime nao encontrado. Rode build-runtime.ps1 antes."
}

# O codigo do backend viaja junto com o runtime: e assim que o instalador vai
# entregar. Sincroniza a cada execucao para o teste refletir o codigo atual.
Write-Step "sincronizando backend/app -> runtime/app"
$appSrc = Join-Path $RepoDir "backend\app"
$appDst = Join-Path $RuntimeDir "app"
if (Test-Path $appDst) { Remove-Item $appDst -Recurse -Force }
Copy-Item $appSrc $appDst -Recurse
Write-Ok "sincronizado"

# --- Relocacao --------------------------------------------------------------

if ($SkipRelocate) {
    $TestRoot = $RuntimeDir
    Write-Step "rodando de $TestRoot (sem relocar)"
} else {
    # Nome com espaco e acentos de proposito: e o caminho que quebra build
    # empacotado mal feito, e e o caminho real de metade dos usuarios.
    #
    # Montado por codepoint em vez de literal: o PowerShell 5.1 le .ps1 sem BOM
    # como ANSI, entao um "é" digitado direto no arquivo vira mojibake e o
    # teste passaria a exercitar um caminho diferente do que diz exercitar.
    $nome = "Xdiag Privacy (Jos{0} Ant{1}nio)" -f [char]0x00E9, [char]0x00F4
    $TestRoot = Join-Path $env:LOCALAPPDATA "Programs\$nome"
    Write-Step "relocando para $TestRoot"
    if (Test-Path $TestRoot) { Remove-Item $TestRoot -Recurse -Force }
    New-Item -ItemType Directory -Force -Path (Split-Path $TestRoot) | Out-Null
    Copy-Item $RuntimeDir $TestRoot -Recurse
    Write-Ok "copiado"
}

$PythonExe = Join-Path $TestRoot "python\python.exe"
$DataDir = Join-Path $TestRoot "data"
$CacheDir = Join-Path $DataDir "cache"
New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null

# --- Ambiente ---------------------------------------------------------------

$port = Get-FreePort
Write-Step "ambiente"
Write-Ok "porta efemera: $port (loopback)"

# XDIAG_HOST em 127.0.0.1, nao no 0.0.0.0 do default: num app de mesa o
# default publicaria a API de anonimizacao para a rede inteira da clinica.
$envVars = @{
    "XDIAG_HOST"             = "127.0.0.1"
    "XDIAG_PORT"             = "$port"
    # Os defaults de config.py sao caminhos Linux (/app/...). No Windows
    # precisam ser sobrescritos ou o backend escreve em lugar nenhum.
    "XDIAG_CACHE_DIR"        = $CacheDir
    "XDIAG_SAMPLES_DIR"      = (Join-Path $RepoDir "samples")
    "HF_HOME"                = (Join-Path $CacheDir "huggingface")
    "TRANSFORMERS_CACHE"     = (Join-Path $CacheDir "huggingface")
    "PADDLE_PDX_CACHE_HOME"  = (Join-Path $CacheDir "paddle")
    "XDIAG_EAGER_LOAD"       = "1"
    "PYTHONUNBUFFERED"       = "1"
    "PYTHONDONTWRITEBYTECODE" = "1"
}
if ($Mock) {
    $envVars["XDIAG_MOCK"] = "1"
    Write-Ok "modo mock: sem download de modelo"
}
foreach ($k in $envVars.Keys) { [Environment]::SetEnvironmentVariable($k, $envVars[$k], "Process") }

# --- Sobe o backend ---------------------------------------------------------

$logOut = Join-Path $BuildDir "smoke-stdout.log"
$logErr = Join-Path $BuildDir "smoke-stderr.log"

Write-Step "subindo uvicorn"
$proc = Start-Process -FilePath $PythonExe `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$port", "--log-level", "info") `
    -WorkingDirectory $TestRoot `
    -RedirectStandardOutput $logOut `
    -RedirectStandardError $logErr `
    -PassThru -NoNewWindow
Write-Ok "pid $($proc.Id), cwd $TestRoot"

$exitCode = 1
try {
    $client = Join-Path $PSScriptRoot "smoke_client.py"
    & $PythonExe $client "http://127.0.0.1:$port" $Document --expect-entities 1
    $exitCode = $LASTEXITCODE
} finally {
    # Diagnostico ANTES de matar o processo. Se o backend morreu sozinho, o
    # taskkill falha, e com ErrorActionPreference=Stop essa falha abortaria o
    # finally e engoliria justamente o traceback que interessa.
    if ($exitCode -ne 0) {
        Write-Bad "--- ultimas linhas de stderr ---"
        if (Test-Path $logErr) { Get-Content $logErr -Tail 40 | ForEach-Object { Write-Host "    $_" } }
        Write-Bad "--- ultimas linhas de stdout ---"
        if (Test-Path $logOut) { Get-Content $logOut -Tail 20 | ForEach-Object { Write-Host "    $_" } }
    }

    Write-Step "encerrando"
    # taskkill /T mata a arvore. Deixar uvicorn orfao trava a porta e segura
    # mais de 1GB de RAM: e o bug classico de shell Electron mal fechado.
    try {
        $ErrorActionPreference = "Continue"
        & taskkill.exe /PID $proc.Id /T /F *>$null
        Write-Ok "processo encerrado"
    } catch {
        Write-Ok "processo ja havia terminado"
    } finally {
        $ErrorActionPreference = "Stop"
    }
}

if ($exitCode -eq 0) {
    Write-Step "SMOKE TEST PASSOU"
    Write-Ok "o backend roda fora do Docker, de $TestRoot"
} else {
    Write-Step "SMOKE TEST FALHOU (codigo $exitCode)"
}
exit $exitCode

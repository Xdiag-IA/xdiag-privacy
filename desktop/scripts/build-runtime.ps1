<#
.SYNOPSIS
  Monta o runtime Python relocavel do Xdiag Privacy para Windows x64.

.DESCRIPTION
  Produz uma pasta autocontida que roda o backend FastAPI sem Docker e sem
  Python instalado na maquina. E o artefato que o instalador vai baixar e
  extrair; nenhum `pip install` roda na maquina do usuario final.

  Base: python-build-standalone (mesma distribuicao usada pelo uv). Ao
  contrario do "embeddable package" oficial, esses builds sao CPython
  completos e projetados para serem relocaveis, que e exatamente o requisito
  aqui: a pasta precisa funcionar em %LOCALAPPDATA% de um usuario chamado
  "Jose Antonio" sem nada ter sido compilado ali.

  Nao cria venv de proposito. Um venv do Windows guarda o caminho absoluto do
  Python base em pyvenv.cfg, entao nao sobrevive a uma copia de pasta. Aqui os
  pacotes vao direto para o site-packages da propria distribuicao.

  A ordem de instalacao espelha backend/Dockerfile: torch CPU primeiro, a
  partir do indice proprio, senao o resolvedor puxa as wheels cu12 (~3GB).

.PARAMETER Stage
  all       (padrao) baixa, extrai e instala tudo
  python    so baixa e extrai a distribuicao Python
  deps      so instala as dependencias (assume Python ja extraido)
  prune     so remove peso morto do site-packages

.PARAMETER Force
  Refaz do zero, apagando build/runtime.
#>
[CmdletBinding()]
param(
    [ValidateSet("all", "python", "deps", "prune")]
    [string]$Stage = "all",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
# Sem isso o Invoke-WebRequest pinta uma barra de progresso que sozinha
# multiplica por varias vezes o tempo de um download grande.
$ProgressPreference = "SilentlyContinue"

# Versao fixada de proposito. O instalador precisa ser deterministico: o que
# funcionou no teste tem que ser bit a bit o que roda na maquina do medico.
$PythonVersion = "3.11.15"
$PythonBuild = "20260718"
$PythonUrl = "https://github.com/astral-sh/python-build-standalone/releases/download/$PythonBuild/cpython-$PythonVersion+$PythonBuild-x86_64-pc-windows-msvc-install_only.tar.gz"

$DesktopDir = Split-Path -Parent $PSScriptRoot
$RepoDir = Split-Path -Parent $DesktopDir
$BuildDir = Join-Path $DesktopDir "build"
$DownloadDir = Join-Path $BuildDir "downloads"
$RuntimeDir = Join-Path $BuildDir "runtime"
$PythonDir = Join-Path $RuntimeDir "python"
$PythonExe = Join-Path $PythonDir "python.exe"
$Requirements = Join-Path $RepoDir "backend\requirements.txt"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn2($msg) { Write-Host "    $msg" -ForegroundColor Yellow }

function Get-DirSizeGB($path) {
    if (-not (Test-Path $path)) { return 0 }
    $bytes = (Get-ChildItem $path -Recurse -File -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum).Sum
    return [math]::Round($bytes / 1GB, 2)
}

if ($Force -and (Test-Path $RuntimeDir)) {
    Write-Step "Force: removendo $RuntimeDir"
    Remove-Item $RuntimeDir -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $DownloadDir | Out-Null
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

# --- 1. Distribuicao Python relocavel ---------------------------------------

if ($Stage -eq "all" -or $Stage -eq "python") {
    Write-Step "Python $PythonVersion (python-build-standalone $PythonBuild)"
    $archive = Join-Path $DownloadDir "cpython-$PythonVersion-win64.tar.gz"

    if (Test-Path $archive) {
        Write-Ok "arquivo ja baixado, reaproveitando"
    } else {
        Write-Host "    baixando $PythonUrl"
        Invoke-WebRequest -Uri $PythonUrl -OutFile $archive -UseBasicParsing
        Write-Ok "baixado ($([math]::Round((Get-Item $archive).Length / 1MB, 1)) MB)"
    }

    if (Test-Path $PythonExe) {
        Write-Ok "python ja extraido"
    } else {
        # tar.exe do Windows (bsdtar) le .tar.gz nativamente desde o Win10 1803.
        # O arquivo extrai uma pasta "python/" na raiz.
        tar.exe -xzf $archive -C $RuntimeDir
        if ($LASTEXITCODE -ne 0) { throw "falha ao extrair $archive" }
        Write-Ok "extraido em $PythonDir"
    }

    & $PythonExe -c "import sys; print('    python', sys.version.split()[0], sys.executable)"
    if ($LASTEXITCODE -ne 0) { throw "python extraido nao executa" }

    & $PythonExe -m pip --version
    if ($LASTEXITCODE -ne 0) { throw "distribuicao veio sem pip" }
}

# --- 2. Dependencias --------------------------------------------------------

if ($Stage -eq "all" -or $Stage -eq "deps") {
    if (-not (Test-Path $PythonExe)) { throw "rode o estagio 'python' antes de 'deps'" }

    Write-Step "pip atualizado"
    & $PythonExe -m pip install --upgrade pip --no-warn-script-location
    if ($LASTEXITCODE -ne 0) { throw "falha ao atualizar pip" }

    # Torch primeiro, do indice CPU. Se vier depois, o resolvedor ja terá
    # fixado a variante CUDA por causa de outra dependencia.
    Write-Step "torch (indice CPU)"
    & $PythonExe -m pip install --no-warn-script-location `
        --index-url https://download.pytorch.org/whl/cpu "torch>=2.4,<3"
    if ($LASTEXITCODE -ne 0) { throw "falha ao instalar torch CPU" }
    Write-Ok "torch instalado"

    Write-Step "requirements do backend"
    & $PythonExe -m pip install --no-warn-script-location -r $Requirements
    if ($LASTEXITCODE -ne 0) { throw "falha ao instalar requirements" }
    Write-Ok "requirements instalados"

    # openmed e best effort, igual ao Dockerfile: pii.py tem fallback para
    # transformers puro se o pacote nao existir no indice.
    Write-Step "openmed[hf] (best effort)"
    & $PythonExe -m pip install --no-warn-script-location "openmed[hf]"
    if ($LASTEXITCODE -ne 0) {
        Write-Warn2 "openmed indisponivel, seguindo com o fallback de transformers"
    } else {
        Write-Ok "openmed instalado"
    }

    Write-Step "tamanho apos instalacao"
    Write-Ok "$(Get-DirSizeGB $RuntimeDir) GB em $RuntimeDir"
}

# --- 3. Poda ----------------------------------------------------------------

if ($Stage -eq "all" -or $Stage -eq "prune") {
    Write-Step "removendo peso morto"
    $before = Get-DirSizeGB $RuntimeDir

    # __pycache__ do build: o app regenera o que precisar no primeiro import.
    Get-ChildItem $PythonDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

    # Suites de teste embarcadas em pacotes grandes. Nao sao importadas em
    # runtime e somam centenas de MB.
    $sitePackages = Join-Path $PythonDir "Lib\site-packages"
    foreach ($rel in @("torch\test", "torch\include", "numpy\tests", "scipy\**\tests", "sympy\**\tests")) {
        Get-ChildItem (Join-Path $sitePackages $rel) -ErrorAction SilentlyContinue |
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }

    $after = Get-DirSizeGB $RuntimeDir
    Write-Ok "$before GB -> $after GB"
}

Write-Step "pronto"
Write-Ok "runtime: $RuntimeDir"
Write-Ok "tamanho: $(Get-DirSizeGB $RuntimeDir) GB"

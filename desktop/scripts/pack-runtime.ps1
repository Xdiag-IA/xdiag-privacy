<#
.SYNOPSIS
  Empacota o runtime Python num zip publicavel, com hash SHA256.

.DESCRIPTION
  Este e o blob que o instalador NAO carrega. O instalador tem 79 MB; o
  runtime tem 1,6 GB e e baixado na primeira execucao.

  A razao de nao embutir nao e preferencia: o NSIS e um executavel de 32 bits
  e falha ao mapear o proprio payload acima de cerca de 2 GB
  ("File: failed creating mmap"). Com tudo dentro, o instalador simplesmente
  nao compila.

  Formato zip de proposito, e nao 7z: o Windows 10 1803+ traz o bsdtar como
  tar.exe, que extrai zip nativamente. Assim o aplicativo nao precisa
  carregar nenhum binario de descompactacao junto.
#>
[CmdletBinding()]
param(
    [string]$Version = "0.1.0"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$DesktopDir = Split-Path -Parent $PSScriptRoot
$RuntimeDir = Join-Path $DesktopDir "build\runtime"
$PythonDir = Join-Path $RuntimeDir "python"
$OutDir = Join-Path $DesktopDir "dist-artifacts"

if (-not (Test-Path (Join-Path $PythonDir "python.exe"))) {
    throw "runtime nao encontrado em $PythonDir. Rode build-runtime.ps1 antes."
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$name = "xdiag-runtime-win-x64-$Version.zip"
$zip = Join-Path $OutDir $name
if (Test-Path $zip) { Remove-Item $zip -Force }

Write-Host "==> limpando peso morto antes de empacotar" -ForegroundColor Cyan
# __pycache__ do build: o app regenera no primeiro import, e sao dezenas de MB
# de arquivo que so existem porque a maquina de build executou os modulos.
Get-ChildItem $PythonDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
# A copia do backend feita pelo smoke test nao entra: o codigo do backend
# viaja dentro do instalador, versionado junto com o app.
Remove-Item (Join-Path $RuntimeDir "app") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $RuntimeDir "data") -Recurse -Force -ErrorAction SilentlyContinue

$antes = [math]::Round(((Get-ChildItem $PythonDir -Recurse -File | Measure-Object Length -Sum).Sum)/1GB, 2)
Write-Host "    runtime: $antes GB" -ForegroundColor Green

Write-Host "==> compactando (leva alguns minutos)" -ForegroundColor Cyan
# tar.exe (bsdtar) do proprio Windows. O -a infere o formato pela extensao.
# Empacota a pasta "python" a partir de build/runtime, entao ao extrair na
# raiz do destino nasce <destino>/python/python.exe, que e o que o app espera.
Push-Location $RuntimeDir
try {
    tar.exe -a -c -f $zip "python"
    if ($LASTEXITCODE -ne 0) { throw "tar.exe falhou ao criar $zip" }
} finally {
    Pop-Location
}

$mb = [math]::Round((Get-Item $zip).Length/1MB, 1)
Write-Host "    $name  $mb MB" -ForegroundColor Green

Write-Host "==> SHA256" -ForegroundColor Cyan
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
"$hash  $name" | Set-Content -Path "$zip.sha256" -Encoding ascii
Write-Host "    $hash" -ForegroundColor Green

Write-Host "`n==> pronto" -ForegroundColor Cyan
Write-Host "    $zip"
Write-Host "`nPara publicar como asset do release:" -ForegroundColor Yellow
Write-Host "    gh release create runtime-v$Version `"$zip`" `"$zip.sha256`" --title `"Runtime Python $Version`" --notes `"Runtime baixado pelo instalador na primeira execucao.`""

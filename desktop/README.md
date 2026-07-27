# Xdiag Privacy Desktop

Empacotamento do Xdiag Privacy como aplicativo Windows, para quem não vai
instalar Docker.

O alvo é um instalador pequeno (bootstrapper) que baixa o runtime e os modelos
na primeira execução. Docker continua sendo o caminho de quem quer servidor ou
GPU; os dois convivem no mesmo repositório.

## Estado atual

Fase 0 concluída: **o backend roda fora do Docker, no Windows, a partir de uma
pasta relocável.** O que falta é o shell Electron, o instalador e a assinatura.

## Como reproduzir

```powershell
# 1. Monta o runtime Python relocável em desktop/build/runtime (~1,6 GB)
powershell -ExecutionPolicy Bypass -File .\desktop\scripts\build-runtime.ps1

# 2. Valida sem baixar modelo (segundos)
powershell -ExecutionPolicy Bypass -File .\desktop\scripts\smoke-test.ps1 -Mock

# 3. Valida de verdade (baixa ~2,1 GB do HuggingFace na primeira vez)
powershell -ExecutionPolicy Bypass -File .\desktop\scripts\smoke-test.ps1
```

O `smoke-test.ps1` copia o runtime para
`%LOCALAPPDATA%\Programs\Xdiag Privacy (José Antônio)` antes de subir. O nome
com espaço e acento é proposital: é o caminho real de boa parte dos usuários e
é o que quebra empacotamento mal feito.

## Números medidos

Máquina de referência: Windows 11 Pro, CPU, disco NVMe.

| | Medido |
|---|---|
| Python 3.11.15 standalone (download) | 46 MB |
| Python + dependências instaladas | 1,62 GB |
| Modelo OpenMed 568M (HuggingFace) | 2,13 GB |
| Modelos PaddleOCR | 0,02 GB |
| **Total instalado** | **~3,8 GB** |
| Primeira subida, baixando os modelos | 6 min 37 s |
| Subida com cache quente | 1 min 11 s |
| Processar uma página | 8 a 10 s |

Bem abaixo dos 4,05 GB da imagem Docker de Linux, que carrega camada de
sistema operacional e `build-essential` que aqui não existem.

## Decisões

**python-build-standalone, não o embeddable package oficial.** É a mesma
distribuição que o `uv` usa. São builds CPython completos e projetados para
serem relocáveis. O embeddable package desabilita processamento de
`site-packages` por padrão e quebra pacotes que dependem de arquivos `.pth`.

**Sem venv.** Um venv do Windows grava o caminho absoluto do Python base em
`pyvenv.cfg`, então não sobrevive a uma cópia de pasta. Os pacotes vão direto
para o `site-packages` da própria distribuição.

**Nunca rodar `pip install` na máquina do usuário.** O ambiente inteiro é
montado no CI, empacotado e verificado por hash. O instalador só baixa,
confere e extrai. `pip` na máquina do usuário significa proxy de clínica,
antivírus, resolução divergindo com o tempo e taxa alta de instalação
quebrada.

**Ordem de instalação espelha o `backend/Dockerfile`:** torch CPU primeiro, do
índice próprio. Se vier depois, o resolvedor já terá fixado a variante CUDA
por causa de outra dependência.

## Armadilhas encontradas

### torch e paddle brigam por `libiomp5md.dll` (resolvido)

`torch` e `paddlepaddle` empacotam cada um a sua cópia do runtime OpenMP da
Intel. O Windows resolve DLL por **nome de módulo já carregado**, não por
caminho, então a primeira das duas a ser importada fixa qual `libiomp5md` o
processo inteiro usa.

Na ordem `paddle -> torch`, o `torch\lib\shm.dll` é resolvido contra o
`libiomp5md` do paddle, que não exporta tudo que ele espera, e o import morre
com `OSError: [WinError 127]`. E essa ordem acontecia sozinha, porque
`paddleocr` importa `albumentations`, que importa `torch`.

O container Linux nunca viu isso: lá o loader resolve por SONAME com caminho e
as duas cópias convivem. É um bug que só existe no build para Windows.

Corrigido em `backend/app/ocr.py`, com `_preload_torch_before_paddle()` colado
no único import de `paddleocr` do projeto. Guardado por `sys.platform` para
não custar nada no Linux.

### PaddleOCR ignora a pasta de cache configurada (aberto)

`PADDLE_PDX_CACHE_HOME` é do PaddleX, não do PaddleOCR 2.x. O PaddleOCR grava
os modelos em `%USERPROFILE%\.paddleocr` (cerca de 20 MB), fora da pasta do
aplicativo. Sobrevive à desinstalação e pode ser bloqueado em perfil
corporativo restrito.

Correção: passar `det_model_dir`, `rec_model_dir` e `cls_model_dir` explícitos
na construção do `PaddleOCR` em `ocr.py`.

### Os defaults de `config.py` são caminhos Linux

`samples_dir` e `cache_dir` apontam para `/app/...`. No Windows precisam ser
sobrescritos por variável de ambiente ou o backend escreve em lugar nenhum. O
perfil desktop precisa definir `XDIAG_CACHE_DIR` e `XDIAG_SAMPLES_DIR`.

### `XDIAG_HOST` precisa mudar no desktop

O default é `0.0.0.0`. Num aplicativo de mesa isso publicaria a API de
anonimização de prontuário para a rede inteira da clínica. O perfil desktop
usa `127.0.0.1` com porta efêmera escolhida em runtime.

### PowerShell 5.1 lê `.ps1` sem BOM como ANSI

Um `é` digitado direto no script vira mojibake. Em `smoke-test.ps1` o nome da
pasta de teste é montado por codepoint (`[char]0x00E9`), senão o teste
exercitaria um caminho diferente do que diz exercitar.

## Próximos passos

1. **Perfil desktop no backend**: `127.0.0.1`, porta em runtime, caminhos de
   cache do Windows, `PaddleOCR` com diretórios de modelo explícitos, e
   `StaticFiles` servindo o SPA na mesma origem (sem isso o
   `showDirectoryPicker` da pasta de saída não funciona, porque `file://` não
   é contexto seguro).
2. **Shell Electron**: splash, spawn do backend, poll de `/api/health`,
   encerramento da árvore de processos.
3. **Instalador**: `electron-builder` com NSIS por usuário, sem UAC, e a tela
   de primeira execução que baixa runtime e modelo com retomada e verificação
   de SHA256.
4. **Assinatura**: sem certificado o SmartScreen mostra aviso e derruba
   conversão.

### Sobre a subida de 1 min 11 s

É o custo de carregar o modelo fp32 de 2,1 GB do disco. Opções, se incomodar:
manter o backend residente na bandeja entre usos, carregar sob demanda para a
janela abrir na hora, ou revisitar quantização (agora só pelo tempo de carga,
não pelo tamanho, e ainda assim medindo recall contra `tests/corpus` antes).

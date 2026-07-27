# Xdiag Privacy

Demonstrador local first de anonimizacao visual de documentos medicos
brasileiros. Roda 100 por cento offline apos a primeira inicializacao,
combina PaddleOCR (lang=pt) com o modelo
`OpenMed/OpenMed-PII-Portuguese-SnowflakeMed-Large-568M-v1` para detectar
PII (CPF, CNPJ, RG, nome, data, idade, telefone, email, endereco, CRM,
prontuario), e rastreia visualmente o processo de redacao no estilo da
camada de tracking visual do OpenMed.

> Aviso LGPD: esta ferramenta auxilia o tratamento de dados pessoais; ela
> nao substitui DPO, encarregado, politica de privacidade nem revisao
> juridica. O operador permanece responsavel pelo uso legitimo, retencao,
> registro de operacoes (Art. 37 da LGPD) e descarte seguro.

## Quickstart

```bash
docker compose up --build
```

Aguarde a primeira execucao baixar PaddleOCR e o modelo OpenMed (cerca de
700 MB no total). Em seguida abra `http://localhost:5173` e arraste um
documento. Para um teste imediato sem download de modelos:

```bash
XDIAG_MOCK=1 docker compose up --build
```

API: `http://localhost:8800`. Documentacao OpenAPI em `/docs`.

> A porta 8800 foi escolhida para evitar choque com a 8000 (comum em outras
> ferramentas Python locais). Para mudar, ajuste o mapping em
> `docker-compose.yml` no servico `api` e tambem o `VITE_API_BASE_URL` do
> servico `web`.

## Requisitos

- Docker 24+ e Docker Compose v2
- 8 GB de RAM
- (Opcional) GPU NVIDIA com `nvidia-container-toolkit`. Para usar, ajuste
  `XDIAG_OCR_USE_GPU=1` e `XDIAG_PII_DEVICE=0` no `docker-compose.yml`,
  acrescente `runtime: nvidia` ao servico `api` e troque a base do
  Dockerfile para `nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04`.

## Estrutura do projeto

```
xdiag-redact/
  backend/
    app/
      main.py        FastAPI, CORS, static samples
      ocr.py         wrapper PaddleOCR + offset map
      pii.py         wrapper OpenMed + validadores BR (Luhn CPF/CNPJ)
      mapper.py      conversao de spans PII em bboxes da imagem
      models.py      schemas Pydantic
      config.py      configuracao via env
    requirements.txt
    Dockerfile
  frontend/
    src/
      App.tsx
      main.tsx
      theme/
      api/             cliente axios + tipos
      stores/          Zustand
      components/      AppHeader, UploadZone, DocumentViewer,
                       RedactionHeader, EntityList, ControlsPanel,
                       ProgressTracker
    package.json
    Dockerfile
  samples/             documentos sinteticos PNG de demonstracao
  tests/
    corpus/            17 PNGs + 1 PDF sinteticos com gabarito JSON
    baselines/         baselines de recall versionados (evaluate.py)
  scripts/
    generate_samples.py  gera corpus com gabarito e samples de demo
    evaluate.py          mede recall/precisao por label contra o corpus
    smoke_test.py        roda OCR+PII+mapper em mock mode
  docker-compose.yml
  README.md
```

## Endpoints

- `GET /api/health` status do servico, modelos, dispositivo, modo mock
- `GET /api/labels` rotulos suportados com cor hexadecimal e placeholder
- `POST /api/redact` recebe `multipart/form-data` com `file`. Aceita as
  query params:
  - `reveal=true` retorna `original_text` no payload (uso administrativo)
  - `threshold=0.5` filtra entidades com score abaixo do limite
  - `is_synthetic=true` marca o arquivo como sintetico (apenas metadado,
    o frontend usa para renderizar a marca dagua)

Resposta (uma entrada em `pages` por pagina do documento; PDFs sao
processados por inteiro, ate `XDIAG_MAX_PDF_PAGES` paginas, acima disso a
API retorna 422 explicito, nunca processa parcialmente em silencio):

```json
{
  "pages": [
    {
      "page_index": 0,
      "image_dimensions": { "w": 1240, "h": 1754 },
      "ocr_blocks": [{ "text": "...", "bbox": [[x,y], ...], "confidence": 0.99, "char_start": 0, "char_end": 23 }],
      "entities": [
        {
          "label": "BR_CPF",
          "text": "529.982.247-25",
          "score": 0.99,
          "char_span": [142, 156],
          "bboxes": [[[x1,y1],[x2,y2],[x3,y3],[x4,y4]]],
          "redacted": "[CPF]",
          "unmapped": false
        }
      ],
      "deidentified_text": "...",
      "rendered_image_data_url": "data:image/png;base64,..."
    }
  ],
  "page_count": 1,
  "stats": { "total_entities": 11, "by_label": { "BR_CPF": 1 }, "unmapped": 0 },
  "is_synthetic": false,
  "elapsed_ms": 3214
}
```

Entidade com `unmapped: true` foi detectada no texto mas nao tem regiao
mapeada na imagem; o frontend bloqueia o export ate a revisao.

## Gerando os samples sinteticos

```bash
python scripts/generate_samples.py
```

Os PNGs sao escritos em `samples/`. O backend monta essa pasta como
diretorio estatico, e o frontend oferece atalhos para carregar cada um
sem upload manual.

## Smoke test

```bash
XDIAG_MOCK=1 python scripts/smoke_test.py
```

Roda o pipeline OCR + PII + mapper sem PaddleOCR nem OpenMed, validando os
schemas e o calculo de bboxes. Util para testar mudancas no `mapper.py` ou
em `models.py` rapidamente.

## Harness de regressao de recall

O diretorio `tests/corpus/` contem 17 PNGs e 1 PDF sinteticos com gabarito
JSON (spans de PII que DEVEM ser tarjados, spans opcionais e regioes nao
textuais como barcode, QR, assinatura e faixa de ultrassom). Para regenerar:

```bash
pip install -r scripts/requirements-dev.txt
python scripts/generate_samples.py --corpus
```

O avaliador roda o pipeline sobre o corpus e imprime, por label, recall e
precisao, com os falsos negativos listados um a um e PRIMEIRO no relatorio.
Politica do projeto: falso negativo e falha critica; falso positivo e ruido
aceitavel. Execucao com o modelo real (reusa o volume de modelos):

```bash
docker compose run --rm eval --level text
```

```bash
docker compose run --rm eval --level full
```

`--level text` injeta o texto canonico do gabarito direto no detector de PII
(rapido, isola pii.py). `--level full` roda PNG -> OCR -> PII -> mapper e
casa por cobertura de pixels, imune a variacao do OCR. `--save-baseline`
grava `tests/baselines/baseline-<level>.json` (versionado); execucoes
seguintes comparam e retornam exit code 1 se houver regressao. Regra do
projeto: rodar antes e depois de cada bloco de mudanca; bloco que piora
recall em qualquer label e revertido.

## Validando o requisito de zero saida de rede

Apos a primeira execucao (modelos ja em cache no volume `xdiag-redact-models`),
suba o stack e observe o trafego:

```bash
docker compose up -d
docker run --rm --net=container:xdiag-privacy-api nicolaka/netshoot \
  tcpdump -nn -i any not port 8000
```

Faca varios uploads via UI. O `tcpdump` deve permanecer silencioso. Se
preferir uma checagem mais simples, `docker compose logs api | grep -i
"download\|http\|request"` nao deve mostrar trafego externo.

## Adicionando novos labels

1. Em `backend/app/pii.py`, acrescente o label novo aos dicionarios
   `LABEL_PLACEHOLDER` e `LABEL_COLOR`.
2. Espelhe a entrada em `frontend/src/labels.ts`
   (`LABEL_COLORS` e o map `FRIENDLY`).
3. Se o modelo OpenMed nao emite o label nativamente, voce pode:
   - escrever um regex no caminho mock e tambem como filtro de pos
     processamento em `_post_filter`, ou
   - fine tunar / adicionar uma regra heuristica em `pii.py` apos a
     deteccao do modelo.

## Trocando para o modelo Small (44M) para edge

Em `docker-compose.yml`, ajuste:

```yaml
environment:
  XDIAG_PII_MODEL: OpenMed/OpenMed-PII-Portuguese-SnowflakeMed-Small-44M-v1
```

A versao Small reduz o uso de RAM em cerca de 90 por cento e fica abaixo
de 200 MB de download, ao custo de recall menor em entidades raras
(prontuario, CEP, CRM longo). Recomendado para deploy em maquinas com
4 GB de RAM ou menor.

## UX, animacao progressiva

A camada visual replica o tracking do OpenMed:

- Layout split, esquerda 60 por cento (viewer), direita 40 por cento
  (painel)
- Documento renderizado em canvas com SVG overlay absoluto
- Cada entidade entra com fade in de 200 ms apos um delay de 80 ms
  acumulado, ordenada de cima para baixo pelo `y1` da bbox
- Header sticky com contador `X / Y redacted` e label atual em destaque
- Marca dagua diagonal `SYNTHETIC` quando o arquivo veio de `samples/`
- Controles de threshold (re processa ao soltar o slider) e toggle de
  texto original (com confirmacao via toast)
- Exporta PNG anonimizado (poligonos preenchidos em preto solido) e TXT
  com placeholders por entidade

## Modelos e dependencias principais

- PaddleOCR 2.8.x, lang=pt, det+rec
- OpenMed PII Portuguese SnowflakeMed Large 568M (default) ou Small 44M
- transformers 4.45+, torch 2.4+, accelerate, sentencepiece
- pypdfium2 (renderiza primeira pagina de PDF sem dependencias nativas)

## Licenca

Apache 2.0, herdada do projeto OpenMed. Inclua a nota de atribuicao do
modelo OpenMed em qualquer redistribuicao.

## Roadmap curto

- multi pagina de PDF com paginacao no viewer
- exportacao em JSON com auditoria (timestamp, hash do upload, lista de
  entidades, threshold)
- batching server side com fila local (RQ + redis local) para clinicas
  com throughput mais alto
- suporte ao modelo Multi (varias linguas) para documentos hibridos
- modo air gapped: pre baixar modelos para um diretorio e validar via
  hash em vez de pegar no startup

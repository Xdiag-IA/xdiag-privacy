# Xdiag Privacy

**Anonimização visual de documentos médicos brasileiros, rodando inteiramente na sua máquina.**

Você arrasta um laudo, uma ficha, uma receita ou uma guia TISS. A ferramenta lê
o documento, encontra os dados pessoais, mostra cada um deles marcado sobre a
imagem para você conferir, e exporta uma versão com os dados cobertos por tarja
preta. Nenhum arquivo sai do computador em nenhum momento.

Feito por [Xdiag Tecnologias](https://www.xdiag.com.br), empresa brasileira de
inteligência artificial em saúde, com médicos no time.

> ### ⚠️ Leia antes de usar
>
> Esta ferramenta **auxilia** o tratamento de dados pessoais sensíveis. Ela
> **não substitui** DPO, encarregado de dados, política de privacidade nem
> revisão jurídica. Nenhum modelo de IA acerta 100% das vezes: **sempre
> confira o resultado antes de compartilhar qualquer documento**. O operador
> continua responsável pelo uso legítimo, pela retenção, pelo registro de
> operações (Art. 37 da LGPD) e pelo descarte seguro.

---

## Índice

- [Por que ele existe](#por-que-ele-existe)
- [Feito para o português do Brasil](#feito-para-o-português-do-brasil)
- [O que ele detecta](#o-que-ele-detecta)
- [Como funciona](#como-funciona)
- [A tarja apaga o pixel, não cobre](#a-tarja-apaga-o-pixel-não-cobre)
- [O que ele não faz](#o-que-ele-não-faz)
- [Como rodar](#como-rodar)
- [Provando que nada sai da máquina](#provando-que-nada-sai-da-máquina)
- [Qualidade e regressão](#qualidade-e-regressão)
- [Configuração](#configuração)
- [API](#api)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Contribuindo](#contribuindo)
- [Licença e créditos](#licença-e-créditos)

---

## Por que ele existe

Compartilhar um caso clínico é rotina: mandar um laudo para um colega, montar
uma aula, publicar um artigo, alimentar um estudo, treinar um residente. Só que
esses documentos vêm cheios de dado pessoal, e tarjar tudo à mão em dezenas de
arquivos é o tipo de tarefa que ninguém faz direito por muito tempo.

As alternativas que existem quase sempre falham em um dos três pontos:

1. **Mandam o documento para a nuvem.** Prontuário de paciente saindo da
   clínica para um servidor de terceiro é exatamente o que a LGPD trata como
   risco, e num serviço estrangeiro vira transferência internacional de dado
   sensível.
2. **Não entendem documento brasileiro.** Ferramenta genérica não sabe o que é
   CNS, CRM, RQE, guia TISS ou carteirinha de convênio, e não valida CPF nem
   CNPJ.
3. **Só desenham um retângulo por cima.** É o erro clássico de PDF de tribunal:
   a tarja é uma camada, e o texto continua lá embaixo, selecionável.

O Xdiag Privacy foi feito para não cair em nenhum dos três.

## Feito para o português do Brasil

Esta não é uma ferramenta internacional traduzida. Cada peça foi escolhida
para o contexto brasileiro:

- **OCR em português** (PaddleOCR com `lang=pt`), que lida com a acentuação e
  com o vocabulário clínico daqui.
- **Modelo de PII treinado em português**
  (`OpenMed/OpenMed-PII-Portuguese-SnowflakeMed-Large-568M-v1`), não um modelo
  em inglês adaptado.
- **Validação real dos nossos documentos**: CPF, CNPJ e CNS passam pelo
  dígito verificador. Número que não valida não é tratado como documento, o
  que derruba falso positivo em número de exame e código de barras.
- **Identificadores do sistema de saúde brasileiro**: CNS, CRM, RQE, COREN,
  CNES, número de guia e senha de autorização TISS, carteirinha de convênio,
  prontuário.
- **A interface inteira em português.**

## O que ele detecta

| Família | Rótulos |
| --- | --- |
| Pessoa | nome de paciente, nome de médico ou profissional |
| Documento oficial | CPF, CNPJ, RG, CNS |
| Registro interno | prontuário, identificador genérico |
| Contato | telefone, e-mail |
| Endereço | logradouro, cidade, UF, CEP |
| Temporal | data, data de nascimento, idade |
| Conselho profissional | CRM, RQE, COREN |
| Instituição | hospital, clínica, laboratório, CNES |
| Convênio | número de guia, senha de autorização, carteirinha |
| Rede | URL, endereço IP |

Números suspeitos que não se encaixam em nenhuma categoria conhecida também
são tarjados, por decisão de projeto: na dúvida, cobre.

Faltou alguma coisa? Você pode **desenhar a tarja à mão** direto sobre o
documento, e ela entra no arquivo exportado igual às automáticas.

## Como funciona

```
documento (PNG, JPG, WEBP ou PDF)
        │
        ▼
   PaddleOCR (pt)          lê o texto e guarda onde cada caractere está na imagem
        │
        ▼
   modelo OpenMed          encontra os dados pessoais no texto
        │
        ▼
   validadores BR          confere dígito verificador de CPF, CNPJ e CNS
        │
        ▼
   mapeador                converte a posição no texto em retângulo na imagem
        │
        ▼
   revisão humana          você confere cada marcação na tela
        │
        ▼
   export                  PNG com os pixels apagados, ou TXT com marcadores
```

O detalhe que faz o conjunto funcionar é o **mapa de deslocamento**: o OCR não
devolve só o texto, ele guarda a que linha da imagem cada caractere pertence.
É isso que permite pegar um CPF encontrado na posição 142 do texto e saber
exatamente qual retângulo cobrir na imagem, sem tokenizar nada de novo.

### Falha fechada, por princípio

Se uma entidade é encontrada no texto mas **não** consegue ser localizada na
imagem, ela é marcada como não mapeada e **o export é bloqueado**. A ferramenta
prefere não deixar você exportar a deixar você exportar um arquivo que ainda
mostra o dado. O mesmo vale para PDF acima do limite de páginas: a API responde
erro explícito em vez de processar só uma parte em silêncio.

## A tarja apaga o pixel, não cobre

Este é o ponto onde a maioria das ferramentas falha, então vale ser específico.

O export **não** desenha um retângulo por cima. Ele reescreve os bytes da
imagem: cada pixel da região tarjada passa a ser preto puro `(0, 0, 0, 255)`.
Não existe camada, não existe "embaixo", não existe nada para recuperar.

Medição feita sobre um arquivo realmente exportado, varrendo toda a área das
tarjas incluindo as bordas:

```
22.201 pixels analisados
     0 pixels não pretos
     0 de luminância máxima residual
```

O perfil vertical atravessando uma tarja é um degrau exato: papel branco (255),
tarja (0), papel branco (255), sem nenhuma linha intermediária. A implementação
escreve direto em `ImageData` justamente para evitar o antialiasing que o
preenchimento de contorno do canvas deixaria na borda, e as coordenadas são
arredondadas **para fora**, de modo que qualquer pixel encostado pela detecção
seja apagado.

Dois efeitos colaterais que jogam a favor:

- **O PDF perde a camada de texto.** O export é uma imagem rasterizada, então
  o erro clássico de "texto selecionável embaixo da tarja" não é possível aqui.
- **Os metadados morrem junto.** A imagem é reconstruída a partir dos pixels,
  então EXIF, dados de scanner e o nome do arquivo original não sobrevivem. O
  arquivo exportado contém apenas `IHDR`, `IDAT` e `IEND`.

E o nome do arquivo também é tratado: o padrão gera um nome novo
(`anonimizado_2026-07-27_a1b2c3.png`) em vez de reaproveitar o original, porque
laudo de laboratório quase sempre chega nomeado com o paciente, e o nome do
arquivo viaja junto com ele no e-mail e no WhatsApp.

## O que ele não faz

Ser honesto sobre os limites é parte da ferramenta:

- **Não substitui a sua revisão.** Nenhum modelo acerta sempre. A tela de
  auditoria existe justamente para você conferir antes de exportar.
- **Não anonimiza o conteúdo clínico.** Uma combinação rara de diagnóstico,
  data e cidade pode reidentificar alguém mesmo sem nome nem CPF. Isso é
  julgamento humano.
- **Documento com mais de uma página exporta só o texto por enquanto.** O
  export de imagem multipágina ainda não está pronto e fica bloqueado de
  propósito, em vez de exportar só a primeira página em silêncio.
- **Não faz OCR de manuscrito.** Letra de médico à mão continua sendo letra de
  médico à mão.
- **Não é dispositivo médico** e não emite laudo, diagnóstico ou parecer.

## Como rodar

Hoje o caminho é Docker. Um instalador para Windows, sem exigir Docker, está
em desenvolvimento (veja [`desktop/`](desktop/)).

### Requisitos

- Docker 24+ com Docker Compose v2
- 8 GB de RAM
- Cerca de 4 GB de espaço em disco para os modelos
- Internet **apenas na primeira execução**, para baixar os modelos

### Subindo

```bash
git clone https://github.com/Xdiag-IA/xdiag-privacy.git
```

```bash
cd xdiag-privacy && docker compose up --build
```

A primeira execução baixa o PaddleOCR e o modelo OpenMed. Depois disso abra
**http://localhost:5173** e arraste um documento.

### Experimentando sem baixar modelo

Para ver a interface funcionando em segundos, com detecções simuladas:

```bash
XDIAG_MOCK=1 docker compose up --build
```

### Documentos de exemplo

A pasta `samples/` traz documentos **sintéticos**, com dados fictícios, para
você testar sem usar material de paciente. Eles aparecem na interface com uma
marca d'água diagonal `SYNTHETIC`, para nunca serem confundidos com documento
real.

Para gerar mais:

```bash
python scripts/generate_samples.py
```

## Provando que nada sai da máquina

A promessa de rodar offline não deveria ser aceita na base da confiança. Depois
da primeira execução, com os modelos já em cache, suba o sistema e observe o
tráfego de rede do container:

```bash
docker compose up -d
```

```bash
docker run --rm --net=container:xdiag-privacy-api nicolaka/netshoot tcpdump -nn -i any not port 8000
```

Faça vários uploads pela interface. O `tcpdump` deve permanecer em silêncio.

## Qualidade e regressão

O diretório `tests/corpus/` contém 18 documentos sintéticos (17 PNG e 1 PDF)
com gabarito em JSON: quais trechos **devem** ser tarjados, quais são
opcionais, e quais regiões não são texto (código de barras, QR, assinatura,
faixa de ultrassom).

**Política do projeto: falso negativo é falha crítica, falso positivo é ruído
aceitável.** O avaliador lista os falsos negativos primeiro, antes de qualquer
outra métrica.

```bash
docker compose run --rm eval --level text
```

```bash
docker compose run --rm eval --level full
```

`--level text` injeta o texto do gabarito direto no detector, isolando a
detecção de PII. `--level full` roda o caminho completo, de imagem a tarja, e
compara por cobertura de pixels, o que o torna imune a variação do OCR.

Os baselines ficam versionados em `tests/baselines/`. Uma execução que piore o
recall de qualquer rótulo retorna código de saída 1. A regra é rodar antes e
depois de cada bloco de mudança, e reverter o que piorar.

## Configuração

Tudo é configurável por variável de ambiente, no `docker-compose.yml`:

| Variável | Padrão | O que faz |
| --- | --- | --- |
| `XDIAG_MOCK` | `0` | Simula OCR e PII, sem baixar modelo |
| `XDIAG_CONFIDENCE` | `0.5` | Limite de confiança para detecções sem validação |
| `XDIAG_PII_SCORE_FLOOR` | `0.15` | Piso de coleta antes da validação e do limite |
| `XDIAG_MAX_PDF_PAGES` | `20` | Acima disso a API responde 422 |
| `XDIAG_MAX_UPLOAD` | `20971520` | Tamanho máximo do arquivo, em bytes |
| `XDIAG_PII_MODEL` | OpenMed 568M | Modelo de detecção de PII |
| `XDIAG_OCR_USE_GPU` | `0` | Usa GPU no OCR |
| `XDIAG_PII_DEVICE` | `-1` | `-1` para CPU, `0` para a primeira GPU |

### Máquina com pouca memória

Trocar para o modelo Small reduz o uso de RAM em cerca de 90% e o download
para menos de 200 MB, ao custo de recall menor em entidades raras como
prontuário, CEP e CRM longo. Recomendado abaixo de 4 GB de RAM:

```yaml
environment:
  XDIAG_PII_MODEL: OpenMed/OpenMed-PII-Portuguese-SnowflakeMed-Small-44M-v1
```

### GPU NVIDIA

Ajuste `XDIAG_OCR_USE_GPU=1` e `XDIAG_PII_DEVICE=0`, acrescente
`runtime: nvidia` ao serviço `api` e troque a base do Dockerfile para
`nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04`.

## API

A API fica em `http://localhost:8800`, com documentação OpenAPI em `/docs`.

| Rota | O que faz |
| --- | --- |
| `GET /api/health` | Estado do serviço, modelo carregado, dispositivo |
| `GET /api/labels` | Rótulos suportados, com cor e marcador de substituição |
| `POST /api/redact` | Recebe `multipart/form-data` com o campo `file` |

Parâmetros de query do `/api/redact`:

- `threshold=0.5` filtra detecções abaixo do limite
- `reveal=true` devolve também o texto original (uso administrativo)
- `is_synthetic=true` marca o arquivo como sintético, o que faz a interface
  desenhar a marca d'água

Resposta, com uma entrada em `pages` por página do documento:

```json
{
  "pages": [
    {
      "page_index": 0,
      "image_dimensions": { "w": 1240, "h": 1754 },
      "ocr_blocks": [
        { "text": "...", "bbox": [[0,0]], "confidence": 0.99, "char_start": 0, "char_end": 23 }
      ],
      "entities": [
        {
          "label": "BR_CPF",
          "text": "529.982.247-25",
          "score": 0.99,
          "char_span": [142, 156],
          "bboxes": [[[10,20],[90,20],[90,40],[10,40]]],
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

Entidade com `"unmapped": true` foi encontrada no texto mas não tem região
correspondente na imagem. A interface bloqueia o export até você revisar.

## Estrutura do projeto

```
backend/app/
  main.py       FastAPI, CORS, arquivos estáticos
  ocr.py        PaddleOCR e o mapa de deslocamento de caracteres
  pii.py        modelo OpenMed, rótulos, cores e marcadores
  patterns.py   padrões e validadores brasileiros (CPF, CNPJ, CNS)
  mapper.py     converte posição no texto em retângulo na imagem
  models.py     schemas Pydantic
  config.py     configuração por variável de ambiente

frontend/src/
  components/   interface (viewer, lista de entidades, controles, ajustes)
  stores/       estado (Zustand)
  labels.ts     espelho da paleta e dos nomes dos rótulos do backend
  theme/        design tokens

desktop/        empacotamento para Windows, em desenvolvimento
samples/        documentos sintéticos de demonstração
scripts/        geração de corpus, avaliação de recall, smoke test
tests/          corpus com gabarito e baselines de regressão
```

### Desenvolvimento

Teste rápido do pipeline, sem modelo:

```bash
XDIAG_MOCK=1 python scripts/smoke_test.py
```

Para acrescentar um rótulo novo, mexa nos dois lados: `LABEL_PLACEHOLDER` e
`LABEL_COLOR` em `backend/app/pii.py`, e o espelho em
`frontend/src/labels.ts`. Os dois arquivos têm que continuar em sincronia.

## Contribuindo

Leia o [CONTRIBUTING.md](CONTRIBUTING.md) antes da primeira contribuição.

> ### 🚫 Nunca envie dado de paciente real
>
> Não em issue, não em pull request, não em anexo, não em print, não em log
> colado, não em nome de arquivo. Um documento publicado numa issue é público
> para sempre: fica em cache de busca, em espelhos do repositório e no e-mail
> de todo mundo que acompanha o projeto. Apagar depois não resolve.
>
> Gere um equivalente sintético com `python scripts/generate_samples.py`.

Contribuição é bem-vinda, especialmente:

- documentos brasileiros que a ferramenta erra (falso negativo é o bug mais
  valioso deste projeto)
- padrões e validadores de identificadores que faltam
- melhorias de recall no corpus

Antes de abrir um PR, rode o avaliador de recall antes e depois da sua
mudança. PR que piora o recall de qualquer rótulo não entra, mesmo que melhore
outra coisa.

### Achou uma falha de segurança?

Se você conseguiu recuperar dado de um arquivo que a ferramenta declarou
anonimizado, **não abra issue pública**: o exemplo que demonstra a falha é,
por definição, um documento com dado exposto. Veja o
[SECURITY.md](SECURITY.md) para o canal privado.

## Licença e créditos

Apache 2.0. Veja [LICENSE](LICENSE) e [NOTICE](NOTICE).

Construído sobre trabalho de outras pessoas:

- [OpenMed](https://huggingface.co/OpenMed) pelo modelo de PII em português
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) pelo reconhecimento
  de texto
- A camada visual de acompanhamento da anonimização é inspirada no
  privacy filter tracking do OpenMed

Qualquer redistribuição precisa manter a nota de atribuição do modelo OpenMed.

## Roadmap

- Instalador para Windows, sem exigir Docker
- Export de imagem para documento com várias páginas
- Export em JSON com trilha de auditoria (data, hash do arquivo, entidades,
  limite usado)
- Modo air gapped: modelos pré-baixados e validados por hash, sem nenhuma
  busca na inicialização
- Suporte a documentos com mais de um idioma
- Tarja manual no modo sem interface (`anonimizar.py --tarjar x0,y0,x1,y1`),
  para corrigir o que a detecção deixou de fora sem abrir a tela

---

<sub>Xdiag Tecnologias Ltda. As soluções da Xdiag são ferramentas de apoio e
não substituem avaliação profissional.</sub>

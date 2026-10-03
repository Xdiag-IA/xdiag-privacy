# Modo servidor (VPS, sem interface)

Um perfil opcional do Xdiag Privacy para rodar **num servidor**, sem a interface
web e sem o aplicativo desktop: você entrega uma imagem ou um PDF de até 10 páginas
a um comando e recebe de volta a imagem com os dados pessoais apagados. Serve
para integrar a anonimização a um fluxo automático, como um agente de IA que
recebe documentos por WhatsApp (veja o [exemplo com o Hermes Agent](exemplo-hermes-agent.md)),
um robô de e-mail ou uma fila de arquivos.

> ### ⚠️ Este modo NÃO tem o sigilo absoluto da anonimização local
>
> O aplicativo desktop e o Docker do projeto processam tudo na máquina: nenhum
> arquivo sai dela. **O modo servidor é outra coisa.** No perfil com a camada
> de IA (recomendado, porque é o que dá recall), o **texto lido do documento é
> enviado a um serviço externo** (a Anthropic, por meio do Claude Code). E, num
> servidor, o arquivo ainda passa pela máquina e por quem o entrega a ela.
>
> Quem envia o documento decide se esse caminho serve para aquele documento e
> responde por isso. Quando o documento exigir que nada saia da máquina, use o
> aplicativo desktop. A ferramenta **auxilia e não garante**: sempre confira a
> imagem devolvida antes de compartilhar.

## O que ele faz de diferente do perfil completo

| | Perfil completo (desktop, Docker) | Modo servidor |
|---|---|---|
| OCR | PaddleOCR | **Tesseract** (`XDIAG_OCR_ENGINE=tesseract`) |
| Detecção | Regras brasileiras + modelo local de PII (568M) | Regras brasileiras + **Claude, chamado por `claude -p`** (`XDIAG_PII_ENGINE=rules`, `XDIAG_PII_LLM=claude`) |
| Peso | ~8 GB de RAM, Docker, ~2 GB de modelo | ~80 MB de RAM por documento, sem Docker, sem modelo |
| Tempo | depende da máquina | ~1,5 s por documento só com regras; ~6 s com a camada de IA |
| Saída | interface, com revisão na tela | **comando**, que grava um PNG novo |
| Sigilo local | sim | **não** (veja o aviso acima) |

A tarja é a mesma do projeto: o pixel é apagado (preto puro), não coberto, e o
arquivo sai reconstruído do zero, sem EXIF nem o nome do original.

## Requisitos

- Linux (testado no Ubuntu 26.04), Python 3.11 ou mais novo (testado no 3.14).
- Tesseract com o idioma português. No Ubuntu/Debian:

  ```bash
  sudo apt-get install -y tesseract-ocr tesseract-ocr-por python3-venv python3-pil
  ```

- Para a camada de IA: o [Claude Code](https://code.claude.com/docs/en/setup)
  instalado para o usuário que roda a ferramenta, e uma credencial no ambiente
  do processo: `CLAUDE_CODE_OAUTH_TOKEN` (um token de assinatura gerado com
  `claude setup-token`, que exige plano Pro, Max, Team ou Enterprise) ou
  `ANTHROPIC_API_KEY`. Sem a camada de IA, nada disso é necessário.

## Instalação

```bash
git clone https://github.com/Xdiag-IA/xdiag-privacy.git
cd xdiag-privacy
python3 -m venv --system-site-packages .venv
.venv/bin/pip install numpy pydantic pypdfium2
```

Não instale o `requirements.txt` completo: o modo servidor dispensa o
PaddlePaddle e o PyTorch, e o PaddlePaddle nem suporta o Python 3.14.

## Uso

```bash
.venv/bin/python scripts/anonimizar.py foto.jpg --saida ./saida --perfil vps
```

`--perfil vps` equivale a definir `XDIAG_OCR_ENGINE=tesseract`,
`XDIAG_PII_ENGINE=rules` e `XDIAG_PII_LLM=claude` (só quando você ainda não
definiu). Para **só regras**, sem a camada de IA e sem enviar nada a ninguém,
defina `XDIAG_OCR_ENGINE=tesseract XDIAG_PII_ENGINE=rules` e não use `--perfil`.

| Opção | O que faz |
|---|---|
| `--saida DIR` | Pasta do arquivo tarjado. Padrão: `./saida` |
| `--apagar-entrada` | Apaga o arquivo de entrada ao terminar, **em qualquer resultado** |
| `--forcar` | Entrega mesmo quando o portão de qualidade recusa |
| `--limite N` | Confiança mínima da detecção (padrão 0,5) |

Aceita PNG, JPG, WEBP e **PDF de até 10 páginas** (`--max-paginas` muda o limite).
Um PDF acima do limite é recusado (código 4, `limite_de_paginas`), em vez de
processar só uma parte em silêncio.

- **Imagem gera PNG; PDF gera PDF.** O PDF de saída tem as páginas tarjadas e é
  **só de imagem**: sem camada de texto (a do original não sobrevive) e sem
  metadado do original. Ele leva apenas um título com o nome novo do arquivo e
  a data de geração.
- **As páginas são detectadas em paralelo** (até 4 por vez), porque cada uma é
  uma chamada à camada de IA. Um PDF de 10 páginas leva uns 10 s só com regras.
- **Tudo ou nada:** se uma página tem dado achado no texto e sem posição na
  imagem, o documento inteiro não é entregue (código 3, com a lista das
  páginas).
- **O portão de qualidade vale para o documento inteiro:** uma página em
  branco ou só de imagem não o barra, mas entra nos `avisos` ("página 4: pouco
  texto lido") para você conferir.

### O que o comando devolve

Uma linha de JSON na saída padrão, **sem os valores encontrados**:

```json
{"ok": true, "arquivo": "/…/saida/anonimizado_2026-10-03_a1b2c3.png", "paginas": 1,
 "cobertos": 15, "por_tipo": {"[NOME]": 3, "[CPF]": 1, "[EMAIL]": 2},
 "qualidade": {"caracteres": 811, "confianca": 0.92, "menor_lado_px": 1240},
 "avisos": ["a ferramenta auxilia e nao garante: confira a imagem antes de compartilhar"]}
```

| Código de saída | Significa |
|---|---|
| 0 | Arquivo gravado |
| 2 | **Qualidade ruim**: não entrega (use `--forcar` para ignorar) |
| 3 | Dado achado no texto, mas sem posição na imagem: **não entrega** (falha fechada) |
| 4 | Formato não suportado, ou PDF acima do limite de páginas |
| 5 | Erro (OCR, camada de IA, arquivo ilegível) |

Nenhuma mensagem de erro carrega trecho do documento.

## O portão de qualidade

Quando o OCR lê mal, o dado não é detectado e o arquivo sairia **com ele à
mostra**, sem nenhum erro: a "falha fechada" do projeto cobre entidade que não se
mapeia, não texto que nunca foi lido. Por isso o comando recusa a entrega (código
2) quando:

- o menor lado da imagem tem menos de **800 px**; ou
- foram lidos menos de **20 caracteres**; ou
- a confiança média do OCR é menor que **0,65**.

Os limites foram calibrados no corpus limpo e nos corpora degradados (abaixo):
nenhum documento limpo é barrado, e o pior caso é barrado por inteiro. **O portão
pega o pior caso, não todos.** Não achei um indicador sem gabarito que separe com
segurança "leu bem" de "leu mal": a confiança do Tesseract sozinha não basta (ele
é confiante no que acha e cego ao que perde), e a proporção de "tinta fora das
caixas lidas" não separa, porque cabeçalhos coloridos e linhas contam como tinta.
**A conferência da pessoa na imagem devolvida continua sendo o controle
principal.**

## Privacidade e retenção

O que o modo servidor faz, e o que ele deixa a cargo de quem o integra:

- **Entrada:** `--apagar-entrada` apaga o arquivo recebido ao terminar, em
  qualquer resultado. Sem a opção, o comando não mexe na entrada.
- **Saída:** o arquivo tarjado fica na pasta de `--saida` até **você** apagá-lo.
  Quem integra deve apagá-lo depois de entregar (veja o exemplo, que o faz na
  próxima execução).
- **Nada do documento vai para log.** Erros e avisos não carregam trecho do
  texto; o aviso de "trecho não localizado" é só uma contagem.
- **Camada de IA:** o texto vai pela **entrada padrão** do processo, nunca na
  linha de comando (que outros usuários da máquina enxergam em `ps`). Cada
  chamada usa uma pasta de configuração temporária, apagada ao fim, e
  `--no-session-persistence`, então o Claude Code não grava transcrição em disco.
  O Claude Code é chamado com `--tools ""` (sem ferramentas) e `--safe-mode`
  (sem `CLAUDE.md`, plugins, hooks nem memória).
- **Do lado do serviço externo:** por quanto tempo a Anthropic guarda as
  requisições feitas por assinatura depende da configuração de privacidade da
  conta. Confira na sua antes de usar com documento real.
- **Credencial:** passe-a por variável de ambiente do processo, não por
  argumento. Não rode como `root`.
- **Quem integra tem um papel:** se a ferramenta é chamada por um agente de IA,
  o agente em si vê o arquivo recebido. Documente isso para quem usa.

## A camada de IA em detalhe

`backend/app/pii_llm.py`. As regras brasileiras pegam o que tem formato fixo
(CPF, CNPJ, telefone, CEP, datas). O Claude marca o resto: **nome de pessoa,
endereço e identificadores sem formato fixo** (prontuário, carteirinha, guia,
atendimento). As entidades entram no mesmo `_pipeline` do modelo local, que
valida, une e arredonda, como se fossem dele.

- O prompt trata o texto do documento como **dado, nunca como instrução**, e
  manda copiar cada trecho exatamente, sem corrigir o erro do OCR. O código
  localiza cada trecho no texto, tolerando espaço e quebra de linha diferentes.
- **Falha fechada:** se a chamada falha, ou devolve algo ilegível, o comando
  sai com erro e **não entrega nada**, em vez de seguir só com as regras em
  silêncio.
- Desligada por padrão: só liga com `XDIAG_PII_LLM=claude`.

## Qualidade medida

Avaliador do projeto (`scripts/evaluate.py --level full`), 17 a 18 documentos
**sintéticos**, em um servidor Linux de 8 vCPUs, sem GPU. "Cobertos" são os
campos do gabarito apagados na imagem, com cobertura de pixel exigida.

| Perfil | Cobertos | Recall |
|---|---|---|
| Só regras (Tesseract) | 73 de 132 | 0,55 |
| Regras + Claude (**corpus limpo**) | 122 e 123 de 132 | 0,92 e 0,93 |
| Regras + Claude, foto comprimida (WhatsApp, 900 px, JPEG 45) | 118 de 122 | 0,97 |
| Regras + Claude, sombra e ruído | 116 de 122 | 0,95 |
| Regras + Claude, inclinada 3° e desfocada | 106 a 108 de 122 | 0,87 a 0,89 |
| Regras + Claude, pior caso (744 px, inclinada, desfocada, ruído) | 52 a 60 de 122 | 0,43 a 0,49 |

Como comparação, o perfil completo (PaddleOCR + modelo local) tem 75 de 132
(0,57) no `tests/baselines/baseline-full.json`. **A camada de IA não é
determinística**: duas execuções diferem em um campo, então trate cada número
como "aproximadamente".

**O que não aparece nesses números:** o corpus é sintético e de imagem limpa, e
os corpora degradados são simulações. Nada substitui medir com os seus próprios
documentos. Nos testes, só documento sintético passou pela camada de IA.

### Corpus degradado (foto de celular)

`scripts/degrade_corpus.py` copia o corpus aplicando degradações
**determinísticas** (semente fixa) e ajusta o gabarito: gira as caixas junto com
a imagem (cada caixa vira o menor retângulo que contém os quatro cantos girados,
o que deixa a medida um pouco mais dura) e usa a escala do avaliador para a
redução de resolução.

```bash
.venv/bin/python scripts/degrade_corpus.py --out ../xdiag-privacy-degradado
XDIAG_OCR_ENGINE=tesseract XDIAG_PII_ENGINE=rules \
  .venv/bin/python scripts/evaluate.py --level full --corpus ../xdiag-privacy-degradado/inclinado
```

Perfis: `whatsapp`, `sombra`, `inclinado`, `pior`. O PDF do corpus fica de fora.

## O que este modo ainda não faz

- **Correção manual:** se a detecção deixou algo de fora, não há como
  desenhar uma tarja pelo comando. Está no roadmap
  (`anonimizar.py --tarjar x0,y0,x1,y1`). Enquanto isso, use o aplicativo
  desktop, onde a tarja se desenha à mão.
- **PDF com mais de 10 páginas:** recusado. Mande em partes. (O aplicativo desktop
  ainda exporta só o texto de documento de várias páginas; o modo servidor exporta
  um PDF de imagens.)
- **Código de barras, QR, assinatura e cabeçalho de ultrassom:** nenhum OCR de
  texto os detecta, nem no perfil completo.
- **Foto torta ou pequena demais:** o OCR perde o texto (veja o portão de
  qualidade). Pré-processamento (ampliar, contraste, corrigir inclinação) não
  foi feito.
- **Manuscrito:** o OCR não lê letra à mão.
- **Conteúdo clínico:** uma combinação rara de diagnóstico, data e cidade pode
  identificar alguém mesmo sem nome nem CPF. Isso é julgamento humano.

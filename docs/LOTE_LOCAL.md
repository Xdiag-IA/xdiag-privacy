# Documentos longos em uma pasta local

Este modo processa uma pasta e suas subpastas no computador do usuário. Aceita
TXT em UTF-8, DOCX, PDF com texto, PDF digitalizado, PNG, JPG, WEBP e TIFF.
Entrega **texto desidentificado em arquivos TXT**, dividido em partes de até
100 mil caracteres por padrão. Não preserva a diagramação, não altera os
originais e não produz uma cópia do PDF ou Word com tarjas.

É útil para preparar textos para leitura e análise. Foi construído sobre o
detector médico brasileiro do Xdiag Privacy: a adequação a auditoria e
processos jurídicos precisa ser conferida. Nomes, números de processos,
segredos comerciais e outros identificadores podem permanecer. Uma execução
concluída significa processamento concluído, não anonimização garantida.

## Uso pelo aluno com um agente

Instale o aplicativo desktop com acesso a projetos locais e terminal. Abra
uma pasta de projeto, por exemplo `C:\dev\privacy`. Guarde os documentos em
outra pasta, por exemplo `C:\Documentos\Auditoria`. Não anexe os originais à
conversa. Cole o prompt abaixo, trocando o caminho:

> Use o modo de lote local de https://github.com/Xdiag-IA/xdiag-privacy.
> Leia docs/LOTE_LOCAL.md, prepare a instalação neste projeto e processe todos
> os documentos de C:\Documentos\Auditoria, incluindo subpastas. Salve os
> resultados em C:\Documentos\Auditoria-anonimizada. Execute somente o
> programa local: não leia, anexe ou mostre o conteúdo dos documentos nesta
> conversa. Preserve os originais, divida saídas grandes em partes e acompanhe
> até terminar. Se houver interrupção, retome o lote. Informe apenas contagens,
> pendências e onde estão os resultados. Use o modelo local completo.

O prompt depende de esta feature estar presente na versão clonada. Em uma
videoaula, mostre documentos fictícios. A primeira instalação baixa
dependências e cerca de 2,3 GB de pesos; não cabe prometer uma instalação
instantânea nem um tempo fixo por lote.

## Instalação no Windows

Pré-requisitos: Git e Python 3.10, 3.11 ou 3.12 disponíveis no terminal.

```powershell
git clone https://github.com/Xdiag-IA/xdiag-privacy.git
cd xdiag-privacy
.\instalar-lote.cmd
```

O instalador cria `.venv-lote`, instala PyTorch para CPU e baixa uma revisão
fixa do modelo OpenMed para `modelos-lote`. O OCR deste perfil usa RapidOCR
com ONNX e um reconhecedor latino baixado com verificação de hash; não é o
PaddleOCR do desktop.
Instalação requer internet. Processamento carrega os pesos locais e desliga
integrações externas. O bloqueio adicional de sockets Python é uma defesa
no processo, não um firewall do sistema operacional.

```powershell
.\anonimizar-lote.cmd --entrada "C:\Documentos\Auditoria" --saida "C:\Documentos\Auditoria-anonimizada"
```

Para partes menores:

```powershell
.\anonimizar-lote.cmd --entrada "C:\Documentos\Auditoria" --saida "C:\Documentos\Auditoria-anonimizada" --max-caracteres 50000
```

As pastas de entrada e saída precisam ser separadas. Use uma saída vazia na
primeira execução. Não mude entrada, conteúdo, modo ou tamanho das partes
durante um lote. Para outro conjunto de arquivos ou configuração, use outra
pasta de saída.

## Lotes demorados e retomada

O programa informa o número do arquivo e a unidade concluída, sem imprimir
conteúdo ou nomes originais. Repita o mesmo comando para retomar. Arquivos
concluídos são verificados e pulados; unidades já detectadas são reaproveitadas.
A extração, inclusive OCR, pode precisar ser repetida para chegar ao checkpoint.
Uma unidade interrompida é refeita. Em TXT, o arquivo é uma unidade; o detector
usa janelas sobrepostas e não envia o texto inteiro a um modelo remoto.

Mantenha o computador ligado e sem suspensão. Fechar o aplicativo pode
interromper seu terminal; a retomada não é um serviço agendado. O agente deve
acompanhar o processo enquanto a sessão estiver ativa e consultar apenas o
relatório de status, sem abrir documentos ou partes da saída na conversa.

## Entrega e revisão

Cada documento concluído ganha uma pasta `documento-<id>` com `parte-0001.txt`,
`parte-0002.txt` e assim por diante. O identificador não contém o nome original.
`relatorio.json` registra contagens, hashes, arquivos gerados e pendências, sem
textos detectados. A pasta `_em_processamento` contém checkpoints locais e
não faz parte da entrega; conserve-a para retomada. Trate toda a saída como
sensível até revisão, inclusive checkpoints.

Os nomes dos arquivos no relatório são neutros. O número de item segue a
ordem dos caminhos da entrada. O agente não precisa mostrar essa relação na
conversa. Não envie a pasta inteira para publicação automática.

Código de saída 0: lote processado, revisão humana pendente. Código 1: um ou
mais documentos não puderam ser concluídos. Código 2: lote não iniciado ou
retomada recusada. Código 130: interrupção pelo usuário.

## Limites desta primeira versão

- DOC antigo, arquivos protegidos por senha, anexos incorporados ao Word e
  formatos não listados não são convertidos silenciosamente.
- Alterações controladas no Word precisam ser resolvidas antes da execução.
- Word: lê parágrafos, tabelas, cabeçalhos, rodapés, notas, comentários e
  imagens compatíveis. Objetos complexos e elementos não textuais não têm
  promessa de reprodução. Metadados do original não são copiados para o TXT.
- PDF: lê todas as páginas. Páginas com imagens também passam pelo OCR; isso
  pode duplicar texto em PDFs mistos. Formulários, anexos e anotações fora do
  conteúdo das páginas não compõem uma reprodução integral do documento.
- OCR vazio ou de baixa confiança bloqueia aquele documento. Mesmo quando
  aceito, OCR pode errar; manuscritos e imagens ruins exigem revisão.
- `--regras` serve para demonstração leve e testes de funcionamento. Não é
  substituto silencioso do modelo; deixa passar nomes em narrativa.
- A divisão em TXT não preserva paginação nem relações de tabela, e não
  garante identidade consistente entre marcadores como `[NOME]`.

## Orientações para o agente

1. Prepare o código e os modelos antes de processar documentos reais.
2. Não use ferramentas de leitura de arquivos, OCR remoto, APIs de LLM nem
   anexos da conversa para inspecionar o conteúdo da pasta indicada.
3. Execute o programa no terminal local, apontando entrada e saída absolutas.
4. Acompanhe o terminal e consulte apenas `relatorio.json`. Não imprima
   exceções com trechos de documentos nem valores detectados.
5. Se o processo demorar, mantenha-o em execução e acompanhe. Não declare
   conclusão enquanto ele estiver ativo. Não rebaixe para `--regras` para
   contornar erro ou acelerar a execução.
6. Entregue caminhos, totais e pendências. Diga que a revisão continua pendente.

## Testes de desenvolvimento

```powershell
.venv-lote\Scripts\python.exe -m pip install -r requirements-lote-test.txt
.venv-lote\Scripts\python.exe scripts/test_lote_local.py
.venv-lote\Scripts\python.exe scripts/test_lote_modelo.py
```

O teste de integração exige os pesos baixados. Os testes usam somente dados
fictícios. O teste de formatos usa PyMuPDF apenas para fabricar PDFs de teste;
essa dependência não entra no processamento do usuário.

Validação local desta implementação (Windows, Python 3.10): sete testes de
formatos/retomada e integração real com 11.335 caracteres. No corpus textual
de 18 documentos, o motor original e o adaptador acertaram 120 de 132
marcações, sem regressões entre ambos. Isso não mede a qualidade em processos
de auditoria reais. A avaliação completa de OCR/mapeamento do desktop via
Docker não foi executada neste ambiente (serviço Docker indisponível).

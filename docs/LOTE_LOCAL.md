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

O fluxo é: **pasta de documentos → processamento local → outra pasta com
textos para revisão**. Os documentos não precisam ficar dentro do repositório.
O agente instala e executa o programa; o modelo de detecção roda no computador.
Não é necessário colar o conteúdo dos documentos na conversa.

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

Em uma videoaula, mostre documentos fictícios. A primeira instalação baixa
dependências e cerca de 2,3 GB de pesos; não cabe prometer uma instalação
instantânea nem um tempo fixo por lote.

## Instalação no Windows

Pré-requisitos: Git e Python 3.10, 3.11 ou 3.12 disponíveis no terminal.

Crie ou abra `C:\dev\privacy` como projeto local. A estrutura pode ser:

```text
C:\dev\privacy\xdiag-privacy\            programa e modelos
C:\Documentos\Auditoria\                documentos originais e subpastas
C:\Documentos\Auditoria-anonimizada\    resultados e checkpoints
```

Execute os comandos abaixo a partir da pasta do projeto. Nas próximas
utilizações, a instalação pode ser reutilizada; basta executar o lote.

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

Para partes menores, como no teste de 40 páginas descrito abaixo:

```powershell
.\anonimizar-lote.cmd --entrada "C:\Documentos\Auditoria" --saida "C:\Documentos\Auditoria-anonimizada" --max-caracteres 20000
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

### Formatos de entrada e resultado

| Entrada | Tratamento | Saída |
| --- | --- | --- |
| TXT UTF-8 | Detecção sobre o texto | Uma ou mais partes TXT |
| DOCX | Extração de texto e OCR nas imagens compatíveis | Uma ou mais partes TXT |
| PDF com texto | Extração página a página | Uma ou mais partes TXT |
| PDF digitalizado | OCR local página a página | Uma ou mais partes TXT |
| PNG, JPG, WEBP e TIFF | OCR local | Uma ou mais partes TXT |
| DOC antigo | Não suportado; converter antes para DOCX | Pendência no relatório |

### Restrições conhecidas

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

Se o programa não iniciar, confira Python, instalação dos modelos, permissões
das pastas e se outro processo já está usando a mesma saída. Se a retomada
for recusada após mudanças na entrada ou na configuração, use uma nova pasta
de saída; não apague o relatório para forçar a continuação. Erros em documentos
individuais ficam registrados como pendências, enquanto os demais podem ser
concluídos. Não trate um lote com pendências como entrega integral.

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

### Teste demonstrativo em 8 de outubro de 2026

Um caso fictício de auditoria foi processado com o modelo completo em CPU,
entrada externa ao repositório e limite de 20.000 caracteres por parte:

| Documento | Unidades processadas | Partes TXT | Substituições |
| --- | ---: | ---: | ---: |
| Relatório PDF de 40 páginas | 40 páginas | 5 | 1.169 |
| Ficha de pagamento PNG | 1 imagem | 1 | 21 |
| Ata DOCX de 3 páginas | 1 unidade de texto | 1 | 51 |

O lote terminou sem erros de processamento, em aproximadamente dois minutos
na máquina utilizada. Esse tempo é uma observação, não uma previsão para
outros computadores. Os originais permaneceram intactos e todas as partes
respeitaram o limite configurado.

A busca pelos valores fictícios conhecidos não encontrou nomes completos ou
fragmentos dos nomes, CPFs, CNPJ, e-mails, telefones, logradouro, CEP ou conta
bancária remanescentes. Os três valores monetários conferidos no PDF e no Word
foram preservados. **Uma ocorrência do protocolo do caso permaneceu no PDF.**
A conferência manual considerou o resultado adequado para o exemplo.

Esse resultado não certifica anonimização completa: a busca por valores
conhecidos não cobre variações desconhecidas nem todos os erros de OCR.
Documentos reais exigem revisão. Os arquivos de entrada, resultados, modelos
e dados locais dessa demonstração não são publicados no repositório.

### Execução dos testes automatizados

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

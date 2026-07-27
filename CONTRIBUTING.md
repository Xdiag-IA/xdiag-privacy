# Contribuindo com o Xdiag Privacy

Obrigado pelo interesse. Este é um projeto de anonimização de documentos de
saúde, então antes de qualquer coisa técnica vem uma regra que não tem exceção.

---

## A regra que não tem exceção

**Nunca envie dado de paciente real. Em lugar nenhum.**

Não em issue, não em pull request, não em anexo, não em print, não em log
colado, não em nome de arquivo, não em mensagem de commit.

Isso vale mesmo que você ache que tarjou tudo. Se o problema que você quer
reportar é justamente que a ferramenta **não** tarjou alguma coisa, então por
definição o arquivo ainda tem dado exposto.

Um documento de paciente publicado numa issue é público para sempre: fica em
cache de busca, em espelhos do repositório, no histórico do git e nos e-mails
de notificação de todo mundo que acompanha o projeto. Apagar depois não
resolve.

### O que fazer no lugar

Gere um documento sintético equivalente. O projeto tem gerador pronto:

```bash
python scripts/generate_samples.py
```

Se o caso que você quer mostrar não existe no gerador, escreva um documento
novo com dados fictícios que tenha **a mesma forma** do original: mesmo
layout, mesmo tipo de campo, mesma fonte, mesma qualidade de digitalização.
O que importa para reproduzir o problema é a estrutura, não o conteúdo.

Precisa de CPF fictício que passe no dígito verificador? Use `529.982.247-25`,
que é o número de teste já usado no corpus do projeto.

---

## Encontrou uma falha de segurança?

Se você achou um jeito de recuperar dado de um arquivo que a ferramenta disse
ter anonimizado, **não abra issue pública**. Leia o [SECURITY.md](SECURITY.md)
e reporte em canal privado.

---

## Tipos de contribuição mais úteis

Em ordem de impacto:

1. **Documento brasileiro que a ferramenta erra.** Falso negativo é o bug mais
   valioso que existe neste projeto. Se um tipo de laudo, guia ou etiqueta
   passa dado batido, queremos saber.
2. **Identificador que falta.** Padrão e validador de algum documento ou
   registro do sistema de saúde brasileiro que ainda não é reconhecido.
3. **Melhoria de recall no corpus existente.**
4. Correção de bug, melhoria de interface, documentação.

---

## A política de recall

**Falso negativo é falha crítica. Falso positivo é ruído aceitável.**

Deixar de tarjar um CPF expõe um paciente. Tarjar um número de exame que não
era dado pessoal atrapalha um pouco a leitura do documento. Os dois erros não
têm o mesmo peso, e o projeto inteiro é calibrado nessa assimetria: na dúvida,
cobre.

Isso aparece em vários lugares do código, e é intencional:

- número suspeito não classificado é tarjado mesmo assim;
- a folga da tarja (`bbox_pad_chars`, `bbox_pad_lines`) sobra para fora;
- as coordenadas do export são arredondadas para fora;
- entidade encontrada no texto mas não localizada na imagem **bloqueia o
  export** em vez de ser ignorada;
- PDF acima do limite de páginas responde erro em vez de processar só uma
  parte.

Se sua mudança inverte alguma dessas escolhas, explique bem o porquê no PR.

### Rode o avaliador antes e depois

Toda mudança que toque detecção, OCR ou mapeamento precisa passar pelo
avaliador de recall:

```bash
docker compose run --rm eval --level text
```

```bash
docker compose run --rm eval --level full
```

`--level text` isola a detecção de PII, injetando o texto do gabarito direto
no modelo. `--level full` roda o caminho inteiro, de imagem a tarja, e compara
por cobertura de pixels.

Os baselines ficam em `tests/baselines/`. Uma execução que piore o recall de
qualquer rótulo retorna código de saída 1.

**PR que piora recall não entra, mesmo que melhore outra coisa.** Se a troca
for realmente vantajosa, discuta numa issue antes de escrever código.

---

## Ambiente de desenvolvimento

```bash
docker compose up --build
```

Interface em `http://localhost:5173`, API em `http://localhost:8800`, com
documentação OpenAPI em `/docs`.

Para iterar rápido, sem esperar o modelo carregar:

```bash
XDIAG_MOCK=1 docker compose up --build
```

Teste do pipeline sem modelo nenhum:

```bash
XDIAG_MOCK=1 python scripts/smoke_test.py
```

---

## Convenções do código

**Rótulos vivem em dois lugares e precisam continuar iguais.** Ao acrescentar
um rótulo, mexa em `LABEL_PLACEHOLDER` e `LABEL_COLOR` em
`backend/app/pii.py`, e espelhe em `frontend/src/labels.ts`
(`LABEL_COLORS` e `FRIENDLY`). Os dois arquivos têm comentário avisando disso.

**Cores têm significado.** Ciano é a cor da marca e da ação. Vermelho é risco,
âmbar é atenção, verde é sucesso. Nenhuma dessas três pode ser usada como
decoração, senão o alerta perde força justamente na tela onde ele importa. As
cores das entidades são organizadas por família de dado, uma cor por família.

**Texto de interface em português acentuado.** Comentário de código pode ficar
sem acento, seguindo o que já está no repositório.

**Explique o porquê, não o quê.** Boa parte das decisões deste projeto parece
errada até você saber o motivo, e alguém vai "consertar" de volta daqui a seis
meses. Se você escrever algo não óbvio, deixe o motivo escrito junto.

---

## Abrindo um pull request

1. Descreva o problema antes da solução.
2. Anexe a saída do avaliador de recall, antes e depois, se tocou em detecção.
3. Documento de teste sintético, sempre.
4. Um assunto por PR.

Se a mudança for grande ou mexer na arquitetura, abra uma issue antes para
combinar a direção. É chato escrever muito código e descobrir depois que o
caminho era outro.

---

## Licença

Ao contribuir, você concorda que sua contribuição será licenciada sob a
Apache 2.0, a mesma do projeto.

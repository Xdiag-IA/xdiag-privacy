# Política de segurança

## Antes de tudo

Se você encontrou um jeito de recuperar dado de um arquivo que o Xdiag Privacy
declarou anonimizado, **não abra issue pública**.

Numa ferramenta de anonimização, o relato da falha normalmente vem acompanhado
do exemplo que a demonstra, e esse exemplo é justamente um documento com dado
exposto. Publicar isso transforma o relato no próprio vazamento.

## Como reportar

Use o canal privado do GitHub:

**[Abrir aviso de segurança privado](https://github.com/Xdiag-IA/xdiag-privacy/security/advisories/new)**

Só você e os mantenedores enxergam. Se preferir e-mail, escreva para o contato
em [xdiag.com.br](https://www.xdiag.com.br) informando que é sobre segurança do
Xdiag Privacy.

## O que nos ajuda a agir rápido

- O que você conseguiu recuperar, e como.
- Um documento **sintético** que reproduza o caso. Se o problema só acontece
  com um documento real, descreva a estrutura dele (layout, tipo de campo,
  fonte, qualidade da digitalização) sem anexar o arquivo.
- Versão usada, ou o commit.
- Se rodou com Docker, com o instalador, ou a partir do código.

## O que consideramos falha de segurança

- Dado pessoal recuperável de um arquivo exportado, por qualquer meio: pixel
  residual, metadado, camada, texto remanescente, nome de arquivo.
- Qualquer saída de rede não intencional. O produto promete rodar offline
  depois da primeira execução, e tráfego externo em runtime quebra a premissa
  inteira.
- Exposição da API ou de dado em processamento para fora da máquina.
- Falha no bloqueio de export, que existe para impedir a saída de arquivo com
  entidade não mapeada.

## O que não é falha de segurança

- **O modelo não detectou um dado.** Isso é falso negativo, é esperado, e é
  exatamente por isso que a tela de revisão existe e o aviso no README diz para
  conferir antes de compartilhar. Reporte como issue normal, com documento
  sintético: é a contribuição mais útil que existe para este projeto, mas não
  entra por este canal.
- Alguém exportar o arquivo sem revisar.
- Alguém configurar `{base}` no nome do arquivo e vazar o nome do paciente pelo
  nome do arquivo. A interface avisa em vermelho quando isso é feito.

## Prazo

Confirmamos o recebimento em até 5 dias úteis e mantemos você informado do
andamento. Não há programa de recompensa: este é um projeto gratuito e de
código aberto.

## Divulgação

Preferimos divulgação coordenada. Corrigimos, publicamos a versão, damos o
crédito a você (se quiser) e só então abrimos o detalhe. Se a falha estiver
sendo explorada ativamente, avisamos os usuários antes da correção ficar
pronta, porque saber do risco vale mais que esperar a solução.

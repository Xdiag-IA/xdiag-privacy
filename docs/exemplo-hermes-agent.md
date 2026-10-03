# Exemplo: o modo servidor chamado por um agente de IA (Hermes Agent)

Este é **um exemplo** de como ligar o [modo servidor](servidor.md) a um fluxo
real: um agente de IA numa VPS que recebe um documento por WhatsApp, chama a
ferramenta e devolve a imagem anonimizada. O agente usado é o
[Hermes Agent](https://github.com/NousResearch/hermes-agent), da Nous Research
([documentação](https://hermes-agent.nousresearch.com/docs/)), que tem um
*gateway* de WhatsApp, executa comandos no servidor e aprende "skills" (receitas
em arquivo). O padrão serve para qualquer agente ou robô: o que importa é o
contrato do comando (`anonimizar.py`), que é o mesmo.

> ⚠️ **Leia antes:** num fluxo assim, o documento passa pelo WhatsApp, pelo
> servidor, **pelo próprio agente de IA** (que enxerga a imagem recebida) e,
> com a camada de IA ligada, pelo modelo que marca os dados pessoais. O sigilo
> absoluto da anonimização local **não se aplica**. Veja o aviso em
> [servidor.md](servidor.md). Quem envia decide se o caminho serve e responde
> por isso.

Conferido na versão `0.21.5` do Hermes Agent. O projeto muda rápido: confira a
documentação dele antes de copiar.

## Como o Hermes trata o arquivo recebido

| Etapa | O que acontece |
|---|---|
| Chega um documento | O gateway grava o arquivo no cache do agente e avisa o agente com uma nota: *"The user sent a document: '…'. It is saved at: `<caminho>`"*. Para foto, a nota traz o endereço da imagem. |
| O agente devolve um arquivo | Ele escreve uma linha `MEDIA:<caminho>` na resposta, e o gateway envia o arquivo. |
| De onde o gateway aceita enviar | Só de pastas de cache do próprio Hermes (por exemplo `~/.hermes/cache/documents/`) ou das listadas em `HERMES_MEDIA_ALLOW_DIRS`. |
| Quando o envio acontece | **Depois** que a resposta termina. O agente **não** consegue apagar o arquivo de saída antes de a pessoa recebê-lo. |
| Limpeza | De hora em hora, o gateway apaga dos caches o que tem mais de 24 horas. |
| Conversa | O histórico fica num banco SQLite do agente (`state.db`), com o texto de tudo o que o agente lê e escreve. |

Daí saem as decisões do exemplo:

1. **A saída vai para `~/.hermes/cache/documents/`**, uma pasta de onde o
   gateway aceita enviar. O script apaga as saídas com mais de 1 hora a cada
   uso, e o gateway apaga as de mais de 24 horas.
2. **Quem chama o modelo é a ferramenta, não o agente.** O texto do OCR vai de
   `anonimizar.py` para o Claude Code por uma requisição própria e sem
   histórico, e o agente só recebe o resumo (o JSON, sem os valores). Assim o
   texto do documento **não entra na conversa do agente nem no `state.db`**.
3. **O agente é instruído a nunca descrever, citar nem guardar** dado do
   documento, e a nunca reenviar o original. Isso é uma regra de comportamento
   (a skill), não uma barreira técnica: o agente enxerga a imagem recebida.

## Os dois arquivos do exemplo

| Arquivo | Para quê |
|---|---|
| [`exemplos/hermes-agent/anonimizar-vps.sh`](exemplos/hermes-agent/anonimizar-vps.sh) | O script que o agente chama: passa a credencial ao processo, apaga a entrada e varre saídas antigas |
| [`exemplos/hermes-agent/SKILL.md`](exemplos/hermes-agent/SKILL.md) | A skill: quando usar, como chamar, o que responder e as regras de privacidade |

Instalação, como o usuário que roda o agente (ajuste os caminhos):

```bash
# 1. a ferramenta (veja servidor.md): clone, venv e dependências em ~/xdiag-privacy
# 2. o script
install -m 750 docs/exemplos/hermes-agent/anonimizar-vps.sh ~/xdiag-privacy/anonimizar-vps.sh
# 3. a skill
mkdir -p ~/.hermes/skills/productivity/xdiag-privacy-vps
cp docs/exemplos/hermes-agent/SKILL.md ~/.hermes/skills/productivity/xdiag-privacy-vps/SKILL.md
```

O Hermes lê as skills a cada conversa nova: não precisa reiniciar o gateway.

## A credencial

O script lê a credencial de um arquivo de ambiente (por padrão
`~/.hermes/.env`, variável `ANTHROPIC_TOKEN`, que é um token de assinatura do
tipo `sk-ant-oat…` gerado com `claude setup-token`) e a entrega ao processo em
`CLAUDE_CODE_OAUTH_TOKEN`. Ela nunca aparece em argumento, em log nem na
conversa. Adapte `ENV_FILE` e `TOKEN_VAR` ao seu agente. Sem a camada de IA
(só regras), nada disso é necessário.

## Retenção

Por padrão o script **não guarda nada**: apaga a entrada ao terminar e varre as
saídas antigas. Para guardar, crie o arquivo `MANTER` ao lado do script
(`touch ~/xdiag-privacy/MANTER`): a entrada deixa de ser apagada e as saídas
antigas também ficam. É uma escolha de instalação, de propósito difícil de ligar
sem querer.

## Armadilhas que o exemplo evita

- **O `claude -p` lê a entrada padrão** e a junta ao pedido. Numa chamada em que
  a entrada não seja o texto do OCR, ela precisa ser fechada com `</dev/null`
  (o script faz isso). Sem isso, o Claude Code pode consumir o resto de um script
  como se fosse o pedido.
- **Não rode o Hermes com `HERMES_HOME` em outra pasta para "isolar" a chamada.**
  O bootstrap grava na instalação real, e o comando `hermes` pode ficar
  quebrado. A chamada isolada ao modelo é feita pelo `anonimizar.py`, não pelo
  agente.
- **O arquivo `.sh` precisa chegar ao servidor com fim de linha LF.** Um
  checkout no Windows pode trocá-lo por CRLF e o script quebra.

## Quem pode usar

A skill do exemplo não classifica documento nem recusa por conteúdo. Se o seu
agente atende várias pessoas, decida (e registre no arquivo de contexto do
agente) quem pode pedir a anonimização e quem pode mudar o código da ferramenta.

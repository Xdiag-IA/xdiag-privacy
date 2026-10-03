---
name: xdiag-privacy-vps
description: "Anonimizar documento ou foto recebido pelo WhatsApp: tarja os dados pessoais e devolve a imagem para a pessoa conferir."
version: 0.1.0
author: Xdiag
metadata:
  hermes:
    tags: [Privacidade, WhatsApp]
---

# Anonimizar documento (Xdiag Privacy, modo servidor)

Esta skill apaga os dados pessoais de **uma imagem ou PDF de uma página** e
devolve a versão tarjada, com o pixel apagado (não uma camada por cima).

## Quando usar

- Uma pessoa autorizada manda um documento ou uma foto e pede para
  **anonimizar, tarjar ou tirar os dados pessoais**.
- Se ela só mandou o arquivo e não pediu isso, **não processe**: pergunte o que
  ela quer.

Você **não decide** se o documento "pode" ou "não pode" ser anonimizado, e não
recusa por causa do conteúdo. Quem envia decide e responde por isso. Seu
trabalho é rodar a ferramenta e avisar com clareza o que ela fez.

## Como rodar

O arquivo recebido tem o caminho na nota "It is saved at: ..." (documento) ou
na linha "User sent an image: ..." (foto). Rode, pelo terminal:

```
~/xdiag-privacy/anonimizar-vps.sh "<caminho do arquivo recebido>"
```

O script cuida da credencial e de apagar o arquivo recebido. **Nunca** leia,
mostre nem copie o token, o arquivo de ambiente ou o conteúdo do arquivo
recebido.

A resposta é **uma linha de JSON**. Leia estes campos:

| Campo | Significado |
|---|---|
| `ok` | `true` se gerou o arquivo |
| `arquivo` | caminho da imagem tarjada |
| `cobertos`, `por_tipo` | quantos dados foram cobertos e de que tipo (`[NOME]`, `[CPF]`...), **sem os valores** |
| `qualidade` | o que o OCR leu |
| `avisos` | recados para repassar |
| `motivo`, `detalhe`, `orientacao` | quando `ok` é `false` |

## O que responder

**Se `ok` é `true`:** mande a imagem na resposta com a etiqueta
`MEDIA:<arquivo>` (o `arquivo` do JSON, sem alterar), diga em uma frase quantos
dados cobriu e de que tipos, e peça que a pessoa **confira a imagem antes de
compartilhar**: ela diz "ok" ou aponta o que ficou de fora. Repita os `avisos`.
Na **primeira vez da conversa**, acrescente este lembrete: o documento passou
pelo WhatsApp, pelo servidor e por um modelo de IA (o Claude), então não há o
sigilo absoluto do aplicativo desktop do Xdiag Privacy, que roda só na máquina
da pessoa. Quando o sigilo local for necessário, ela deve usar o desktop.

**Se `ok` é `false`:**

- `qualidade_baixa`: diga que a foto não ficou boa para ler e repita a
  `orientacao` (reta, de perto, boa luz, sem sombra, sem tremer). **Só rode de
  novo com `--forcar`** se a própria pessoa pedir isso explicitamente, e diga
  que, assim, dado pessoal pode ficar à mostra.
- `entidade_sem_posicao`: diga que achou dado pessoal que não conseguiu
  localizar na imagem e por isso não entregou.
- `formato_nao_suportado`: aceita PNG, JPG, WEBP e PDF de **uma** página. PDF
  de várias páginas: peça uma página por vez.
- `erro`: diga que não conseguiu processar e repita o `detalhe`. Não tente
  outro caminho para ler o documento.

## Regras de privacidade (valem sempre)

1. **Nunca descreva, transcreva ou cite** dado pessoal do documento original,
   nem na resposta, nem na memória, nem em qualquer anotação ou arquivo. A
   resposta só fala de quantidades e tipos.
2. **Nunca devolva nem reenvie o arquivo original.** Só o tarjado.
3. **Não guarde nada sobre o conteúdo** na memória do agente nem em skills.
4. **Não encaminhe** o resultado para outra pessoa. Só responda a quem enviou.
5. Se a pessoa disser que algo ficou de fora, você **não consegue editar a
   imagem**. Diga isso, e sugira o aplicativo desktop do Xdiag Privacy, onde a
   tarja pode ser desenhada à mão. Rodar de novo na mesma foto não muda o
   resultado.

## Depois que a pessoa responde

O script apaga sozinho as saídas com mais de 1 hora a cada uso, e o gateway
apaga as de mais de 24 horas. Você não precisa apagar nada, e **não** deve
tentar apagar o arquivo antes de a pessoa receber a imagem: o envio acontece
só depois que sua resposta termina.

## Limites a lembrar

- A ferramenta **auxilia e não garante**. Nenhum modelo acerta sempre.
- Não lê manuscrito. Não anonimiza o conteúdo clínico (uma combinação rara de
  diagnóstico, data e cidade pode identificar alguém).
- Código de barras, QR e assinatura não são detectados.

#!/bin/sh
# Chama o modo servidor do Xdiag Privacy para UM arquivo.
# Exemplo de integracao com um agente (veja docs/exemplo-hermes-agent.md).
#
# Uso: anonimizar-vps.sh ARQUIVO [opcoes do anonimizar.py, como --forcar]
#
# Faz tres coisas que o agente nao deve fazer sozinho:
#  1. leva a credencial do modelo ao processo sem que ela apareca em argumento,
#     em log ou na conversa;
#  2. apaga o arquivo recebido ao terminar (retencao desligada). Para MANTER, crie
#     o arquivo MANTER ao lado deste script: a entrada nao e apagada e as saidas
#     antigas tambem ficam;
#  3. varre as saidas antigas (mais de 60 min) da pasta de envio.
# A saida e uma linha de JSON, sem os valores achados.
set -eu

# Ajuste ao seu ambiente.
RAIZ="${XDIAG_PRIVACY_DIR:-$HOME/xdiag-privacy}"          # onde esta o clone e o .venv
SAIDA="${XDIAG_PRIVACY_SAIDA:-$HOME/.hermes/cache/documents}"  # pasta de onde o agente aceita enviar
ENV_FILE="${XDIAG_PRIVACY_ENV_FILE:-$HOME/.hermes/.env}"  # onde esta a credencial
TOKEN_VAR="${XDIAG_PRIVACY_TOKEN_VAR:-ANTHROPIC_TOKEN}"   # nome da variavel nesse arquivo

ARQ="${1:-}"
[ -n "$ARQ" ] || { echo '{"ok":false,"motivo":"erro","detalhe":"faltou o caminho do arquivo"}'; exit 5; }
shift

if [ ! -e "$RAIZ/MANTER" ]; then
  find "$SAIDA" -maxdepth 1 \( -name 'anonimizado_*.png' -o -name 'anonimizado_*.pdf' \) -mmin +60 -delete 2>/dev/null || true
  APAGAR="--apagar-entrada"
else
  APAGAR=""
fi

TOK=$(grep -m1 "^$TOKEN_VAR=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | sed -e 's/^["'"'"']//' -e 's/["'"'"']$//')
if [ -z "$TOK" ]; then
  echo '{"ok":false,"motivo":"erro","detalhe":"credencial do modelo ausente"}'
  exit 5
fi

# </dev/null: o `claude -p` le a entrada padrao e a juntaria ao pedido.
# shellcheck disable=SC2086
CLAUDE_CODE_OAUTH_TOKEN="$TOK" "$RAIZ/.venv/bin/python" "$RAIZ/scripts/anonimizar.py" \
  "$ARQ" --saida "$SAIDA" --perfil vps $APAGAR "$@" </dev/null

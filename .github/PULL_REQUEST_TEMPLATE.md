## Qual problema isso resolve

<!-- Descreva o problema antes da solução. -->

## Como você resolveu

<!-- E, se a escolha não for óbvia, por quê. -->

---

## Antes de marcar como pronto

- [ ] Nenhum dado de paciente real entrou no PR: nem em arquivo, nem em print, nem em log, nem em nome de arquivo, nem em mensagem de commit.
- [ ] Documento de teste, se houver, é sintético.

### Se mexeu em detecção, OCR ou mapeamento

- [ ] Rodei o avaliador de recall antes e depois, e colei o resultado abaixo.
- [ ] Nenhum rótulo teve o recall piorado.

```
<!-- saída de: docker compose run --rm eval --level full -->
```

### Se acrescentou ou mudou um rótulo

- [ ] `LABEL_PLACEHOLDER` e `LABEL_COLOR` em `backend/app/pii.py`
- [ ] `LABEL_COLORS` e `FRIENDLY` em `frontend/src/labels.ts`
- [ ] Os dois lados continuam em sincronia.

### Se mexeu na interface

- [ ] Texto novo em português acentuado.
- [ ] Vermelho, âmbar e verde continuam significando risco, atenção e sucesso, e não foram usados como decoração.

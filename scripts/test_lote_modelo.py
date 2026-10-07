"""Integracao opcional: modelo real offline e recall textual antes/depois."""
from pathlib import Path
import json
import socket
import sys
import time

sys.path.insert(0, str(Path(__file__).parent / 'lote_local'))
import anonimizar as batch
from motor_local import create_engine
import evaluate
import app.pii

socket.socket.connect = batch.block_network
socket.create_connection = batch.block_network
started = time.perf_counter()
engine = create_engine()
text = ('A reuniao foi conduzida por Beatriz Albuquerque e Gustavo Peixoto.\n'
        'CPF: 529.982.247-25. Email: pessoa@example.com\n'
        'A evidencia foi conferida.\n') * 80
text += '\nULTIMA PAGINA\nNome: Maria da Silva\nCPF: 529.982.247-25'
result, count = batch.redact(text, engine)
assert '529.982.247-25' not in result
assert 'pessoa@example.com' not in result
assert 'Beatriz Albuquerque' not in result
assert 'Gustavo Peixoto' not in result
assert result.count('A evidencia foi conferida.') == 80
assert 'ULTIMA PAGINA' in result
long_result = dict(caracteres=len(text), substituicoes=count,
                   segundos=round(time.perf_counter()-started, 2))

# Reutiliza os mesmos pesos para isolar o efeito da adaptacao de janelas.
original = batch.PIIEngine(batch.Settings())
original._pipe = engine._pipe
original._loaded = True
docs = evaluate.load_corpus(evaluate.DEFAULT_CORPUS, None)
app.pii.get_engine = lambda: original
before = evaluate.eval_text(docs, 0.5)
app.pii.get_engine = lambda: engine
after = evaluate.eval_text(docs, 0.5)
before_by_key = {s.key: s for s in before.span_results}
regressions = [s.key for s in after.span_results if s.outcome == 'miss'
               and before_by_key[s.key].outcome != 'miss']
report = {'texto_longo': long_result, 'documentos_corpus': len(docs),
          'antes_acertos': sum(s.outcome != 'miss' for s in before.span_results),
          'depois_acertos': sum(s.outcome != 'miss' for s in after.span_results),
          'total_entidades': len(after.span_results), 'regressoes': regressions,
          'rede': 'socket.connect bloqueado no processo; pesos carregados localmente'}
print(json.dumps(report, ensure_ascii=False, indent=2))
assert not regressions, 'Regressao de recall textual'

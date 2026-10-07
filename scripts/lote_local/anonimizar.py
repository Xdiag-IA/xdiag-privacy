"""Processa uma pasta local e entrega TXT em partes, com retomada e revisao pendente."""
from pathlib import Path
from contextlib import contextmanager
from dataclasses import replace
import argparse
import hashlib
import json
import logging
import os
import socket
import sys

from extrair import extract, SUPPORTED

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from app.config import Settings
from app.pii import PIIEngine, label_placeholder


def block_network(*args, **kwargs):
    raise RuntimeError('Rede bloqueada durante o processamento')


def atomic_json(path, value):
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


@contextmanager
def exclusive_lock(folder):
    """Trava liberada pelo SO mesmo se o processo for interrompido."""
    with (folder / '.lote.lock').open('a+b') as handle:
        handle.seek(0, 2)
        if not handle.tell():
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def redact(text, engine, progress=None):
    # Janelas externas limitam custo das regras e mantem contexto nas fronteiras.
    entities = []
    for offset in range(0, len(text), 12000):
        start, end = max(0, offset - 1000), min(len(text), offset + 13000)
        for ent in engine.detect(text[start:end]):
            if not 0 <= ent.start < ent.end <= end - start:
                raise ValueError('Intervalo invalido')
            entities.append(replace(ent, start=ent.start + start, end=ent.end + start))
        if progress is not None:
            progress(offset // 12000 + 1, (len(text) + 11999) // 12000)
    spans = []
    for ent in sorted(entities, key=lambda e: (e.start, e.end)):
        if spans and ent.start < spans[-1][1]:
            start, end, label = spans[-1]
            label = label if label == ent.label else 'REDACTED'
            spans[-1] = (start, max(end, ent.end), label)
        else:
            spans.append((ent.start, ent.end, ent.label))
    parts, cursor = [], 0
    for start, end, label in spans:
        parts.extend((text[cursor:start], label_placeholder(label)))
        cursor = end
    parts.append(text[cursor:])
    return ''.join(parts), len(spans)


def split_output(work, destination, units, limit):
    """Divide somente texto ja desidentificado; cada parte tem tamanho limitado."""
    destination.mkdir(exist_ok=True)
    buffer, index, outputs = '', 1, []

    def write_part(value):
        nonlocal index
        name = f'parte-{index:04d}.txt'
        path = destination / name
        path.write_text(value, encoding='utf-8')
        outputs.append({'arquivo': name, 'sha256': digest(path), 'caracteres': len(value)})
        index += 1

    for unit in range(1, units + 1):
        buffer += (work / f'unidade-{unit:06d}.txt').read_text(encoding='utf-8')
        while len(buffer) > limit:
            cut = buffer.rfind('\n', 0, limit)
            cut = limit if cut < limit // 2 else cut + 1
            write_part(buffer[:cut])
            buffer = buffer[cut:]
    if buffer:
        write_part(buffer)
    return outputs


def run_batch(incoming, outgoing, engine, limit):
    incoming, outgoing = incoming.resolve(), outgoing.resolve()
    print('Conferindo os arquivos do lote...', flush=True)
    files = []
    for directory, dirs, names in os.walk(incoming, followlinks=False):
        if any((Path(directory) / name).is_symlink() or
               (Path(directory) / name).resolve() != Path(directory) / name for name in dirs):
            raise ValueError('Links de diretorio nao suportados')
        for name in names:
            path = Path(directory) / name
            if path.is_symlink() or incoming not in path.resolve().parents:
                raise ValueError('Links de arquivo nao suportados')
            files.append(path)
    files.sort()
    inventory = [{'id': hashlib.sha256(str(p.relative_to(incoming)).encode()).hexdigest()[:24],
                  'sha256': digest(p)} for p in files]
    signature = {'versao': 1, 'origem': hashlib.sha256(str(incoming).encode()).hexdigest(),
                 'modo': engine.backend, 'limite_parte': limit, 'inventario': inventory}
    report_path = outgoing / 'relatorio.json'
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding='utf-8'))
        if report['configuracao'] != signature:
            raise ValueError('A pasta, os arquivos ou a configuracao mudaram. Escolha outra pasta de saida.')
    else:
        if any(p.name != '.lote.lock' for p in outgoing.iterdir()):
            raise ValueError('Use uma pasta de saida vazia ou um lote existente.')
        report = {'configuracao': signature, 'revisao_humana_obrigatoria': True,
                  'status': 'em_andamento', 'arquivos': {}}
        atomic_json(report_path, report)
    failures = 0
    for index, (path, entry) in enumerate(zip(files, inventory), 1):
        ident = entry['id']
        record = report['arquivos'].setdefault(ident, {'item': index, 'status': 'pendente'})
        target = outgoing / ('documento-' + ident)
        if record['status'] == 'processado_revisao_pendente':
            if all((target / p['arquivo']).is_file() and digest(target / p['arquivo']) == p['sha256']
                   for p in record['partes']):
                print(f'Item {index}/{len(files)}: já concluído.', flush=True)
                continue
            raise ValueError('Uma saida foi alterada ou removida. Use outra pasta de saida.')
        work = outgoing / '_em_processamento' / ident
        work.mkdir(parents=True, exist_ok=True)
        checkpoint = work / 'checkpoint.json'
        state = json.loads(checkpoint.read_text(encoding='utf-8')) if checkpoint.exists() else {
            'unidades': 0, 'caracteres': 0, 'substituicoes': 0, 'unidades_ocr': 0, 'hashes': []}
        try:
            if path.suffix.lower() not in SUPPORTED:
                record['status'] = 'formato_nao_suportado'
                failures += 1
                continue
            for unit, (text, kind) in enumerate(extract(path), 1):
                unit_path = work / f'unidade-{unit:06d}.txt'
                if unit <= state['unidades']:
                    if digest(unit_path) != state['hashes'][unit - 1]:
                        raise ValueError('Checkpoint alterado')
                    continue
                if not text.strip():
                    raise ValueError('Unidade sem texto')
                result, found = redact(text, engine, lambda current, total: print(
                    f'Item {index}/{len(files)}: unidade {unit}, bloco {current}/{total}.', flush=True))
                unit_path.write_text(result + '\n\n', encoding='utf-8')
                state['unidades'] = unit
                state['caracteres'] += len(text)
                state['substituicoes'] += found
                state['unidades_ocr'] += int('ocr' in kind)
                state['hashes'].append(digest(unit_path))
                atomic_json(checkpoint, state)
                record.update(status='em_andamento', unidades=unit)
                atomic_json(report_path, report)
                print(f'Item {index}/{len(files)}: unidade {unit} concluída.', flush=True)
            if not state['unidades'] or digest(path) != entry['sha256']:
                raise ValueError('Documento vazio ou alterado durante processamento')
            staging = work / 'partes'
            parts = split_output(work, staging, state['unidades'], limit)
            if target.exists():
                if not all((target / p['arquivo']).is_file() and digest(target / p['arquivo']) == p['sha256']
                           for p in parts):
                    raise ValueError('Saida divergente')
            else:
                staging.replace(target)
            record.update(status='processado_revisao_pendente', partes=parts,
                          **{k: v for k, v in state.items() if k != 'hashes'})
        except Exception as exc:
            record['status'] = 'erro_extracao_ou_processamento'
            record['erro_tipo'] = type(exc).__name__
            failures += 1
        finally:
            atomic_json(report_path, report)
            print(f"Item {index}/{len(files)}: {record['status']}", flush=True)
    report['status'] = 'concluido_com_pendencias' if failures else 'concluido_revisao_pendente'
    atomic_json(report_path, report)
    print(f'Lote encerrado: {len(files)} arquivo(s), {failures} pendência(s). Revise antes de compartilhar.')
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entrada', type=Path, required=True, help='Pasta local, incluindo subpastas')
    parser.add_argument('--saida', type=Path, required=True, help='Pasta separada; reutilize para retomar')
    parser.add_argument('--max-caracteres', type=int, default=100000)
    parser.add_argument('--regras', action='store_true', help='Demonstração limitada, sem modelo de IA')
    args = parser.parse_args()
    incoming, outgoing = args.entrada.resolve(), args.saida.resolve()
    if not incoming.is_dir():
        parser.error('A pasta de entrada não existe.')
    if incoming == outgoing or incoming in outgoing.parents or outgoing in incoming.parents:
        parser.error('Entrada e saída devem ser separadas, sem conter uma à outra.')
    if args.max_caracteres < 1000:
        parser.error('Use pelo menos 1000 caracteres por parte.')
    logging.disable(logging.CRITICAL)
    socket.socket.connect = block_network
    socket.socket.connect_ex = block_network
    socket.create_connection = block_network
    outgoing.mkdir(parents=True, exist_ok=True)
    try:
        with exclusive_lock(outgoing):
            if args.regras:
                engine = PIIEngine(Settings(pii_engine='rules', pii_llm='', mock_mode=False))
                engine.warmup()
            else:
                from motor_local import create_engine
                print('Carregando o modelo local...', flush=True)
                engine = create_engine()
            return run_batch(incoming, outgoing, engine, args.max_caracteres)
    except KeyboardInterrupt:
        print('Interrompido. Repita o mesmo comando para retomar.')
        return 130
    except Exception:
        print('Não foi possível iniciar ou retomar. Confira a instalação, as pastas e se há outro lote em execução. Não exponha documentos em logs de diagnóstico.')
        return 2


if __name__ == '__main__':
    sys.exit(main())

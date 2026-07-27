"""Cliente de smoke test do backend empacotado.

Usa apenas a stdlib de proposito: se este script roda, esta provado que o
runtime relocavel executa Python de verdade, sem depender de nenhum pacote
extra ter sido instalado so para testar.

Uso:
    python smoke_client.py <base_url> <arquivo> [--expect-entities N]
"""

from __future__ import annotations

import json
import mimetypes
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def wait_health(base_url: str, timeout_s: float = 900.0) -> dict:
    """Espera o backend responder. O timeout e generoso porque a primeira
    subida baixa ~2,2GB de modelo do HuggingFace antes de abrir a porta."""
    deadline = time.time() + timeout_s
    last_err: str = "sem tentativa"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/api/health", timeout=5) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # conexao recusada enquanto carrega o modelo
            last_err = f"{type(exc).__name__}: {exc}"
            time.sleep(2.0)
    raise TimeoutError(f"backend nao respondeu em {timeout_s}s (ultimo erro: {last_err})")


def post_file(base_url: str, path: Path, threshold: float = 0.5) -> dict:
    """POST multipart/form-data montado na mao, sem requests."""
    boundary = f"----xdiag{uuid.uuid4().hex}"
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    payload = path.read_bytes()

    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'.encode(),
            f"Content-Type: {mime}\r\n\r\n".encode(),
            payload,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )

    url = f"{base_url}/api/redact?threshold={threshold}&reveal=false"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:600]
        raise RuntimeError(f"HTTP {exc.code} em /api/redact: {detail}") from exc


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2

    base_url = sys.argv[1].rstrip("/")
    doc = Path(sys.argv[2])
    expect = 0
    if "--expect-entities" in sys.argv:
        expect = int(sys.argv[sys.argv.index("--expect-entities") + 1])

    if not doc.is_file():
        print(f"FALHA: arquivo nao encontrado: {doc}")
        return 1

    print(f"[1/3] aguardando {base_url}/api/health ...")
    t0 = time.time()
    health = wait_health(base_url)
    print(f"      ok em {time.time() - t0:.1f}s")
    print(f"      device={health.get('device')} pii={health.get('pii')} mock={health.get('mock_mode')}")

    print(f"[2/3] enviando {doc.name} ({doc.stat().st_size / 1024:.0f} KB) ...")
    t1 = time.time()
    result = post_file(base_url, doc)
    elapsed = time.time() - t1

    pages = result.get("pages", [])
    total = sum(len(p.get("entities", [])) for p in pages)
    unmapped = sum(1 for p in pages for e in p.get("entities", []) if e.get("unmapped"))
    labels: dict[str, int] = {}
    for p in pages:
        for e in p.get("entities", []):
            labels[e["label"]] = labels.get(e["label"], 0) + 1

    print(f"[3/3] resposta em {elapsed:.1f}s (backend reportou {result.get('elapsed_ms', 0) / 1000:.2f}s)")
    print(f"      paginas={len(pages)} entidades={total} nao_mapeadas={unmapped}")
    for label, count in sorted(labels.items(), key=lambda kv: -kv[1]):
        print(f"      {label:<24} {count}")

    first = pages[0] if pages else {}
    sample_text = (first.get("deidentified_text") or "")[:200].replace("\n", " | ")
    print(f"      texto: {sample_text}")

    if total < expect:
        print(f"FALHA: esperava ao menos {expect} entidades, veio {total}")
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

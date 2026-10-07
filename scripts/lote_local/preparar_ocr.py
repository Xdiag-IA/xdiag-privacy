"""Baixa o reconhecedor latino uma vez; nao recebe documentos."""
from pathlib import Path
import hashlib
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
URL = 'https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/onnx/PP-OCRv4/rec/latin_PP-OCRv3_rec_mobile.onnx'
SHA256 = 'e9d7a33667e8aaa702862975186adf2012e3f390cc0f9422865957125f8071cf'


def main():
    path = ROOT / 'modelos-lote' / 'latin-rec.onnx'
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == SHA256:
        print('OCR local preparado.')
        return
    with urllib.request.urlopen(URL, timeout=60) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise RuntimeError('Download do OCR nao corresponde ao hash esperado')
    path.write_bytes(data)
    print('OCR local preparado.')


if __name__ == '__main__':
    main()

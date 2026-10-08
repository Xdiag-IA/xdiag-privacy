"""Extracao local para TXT; nenhum arquivo extraido e gravado em disco."""
from io import BytesIO
from contextlib import closing
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

SUPPORTED = {'.txt', '.docx', '.pdf', '.png', '.jpg', '.jpeg', '.webp', '.tif', '.tiff'}
_ocr = None


def ocr_image(data):
    global _ocr
    import numpy as np
    from PIL import Image, ImageOps
    from rapidocr_onnxruntime import RapidOCR
    if _ocr is None:
        model = Path(__file__).resolve().parents[2] / 'modelos-lote' / 'latin-rec.onnx'
        if not model.is_file():
            raise ValueError('Modelo de OCR local nao instalado')
        _ocr = RapidOCR(rec_model_path=str(model), intra_op_num_threads=2, inter_op_num_threads=2)
    with Image.open(BytesIO(data)) as image:
        pixels = np.array(ImageOps.exif_transpose(image).convert('RGB'))[:, :, ::-1]
    result, _ = _ocr(pixels)
    if not result or any(item[2] < 0.65 for item in result):
        raise ValueError('OCR vazio ou com baixa confianca; documento exige revisao')
    return '\n'.join(item[1] for item in (result or []))


def extract(path):
    """Gera unidades independentes, sem limite arbitrario de paginas."""
    suffix = path.suffix.lower()
    if suffix == '.txt':
        yield path.read_text(encoding='utf-8-sig'), 'texto'
    elif suffix == '.pdf':
        from pypdf import PdfReader
        import pypdfium2 as pdfium
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise ValueError('PDF protegido')
        with closing(pdfium.PdfDocument(path)) as pdf:
            for index, page in enumerate(reader.pages):
                text = page.extract_text() or ''
                # Tambem faz OCR nas paginas mistas para nao perder imagens com texto.
                if page.images or not text.strip():
                    rendered_page = pdf[index]
                    bitmap = rendered_page.render(scale=2.5)
                    buffer = BytesIO()
                    image = bitmap.to_pil()
                    image.save(buffer, format='PNG')
                    image.close()
                    bitmap.close()
                    rendered_page.close()
                    scanned = ocr_image(buffer.getvalue())
                    text += '\n' + scanned
                    yield text, 'pagina_com_ocr'
                else:
                    yield text, 'pagina_texto'
    elif suffix == '.docx':
        with ZipFile(path) as doc:
            names = doc.namelist()
            if any(n.startswith('word/embeddings/') for n in names):
                raise ValueError('Anexo incorporado exige tratamento separado')
            parts = ['word/document.xml'] + sorted(n for n in names if
                n.startswith(('word/header', 'word/footer', 'word/footnotes', 'word/endnotes', 'word/comments'))
                and n.endswith('.xml'))
            ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
            for part in parts:
                root = ET.fromstring(doc.read(part))
                if any(root.iter(ns + 'del')) or any(root.iter(ns + 'ins')):
                    raise ValueError('Resolva as alteracoes controladas antes de processar')
                text = '\n'.join(''.join(t.text or '' for t in p.iter(ns + 't'))
                    for p in root.iter(ns + 'p'))
                if text.strip():
                    yield text, 'word_texto'
            for name in names:
                if name.startswith('word/media/'):
                    if Path(name).suffix.lower() not in SUPPORTED - {'.txt', '.pdf', '.docx'}:
                        raise ValueError('Imagem incorporada nao suportada')
                    yield ocr_image(doc.read(name)), 'word_imagem_ocr'
    else:
        from PIL import Image
        with Image.open(path) as image:
            for index in range(getattr(image, 'n_frames', 1)):
                image.seek(index)
                buffer = BytesIO()
                image.convert('RGB').save(buffer, format='PNG')
                yield ocr_image(buffer.getvalue()), 'imagem_ocr'

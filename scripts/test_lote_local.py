"""Testes sinteticos do lote; execute com o Python do perfil local."""
import contextlib
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).parent / 'lote_local'))
import anonimizar as batch
import extrair


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'entrada'
        self.output = self.root / 'saida'
        self.source.mkdir()
        self.output.mkdir()
        self.engine = batch.PIIEngine(batch.Settings(pii_engine='rules', pii_llm='', mock_mode=False))
        self.engine.warmup()

    def tearDown(self):
        self.temp.cleanup()

    def run_batch(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return batch.run_batch(self.source, self.output, self.engine, 1000)

    def test_long_text_split_resume_and_no_original_changes(self):
        source = self.source / 'Maria-da-Silva.txt'
        text = ('Nome: Maria da Silva\nCPF: 529.982.247-25\nE-mail: pessoa@example.com\n'
                'A evidencia foi conferida.\n') * 2000
        source.write_text(text, encoding='utf-8')
        original = batch.digest(source)
        self.assertEqual(self.run_batch(), 0)
        parts = sorted(self.output.glob('documento-*/parte-*.txt'))
        result = ''.join(p.read_text(encoding='utf-8') for p in parts)
        self.assertGreater(len(parts), 50)
        self.assertTrue(all(len(p.read_text(encoding='utf-8')) <= 1000 for p in parts))
        self.assertNotIn('529.982.247-25', result)
        self.assertNotIn('Maria da Silva', result)
        self.assertNotIn('pessoa@example.com', result)
        self.assertEqual(result.count('A evidencia foi conferida.'), 2000)
        self.assertEqual(batch.digest(source), original)
        report = (self.output / 'relatorio.json').read_text(encoding='utf-8')
        self.assertNotIn('Maria', report)
        with patch.object(self.engine, 'detect', side_effect=AssertionError('Nao deve repetir')):
            self.assertEqual(self.run_batch(), 0)
        source.write_text(text + 'alterado', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.run_batch()

    def test_boundary(self):
        for offset in (11994, 12994, 23994):
            text = ('x ' * (offset // 2)) + 'CPF: 529.982.247-25\nFIM'
            result, _ = batch.redact(text, self.engine)
            self.assertNotIn('529.982.247-25', result)
            self.assertTrue(result.endswith('FIM'))

    def test_interruption_resumes_units(self):
        (self.source / 'teste.txt').write_text('fixture', encoding='utf-8')
        def interrupted(_):
            yield 'CPF: 529.982.247-25', 'texto'
            raise KeyboardInterrupt()
        with patch.object(batch, 'extract', interrupted), self.assertRaises(KeyboardInterrupt):
            self.run_batch()
        units = [('CPF: 529.982.247-25', 'texto'), ('Email: pessoa@example.com', 'texto')]
        with patch.object(batch, 'extract', return_value=iter(units)), patch.object(
                self.engine, 'detect', wraps=self.engine.detect) as detect:
            self.assertEqual(self.run_batch(), 0)
            self.assertEqual(detect.call_count, 1)

    def test_unsupported_and_invalid_do_not_look_successful(self):
        (self.source / 'old.doc').write_bytes(b'not supported')
        (self.source / 'broken.pdf').write_bytes(b'not a PDF')
        self.assertEqual(self.run_batch(), 1)
        report = json.loads((self.output / 'relatorio.json').read_text(encoding='utf-8'))
        self.assertEqual(report['status'], 'concluido_com_pendencias')
        self.assertEqual(list(self.output.glob('documento-*')), [])

    def test_pdf_all_25_pages(self):
        import fitz
        path = self.source / 'longo.pdf'
        with fitz.open() as pdf:
            for i in range(25):
                pdf.new_page().insert_text((50, 60), f'Pagina {i + 1}\nCPF: 529.982.247-25')
            pdf.save(path)
        units = list(extrair.extract(path))
        self.assertEqual(len(units), 25)
        self.assertIn('Pagina 25', units[-1][0])
        self.assertEqual(self.run_batch(), 0)

    def test_docx_includes_tables_headers_and_notes(self):
        path = self.source / 'teste.docx'
        def xml(text):
            return f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:document>'
        with ZipFile(path, 'w') as doc:
            doc.writestr('word/document.xml', xml('CPF: 529.982.247-25'))
            doc.writestr('word/header1.xml', xml('Nome: Maria da Silva'))
            doc.writestr('word/footnotes.xml', xml('pessoa@example.com'))
        self.assertEqual(len(list(extrair.extract(path))), 3)
        self.assertEqual(self.run_batch(), 0)

    def test_scanned_pdf_and_image_offline(self):
        import fitz
        from PIL import Image, ImageDraw, ImageFont
        image = Image.new('RGB', (1600, 900), 'white')
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 48)
        draw.text((80, 100), 'CPF: 529.982.247-25', font=font, fill='black')
        draw.text((80, 200), 'Email: pessoa@example.com', font=font, fill='black')
        image.save(self.source / 'imagem.png')
        with fitz.open() as pdf:
            page = pdf.new_page(width=800, height=450)
            page.insert_image(page.rect, filename=str(self.source / 'imagem.png'))
            pdf.save(self.source / 'digitalizado.pdf')
        with patch.object(socket.socket, 'connect', batch.block_network):
            extracted = list(extrair.extract(self.source / 'digitalizado.pdf'))
            self.assertIn('529.982.247-25', extracted[0][0])
            self.assertEqual(self.run_batch(), 0)
        output = ''.join(p.read_text(encoding='utf-8') for p in self.output.glob('documento-*/*.txt'))
        self.assertNotIn('529.982.247-25', output)
        self.assertNotIn('pessoa@example.com', output)


if __name__ == '__main__':
    unittest.main()

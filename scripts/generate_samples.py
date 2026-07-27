"""Generate three synthetic Brazilian medical document images.

Outputs in samples/:
  laudo_us_obstetrico.png   ultrasound report layout
  ficha_admissao.png        hospital admission form
  prescricao_medica.png     prescription / receita medica

All identifiers are fake (CPFs validated by Luhn but obviously fictitious,
phones in reserved ranges, names from a synthetic pool). A diagonal
SYNTHETIC watermark is rendered on every page so the output is unambiguous.

Run from the repo root:
    python scripts/generate_samples.py
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


SAMPLES_DIR = Path(__file__).resolve().parents[1] / "samples"
WIDTH = 1240
HEIGHT = 1754  # roughly A4 at 150 DPI


# --- Font helpers -----------------------------------------------------------

CANDIDATE_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
    "/Library/Fonts/Arial.ttf",
]


def _find_font(bold: bool = False) -> str | None:
    for path in CANDIDATE_FONTS:
        if not os.path.exists(path):
            continue
        is_bold = "bold" in path.lower() or "bd" in path.lower()
        if bold == is_bold:
            return path
    # fallback: any candidate
    for path in CANDIDATE_FONTS:
        if os.path.exists(path):
            return path
    return None


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    path = _find_font(bold=bold)
    if path is None:
        return ImageFont.load_default()
    return ImageFont.truetype(path, size=size)


# --- Drawing primitives -----------------------------------------------------


@dataclass
class Cursor:
    x: int
    y: int
    line_height: int = 28


def draw_line(img: ImageDraw.ImageDraw, cur: Cursor, text: str, *, size: int = 20, bold: bool = False, color=(20, 20, 20)) -> None:
    img.text((cur.x, cur.y), text, font=font(size, bold=bold), fill=color)
    cur.y += cur.line_height


def draw_centered(img: ImageDraw.ImageDraw, y: int, text: str, *, size: int = 26, bold: bool = True, color=(15, 23, 42)) -> None:
    f = font(size, bold=bold)
    bbox = img.textbbox((0, 0), text, font=f)
    w = bbox[2] - bbox[0]
    img.text(((WIDTH - w) // 2, y), text, font=f, fill=color)


def draw_separator(img: ImageDraw.ImageDraw, y: int, color=(148, 163, 184)) -> None:
    img.line([(80, y), (WIDTH - 80, y)], fill=color, width=1)


def draw_watermark(img: Image.Image, text: str = "SYNTHETIC") -> None:
    """Diagonal translucent watermark stamped across the page."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    f = font(140, bold=True)
    bbox = od.textbbox((0, 0), text, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    rotated = Image.new("RGBA", (tw + 40, th + 40), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rotated)
    rd.text((20, 20), text, font=f, fill=(220, 38, 38, 70))
    rotated = rotated.rotate(30, expand=True, resample=Image.BICUBIC)
    rx = (img.width - rotated.width) // 2
    ry = (img.height - rotated.height) // 2
    overlay.paste(rotated, (rx, ry), rotated)
    img.alpha_composite(overlay)


def draw_header_bar(img: ImageDraw.ImageDraw, title: str, subtitle: str) -> None:
    img.rectangle([(0, 0), (WIDTH, 110)], fill=(15, 23, 42))
    img.rectangle([(0, 110), (WIDTH, 116)], fill=(220, 38, 38))
    img.text((80, 28), "Xdiag", font=font(32, bold=True), fill=(248, 250, 252))
    img.text((80, 70), title, font=font(20), fill=(203, 213, 225))
    f = font(16)
    bbox = img.textbbox((0, 0), subtitle, font=f)
    img.text((WIDTH - 80 - (bbox[2] - bbox[0]), 78), subtitle, font=f, fill=(148, 163, 184))


def new_page() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", (WIDTH, HEIGHT), (255, 255, 255, 255))
    return img, ImageDraw.Draw(img)


def save_page(img: Image.Image, path: Path) -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    rgb = img.convert("RGB")
    rgb.save(path, format="PNG", optimize=True)


# --- Document generators ----------------------------------------------------


def gen_laudo_us_obstetrico(path: Path) -> None:
    img, d = new_page()
    draw_header_bar(d, "Clinica Xdiag de Imagem", "CNPJ: 11.222.333/0001-81")
    draw_centered(d, 150, "LAUDO DE ULTRASSONOGRAFIA OBSTETRICA")
    draw_centered(d, 188, "Documento sintetico para teste, dados ficticios", size=14, bold=False, color=(100, 116, 139))
    draw_separator(d, 230)

    cur = Cursor(x=80, y=260)
    draw_line(d, cur, "Paciente: Maria Aparecida Pereira da Silva", size=20, bold=True)
    draw_line(d, cur, "CPF: 529.982.247-25                RG: 12.345.678-9 SSP/SP")
    draw_line(d, cur, "Data de nascimento: 12/03/1991                Idade: 34 anos")
    draw_line(d, cur, "Telefone: (11) 98765-4321         Email: maria.silva@example.com")
    draw_line(d, cur, "Endereco: Rua das Acacias, 245, apto 72, Vila Mariana, Sao Paulo, SP, CEP 04101-000")
    draw_line(d, cur, "Convenio: Saude Plena            Carteirinha: 0099 8877 6655 4433")
    draw_line(d, cur, "Data do exame: 15/04/2026                     Idade gestacional: 22 semanas e 4 dias")
    cur.y += 18
    draw_separator(d, cur.y); cur.y += 18

    draw_line(d, cur, "EXAME REALIZADO", size=18, bold=True, color=(15, 23, 42))
    cur.y += 4
    body = [
        "Realizada ultrassonografia obstetrica por via abdominal, com transdutor convexo.",
        "Feto unico, em apresentacao cefalica, dorso a esquerda materna.",
        "Batimentos cardiacos fetais presentes e ritmicos, com frequencia de 148 bpm.",
        "Movimentacao fetal ativa observada durante o exame.",
        "Placenta de insercao posterior, grau 1 de Grannum, sem sinais de descolamento.",
        "Liquido amniotico em quantidade normal (ILA estimado em 14 cm).",
        "Cordao umbilical com tres vasos (duas arterias e uma veia).",
    ]
    for line in body:
        draw_line(d, cur, line, size=16)
    cur.y += 8
    draw_line(d, cur, "BIOMETRIA FETAL", size=18, bold=True, color=(15, 23, 42))
    biometria = [
        "DBP: 54 mm     CC: 198 mm     CA: 175 mm     CF: 38 mm",
        "Peso fetal estimado: 540 gramas (percentil 52 para a idade gestacional).",
    ]
    for line in biometria:
        draw_line(d, cur, line, size=16)
    cur.y += 8
    draw_line(d, cur, "CONCLUSAO", size=18, bold=True, color=(15, 23, 42))
    draw_line(d, cur, "Gestacao topica, unica, em evolucao normal para a idade gestacional referida.", size=16)
    cur.y += 24

    draw_separator(d, cur.y); cur.y += 14
    draw_line(d, cur, "Medico responsavel: Dr. Joao Carlos Pereira", size=18, bold=True)
    draw_line(d, cur, "CRM/SP 123456                 RQE 54321")
    draw_line(d, cur, "Telefone do consultorio: (11) 3000-1234")
    draw_line(d, cur, "Email: joao.pereira@example.com")
    draw_line(d, cur, "Sao Paulo, 15/04/2026")

    draw_watermark(img)
    save_page(img, path)


def gen_ficha_admissao(path: Path) -> None:
    img, d = new_page()
    draw_header_bar(d, "Hospital Sintetico Xdiag", "CNPJ: 33.444.555/0001-81")
    draw_centered(d, 150, "FICHA DE ADMISSAO HOSPITALAR")
    draw_centered(d, 188, "Documento sintetico para teste, dados ficticios", size=14, bold=False, color=(100, 116, 139))
    draw_separator(d, 230)

    cur = Cursor(x=80, y=260)
    draw_line(d, cur, "Numero do prontuario: 2026-004-887       Atendimento: 778991", size=18, bold=True)
    cur.y += 6
    draw_line(d, cur, "DADOS DO PACIENTE", size=18, bold=True, color=(15, 23, 42))
    draw_line(d, cur, "Nome: Carlos Eduardo Marques de Oliveira", size=18, bold=True)
    draw_line(d, cur, "CPF: 111.444.777-35              RG: 22.333.444-5 SSP/RJ")
    draw_line(d, cur, "Data de nascimento: 04/07/1968               Idade: 57 anos")
    draw_line(d, cur, "Sexo: Masculino                  Cor declarada: parda")
    draw_line(d, cur, "Naturalidade: Niteroi, RJ        Nacionalidade: brasileira")
    draw_line(d, cur, "Telefone: (21) 99876-5432        Email: carlos.marques@example.com")
    draw_line(d, cur, "Endereco: Av. Atlantica, 4567, ap 301, Copacabana, Rio de Janeiro, RJ, CEP 22070-002")
    cur.y += 6
    draw_separator(d, cur.y); cur.y += 12

    draw_line(d, cur, "RESPONSAVEL / CONTATO DE EMERGENCIA", size=18, bold=True, color=(15, 23, 42))
    draw_line(d, cur, "Nome: Beatriz Marques de Oliveira          Parentesco: filha")
    draw_line(d, cur, "Telefone: (21) 98123-4567         CPF: 935.411.347-80")
    cur.y += 6
    draw_separator(d, cur.y); cur.y += 12

    draw_line(d, cur, "DADOS CLINICOS", size=18, bold=True, color=(15, 23, 42))
    draw_line(d, cur, "Data de admissao: 22/04/2026  Hora: 14:35     Origem: Pronto Socorro", size=16)
    draw_line(d, cur, "Queixa principal: dor toracica retroesternal de inicio ha 2 horas.", size=16)
    draw_line(d, cur, "Pressao arterial: 150 x 90 mmHg     Frequencia cardiaca: 96 bpm", size=16)
    draw_line(d, cur, "Saturacao: 96 por cento     Temperatura: 36.7 graus Celsius", size=16)
    draw_line(d, cur, "Antecedentes: hipertensao, dislipidemia, ex tabagista.", size=16)
    draw_line(d, cur, "Alergia conhecida: dipirona.", size=16)
    cur.y += 6
    draw_separator(d, cur.y); cur.y += 12

    draw_line(d, cur, "EQUIPE", size=18, bold=True, color=(15, 23, 42))
    draw_line(d, cur, "Medico admissor: Dra. Patricia Souza Lima", size=18, bold=True)
    draw_line(d, cur, "CRM/RJ 098765                Especialidade: Cardiologia")
    draw_line(d, cur, "Enfermeira: Fernanda Castro       COREN/RJ 234567")
    draw_line(d, cur, "Email do plantao: plantao.cardio@example.com")
    cur.y += 16
    draw_line(d, cur, "Rio de Janeiro, 22/04/2026", size=16)

    draw_watermark(img)
    save_page(img, path)


def gen_prescricao_medica(path: Path) -> None:
    img, d = new_page()
    draw_header_bar(d, "Consultorio Xdiag, Clinica Medica", "CNPJ: 12.345.678/0001-95")
    draw_centered(d, 150, "RECEITUARIO MEDICO")
    draw_centered(d, 188, "Documento sintetico para teste, dados ficticios", size=14, bold=False, color=(100, 116, 139))
    draw_separator(d, 230)

    cur = Cursor(x=80, y=260)
    draw_line(d, cur, "Paciente: Ana Beatriz Rodrigues Lima", size=20, bold=True)
    draw_line(d, cur, "CPF: 935.411.347-80              Data de nascimento: 30/11/1979 (46 anos)")
    draw_line(d, cur, "Telefone: (31) 99988-1122        Email: ana.lima@example.com")
    draw_line(d, cur, "Endereco: Rua das Palmeiras, 88, Funcionarios, Belo Horizonte, MG")
    draw_line(d, cur, "Convenio: Plano Saude Mais       Carteirinha: 0001 2233 4455 6677")
    cur.y += 8
    draw_separator(d, cur.y); cur.y += 14

    draw_line(d, cur, "PRESCRICAO", size=20, bold=True, color=(15, 23, 42))
    cur.y += 4
    items = [
        "1. Losartana potassica 50 mg",
        "   Tomar 1 comprimido pela manha, em jejum, por 30 dias.",
        "",
        "2. Atorvastatina 20 mg",
        "   Tomar 1 comprimido a noite, apos o jantar, por 30 dias.",
        "",
        "3. Acido acetilsalicilico 100 mg",
        "   Tomar 1 comprimido apos o almoco, uso continuo.",
        "",
        "4. Omeprazol 20 mg",
        "   Tomar 1 capsula em jejum, por 14 dias.",
    ]
    for line in items:
        if line == "":
            cur.y += 6
            continue
        draw_line(d, cur, line, size=18)

    cur.y += 16
    draw_line(d, cur, "Orientacoes: dieta hipossodica, atividade fisica regular,", size=16)
    draw_line(d, cur, "retorno em 30 dias com exames laboratoriais.", size=16)
    cur.y += 18
    draw_separator(d, cur.y); cur.y += 18

    draw_line(d, cur, "Belo Horizonte, 28/04/2026", size=18)
    cur.y += 18
    draw_line(d, cur, "Dr. Roberto Mendes Carvalho", size=20, bold=True)
    draw_line(d, cur, "CRM/MG 045678                RQE 78901", size=16)
    draw_line(d, cur, "Telefone: (31) 3221-5500         Email: roberto.mendes@example.com", size=16)

    draw_watermark(img)
    save_page(img, path)


def main() -> int:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Writing samples into {SAMPLES_DIR}")
    gen_laudo_us_obstetrico(SAMPLES_DIR / "laudo_us_obstetrico.png")
    gen_ficha_admissao(SAMPLES_DIR / "ficha_admissao.png")
    gen_prescricao_medica(SAMPLES_DIR / "prescricao_medica.png")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

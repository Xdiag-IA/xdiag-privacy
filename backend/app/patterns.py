"""Registro declarativo de padroes sintaticos de PII brasileira.

Tres consumidores:
  1. scan_text: varredura regex-first do texto COMPLETO em todo modo (nao
     apenas mock). Nao depende do modelo disparar, entao identificadores de
     forma inequivoca (CPF formatado, email) nunca dependem de recall do
     modelo. Tambem cobre padroes cortados na fronteira de chunk do modelo.
  2. snap_to_spec: reancoragem de um span parcial do modelo ao padrao
     sintatico completo (recuperacao de fragmentacao de tokens).
  3. o caminho mock de pii.py, que itera o REGISTRY diretamente.

Politica de score: entidade com validador de digito verificador aprovado e
`validated=True` e NUNCA e removida pelo threshold de confianca. Um CPF
matematicamente valido nao e falso positivo.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, replace
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .pii import PIIEntity


# --- Validadores de digito verificador --------------------------------------


_DIGITS_RE = re.compile(r"\D+")


def digits(s: str) -> str:
    return _DIGITS_RE.sub("", s)


def cpf_is_valid(value: str) -> bool:
    """Valida CPF pelo mod 11 padrao."""
    d = digits(value)
    if len(d) != 11 or len(set(d)) == 1:
        return False
    nums = [int(c) for c in d]

    def check(n: int) -> int:
        s = sum((n + 1 - i) * nums[i] for i in range(n))
        r = (s * 10) % 11
        return 0 if r == 10 else r

    return check(9) == nums[9] and check(10) == nums[10]


def cnpj_is_valid(value: str) -> bool:
    """Valida CNPJ pelo mod 11 padrao."""
    d = digits(value)
    if len(d) != 14 or len(set(d)) == 1:
        return False
    nums = [int(c) for c in d]
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    def check(weights: list[int], length: int) -> int:
        s = sum(nums[i] * weights[i] for i in range(length))
        r = s % 11
        return 0 if r < 2 else 11 - r

    return check(weights1, 12) == nums[12] and check(weights2, 13) == nums[13]


def cns_is_valid(value: str) -> bool:
    """Valida CNS (Cartao Nacional de Saude), 15 digitos, mod 11 proprio.

    Numeros iniciados em 1/2 derivam de um PIS com DV; iniciados em 7/8/9
    (provisorios) exigem soma ponderada divisivel por 11.
    """
    d = digits(value)
    if len(d) != 15 or len(set(d)) == 1:
        return False
    if d[0] in "12":
        pis = d[:11]
        soma = sum(int(pis[i]) * (15 - i) for i in range(11))
        resto = soma % 11
        dv = 11 - resto
        if dv == 11:
            dv = 0
        if dv == 10:
            soma2 = soma + 2
            dv = 11 - (soma2 % 11)
            if dv == 11:
                dv = 0
            return d == pis + "001" + str(dv)
        return d == pis + "000" + str(dv)
    if d[0] in "789":
        soma = sum(int(d[i]) * (15 - i) for i in range(15))
        return soma % 11 == 0
    return False


# --- Normalizacao de contexto ------------------------------------------------

# Confusoes comuns de OCR corrigidas apenas em tokens majoritariamente
# alfabeticos ("Pr0ntuari0" -> "prontuario").
_OCR_CONFUSION = str.maketrans({"0": "o", "1": "l", "5": "s"})


def normalize_context(s: str) -> str:
    """casefold + NFD sem acentos + correcao de confusao OCR em palavras."""
    s = unicodedata.normalize("NFD", s.casefold())
    s = "".join(c for c in s if not unicodedata.combining(c))
    tokens = []
    for tok in s.split():
        alpha = sum(1 for c in tok if c.isalpha())
        if alpha >= max(2, len(tok) // 2) and any(c in "015" for c in tok):
            tok = tok.translate(_OCR_CONFUSION)
        tokens.append(tok)
    return " ".join(tokens)


# --- PatternSpec e REGISTRY --------------------------------------------------


@dataclass(frozen=True)
class PatternSpec:
    """Um padrao sintatico com label, validador e regras de contexto."""

    label: str
    regex: re.Pattern[str]
    validator: Optional[Callable[[str], bool]] = None
    context: tuple[str, ...] = ()  # keywords normalizadas (minusculas, sem acento)
    context_required: bool = False
    priority: int = 0  # desempate em overlap; maior vence
    snap_sources: frozenset[str] = frozenset()  # labels do modelo que snapam aqui
    window: tuple[int, int] = (6, 16)  # chars (tras, frente) na janela de snap
    base_score: float = 0.90
    scan: bool = True  # participa da varredura regex-first
    keep_source_label: bool = False  # snap preserva o label do modelo


_DOC_SOURCES = frozenset(
    {"BR_DOC", "BR_CPF", "CPF", "BR_CNPJ", "CNPJ", "BR_RG", "RG", "ID", "NUM_CANDIDATE"}
)

REGISTRY: tuple[PatternSpec, ...] = (
    PatternSpec(
        label="BR_CNPJ",
        regex=re.compile(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)"),
        validator=cnpj_is_valid,
        priority=100,
        snap_sources=_DOC_SOURCES,
        window=(6, 18),
    ),
    PatternSpec(
        label="BR_CPF",
        regex=re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)"),
        validator=cpf_is_valid,
        priority=95,
        snap_sources=_DOC_SOURCES,
        window=(6, 16),
    ),
    PatternSpec(
        label="EMAIL",
        regex=re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        priority=80,
        snap_sources=frozenset({"EMAIL"}),
        window=(10, 60),
        base_score=0.95,
    ),
    PatternSpec(
        label="PHONE",
        # Exige formatacao (parenteses ou hifen); 10-11 digitos crus caem no
        # classificador numerico, nao aqui.
        regex=re.compile(r"(?:\(\d{2}\)\s*\d{4,5}-?\d{4}|(?<!\d)\d{2}\s?\d{4,5}-\d{4}(?!\d))"),
        priority=78,
        snap_sources=frozenset({"PHONE", "PHONE_NUMBER", "NUM_CANDIDATE"}),
        window=(6, 18),
    ),
    PatternSpec(
        label="CRM",
        regex=re.compile(r"CRM[\s/.-]*[A-Z]{2}\s*\d{4,7}", re.IGNORECASE),
        priority=75,
        snap_sources=frozenset({"CRM", "ID", "NUM_CANDIDATE"}),
        window=(6, 22),
        base_score=0.93,
    ),
    PatternSpec(
        label="ZIPCODE",
        regex=re.compile(r"(?<!\d)\d{5}-\d{3}(?!\d)"),
        priority=50,
        snap_sources=frozenset({"ZIPCODE", "ZIP", "POSTAL_CODE", "NUM_CANDIDATE"}),
        window=(4, 10),
    ),
    PatternSpec(
        label="DATE",
        regex=re.compile(r"(?<!\d)\d{1,2}/\d{1,2}/\d{2,4}(?!\d)"),
        priority=48,
        snap_sources=frozenset({"DATE", "DATE_OF_BIRTH", "DOB", "NUM_CANDIDATE"}),
        window=(4, 12),
        base_score=0.88,
    ),
    PatternSpec(
        label="AGE",
        regex=re.compile(r"(?<!\d)\d{1,3}\s?anos?\b", re.IGNORECASE),
        priority=40,
        snap_sources=frozenset({"AGE", "NUM_CANDIDATE"}),
        window=(4, 10),
        base_score=0.85,
    ),
    PatternSpec(
        label="BR_RG",
        # Somente a forma pontuada participa do scan; 8-9 digitos crus sao
        # ambiguos demais e ficam para o classificador numerico fail-closed.
        regex=re.compile(r"(?<!\d)\d{1,2}\.\d{3}\.\d{3}-?[\dXx](?![\dXx])"),
        priority=45,
        snap_sources=_DOC_SOURCES,
        window=(6, 16),
        base_score=0.88,
    ),
    PatternSpec(
        # Ultimo recurso de snap (nunca de scan): reancora um fragmento de
        # documento numerico do modelo a sequencia COMPLETA de digitos que
        # ele intersecta (CNS cru, matricula, prontuario, carteirinha com
        # espacos). Mantem o label original; snap fraco, sem bypass.
        label="DIGIT_RUN",
        regex=re.compile(r"(?<![\d])\d(?:[ .\-/]?\d)*(?![\d])"),
        priority=10,
        snap_sources=_DOC_SOURCES
        | frozenset({"MEDICAL_RECORD", "MRN", "ZIPCODE", "ZIP", "POSTAL_CODE"}),
        window=(8, 24),
        base_score=0.5,
        scan=False,
        keep_source_label=True,
    ),
)

_PRIORITY_BY_LABEL: dict[str, int] = {s.label: s.priority for s in REGISTRY}
# Labels alfabeticos do modelo tem prioridade intermediaria em trims.
_DEFAULT_PRIORITY = 55


def label_priority(label: str) -> int:
    return _PRIORITY_BY_LABEL.get(label.upper(), _DEFAULT_PRIORITY)


def _context_window(text: str, start: int, end: int, back: int = 40, ahead: int = 10) -> str:
    return text[max(0, start - back) : min(len(text), end + ahead)]


def _has_context(text: str, start: int, end: int, keywords: tuple[str, ...]) -> bool:
    window = normalize_context(_context_window(text, start, end))
    return any(k in window for k in keywords)


# --- Consumidor 1: varredura regex-first ------------------------------------


def scan_text(text: str) -> "list[PIIEntity]":
    """Varre o texto completo com todos os specs habilitados para scan.

    Roda em TODO modo (nao apenas mock). Specs com validador so emitem
    quando o digito verificador confere; specs com context_required so
    emitem com keyword na janela.
    """
    from .pii import PIIEntity

    out: list[PIIEntity] = []
    for spec in REGISTRY:
        if not spec.scan:
            continue
        for m in spec.regex.finditer(text):
            cand = m.group()
            validated = False
            score = spec.base_score
            if spec.validator is not None:
                if not spec.validator(cand):
                    continue
                validated = True
                score = 0.99
            elif spec.context_required:
                if not _has_context(text, m.start(), m.end(), spec.context):
                    continue
                score = 0.92
            elif spec.context and _has_context(text, m.start(), m.end(), spec.context):
                score = min(0.99, spec.base_score + 0.05)
            out.append(
                PIIEntity(
                    label=spec.label,
                    text=cand,
                    score=score,
                    start=m.start(),
                    end=m.end(),
                    origin="regex",
                    validated=validated,
                )
            )
    return out


# --- Consumidor 2: snap orientado ao registro --------------------------------


_FORMAT_EVIDENCE_RE = re.compile(r"[./()\-]")
_INHERENTLY_STRONG = {"EMAIL", "CRM", "AGE"}


def snap_to_spec(text: str, e: "PIIEntity") -> "tuple[PIIEntity, bool]":
    """Reancora o span do modelo ao padrao completo que ele intersecta.

    Retorna (entidade, strong). strong=True quando ha evidencia real
    (validador aprovado, formatacao com pontuacao, keyword de contexto ou
    forma inequivoca); snap fraco NAO ganha bypass de threshold.
    """
    label = e.label.upper()
    candidates = [s for s in REGISTRY if label in s.snap_sources]
    if not candidates:
        return e, False
    candidates.sort(key=lambda s: -s.priority)

    for spec in candidates:
        back, ahead = spec.window
        win_start = max(0, e.start - back)
        win_end = min(len(text), e.end + ahead)
        window = text[win_start:win_end]
        best: tuple[int, int, str] | None = None
        for m in spec.regex.finditer(window):
            ns = win_start + m.start()
            ne = win_start + m.end()
            if ne <= e.start or ns >= e.end:
                continue
            if spec.validator is not None and not spec.validator(m.group()):
                continue
            if best is None or (ne - ns) > (best[1] - best[0]):
                best = (ns, ne, m.group())
        if best is None:
            continue
        ns, ne, cand = best
        validated = spec.validator is not None
        new_label = e.label if spec.keep_source_label else spec.label
        strong = not spec.keep_source_label and (
            validated
            or spec.label in _INHERENTLY_STRONG
            or bool(_FORMAT_EVIDENCE_RE.search(cand))
            or (bool(spec.context) and _has_context(text, ns, ne, spec.context))
        )
        return (
            replace(
                e,
                label=new_label,
                text=cand,
                start=ns,
                end=ne,
                validated=validated or e.validated,
            ),
            strong,
        )
    return e, False


# --- Dedup, containment e disjuncao ------------------------------------------


def _rank(e: "PIIEntity") -> tuple:
    return (e.validated, label_priority(e.label), e.end - e.start, e.score)


def dedupe_exact(entities: "list[PIIEntity]") -> "list[PIIEntity]":
    """Colapsa spans identicos (regex-first + modelo detectando o mesmo CPF).

    Sem isso, deidentify_text faria splice duplo no mesmo offset e as
    estatisticas contariam em dobro.
    """
    by_span: dict[tuple[int, int], "PIIEntity"] = {}
    for e in entities:
        key = (e.start, e.end)
        cur = by_span.get(key)
        if cur is None or _rank(e) > _rank(cur):
            merged = e if cur is None else replace(
                e,
                score=max(e.score, cur.score),
                validated=e.validated or cur.validated,
            )
            by_span[key] = merged
        else:
            by_span[key] = replace(
                cur,
                score=max(e.score, cur.score),
                validated=e.validated or cur.validated,
            )
    return sorted(by_span.values(), key=lambda x: (x.start, -(x.end - x.start)))


def finalize_disjoint(entities: "list[PIIEntity]", text: str) -> "list[PIIEntity]":
    """Containment drop + trim de overlaps parciais.

    Garante spans estritamente disjuntos: o splice reverso de
    deidentify_text e o mapeamento de bboxes assumem isso.
    """
    entities = sorted(entities, key=lambda x: (x.start, -(x.end - x.start)))

    # Drop de contidos em spans estritamente maiores (o placeholder do
    # container ja cobre o conteudo).
    kept: list["PIIEntity"] = []
    for e in entities:
        contained = False
        for o in entities:
            if (o.start, o.end) == (e.start, e.end):
                continue
            if o.start <= e.start and o.end >= e.end:
                contained = True
                break
        if not contained:
            kept.append(e)

    # Trim de overlaps parciais: perde quem tem rank menor.
    result: list["PIIEntity"] = []
    for e in kept:
        cur = e
        drop = False
        for i, prev in enumerate(result):
            if cur.start >= prev.end or cur.end <= prev.start:
                continue
            if _rank(cur) > _rank(prev):
                # encolhe o anterior
                if prev.start < cur.start:
                    result[i] = replace(prev, end=cur.start, text=text[prev.start : cur.start])
                elif prev.end > cur.end:
                    result[i] = replace(prev, start=cur.end, text=text[cur.end : prev.end])
                else:
                    result[i] = replace(prev, end=prev.start, text="")
            else:
                if cur.end > prev.end:
                    cur = replace(cur, start=prev.end, text=text[prev.end : cur.end])
                elif cur.start < prev.start:
                    cur = replace(cur, end=prev.start, text=text[cur.start : prev.start])
                else:
                    drop = True
                    break
        if drop:
            continue
        result.append(cur)

    def alive(e: "PIIEntity") -> bool:
        inner = e.text.strip(".,-/:;()[]_ \t\n")
        return e.end > e.start and sum(1 for c in inner if c.isalnum()) >= 2

    return sorted((e for e in result if alive(e)), key=lambda x: x.start)


# --- Classificador fail-closed de tokens numericos ---------------------------

# Keywords identificadoras (normalizadas). A MAIS PROXIMA a esquerda do
# numero vence sobre qualquer indicio de medida (fail-closed em empate).
IDENT_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("prontuario", "pront", "registro hospitalar", "mrn"), "MEDICAL_RECORD"),
    (("atendimento", "atend", "boletim"), "MEDICAL_RECORD"),
    (("guia",), "TISS_GUIDE"),
    (("senha", "autorizacao"), "TISS_AUTH"),
    (
        (
            "matricula", "carteirinha", "carteira", "cartao", "beneficiario",
            "convenio", "unimed", "bradesco", "amil", "sulamerica",
            "sul america", "cassi", "ipasgo", "hapvida",
        ),
        "INSURANCE_ID",
    ),
    (("cns", "cartao sus", "cartao nacional de saude"), "CNS"),
    (("cnes",), "CNES"),
    (("rqe",), "RQE"),
    (("crm", "cfm"), "CRM"),
    (("coren",), "COREN"),
    (("crbm", "crf", "cro"), "ID"),
    (("registro", "protocolo", "pedido", "ordem de servico", "codigo"), "ID"),
)

# Keywords de medida clinica: numero precedido por uma delas e valor, nao
# identificador. Tokens curtos exigem fronteira de palavra.
MEASURE_KEYWORDS: tuple[str, ...] = (
    "dbp", "ccn", "cc", "ca", "cf", "cn", "ila", "bcf", "fc", "fr", "pa",
    "spo2", "sat", "peso", "altura", "comprimento", "diametro", "espessura",
    "volume", "vol", "medida", "area", "imc", "percentil", "grau", "graus",
    "ig", "idade gestacional", "hb", "ht", "hto", "vcm", "hcm", "chcm",
    "rdw", "dose", "dosagem", "valor", "qtde", "quantidade", "frequencia",
    "pressao", "temperatura", "saturacao", "indice",
)

# Unidades adjacentes a direita (ate 3 chars de distancia, aceita colado).
_UNIT_RE = re.compile(
    r"^[\s.:,]{0,3}(?:mm3|cm3|mm2|cm2|mmhg|mcg|kcal|bpm|rpm|mg/dl|g/dl|"
    r"ng/ml|u/l|ui|ml|dl|mg|kg|ug|fl|pg|hz|db|cm|mm|graus?|semanas?|sem\b|"
    r"dias?|min|seg|hs?\b|x\b|%|°c|oc\b|g\b|l\b|m\b|s\b)",
    re.IGNORECASE,
)
_DIM_LEFT_RE = re.compile(r"x\s{0,2}$", re.IGNORECASE)
_DECIMAL_RE = re.compile(r"\d,\d")
_DATE_FRAG_RE = re.compile(r"^\d{1,2}/\d{1,2}(/\d{2,4})?$|^\d{1,2}/\d{4}$")
_TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")
_CID_BODY_RE = re.compile(r"^\d{2}(\.\d)?$")

# Labels que nascem do classificador numerico: merge apenas com gap zero
# (nunca o filler de PERSON), para nao fundir uma linha de biometria em uma
# tarja unica.
NUMERIC_CONTEXT_LABELS: frozenset[str] = frozenset(
    {
        "NUMERO", "MEDICAL_RECORD", "TISS_GUIDE", "TISS_AUTH", "INSURANCE_ID",
        "CNS", "CNES", "RQE", "COREN",
    }
)


def _left_window(text: str, start: int, back: int = 40) -> str:
    """Janela esquerda de ate `back` chars cruzando NO MAXIMO 1 quebra."""
    lo = max(0, start - back)
    window = text[lo:start]
    parts = window.split("\n")
    if len(parts) > 2:
        window = "\n".join(parts[-2:])
    return window


def _right_window(text: str, end: int, ahead: int = 10) -> str:
    """Janela direita sem cruzar quebra de linha (unidade gruda no valor)."""
    hi = min(len(text), end + ahead)
    window = text[end:hi]
    return window.split("\n", 1)[0]


def classify_numeric(text: str, e: "PIIEntity") -> "Optional[PIIEntity]":
    """Decide o destino de um NUM_CANDIDATE que nao snapou a padrao algum.

    Fail-closed: na duvida, tarja. Retorna None APENAS quando ha evidencia
    de valor clinico (unidade, keyword de medida, virgula decimal, cadeia
    dimensional, CID, hora) ou quando o token tem 3 digitos ou menos (unico
    furo deliberado: nenhum identificador brasileiro relevante cabe em 3
    digitos, e tarjar todo "grau 1" destruiria a legibilidade do laudo).
    """
    span_text = e.text.strip(".,-/:;()[]_ \t\n")
    left_raw = _left_window(text, e.start)
    left = normalize_context(left_raw)
    right = _right_window(text, e.end)

    # 1. Idade ("34 anos") vira AGE, e PII.
    if re.match(r"^\s{0,2}anos?\b", right, re.IGNORECASE):
        return replace(e, label="AGE", origin="numeric")

    # 2. Keyword identificadora mais proxima a esquerda vence sobre tudo.
    best: "tuple[int, str] | None" = None  # (distancia, label)
    for keywords, label in IDENT_KEYWORDS:
        for k in keywords:
            idx = left.rfind(k)
            if idx < 0:
                continue
            dist = len(left) - (idx + len(k))
            if best is None or dist < best[0]:
                best = (dist, label)
    measure_dist: "int | None" = None
    for k in MEASURE_KEYWORDS:
        pat = r"\b" + re.escape(k) + r"\b" if len(k) <= 4 else re.escape(k)
        for m in re.finditer(pat, left):
            dist = len(left) - m.end()
            if measure_dist is None or dist < measure_dist:
                measure_dist = dist
    if best is not None and (measure_dist is None or best[0] <= measure_dist):
        label = best[1]
        validated = label == "CNS" and cns_is_valid(span_text)
        return replace(e, label=label, origin="numeric", validated=validated)

    # 3. Evidencias de valor clinico descartam.
    if _UNIT_RE.match(right):
        return None
    if measure_dist is not None:
        return None
    if _DECIMAL_RE.search(span_text):
        return None
    if _DIM_LEFT_RE.search(left_raw):
        return None
    if _TIME_RE.match(span_text):
        return None
    prev = text[e.start - 1] if e.start > 0 else ""
    if prev.isalpha() and _CID_BODY_RE.match(span_text):
        return None
    if _DATE_FRAG_RE.match(span_text):
        return replace(e, label="DATE", origin="numeric")

    # 4. Fallback fail-closed por contagem de digitos.
    n_digits = sum(1 for c in span_text if c.isdigit())
    if n_digits >= 4:
        return replace(e, label="NUMERO", origin="numeric")
    return None


# --- Nomes: ancoragem por rotulo e expansao de span --------------------------
#
# Nome nao tem validador de digito verificador nem forma sintatica propria,
# entao ate aqui dependia 100% do recall do modelo. Duas falhas reais
# motivaram esta secao:
#
#   "Paciente : APARECIDO SILVERIO BORGES" -> o modelo achou so
#   "SILVERIO BORGES"; o primeiro nome ficou exposto porque "APARECIDO"
#   tambem e palavra comum do portugues.
#
#   "KELLITA DE OLIVEIRA FRAGA FARIA" em cabecalho DICOM -> caixa alta sem
#   rotulo, o modelo nao emitiu nada.
#
# A ancoragem por rotulo resolve o primeiro caso sem depender do modelo; a
# expansao de span resolve o nome cortado quando o modelo acerta so um
# pedaco. Ambas sao fail-closed: na duvida, tarjam a mais.

# Conectivos que ficam em minuscula no meio de um nome brasileiro.
NAME_CONNECTIVES: frozenset[str] = frozenset(
    {"de", "da", "do", "dos", "das", "e", "del", "di", "du", "van", "von", "der", "la", "le"}
)

# Titulos e pronomes de tratamento: nao sao PII por si so (o LABEL_REMAP ja
# dropa PREFIX/TITLE do modelo pelo mesmo motivo). Ficam FORA do span para
# que o laudo continue legivel: "DRA. [NOME]" em vez de "[NOME]".
NAME_TITLES: frozenset[str] = frozenset(
    {"dr", "dra", "drs", "doutor", "doutora", "sr", "sra", "srta",
     "prof", "profa", "professor", "professora"}
)

# Rotulo de campo que introduz um nome de pessoa. Tolerante a acento porque
# a varredura roda sobre o texto cru do OCR, onde os offsets precisam valer.
_NAME_KEY_RE = re.compile(
    r"\b(?:"
    r"pacientes?|pac|nome(?:\s+(?:completo|do\s+paciente|da\s+m[aã]e|social))?|"
    r"m[eé]dic[oa]|doutor[a]?|dr[a]?|"
    r"solicitante|requisitante|executante|respons[aá]vel|profissional|"
    r"examinador[a]?|benefici[aá]ri[oa]|titular|segurad[oa]|"
    r"m[aã]e|pai|acompanhante"
    r")\b\.?",
    re.IGNORECASE,
)

# Um token alfabetico, com apostrofo interno e ponto final opcional (inicial).
_NAME_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ']*\.?")

# Palavras capitalizadas que aparecem coladas a um nome mas NAO fazem parte
# dele. Sem esta barreira a expansao produzia
# "Tereza Cristina Fontes Amaral    Registro" e "Livia Quintela Matos  CRBM".
# Rotulo de campo seguido de ":" ja e barrado pela regra geral em
# _followed_by_colon; esta lista cobre o que aparece SEM dois pontos.
NAME_STOPWORDS: frozenset[str] = frozenset(
    {
        # conselhos profissionais
        "crm", "crmv", "cro", "crf", "crbm", "coren", "crefito", "crn", "crp",
        "cns", "cnes", "rqe", "uf", "sp", "rj", "mg", "rs", "pr", "ba", "pe",
        # rotulos e cabecalhos comuns em laudo e ficha
        "registro", "prontuario", "prontuário", "matricula", "matrícula",
        "idade", "data", "convenio", "convênio", "plano", "carteirinha",
        # "nascimento" NAO entra: e sobrenome comum ("JOSE ROBERTO NASCIMENTO
        # FILHO"). Como rotulo de campo ele sempre vem com dois pontos, e a
        # regra geral de _followed_by_colon ja o barra sem cortar o sobrenome.
        "sexo", "telefone", "celular", "email", "endereco",
        "endereço", "cpf", "rg", "guia", "senha", "leito", "quarto", "setor",
        "especialidade", "exame", "solicitante", "requisitante", "executante",
        "responsavel", "responsável", "clinica", "clínica", "hospital",
        "laboratorio", "laboratório", "unidade", "operadora", "codigo",
        "código", "assinatura", "carimbo", "obs", "observacoes", "observações",
    }
)


def _followed_by_colon(text: str, pos: int, limit: int) -> bool:
    """True se, a partir de `pos`, vem ':' apos espacos opcionais.

    Um token assim e rotulo de campo ("... Amaral   Registro: 20261578"), nao
    parte do nome. Regra geral: dispensa listar todo rotulo possivel.
    """
    while pos < limit and text[pos] in " \t":
        pos += 1
    return pos < limit and text[pos] == ":"


def _is_name_stopword(tok: str) -> bool:
    return tok.rstrip(".").casefold() in NAME_STOPWORDS

# Teto de tokens de um nome. "KELLITA DE OLIVEIRA FRAGA FARIA" tem 5; 8 da
# folga sem deixar a expansao correr solta sobre prosa clinica.
_NAME_MAX_TOKENS = 8


def _is_name_token(tok: str) -> bool:
    """Token que pode compor um nome proprio.

    Aceita palavra capitalizada, palavra em caixa alta e inicial ("F.").
    NAO aceita palavra toda minuscula que nao seja conectivo: e o que impede
    a expansao de engolir prosa clinica ("Apresentando imagem anecoica ..."
    para em "imagem").
    """
    bare = tok.rstrip(".")
    if not bare:
        return False
    if len(bare) == 1:
        # Inicial so vale com o ponto ("F."), senao qualquer letra solta
        # de uma tabela viraria nome.
        return tok.endswith(".") and bare.isalpha() and bare.isupper()
    if not bare.isalpha():
        return False
    if bare.casefold() in NAME_CONNECTIVES:
        return True
    return bare.isupper() or bare[0].isupper()


def _is_connective(tok: str) -> bool:
    return tok.rstrip(".").casefold() in NAME_CONNECTIVES


def _is_title(tok: str) -> bool:
    return tok.rstrip(".").casefold() in NAME_TITLES


def _line_bounds(text: str, pos: int) -> tuple[int, int]:
    """Limites da linha que contem `pos`. Nome nunca cruza quebra de linha."""
    lo = text.rfind("\n", 0, pos) + 1
    hi = text.find("\n", pos)
    return lo, (len(text) if hi < 0 else hi)


def _name_run_forward(text: str, start: int, limit: int) -> int:
    """Fim da corrida de tokens de nome a partir de `start`, dentro de `limit`.

    Conectivo nunca encerra o nome nem o termina: "de" so entra se vier
    outro token de nome depois, senao o span terminaria em "OLIVEIRA DE".
    """
    end = start
    cursor = start
    tokens = 0
    while cursor < limit and tokens < _NAME_MAX_TOKENS:
        m = _NAME_TOKEN_RE.match(text, cursor)
        if m is None:
            # pula espacos simples entre tokens; qualquer outra coisa
            # (digito, dois pontos, virgula) encerra o nome
            if text[cursor] == " " and cursor + 1 < limit:
                cursor += 1
                continue
            break
        tok = m.group()
        if not _is_name_token(tok) or _is_name_stopword(tok):
            break
        if _followed_by_colon(text, m.end(), limit):
            break  # rotulo do proximo campo, nao sobrenome
        cursor = m.end()
        tokens += 1
        if not _is_connective(tok):
            end = cursor
    return end


def _name_run_backward(text: str, end: int, limit: int) -> int:
    """Inicio da corrida de tokens de nome terminando em `end`, acima de `limit`."""
    start = end
    cursor = end
    tokens = 0
    while cursor > limit and tokens < _NAME_MAX_TOKENS:
        probe = cursor
        while probe > limit and text[probe - 1] == " ":
            probe -= 1
        if probe == cursor and probe > limit and not text[probe - 1].isalpha() \
                and text[probe - 1] != ".":
            break
        tok_end = probe
        tok_start = probe
        while tok_start > limit and (
            text[tok_start - 1].isalpha() or text[tok_start - 1] in "'."
        ):
            tok_start -= 1
        tok = text[tok_start:tok_end]
        if not tok or not _is_name_token(tok) or _is_title(tok) or _is_name_stopword(tok):
            break
        cursor = tok_start
        tokens += 1
        if not _is_connective(tok):
            start = tok_start
    return start


def scan_labeled_names(text: str) -> "list[PIIEntity]":
    """Nome ancorado em rotulo de campo, independente do modelo.

    "Paciente : APARECIDO SILVERIO BORGES" -> o rotulo e evidencia forte de
    que o valor a direita e nome de pessoa, entao a entidade nasce com
    origin="regex" e ignora o threshold, igual a um CPF validado.

    O rotulo e o valor podem estar em linhas diferentes do stream do OCR:
    numa tabela, PaddleOCR frequentemente devolve "Paciente" e
    ": APARECIDO ..." como caixas separadas. Por isso a janela cruza no
    maximo UMA quebra.
    """
    from .pii import PIIEntity

    out: list[PIIEntity] = []
    # Rotulos encadeados ("Medico : DRA. ANA CAROLINA") disparam duas vezes,
    # pelo campo e pelo tratamento; ambos convergem para o mesmo span.
    seen: set[tuple[int, int]] = set()
    for m in _NAME_KEY_RE.finditer(text):
        cursor = m.end()
        crossed_newline = False
        # Consome o separador entre rotulo e valor (": ", " - ", espacos e no
        # maximo uma quebra de linha).
        while cursor < len(text) and text[cursor] in " \t:-\n":
            if text[cursor] == "\n":
                if crossed_newline:
                    break
                crossed_newline = True
            cursor += 1
        if cursor >= len(text):
            continue
        _, line_end = _line_bounds(text, cursor)
        # Titulo colado no valor ("Medico: DRA. ANA CAROLINA") fica fora.
        while True:
            tm = _NAME_TOKEN_RE.match(text, cursor)
            if tm is None or not _is_title(tm.group()):
                break
            cursor = tm.end()
            while cursor < line_end and text[cursor] in " \t.":
                cursor += 1
        end = _name_run_forward(text, cursor, line_end)
        if end <= cursor:
            continue
        value = text[cursor:end]
        # Exige pelo menos um token de nome de verdade (2+ letras); um "A"
        # solto ou um conectivo isolado nao viram entidade.
        if sum(1 for t in _NAME_TOKEN_RE.findall(value) if len(t.rstrip(".")) >= 2) < 1:
            continue
        if (cursor, end) in seen:
            continue
        seen.add((cursor, end))
        out.append(
            PIIEntity(
                label="PERSON",
                text=value,
                score=0.94,
                start=cursor,
                end=end,
                origin="regex",
            )
        )
    return out


def expand_person_span(text: str, e: "PIIEntity") -> "PIIEntity":
    """Estende um span de PERSON sobre o nome completo ao redor.

    Corrige o caso em que o modelo acerta so um pedaco: achou
    "SILVERIO BORGES" e deixou "APARECIDO" exposto, ou fatiou
    "ANA CAROLINA" e "PRUDENTE" em dois spans com "F." no meio.

    Fail-closed com freio: a expansao so atravessa tokens capitalizados, em
    caixa alta ou conectivos, e nunca cruza quebra de linha.
    """
    if e.label.upper() not in {"PERSON", "PATIENT", "PATIENT_NAME", "DOCTOR", "DOCTOR_NAME"}:
        return e
    line_start, line_end = _line_bounds(text, e.start)
    if e.end > line_end:  # span multi-linha: nao mexe
        return e
    new_start = _name_run_backward(text, e.start, line_start)
    new_end = _name_run_forward(text, e.end, line_end)
    # A corrida para tras pode ter parado dentro do proprio span; o span
    # original e sempre o piso.
    new_start = min(new_start, e.start)
    new_end = max(new_end, e.end)
    while new_end > new_start and text[new_end - 1] in " \t":
        new_end -= 1
    while new_start < new_end and text[new_start] in " \t":
        new_start += 1
    if (new_start, new_end) == (e.start, e.end):
        return e
    return replace(e, start=new_start, end=new_end, text=text[new_start:new_end])

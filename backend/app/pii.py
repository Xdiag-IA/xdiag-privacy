"""OpenMed PII detector.

Wraps the openmed[hf] package and falls back to a vanilla transformers
pipeline if the openmed convenience API is not available. The fallback path
exists because openmed releases sometimes lag the underlying transformers
versions, and we never want PII detection to silently drop to mock mode.

Brazilian validators (Luhn style) are applied on top of the model output to
filter false positives on CPF and CNPJ. The model is strong but document
noise (especially OCR artifacts) can occasionally produce malformed digits.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from threading import Lock
from typing import Any

from .config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class PIIEntity:
    label: str
    text: str
    score: float
    start: int
    end: int


# Maps the raw label emitted by the model to a canonical normalized label.
# OpenMed PII Portuguese SnowflakeMed uses the universal English label set
# (SSN, FIRSTNAME, LASTNAME, ZIPCODE, BUILDINGNUMBER, etc.). We normalize to
# Brazilian friendly buckets so the UI can show meaningful labels and so
# downstream Luhn validators can run on document numbers.
LABEL_REMAP: dict[str, str] = {
    # Documents
    "SSN": "BR_DOC",  # disambiguated to BR_CPF / BR_CNPJ by Luhn in post filter
    "TAXNUM": "BR_DOC",
    "TAXID": "BR_DOC",
    "GOVID": "BR_DOC",
    # Persons
    "FIRSTNAME": "PERSON",
    "LASTNAME": "PERSON",
    "MIDDLENAME": "PERSON",
    "FULLNAME": "PERSON",
    "USERNAME": "PERSON",
    # Contact
    "PHONENUMBER": "PHONE",
    "PHONE_NUMBER": "PHONE",
    "PHONEIMEI": "PHONE",
    "EMAILADDRESS": "EMAIL",
    "EMAIL_ADDRESS": "EMAIL",
    # Address pieces
    "STREET": "ADDRESS",
    "STREETADDRESS": "ADDRESS",
    "BUILDINGNUMBER": "ADDRESS",
    "SECONDARYADDRESS": "ADDRESS",
    "COUNTY": "CITY",
    # Other
    "DATEOFBIRTH": "DATE_OF_BIRTH",
    "DOB": "DATE_OF_BIRTH",
    "ACCOUNTNUMBER": "ID",
    "ACCOUNTNAME": "ID",
    "CREDITCARDNUMBER": "ID",
    "USERAGENT": "ID",
    "URL": "URL",
    "IP": "IP",
    "IPV4": "IP",
    "IPV6": "IP",
    "PREFIX": "DROP",  # "Dr.", "Sr." etc. usually not PII on its own
    "SUFFIX": "DROP",
    "TITLE": "DROP",
    "JOBTITLE": "DROP",
    "JOBAREA": "DROP",
    "JOBTYPE": "DROP",
    # Medical measurements and monetary values are NOT PII in clinical
    # documents (e.g. "100ml", "28,64 g", "13,0 N"). The model emits these
    # as AMOUNT/CURRENCY/MONEY but in a laudo context they are clinical
    # measurements, not identifying information.
    "AMOUNT": "DROP",
    "AMOUNTOFMONEY": "DROP",
    "MONEY": "DROP",
    "CURRENCY": "DROP",
    "CURRENCYCODE": "DROP",
    "CURRENCYNAME": "DROP",
    "CURRENCYSYMBOL": "DROP",
    "MEASUREMENT": "DROP",
    "PERCENT": "DROP",
    "PERCENTAGE": "DROP",
    "QUANTITY": "DROP",
    "TIME": "DROP",
    "ORDINAL": "DROP",
    "CARDINAL": "DROP",
    "NUMBER": "DROP",
    "COMPANY_NAME": "INSTITUTION",
    "COMPANYNAME": "INSTITUTION",
    "ORDINALDIRECTION": "DROP",
    "MASKEDNUMBER": "ID",
    "PIN": "ID",
    "BIC": "ID",
    "IBAN": "ID",
    "VEHICLEVRM": "ID",
    "VEHICLEVIN": "ID",
    "BITCOINADDRESS": "ID",
    "ETHEREUMADDRESS": "ID",
    "LITECOINADDRESS": "ID",
}


# Maps a label to the redaction placeholder used in deidentified_text.
LABEL_PLACEHOLDER: dict[str, str] = {
    "BR_DOC": "[DOC]",
    "BR_CPF": "[CPF]",
    "CPF": "[CPF]",
    "BR_CNPJ": "[CNPJ]",
    "CNPJ": "[CNPJ]",
    "BR_RG": "[RG]",
    "RG": "[RG]",
    "PERSON": "[NOME]",
    "PATIENT": "[NOME]",
    "PATIENT_NAME": "[NOME]",
    "DOCTOR": "[MEDICO]",
    "DOCTOR_NAME": "[MEDICO]",
    "PROFESSIONAL": "[PROFISSIONAL]",
    "DATE": "[DATA]",
    "DATE_OF_BIRTH": "[DATA_NASC]",
    "DOB": "[DATA_NASC]",
    "AGE": "[IDADE]",
    "PHONE": "[TELEFONE]",
    "PHONE_NUMBER": "[TELEFONE]",
    "EMAIL": "[EMAIL]",
    "ADDRESS": "[ENDERECO]",
    "STREET_ADDRESS": "[ENDERECO]",
    "CITY": "[CIDADE]",
    "STATE": "[UF]",
    "ZIP": "[CEP]",
    "ZIPCODE": "[CEP]",
    "POSTAL_CODE": "[CEP]",
    "ID": "[ID]",
    "MEDICAL_RECORD": "[PRONTUARIO]",
    "MEDICAL_RECORD_NUMBER": "[PRONTUARIO]",
    "MRN": "[PRONTUARIO]",
    "CRM": "[CRM]",
    "INSTITUTION": "[INSTITUICAO]",
    "HOSPITAL": "[INSTITUICAO]",
    "ORGANIZATION": "[INSTITUICAO]",
    "URL": "[URL]",
    "IP": "[IP]",
}

LABEL_COLOR: dict[str, str] = {
    "BR_DOC": "#dc2626",
    "BR_CPF": "#dc2626",
    "CPF": "#dc2626",
    "BR_CNPJ": "#ea580c",
    "CNPJ": "#ea580c",
    "BR_RG": "#d97706",
    "RG": "#d97706",
    "PERSON": "#f43f5e",
    "PATIENT": "#f43f5e",
    "PATIENT_NAME": "#f43f5e",
    "DOCTOR": "#be185d",
    "DOCTOR_NAME": "#be185d",
    "PROFESSIONAL": "#db2777",
    "DATE": "#2563eb",
    "DATE_OF_BIRTH": "#1d4ed8",
    "DOB": "#1d4ed8",
    "AGE": "#0891b2",
    "PHONE": "#16a34a",
    "PHONE_NUMBER": "#16a34a",
    "EMAIL": "#0d9488",
    "ADDRESS": "#9333ea",
    "STREET_ADDRESS": "#9333ea",
    "CITY": "#7c3aed",
    "STATE": "#6d28d9",
    "ZIP": "#4f46e5",
    "ZIPCODE": "#4f46e5",
    "POSTAL_CODE": "#4f46e5",
    "ID": "#4338ca",
    "MEDICAL_RECORD": "#3730a3",
    "MEDICAL_RECORD_NUMBER": "#3730a3",
    "MRN": "#3730a3",
    "CRM": "#db2777",
    "INSTITUTION": "#475569",
    "HOSPITAL": "#475569",
    "ORGANIZATION": "#475569",
    "URL": "#0369a1",
    "IP": "#075985",
}

DEFAULT_PLACEHOLDER = "[REDACTED]"
DEFAULT_COLOR = "#dc2626"


def label_placeholder(label: str) -> str:
    return LABEL_PLACEHOLDER.get(label.upper(), DEFAULT_PLACEHOLDER)


def label_color(label: str) -> str:
    return LABEL_COLOR.get(label.upper(), DEFAULT_COLOR)


def supported_labels() -> list[tuple[str, str, str]]:
    """Return triples of (label, color, placeholder) for the labels endpoint."""
    seen: dict[str, tuple[str, str]] = {}
    for lbl, ph in LABEL_PLACEHOLDER.items():
        seen[lbl] = (LABEL_COLOR.get(lbl, DEFAULT_COLOR), ph)
    return [(k, v[0], v[1]) for k, v in seen.items()]


# --- Brazilian validators ---------------------------------------------------


_DIGITS_RE = re.compile(r"\D+")


def _digits(s: str) -> str:
    return _DIGITS_RE.sub("", s)


def cpf_is_valid(value: str) -> bool:
    """Validate a Brazilian CPF using the standard mod 11 check digits."""
    d = _digits(value)
    if len(d) != 11 or len(set(d)) == 1:
        return False
    nums = [int(c) for c in d]

    def check(n: int) -> int:
        s = sum((n + 1 - i) * nums[i] for i in range(n))
        r = (s * 10) % 11
        return 0 if r == 10 else r

    return check(9) == nums[9] and check(10) == nums[10]


def cnpj_is_valid(value: str) -> bool:
    """Validate a Brazilian CNPJ using the standard mod 11 check digits."""
    d = _digits(value)
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


# --- Engine -----------------------------------------------------------------


class PIIEngine:
    """OpenMed wrapper with a transformers fallback."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._pipe: Any | None = None
        self._lock = Lock()
        self._loaded = False
        self._backend: str = "uninitialized"

    @property
    def loaded(self) -> bool:
        return self._loaded or self.settings.mock_mode

    @property
    def backend(self) -> str:
        if self.settings.mock_mode:
            return "mock"
        return self._backend

    def warmup(self) -> None:
        if self.settings.mock_mode:
            self._loaded = True
            self._backend = "mock"
            logger.info("PII engine running in mock mode")
            return
        with self._lock:
            if self._pipe is not None:
                return
            self._pipe = self._load_pipeline()
            self._loaded = True
            logger.info("PII engine loaded via %s", self._backend)

    def _load_pipeline(self) -> Any:
        # First try the openmed convenience wrapper.
        try:
            import openmed  # type: ignore

            if hasattr(openmed, "pipeline"):
                pipe = openmed.pipeline(  # type: ignore[attr-defined]
                    "pii",
                    model=self.settings.pii_model,
                    aggregation_strategy=self.settings.pii_aggregation,
                    device=self.settings.pii_device,
                )
                self._backend = "openmed.pipeline"
                return pipe
        except Exception as exc:  # pragma: no cover
            logger.info("openmed.pipeline unavailable (%s), falling back to transformers", exc)

        # Fallback to the transformers token classification pipeline directly.
        from transformers import pipeline  # type: ignore

        pipe = pipeline(
            "token-classification",
            model=self.settings.pii_model,
            aggregation_strategy=self.settings.pii_aggregation,
            device=self.settings.pii_device,
        )
        self._backend = "transformers.pipeline"
        return pipe

    def detect(self, text: str, threshold: float = 0.5) -> list[PIIEntity]:
        if not text.strip():
            return []
        if self.settings.mock_mode:
            return self._mock_detect(text, threshold)
        if self._pipe is None:
            self.warmup()
        assert self._pipe is not None

        # Naive chunking for very long pages: split on the last newline before
        # the chunk size limit so we never break a token.
        chunks = self._chunk_text(text, self.settings.pii_max_input_chars)
        all_entities: list[PIIEntity] = []
        for offset, chunk in chunks:
            with self._lock:
                results = self._pipe(chunk)
            for r in results or []:
                ent = self._normalize_hf_entity(r, offset)
                if ent is None or ent.score < threshold:
                    continue
                all_entities.append(ent)
        return self._post_filter(all_entities, text)

    @staticmethod
    def _chunk_text(text: str, max_chars: int) -> list[tuple[int, str]]:
        if len(text) <= max_chars:
            return [(0, text)]
        chunks: list[tuple[int, str]] = []
        cursor = 0
        while cursor < len(text):
            window_end = min(cursor + max_chars, len(text))
            if window_end < len(text):
                # back off to the previous newline for a cleaner split
                nl = text.rfind("\n", cursor, window_end)
                if nl > cursor:
                    window_end = nl
            chunks.append((cursor, text[cursor:window_end]))
            cursor = window_end if window_end > cursor else cursor + max_chars
        return chunks

    @staticmethod
    def _normalize_hf_entity(raw: dict[str, Any], offset: int) -> PIIEntity | None:
        label = str(raw.get("entity_group") or raw.get("entity") or "").upper()
        if not label or label.startswith("LABEL_"):
            return None
        # Strip BIO prefix if present (B- I- E- S-)
        if len(label) > 2 and label[1] == "-":
            label = label[2:]
        # Apply remap; DROP entries get filtered out.
        remapped = LABEL_REMAP.get(label, label)
        if remapped == "DROP":
            return None
        label = remapped
        try:
            start = int(raw["start"]) + offset
            end = int(raw["end"]) + offset
            score = float(raw.get("score", 1.0))
        except (KeyError, TypeError, ValueError):
            return None
        if end <= start:
            return None
        text = str(raw.get("word") or raw.get("text") or "").strip()
        return PIIEntity(label=label, text=text, score=score, start=start, end=end)

    @staticmethod
    def _post_filter(entities: list[PIIEntity], text: str) -> list[PIIEntity]:
        """Pipeline:
        1. Snap each entity to known syntactic patterns (CPF, CNPJ, EMAIL,
           PHONE, ZIP, DATE, CRM) to recover from token level fragmentation.
        2. Re slice text to the actual span, drop too short fragments.
        3. Sort, merge adjacent same label spans across simple punctuation.
        4. Validate CPF/CNPJ via Luhn; promote BR_DOC accordingly.
        5. Drop entities fully contained within larger entities (the model
           sometimes tags PERSON inside an email, which we want to suppress).
        """
        if not entities:
            return []

        snapped = [_snap_to_pattern(text, e) for e in entities if e.end > e.start]

        cleaned: list[PIIEntity] = []
        for e in snapped:
            slice_text = text[e.start : e.end]
            inner = slice_text.strip(".,-/:;()[]_ \t\n")
            alnum = sum(1 for c in inner if c.isalnum())
            if alnum < 2:
                continue
            cleaned.append(
                PIIEntity(
                    label=e.label,
                    text=slice_text,
                    score=e.score,
                    start=e.start,
                    end=e.end,
                )
            )

        cleaned.sort(key=lambda x: (x.start, -(x.end - x.start)))

        merged: list[PIIEntity] = []
        for e in cleaned:
            if merged:
                last = merged[-1]
                same = e.label == last.label
                if same and e.start <= last.end:
                    ne = max(last.end, e.end)
                    merged[-1] = PIIEntity(
                        label=last.label,
                        text=text[last.start : ne],
                        score=max(last.score, e.score),
                        start=last.start,
                        end=ne,
                    )
                    continue
                between = text[last.end : e.start]
                gap_punct_only = bool(between) and all(
                    c.isspace() or c in ".,-/:;()[]_" for c in between
                )
                # PERSON spans benefit from a wider, name aware merge: the
                # model often splits a full name across the FIRSTNAME and
                # LASTNAME tags with letters in between (e.g. 'Maria',
                # 'cida Pereira', 'Silva' for 'Maria Aparecida Pereira da
                # Silva'). Merge if the gap is purely Latin letters and
                # spaces and short enough that a newline would have broken
                # it on a real document.
                gap_is_name_filler = (
                    bool(between)
                    and "\n" not in between
                    and all(c.isalpha() or c.isspace() for c in between)
                )
                if same and (
                    (len(between) <= 3 and gap_punct_only)
                    or (e.label == "PERSON" and len(between) <= 12 and gap_is_name_filler)
                ):
                    ne = max(last.end, e.end)
                    merged[-1] = PIIEntity(
                        label=last.label,
                        text=text[last.start : ne],
                        score=max(last.score, e.score),
                        start=last.start,
                        end=ne,
                    )
                    continue
            merged.append(e)

        validated: list[PIIEntity] = []
        for e in merged:
            label = e.label.upper()
            st = e.text.strip(".,-/:;()[]_ \t\n")
            if label == "BR_DOC":
                if cpf_is_valid(st):
                    validated.append(_replace_label(e, "BR_CPF"))
                    continue
                if cnpj_is_valid(st):
                    validated.append(_replace_label(e, "BR_CNPJ"))
                    continue
                digits = sum(1 for c in st if c.isdigit())
                if digits >= 8:
                    validated.append(e)
                continue
            if label in {"BR_CPF", "CPF"} and not cpf_is_valid(st):
                continue
            if label in {"BR_CNPJ", "CNPJ"} and not cnpj_is_valid(st):
                continue
            validated.append(e)

        # Drop entities fully contained within strictly larger ones.
        validated.sort(key=lambda x: (x.start, -(x.end - x.start)))
        final: list[PIIEntity] = []
        for e in validated:
            contained = False
            for o in validated:
                if (o.start, o.end) == (e.start, e.end):
                    continue
                if o.start <= e.start and o.end >= e.end:
                    contained = True
                    break
            if not contained:
                final.append(e)
        return final

    @staticmethod
    def _mock_detect(text: str, threshold: float) -> list[PIIEntity]:
        """Heuristic detector used in mock mode.

        We use simple regexes to find common Brazilian PII so the rest of the
        pipeline can be smoke tested. This is NOT a substitute for the model.
        """
        patterns: list[tuple[str, str]] = [
            ("BR_CPF", r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
            ("BR_CNPJ", r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"),
            ("BR_RG", r"\b\d{1,2}\.\d{3}\.\d{3}-[\dXx]\b"),
            ("PHONE", r"\(\d{2}\)\s*\d{4,5}-\d{4}"),
            ("EMAIL", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
            ("DATE", r"\b\d{2}/\d{2}/\d{4}\b"),
            ("AGE", r"\b\d{1,3}\s*anos?\b"),
            ("CRM", r"CRM[\/\-]?[A-Z]{2}\s*\d{4,7}"),
        ]
        ents: list[PIIEntity] = []
        for label, pat in patterns:
            for m in re.finditer(pat, text, flags=re.IGNORECASE):
                ents.append(
                    PIIEntity(
                        label=label,
                        text=m.group(0),
                        score=0.97,
                        start=m.start(),
                        end=m.end(),
                    )
                )
        # Names: very rough heuristic, two or more capitalized tokens after
        # a known prefix. Good enough for the mock path only.
        for m in re.finditer(
            r"(?:Paciente|Medico|Dr\.?|Dra\.?)[:\s]+((?:[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+\s?){2,5})",
            text,
        ):
            grp = m.group(1).strip()
            start = m.start(1)
            ents.append(
                PIIEntity(
                    label="PERSON",
                    text=grp,
                    score=0.95,
                    start=start,
                    end=start + len(grp),
                )
            )
        # Address heuristic
        for m in re.finditer(
            r"Endereco[:\s]+([^\n]+)", text, flags=re.IGNORECASE
        ):
            grp = m.group(1).strip()
            start = m.start(1)
            ents.append(
                PIIEntity(
                    label="ADDRESS",
                    text=grp,
                    score=0.93,
                    start=start,
                    end=start + len(grp),
                )
            )
        ents = [e for e in ents if e.score >= threshold]
        return PIIEngine._post_filter(ents, text)


def _replace_label(e: PIIEntity, new_label: str) -> PIIEntity:
    return PIIEntity(label=new_label, text=e.text, score=e.score, start=e.start, end=e.end)


# Patterns used to snap a partial model span back to its full syntactic form.
# Each entry: (label_to_emit, regex, optional_validator).
_CPF_RE = re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}")
_CNPJ_RE = re.compile(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}")
_RG_RE = re.compile(r"\d{1,2}\.?\d{3}\.?\d{3}-?[\dXx]")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\(?\d{2}\)?\s*\d{4,5}-?\d{4}")
_ZIP_RE = re.compile(r"\d{5}-?\d{3}")
_DATE_RE = re.compile(r"\d{1,2}/\d{1,2}/\d{2,4}")
_CRM_RE = re.compile(r"CRM[\s/.-]*[A-Z]{2}\s*\d{4,7}")

# Per label snap window sizes (chars to look back / ahead from the model span).
# Wider for EMAIL because addresses can stretch 25+ chars.
_WINDOW_BY_LABEL: dict[str, tuple[int, int]] = {
    "EMAIL": (10, 60),
    "BR_DOC": (6, 16),
    "BR_CPF": (6, 16),
    "CPF": (6, 16),
    "BR_CNPJ": (6, 18),
    "CNPJ": (6, 18),
    "BR_RG": (6, 16),
    "RG": (6, 16),
    "PHONE": (6, 18),
    "PHONE_NUMBER": (6, 18),
    "ZIPCODE": (4, 10),
    "ZIP": (4, 10),
    "DATE": (4, 12),
    "DATE_OF_BIRTH": (4, 12),
    "DOB": (4, 12),
    "CRM": (6, 22),
}


def _snap_to_pattern(text: str, e: PIIEntity) -> PIIEntity:
    """If e's span overlaps a syntactically complete pattern (CPF, CNPJ,
    EMAIL, PHONE, ZIP, DATE, RG, CRM), extend the span to cover the full
    pattern. Used to recover from token level fragmentation in the model
    output. Window size is per label (emails can be much wider than docs).
    """
    label = e.label.upper()
    back, ahead = _WINDOW_BY_LABEL.get(label, (6, 14))
    win_start = max(0, e.start - back)
    win_end = min(len(text), e.end + ahead)
    window = text[win_start:win_end]

    candidates: list[tuple[str, re.Pattern[str], Any]] = []
    if label in {"BR_DOC", "BR_CPF", "CPF", "BR_CNPJ", "CNPJ", "ID"}:
        candidates = [
            ("BR_CNPJ", _CNPJ_RE, cnpj_is_valid),
            ("BR_CPF", _CPF_RE, cpf_is_valid),
            ("BR_RG", _RG_RE, None),
        ]
    elif label in {"BR_RG", "RG"}:
        candidates = [("BR_RG", _RG_RE, None)]
    elif label == "EMAIL":
        candidates = [("EMAIL", _EMAIL_RE, None)]
    elif label in {"PHONE", "PHONE_NUMBER"}:
        candidates = [("PHONE", _PHONE_RE, None)]
    elif label in {"ZIPCODE", "ZIP", "POSTAL_CODE"}:
        candidates = [("ZIPCODE", _ZIP_RE, None)]
    elif label in {"DATE", "DATE_OF_BIRTH", "DOB"}:
        candidates = [(label, _DATE_RE, None)]
    elif label == "CRM":
        candidates = [("CRM", _CRM_RE, None)]
    else:
        return e

    for new_label, pattern, validator in candidates:
        for m in pattern.finditer(window):
            cand = m.group()
            if validator is not None and not validator(cand):
                continue
            ns = win_start + m.start()
            ne = win_start + m.end()
            if ne > e.start and ns < e.end:
                return PIIEntity(
                    label=new_label,
                    text=cand,
                    score=e.score,
                    start=ns,
                    end=ne,
                )
    return e


_engine_singleton: PIIEngine | None = None


def get_engine() -> PIIEngine:
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = PIIEngine()
    return _engine_singleton

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
from dataclasses import dataclass, replace
from threading import Lock
from typing import Any

from . import patterns
from .config import Settings, get_settings
from .patterns import cnpj_is_valid, cns_is_valid, cpf_is_valid  # noqa: F401  reexport

logger = logging.getLogger(__name__)


@dataclass
class PIIEntity:
    label: str
    text: str
    score: float
    start: int
    end: int
    # Metadados internos do pipeline (nao expostos no contrato da API):
    # origin: "model" | "regex" | "mock"; validated: digito verificador
    # aprovado (bypass permanente de threshold); strong: snap com evidencia
    # real (formatacao, keyword ou validador).
    origin: str = "model"
    validated: bool = False
    strong: bool = False


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
    # O modelo usa CREDITCARD/BANKACCOUNT para fragmentos de identificadores
    # numericos longos (CNS, carteirinha); remapear para ID permite o snap
    # de sequencia de digitos reancorar o span completo.
    "CREDITCARD": "ID",
    "BANKACCOUNT": "ID",
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


# Validadores de CPF/CNPJ/CNS vivem em patterns.py e sao reexportados acima
# para manter os nomes publicos existentes deste modulo.

_digits = patterns.digits


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

        # Coleta com piso baixo, NAO com o threshold do usuario: o corte por
        # confianca acontece no fim do pipeline, depois de snap e validacao.
        # Um fragmento a 0.2 pode virar um CPF valido apos o snap; corta-lo
        # aqui seria fail-open.
        floor = self.settings.pii_score_floor
        chunks = self._chunk_text(text, self.settings.pii_max_input_chars)
        model_entities: list[PIIEntity] = []
        for offset, chunk in chunks:
            with self._lock:
                results = self._pipe(chunk)
            for r in results or []:
                ent = self._normalize_hf_entity(r, offset)
                if ent is None or ent.score < floor:
                    continue
                model_entities.append(ent)
        return self._pipeline(model_entities, text, threshold)

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
    def _pipeline(
        model_entities: list[PIIEntity], text: str, threshold: float
    ) -> list[PIIEntity]:
        """Pipeline fail-closed, na ordem:

        1. varredura regex-first do texto completo (independe do modelo);
        2. snap dos spans do modelo aos padroes do registro (strong/weak);
        3. re-slice do texto real e descarte de fragmentos curtos;
        4. dedup de spans identicos (modelo + regex acham o mesmo CPF);
        5. validacao de digito verificador (seta validated, promove BR_DOC);
        6. merge estrutural ANTES do threshold (fragmento fraco de nome pega
           carona no vizinho forte via score max);
        7. threshold: so poda deteccao de modelo sem validacao e sem snap
           forte; entidade validada sobrevive SEMPRE, em qualquer score;
        8. containment e disjuncao final (spans estritamente disjuntos).
        """
        regex_entities = patterns.scan_text(text)

        snapped: list[PIIEntity] = []
        for e in model_entities:
            if e.end <= e.start:
                continue
            se, strong = patterns.snap_to_spec(text, e)
            snapped.append(replace(se, strong=strong or se.strong))

        cleaned: list[PIIEntity] = []
        for e in snapped + regex_entities:
            slice_text = text[e.start : e.end]
            inner = slice_text.strip(".,-/:;()[]_ \t\n")
            if sum(1 for c in inner if c.isalnum()) < 2:
                continue
            cleaned.append(replace(e, text=slice_text))

        deduped = patterns.dedupe_exact(cleaned)
        validated = PIIEngine._validate(deduped)
        merged = PIIEngine._merge_adjacent(validated, text)

        kept = [
            e
            for e in merged
            if e.validated
            or e.origin in ("regex", "mock")
            or e.strong
            or e.score >= threshold
        ]
        return patterns.finalize_disjoint(kept, text)

    @staticmethod
    def _validate(entities: list[PIIEntity]) -> list[PIIEntity]:
        """Digito verificador: promove BR_DOC e marca validated.

        Checksum reprovado NAO descarta a entidade: um CPF real com um digito
        corrompido pelo OCR continua sendo PII na imagem. Ele apenas perde o
        bypass (vira BR_DOC sujeito ao threshold pelo score do modelo).
        """
        out: list[PIIEntity] = []
        for e in entities:
            label = e.label.upper()
            st = e.text.strip(".,-/:;()[]_ \t\n")
            if label == "BR_DOC":
                if cpf_is_valid(st):
                    out.append(replace(e, label="BR_CPF", validated=True))
                    continue
                if cnpj_is_valid(st):
                    out.append(replace(e, label="BR_CNPJ", validated=True))
                    continue
                if sum(1 for c in st if c.isdigit()) >= 8:
                    out.append(e)
                continue
            if label in {"BR_CPF", "CPF"}:
                if cpf_is_valid(st):
                    out.append(replace(e, validated=True))
                else:
                    out.append(replace(e, label="BR_DOC"))
                continue
            if label in {"BR_CNPJ", "CNPJ"}:
                if cnpj_is_valid(st):
                    out.append(replace(e, validated=True))
                else:
                    out.append(replace(e, label="BR_DOC"))
                continue
            if label == "CNS" and cns_is_valid(st):
                out.append(replace(e, validated=True))
                continue
            out.append(e)
        return out

    @staticmethod
    def _merge_adjacent(entities: list[PIIEntity], text: str) -> list[PIIEntity]:
        """Merge de spans adjacentes de mesmo label.

        Gap de ate 3 chars de pontuacao, ou ate 12 chars de letras/espacos
        para PERSON (o modelo fatia nomes compostos). O merge preserva o
        score maximo e os flags mais fortes dos membros.
        """
        entities = sorted(entities, key=lambda x: (x.start, -(x.end - x.start)))
        merged: list[PIIEntity] = []
        for e in entities:
            if merged:
                last = merged[-1]
                same = e.label == last.label
                fuse = False
                if same and e.start <= last.end:
                    fuse = True
                elif same:
                    between = text[last.end : e.start]
                    gap_punct_only = bool(between) and all(
                        c.isspace() or c in ".,-/:;()[]_" for c in between
                    )
                    gap_is_name_filler = (
                        bool(between)
                        and "\n" not in between
                        and all(c.isalpha() or c.isspace() for c in between)
                    )
                    fuse = (len(between) <= 3 and gap_punct_only) or (
                        e.label == "PERSON"
                        and len(between) <= 12
                        and gap_is_name_filler
                    )
                if fuse:
                    ne = max(last.end, e.end)
                    merged[-1] = replace(
                        last,
                        text=text[last.start : ne],
                        score=max(last.score, e.score),
                        end=ne,
                        validated=last.validated or e.validated,
                        strong=last.strong or e.strong,
                    )
                    continue
            merged.append(e)
        return merged

    @staticmethod
    def _mock_detect(text: str, threshold: float) -> list[PIIEntity]:
        """Detector heuristico do modo mock.

        Os padroes sintaticos vem do MESMO registro (patterns.REGISTRY) usado
        no modo real, via _pipeline; aqui entram apenas as heuristicas de
        nome e endereco que no modo real sao papel do modelo.
        """
        ents: list[PIIEntity] = []
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
                    origin="mock",
                )
            )
        for m in re.finditer(r"Endereco[:\s]+([^\n]+)", text, flags=re.IGNORECASE):
            grp = m.group(1).strip()
            start = m.start(1)
            ents.append(
                PIIEntity(
                    label="ADDRESS",
                    text=grp,
                    score=0.93,
                    start=start,
                    end=start + len(grp),
                    origin="mock",
                )
            )
        return PIIEngine._pipeline(ents, text, threshold)


_engine_singleton: PIIEngine | None = None


def get_engine() -> PIIEngine:
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = PIIEngine()
    return _engine_singleton

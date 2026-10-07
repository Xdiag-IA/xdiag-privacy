import os
from dataclasses import replace
from pathlib import Path
from app.pii import PIIEngine
from app.config import Settings

ROOT = Path(__file__).resolve().parents[2]


class LocalEngine(PIIEngine):
    def _load_pipeline(self):
        # Carrega exclusivamente os arquivos previamente baixados.
        import torch
        from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
        torch.set_num_threads(4)
        folder = Path(os.environ.get('XDIAG_BATCH_MODEL_DIR', str(ROOT / 'modelos-lote' / 'pii')))
        tokenizer = AutoTokenizer.from_pretrained(folder, local_files_only=True)
        model = AutoModelForTokenClassification.from_pretrained(folder, local_files_only=True)
        self._backend = 'transformers.pipeline.local'
        return pipeline('token-classification', model=model, tokenizer=tokenizer,
                        aggregation_strategy='simple', device=-1)

    def _chunk_text(self, text, max_chars):
        # Limite em tokens com sobreposicao: evita truncamento por caracteres.
        offsets = self._pipe.tokenizer(text, add_special_tokens=False,
                                      return_offsets_mapping=True, truncation=False)['offset_mapping']
        width = min(1024, self._pipe.tokenizer.model_max_length - 2)
        if len(offsets) <= width:
            return [(0, text)]
        chunks = []
        for index in range(0, len(offsets), width - 128):
            window = offsets[index:index + width]
            start, end = window[0][0], window[-1][1]
            chunks.append((start, text[start:end]))
            if index + width >= len(offsets):
                break
        return chunks

    def _caps_retry(self, text, found, floor):
        entities = []
        for offset, chunk in self._chunk_text(text, 0):
            local = [replace(e, start=e.start-offset, end=e.end-offset) for e in found
                     if offset <= e.start < e.end <= offset + len(chunk)]
            entities.extend(replace(e, start=e.start+offset, end=e.end+offset)
                            for e in super()._caps_retry(chunk, local, floor))
        return entities


def create_engine():
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    engine = LocalEngine(Settings(pii_engine='model', pii_llm='', mock_mode=False, caps_retry=True))
    engine.warmup()
    return engine

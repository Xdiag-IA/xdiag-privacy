"""Execute uma vez com internet, antes de colocar documentos reais na entrada."""
from pathlib import Path
from huggingface_hub import snapshot_download

root = Path(__file__).resolve().parents[2]
snapshot_download('OpenMed/OpenMed-PII-Portuguese-SnowflakeMed-Large-568M-v1',
                  revision='73e90e3ccb319965a723c76996450ed01ac89f22',
                  local_dir=root / 'modelos-lote' / 'pii',
                  allow_patterns=['config.json', 'tokenizer*', 'special_tokens_map.json',
                                  'model.safetensors', 'sentencepiece*', 'spm*'])
print('Modelo local preparado.')

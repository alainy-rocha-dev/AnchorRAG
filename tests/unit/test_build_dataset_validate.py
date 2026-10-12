import json
import sys
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from eval.build_dataset import cmd_validate

def test_validate_invalid_dataset(tmp_path):
    chunks_file = tmp_path / "chunks.jsonl"
    v1_file = tmp_path / "v1.jsonl"
    
    # Valid chunk
    chunks_file.write_text(json.dumps({"chunk_id": "norma_1:art1", "norma": "norma_1", "texto": "artigo 1"}) + "\n", encoding="utf-8")
    
    # Invalid v1 items (invalid category, non-existent chunk_id)
    invalid_item = {
        "id": "abc1234567",
        "pergunta": "Pergunta de teste?",
        "categoria": "categoria_inexistente",
        "chunk_ids_relevantes": ["chunk_fantasma:art99"],
        "resposta_ouro": "Resposta",
        "revisado": True
    }
    v1_file.write_text(json.dumps(invalid_item) + "\n", encoding="utf-8")
    
    class Args:
        chunks = str(chunks_file)
        v1 = str(v1_file)
    
    with pytest.raises(SystemExit) as exc_info:
        cmd_validate(Args())
    
    assert exc_info.value.code == 1

def test_validate_valid_dataset_exit_zero(tmp_path):
    chunks_file = tmp_path / "chunks.jsonl"
    v1_file = tmp_path / "v1.jsonl"
    
    chunks_file.write_text(json.dumps({"chunk_id": "norma_1:art1", "norma": "norma_1", "texto": "artigo 1"}) + "\n", encoding="utf-8")
    
    valid_item = {
        "id": "abc1234567",
        "pergunta": "Pergunta de teste sobre regulamento?",
        "categoria": "respondivel",
        "chunk_ids_relevantes": ["norma_1:art1"],
        "resposta_ouro": "Resposta de teste",
        "revisado": True
    }
    v1_file.write_text(json.dumps(valid_item) + "\n", encoding="utf-8")
    
    class Args:
        chunks = str(chunks_file)
        v1 = str(v1_file)
    
    with pytest.raises(SystemExit) as exc_info:
        cmd_validate(Args())
    
    # In validate, if there are no errors, it exits with 0
    assert exc_info.value.code == 0

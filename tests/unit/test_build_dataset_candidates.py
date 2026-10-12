import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from eval.build_dataset import cmd_candidates


def test_candidates_max_por_norma_limit_and_interleaving(tmp_path):
    chunks_file = tmp_path / "chunks.jsonl"
    cand_file = tmp_path / "candidates.jsonl"
    v1_file = tmp_path / "v1.jsonl"
    rej_file = tmp_path / "rejected.jsonl"

    chunks = []
    # Norma grande: 40 chunks
    for i in range(1, 41):
        chunks.append({
            "chunk_id": f"norma_grande:art{i}",
            "norma": "norma_grande",
            "artigo": str(i),
            "texto": f"Art. {i}. Texto suficiente com mais de duzentos caracteres para passar no filtro de tamanho mínimo de usables do candidate. " * 3,
            "n_chars": 350
        })
    # Norma pequena 1: 6 chunks
    for i in range(1, 7):
        chunks.append({
            "chunk_id": f"norma_p1:art{i}",
            "norma": "norma_p1",
            "artigo": str(i),
            "texto": f"Art. {i}. Texto suficiente com mais de duzentos caracteres para passar no filtro de tamanho mínimo de usables do candidate. " * 3,
            "n_chars": 350
        })
    # Norma pequena 2: 6 chunks
    for i in range(1, 7):
        chunks.append({
            "chunk_id": f"norma_p2:art{i}",
            "norma": "norma_p2",
            "artigo": str(i),
            "texto": f"Art. {i}. Texto suficiente com mais de duzentos caracteres para passar no filtro de tamanho mínimo de usables do candidate. " * 3,
            "n_chars": 350
        })

    with chunks_file.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    class Args:
        categoria = "respondivel"
        n = 30
        seed = 42
        chunks = str(chunks_file)
        out = str(cand_file)
        v1 = str(v1_file)
        rej = str(rej_file)
        max_por_norma = 5

    counter = 0
    def mock_llm_json(prompt):
        nonlocal counter
        counter += 1
        return {
            "pergunta": f"Pergunta mock unica {counter} sobre trecho de norma",
            "resposta_ouro": f"Resposta ouro mock {counter}"
        }

    with patch("eval.build_dataset.llm_json", side_effect=mock_llm_json):
        cmd_candidates(Args())

    assert cand_file.exists()
    candidates = [json.loads(line) for line in cand_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    # Count unique chunks used per norm
    used_chunks_per_norm = {}
    for item in candidates:
        for cid in item["chunk_ids_relevantes"]:
            norma = cid.split(":")[0]
            used_chunks_per_norm.setdefault(norma, set()).add(cid)

    # Verify max_por_norma limit (5) is respected for all norms
    for norma, used_set in used_chunks_per_norm.items():
        assert len(used_set) <= 5, f"Norma {norma} usou {len(used_set)} chunks, excedendo o limite de 5!"

    # Verify norma_grande used exactly 5 chunks (not 30)
    assert len(used_chunks_per_norm.get("norma_grande", set())) == 5


def test_candidates_termos_fora_do_trecho_marcados(tmp_path):
    chunks_file = tmp_path / "chunks.jsonl"
    cand_file = tmp_path / "candidates.jsonl"
    v1_file = tmp_path / "v1.jsonl"
    rej_file = tmp_path / "rejected.jsonl"

    chunk_1 = (
        "Art. 54. A estrutura unificada para gerenciamento de capital do conglomerado prudencial, "
        "de que trata o art. 2º, § 2º, deve avaliar os possíveis impactos no capital e na liquidez "
        "do conglomerado prudencial oriundos dos riscos de que trata o art. 6º."
    )
    chunk_3 = (
        "Art. 9º É vedado a membro da equipe de auditoria interna:\n"
        "I - envolver-se no desenvolvimento e implementação de medidas específicas relativas aos controles internos; e\n"
        "II - atuar na auditoria de atividades pelas quais tenham tido responsabilidade, antes de decorridos, no mínimo, doze meses."
    )
    chunks = [
        {
            "chunk_id": "res_4557:art54",
            "norma": "res_4557",
            "artigo": "54",
            "texto": chunk_1,
            "n_chars": len(chunk_1),
        },
        {
            "chunk_id": "res_cmn_4879:art9",
            "norma": "res_cmn_4879",
            "artigo": "9",
            "texto": chunk_3,
            "n_chars": len(chunk_3),
        },
        {
            "chunk_id": "res_4557:art55",
            "norma": "res_4557",
            "artigo": "55",
            "texto": "Art. 55. As avaliacoes de risco de mercado e de credito devem ser realizadas periodicamente pela instituicao, considerando a exposicao a riscos de mercado e de credito em suas operacoes de financiamento e investimento.",
            "n_chars": 300,
        },
        {
            "chunk_id": "res_4557:art56",
            "norma": "res_4557",
            "artigo": "56",
            "texto": "Art. 56. O conglomerado deve manter registro atualizado de seus riscos de mercado e de credito, disponibilizando as informacoes aos nivel de seguranca adequado.",
            "n_chars": 300,
        },
        {
            "chunk_id": "res_4557:art57",
            "norma": "res_4557",
            "artigo": "57",
            "texto": "Art. 57. A analise de mercado e de credito e parte integrante do gerenciamento de capital do conglomerado prudencial, exigindo controles adequados de seguranca.",
            "n_chars": 300,
        },
        {
            "chunk_id": "res_4557:art58",
            "norma": "res_4557",
            "artigo": "58",
            "texto": "Art. 58. Dos riscos de mercado e de credito, o conglomerado deve identificar os de maior impacto e adotar medidas corretivas proporcionais.",
            "n_chars": 300,
        },
        {
            "chunk_id": "res_4557:art59",
            "norma": "res_4557",
            "artigo": "59",
            "texto": "Art. 59. O comite de risco deve monitorar continuamente os riscos de mercado e de credito, assegurando conformidade com as normas do Banco Central.",
            "n_chars": 300,
        },
    ]
    with chunks_file.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    class Args:
        categoria = "respondivel"
        n = 2
        seed = 42
        chunks = str(chunks_file)
        out = str(cand_file)
        v1 = str(v1_file)
        rej = str(rej_file)
        max_por_norma = 15

    def mock_llm_json(prompt):
        if "res_4557:art54" in prompt:
            return {
                "pergunta": "Como a estrutura de gerenciamento de capital do conglomerado prudencial deve se comportar em relacao aos riscos de mercado e credito?",
                "resposta_ouro": "Deve avaliar os possiveis impactos no capital e na liquidez do conglomerado prudencial oriundos dos riscos de mercado e credito."
            }
        else:
            return {
                "pergunta": "A auditoria interna pode avaliar suas proprias atividades recentes?",
                "resposta_ouro": "Nao, membro da equipe de auditoria interna nao pode atuar na auditoria de atividades nas quais tenham tido responsabilidade nos ultimos doze meses."
            }

    with patch("eval.build_dataset.llm_json", side_effect=mock_llm_json):
        cmd_candidates(Args())

    assert cand_file.exists()
    candidates = [json.loads(line) for line in cand_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(candidates) == 2

    cand_map = {c["chunk_ids_relevantes"][0]: c for c in candidates}

    # Item 1 (res_4557:art54): inventou "mercado" e "credito" -> DEVE GERAR ALERTA
    item_1 = cand_map["res_4557:art54"]
    assert "termos_fora_resposta" in item_1
    assert "termos_fora_pergunta" in item_1
    assert "mercado" in item_1["termos_fora_resposta"]
    assert "credito" in item_1["termos_fora_resposta"]
    assert len(item_1["termos_fora_resposta"]) > 0  # Dispara alerta

    # Item 3 (res_cmn_4879:art9): resposta fiel, pergunta parafraseada -> NÃO PODE GERAR ALERTA
    item_3 = cand_map["res_cmn_4879:art9"]
    assert "termos_fora_resposta" in item_3
    assert "termos_fora_pergunta" in item_3
    assert len(item_3["termos_fora_resposta"]) == 0  # NÃO dispara alerta na resposta
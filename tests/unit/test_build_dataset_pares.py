"""multi_trecho com pares escolhidos a mao (--pares) e travas do review."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from eval import build_dataset as bd  # noqa: E402

IDS = {
    "res_x:art1", "res_x:art2", "res_x:art3",
    "res_x:art15-p1", "res_x:art15-p2", "res_x:art71", "res_x:art71-A",
}


def _arquivo(tmp_path, texto):
    f = tmp_path / "pares.txt"
    f.write_text(texto, encoding="utf-8")
    return f


def test_ler_pares_formatos_e_avisos(tmp_path):
    f = _arquivo(tmp_path, (
        "# comentario\n"
        "\n"
        "- res_x:art1 + res_x:art2 | foco do par\n"
        "res_x:art71 + art2 + art3\n"
        "res_x:art1 + art15 | parte dividida\n"
        "res_x:art1 + res_x:art99 | inexistente\n"
        "res_x:art1 + arts. 15 e 16 | texto livre\n"
        "res_x:art1 | um so\n"
        "res_x:art2 + res_x:art1 | duplicado em outra ordem\n"
    ))
    pares, avisos = bd.ler_pares(f, IDS)
    assert pares == [
        (["res_x:art1", "res_x:art2"], "foco do par"),
        (["res_x:art71", "res_x:art2", "res_x:art3"], ""),
        (["res_x:art1", "res_x:art15-p1", "res_x:art15-p2"], "parte dividida"),
    ]
    assert len(avisos) == 3
    assert any("art99" in a for a in avisos)


def test_ler_pares_nao_confunde_artigo_com_letra(tmp_path):
    # art71 existe e art71-A e outro artigo: nao pode ser incluido como "parte"
    f = _arquivo(tmp_path, "res_x:art71 + res_x:art1\n")
    pares, _ = bd.ler_pares(f, IDS)
    assert pares == [(["res_x:art71", "res_x:art1"], "")]


def test_prompt_multi_com_tres_trechos_e_foco():
    p = bd.montar_prompt_multi("Tema", [("a:1", "TA"), ("a:2", "TB"), ("a:3", "TC")], "meu foco")
    assert "[A] (a:1)" in p and "[B] (a:2)" in p and "[C] (a:3)" in p
    assert "3 trechos" in p and "Foco sugerido pela revisora: meu foco" in p


def _corpus(tmp_path):
    chunks = [{"chunk_id": f"res_x:art{i}", "norma": "res_x", "artigo": str(i),
               "texto": f"Art. {i}. Texto do artigo {i}.", "n_chars": 30} for i in (1, 2, 3)]
    f = tmp_path / "chunks.jsonl"
    f.write_text("".join(json.dumps(c) + "\n" for c in chunks), encoding="utf-8")
    return f


def _args(tmp_path, pares):
    return SimpleNamespace(categoria="multi_trecho", n=10, seed=1, chunks=str(_corpus(tmp_path)),
                           temas=str(tmp_path / "nao_existe.json"), out=str(tmp_path / "cand.jsonl"),
                           v1=str(tmp_path / "v1.jsonl"), rej=str(tmp_path / "rej.jsonl"),
                           max_por_norma=1, pares=str(pares))


def test_candidates_usa_pares_manuais_e_nao_repete(tmp_path):
    pares = _arquivo(tmp_path, "res_x:art1 + res_x:art2 | foco A\nres_x:art2 + art3\n")
    prompts = []

    def fake(prompt):
        prompts.append(prompt)
        return {"pergunta": f"Pergunta {len(prompts)}?", "resposta_ouro": "Resposta."}

    with patch.object(bd, "llm_json", side_effect=fake):
        bd.cmd_candidates(_args(tmp_path, pares))
        bd.cmd_candidates(_args(tmp_path, pares))  # segunda rodada nao gera de novo

    itens = [json.loads(l) for l in (tmp_path / "cand.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [i["chunk_ids_relevantes"] for i in itens] == [["res_x:art1", "res_x:art2"],
                                                         ["res_x:art2", "res_x:art3"]]
    assert all(i["categoria"] == "multi_trecho" and i["par_manual"] for i in itens)
    assert "Foco sugerido pela revisora: foco A" in prompts[0]
    # max_por_norma=1 nao bloqueia pares manuais
    assert len(prompts) == 2


def test_review_exige_terminal(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    a = SimpleNamespace(categoria=None, chunks=str(_corpus(tmp_path)), cand=str(tmp_path / "c.jsonl"),
                        v1=str(tmp_path / "v1.jsonl"), rej=str(tmp_path / "r.jsonl"))
    with pytest.raises(SystemExit) as e:
        bd.cmd_review(a)
    assert e.value.code == "o review exige uma pessoa no terminal"


def test_review_recusa_chunk_id_inexistente_na_edicao(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    cand = tmp_path / "c.jsonl"
    cand.write_text(json.dumps({"id": "x1", "pergunta": "P?", "resposta_ouro": "R.",
                                "chunk_ids_relevantes": ["res_x:art1"],
                                "categoria": "respondivel"}) + "\n", encoding="utf-8")
    respostas = iter(["e", "", "", "nota colada no lugar errado", "res_x:art2", "minha nota"])
    monkeypatch.setattr("builtins.input", lambda *_: next(respostas))
    a = SimpleNamespace(categoria=None, chunks=str(_corpus(tmp_path)), cand=str(cand),
                        v1=str(tmp_path / "v1.jsonl"), rej=str(tmp_path / "r.jsonl"))
    bd.cmd_review(a)
    item = json.loads((tmp_path / "v1.jsonl").read_text(encoding="utf-8"))
    assert item["chunk_ids_relevantes"] == ["res_x:art2"]
    assert item["nota_edicao"] == "minha nota"
    assert "chunk_id inexistente" in capsys.readouterr().out


def test_review_mostra_texto_completo(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    longo = "Art. 1. " + "palavra " * 400 + "FIM_DO_TEXTO"
    chunks = tmp_path / "chunks.jsonl"
    chunks.write_text(json.dumps({"chunk_id": "res_x:art1", "norma": "res_x", "artigo": "1",
                                  "texto": longo, "n_chars": len(longo)}) + "\n", encoding="utf-8")
    cand = tmp_path / "c.jsonl"
    cand.write_text(json.dumps({"id": "x1", "pergunta": "P?", "resposta_ouro": "R.",
                                "chunk_ids_relevantes": ["res_x:art1"],
                                "categoria": "respondivel"}) + "\n", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda *_: "q")
    a = SimpleNamespace(categoria=None, chunks=str(chunks), cand=str(cand),
                        v1=str(tmp_path / "v1.jsonl"), rej=str(tmp_path / "r.jsonl"))
    bd.cmd_review(a)
    assert "FIM_DO_TEXTO" in capsys.readouterr().out

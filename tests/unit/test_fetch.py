"""fetch e ingest: baixa só normas vigentes, registra no SOURCES.md, não duplica e limpa revogados."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

_spec = importlib.util.spec_from_file_location(
    "build_dataset", Path(__file__).resolve().parents[2] / "eval" / "build_dataset.py"
)
bd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bd)


def _texto(n_artigos: int) -> str:
    arts = "".join(
        f"<p>Art. {i}º  Dispositivo {i} com texto suficiente para virar um chunk utilizável.</p>"
        for i in range(1, n_artigos + 1))
    return ("<div><p>RESOLUÇÃO CMN Nº 4.893</p>"
            "<p><s><span style='color:red'>Art. 1º Redação antiga riscada.</span></s></p>"
            + arts + "</div>")


RESPOSTAS = {
    ("Resolução CMN", "4893"): {"conteudo": [{
        "Titulo": "Resolução CMN N° 4.893", "Data": "2021-02-26T17:06:00Z",
        "VersaoNormativo": 3.0, "Revogado": False, "Cancelado": False,
        "Atualizacoes": "Resolução CMN nº 5.117/2024 - Alteração;#"
                        "Resolução CMN nº 5.274/2025 - Nova redação;#",
        "Texto": _texto(20)}]},
    ("Resolução CMN", "4658"): {"conteudo": [{
        "Titulo": "Resolução CMN N° 4.658", "Revogado": True, "Cancelado": False,
        "Texto": _texto(20)}]},
    ("Resolução BCB", "7"): {"conteudo": [{
        "Titulo": "Resolução BCB N° 7", "Data": "2020-08-01T00:00:00Z",
        "VersaoNormativo": 1.0, "Revogado": False, "Cancelado": False,
        "Atualizacoes": None, "Texto": _texto(4)}]},
    ("Circular", "9999"): {"conteudo": []},
}


@pytest.fixture
def api(monkeypatch):
    chamadas = []

    def falso(url, params):
        chamadas.append(params)
        chave = (params["p1"], params["p2"])
        if chave == ("Resolução CMN", "1"):
            raise OSError("timeout simulado")
        return RESPOSTAS[chave]

    monkeypatch.setattr(bd, "_http_get_json", falso)
    return chamadas


def _rodar(tmp_path, linhas, **extra):
    lista = tmp_path / "normas.txt"
    lista.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    args = dict(lista=str(lista), raw=str(tmp_path / "raw"),
                sources=str(tmp_path / "SOURCES.md"), verificar=False, forcar=False)
    args.update(extra)
    bd.cmd_fetch(SimpleNamespace(**args))
    return tmp_path / "raw", tmp_path / "SOURCES.md"


def test_baixa_vigente_e_registra_fonte(tmp_path, api, capsys):
    raw, sources = _rodar(tmp_path, ["# comentário", "", "Resolução CMN;4893"])
    arq = raw / "res_cmn_4893.html"
    assert arq.exists()
    linhas = sources.read_text(encoding="utf-8").splitlines()
    assert linhas[0].startswith("| arquivo |")
    assert len(linhas) == 3
    assert "Resolução CMN N° 4.893/2021" in linhas[2]
    assert "v3; última: Resolução CMN nº 5.274/2025" in linhas[2]
    assert "tipo=Resolução CMN&numero=4893" in linhas[2]
    assert "VIGENTE" in capsys.readouterr().out


def test_arquivo_baixado_passa_no_ingest_sem_redacao_riscada(tmp_path, api):
    raw, _ = _rodar(tmp_path, ["Resolução CMN;4893"])
    out = tmp_path / "chunks.jsonl"
    bd.cmd_ingest(SimpleNamespace(raw=str(raw), out=str(out), max_chars=2500))
    textos = out.read_text(encoding="utf-8")
    assert "Redação antiga riscada" not in textos
    assert textos.count('"res_cmn_4893:art1"') == 1
    assert len(textos.splitlines()) == 20


def test_revogado_nao_achado_e_erro_nao_salvam(tmp_path, api, capsys):
    raw, sources = _rodar(tmp_path, ["Resolução CMN;4658", "Circular;9999", "Resolução CMN;1"])
    assert not raw.exists() or not any(raw.iterdir())
    assert not sources.exists()
    saida = capsys.readouterr().out
    assert "REVOGADO" in saida and "NÃO ACHADO" in saida and "ERRO" in saida
    assert "Revise a lista" in saida


def test_verificar_nao_salva_nada(tmp_path, api, capsys):
    raw, sources = _rodar(tmp_path, ["Resolução CMN;4893"], verificar=True)
    assert not raw.exists()
    assert not sources.exists()
    saida = capsys.readouterr().out
    assert "VIGENTE" in saida and "20" in saida


def test_avisa_fora_da_faixa_de_artigos(tmp_path, api, capsys):
    _rodar(tmp_path, ["Resolução BCB;7"], verificar=True)
    assert "fora da faixa" in capsys.readouterr().out


def test_rodar_de_novo_nao_duplica_nem_sobrescreve(tmp_path, api, capsys):
    raw, sources = _rodar(tmp_path, ["Resolução CMN;4893"])
    arq = raw / "res_cmn_4893.html"
    arq.write_text("editado à mão", encoding="utf-8")
    _rodar(tmp_path, ["Resolução CMN;4893"])
    assert arq.read_text(encoding="utf-8") == "editado à mão"
    assert "já existe" in capsys.readouterr().out
    _rodar(tmp_path, ["Resolução CMN;4893"], forcar=True)
    assert arq.read_text(encoding="utf-8") != "editado à mão"
    assert sources.read_text(encoding="utf-8").count("res_cmn_4893.html") == 1


def test_lista_com_formato_errado_para_com_mensagem(tmp_path):
    lista = tmp_path / "normas.txt"
    lista.write_text("Resolução CMN 4893\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="formato esperado"):
        bd.ler_lista(lista)


def test_reinicio_numeracao_gera_prefixo_anexo(tmp_path):
    texto = (
        "Art. 11. Texto do artigo onze.\n"
        "Art. 12. Texto do artigo doze.\n"
        "Art. 1º Texto do regulamento anexo um.\n"
        "Art. 2º Texto do regulamento anexo dois.\n"
    )
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "res_teste.html").write_text(texto, encoding="utf-8")
    out = tmp_path / "chunks.jsonl"
    bd.cmd_ingest(SimpleNamespace(raw=str(raw), out=str(out), max_chars=2500))
    linhas = [line for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    cids = [eval(l)["chunk_id"] for l in linhas]
    assert cids == [
        "res_teste:art11",
        "res_teste:art12",
        "res_teste:anexo1-art1",
        "res_teste:anexo1-art2",
    ]


def test_artigos_com_letras_nao_abrem_anexo(tmp_path):
    texto = (
        "Art. 3º Texto do artigo 3.\n"
        "Art. 3º-A Texto do artigo 3-A.\n"
        "Art. 4º Texto do artigo 4.\n"
    )
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "res_teste.html").write_text(texto, encoding="utf-8")
    out = tmp_path / "chunks.jsonl"
    bd.cmd_ingest(SimpleNamespace(raw=str(raw), out=str(out), max_chars=2500))
    linhas = [line for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    cids = [eval(l)["chunk_id"] for l in linhas]
    assert cids == [
        "res_teste:art3",
        "res_teste:art3-A",
        "res_teste:art4",
    ]


def test_artigo_totalmente_revogado_descartado(tmp_path):
    texto = (
        "Art. 1º Texto vigente.\n"
        "Art. 2º (Revogado pela Resolução BCB nº 494, de 5/9/2025.)\n"
        "Art. 3º Outro vigente.\n"
    )
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "res_teste.html").write_text(texto, encoding="utf-8")
    out = tmp_path / "chunks.jsonl"
    bd.cmd_ingest(SimpleNamespace(raw=str(raw), out=str(out), max_chars=2500))
    linhas = [line for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    cids = [eval(l)["chunk_id"] for l in linhas]
    assert cids == ["res_teste:art1", "res_teste:art3"]


def test_artigo_com_inciso_revogado_mantido_e_limpo(tmp_path):
    texto = (
        "Art. 25. As instituições devem observar:\n"
        "I - (Revogado pela Resolução nº 155.)\n"
        "II - a cobrança de tarifas de serviços;\n"
        "§ 1º (Revogado pelo ato X.)\n"
        "§ 2º Parágrafo que segue vigente.\n"
    )
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "res_teste.html").write_text(texto, encoding="utf-8")
    out = tmp_path / "chunks.jsonl"
    bd.cmd_ingest(SimpleNamespace(raw=str(raw), out=str(out), max_chars=2500))
    linhas = [line for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(linhas) == 1
    chunk = eval(linhas[0])
    assert chunk["chunk_id"] == "res_teste:art25"
    assert "I - (Revogado" not in chunk["texto"]
    assert "§ 1º (Revogado" not in chunk["texto"]
    assert "II - a cobrança de tarifas" in chunk["texto"]
    assert "§ 2º Parágrafo que segue vigente." in chunk["texto"]


def test_duplicata_forcada_aborta_ingest(tmp_path, monkeypatch):
    texto = "Art. 1º Artigo 1.\n"
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "res_teste.html").write_text(texto, encoding="utf-8")
    out = tmp_path / "chunks.jsonl"
    chaves = [(1, ""), (2, "")]
    monkeypatch.setattr(bd, "split_artigos", lambda t: [("1", "Artigo 1", "Art. 1º Artigo 1"), ("1", "Artigo 1", "Art. 1º Artigo 1")])
    monkeypatch.setattr(bd, "chave_artigo", lambda r: chaves.pop(0))
    with pytest.raises(SystemExit, match="chunk_id.*duplicado"):
        bd.cmd_ingest(SimpleNamespace(raw=str(raw), out=str(out), max_chars=2500))


def test_resposta_ouro_lista_convertida_para_texto(tmp_path, monkeypatch):
    """Testa se lista é convertida em string com quebra de linha ao salvar candidatas."""
    candidatas_out = tmp_path / "candidates.jsonl"
    chunks_path = tmp_path / "chunks.jsonl"
    chunks_path.write_text(
        '{"chunk_id": "norma:art1", "norma": "norma", "artigo": "1", "texto": "' + ('x' * 300) + '", "n_chars": 300}\n',
        encoding="utf-8"
    )
    monkeypatch.setattr(bd, "llm_json", lambda prompt: {"pergunta": "Pergunta teste?", "resposta_ouro": ["Item 1", "Item 2"]})
    args = SimpleNamespace(
        categoria="respondivel", n=1, seed=42, chunks=str(chunks_path),
        temas=str(tmp_path / "temas.json"), out=str(candidatas_out),
        v1=str(tmp_path / "v1.jsonl"), rej=str(tmp_path / "rej.jsonl"), max_por_norma=15
    )
    bd.cmd_candidates(args)
    linhas = [line for line in candidatas_out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(linhas) == 1
    import json
    item = json.loads(linhas[0])
    assert isinstance(item["resposta_ouro"], str)
    assert item["resposta_ouro"] == "Item 1\nItem 2"


def test_validate_acusa_erro_se_resposta_ouro_nao_for_string(tmp_path, capsys):
    """Testa se validate aborta com erro quando resposta_ouro não for texto (str)."""
    chunks_path = tmp_path / "chunks.jsonl"
    chunks_path.write_text(
        '{"chunk_id": "norma:art1", "norma": "norma", "artigo": "1", "texto": "texto", "n_chars": 100}\n',
        encoding="utf-8"
    )
    v1_path = tmp_path / "v1.jsonl"
    # item com lista em resposta_ouro
    v1_path.write_text(
        '{"id": "abc1", "pergunta": "P1?", "categoria": "respondivel", "chunk_ids_relevantes": ["norma:art1"], "resposta_ouro": ["item"], "revisado": true}\n',
        encoding="utf-8"
    )
    args = SimpleNamespace(chunks=str(chunks_path), v1=str(v1_path))
    with pytest.raises(SystemExit):
        bd.cmd_validate(args)
    saida = capsys.readouterr().out
    assert "resposta_ouro deve ser texto (str)" in saida


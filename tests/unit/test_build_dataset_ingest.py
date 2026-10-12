import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from eval.build_dataset import split_artigos, dividir_longo, cmd_ingest

def test_split_artigos_and_revogados():
    texto = """
    Art. 1º Este é o primeiro artigo ativo da norma.
    Art. 2º (Revogado pela Resolução nº 100)
    Art. 3º Artigo ativo com mais detalhes.
    """
    artigos = split_artigos(texto)
    assert len(artigos) == 3
    assert artigos[0][0] == "1"
    assert "primeiro artigo" in artigos[0][1]
    assert artigos[1][0] == "2"
    assert "Revogado" in artigos[1][1]

def test_ingest_revogados_and_split_longo(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    norma_file = raw_dir / "norma_teste.txt"
    
    # Text with an active short article, a revoked article, and a long active article
    long_content = "Parágrafo 1 com texto extenso. " * 30 + "\nParágrafo único. " + "Outro bloco longo. " * 30
    norma_file.write_text(
        f"Art. 1º Texto normal.\n"
        f"Art. 2º (revogado pelo BACEN)\n"
        f"Art. 3º {long_content}",
        encoding="utf-8"
    )
    
    out_file = tmp_path / "chunks.jsonl"
    
    class Args:
        raw = str(raw_dir)
        out = str(out_file)
        max_chars = 300
    
    cmd_ingest(Args())
    
    assert out_file.exists()
    lines = [json.loads(line) for line in out_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    
    chunk_ids = [c["chunk_id"] for c in lines]
    
    # Art. 2 (revogado) must be ignored
    assert not any("art2" in cid for cid in chunk_ids)
    
    # Art. 1 must exist
    assert any("art1" in cid for cid in chunk_ids)
    
    # Art. 3 must be split into -p1 and -p2 (or more parts)
    p_chunks = [cid for cid in chunk_ids if "art3" in cid]
    assert len(p_chunks) >= 2
    assert any("-p1" in cid for cid in p_chunks)
    assert any("-p2" in cid for cid in p_chunks)


def test_artigos_sufixo_multiplas_letras_nao_abrem_anexo(tmp_path):
    """Art. 78-H, Art. 78-HA e Art. 78-HB geram três ids distintos, sem abrir anexo."""
    texto = (
        "Art. 78-H. Texto do artigo 78-H.\n"
        "Art. 78-HA. Texto do artigo 78-HA.\n"
        "Art. 78-HB. Texto do artigo 78-HB.\n"
    )
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "res_letras.html").write_text(texto, encoding="utf-8")
    out = tmp_path / "chunks.jsonl"
    cmd_ingest(type("Args", (), {"raw": str(raw), "out": str(out), "max_chars": 2500})())
    linhas = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    cids = [c["chunk_id"] for c in linhas]
    assert cids == [
        "res_letras:art78-H",
        "res_letras:art78-HA",
        "res_letras:art78-HB",
    ]
    assert not any("anexo" in cid for cid in cids)


def test_dividir_longo_por_incisos_sem_paragrafos():
    """Um artigo longo sem parágrafos é dividido por incisos, e todas as partes ficam abaixo do limite."""
    romanos = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
               "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX"]
    incisos = "\n".join(f"{r} - Inciso com detalhamento longo da obrigação normativa {r}." for r in romanos)
    corpo = "Art. 10. São atribuições do comitê de risco:\n" + incisos
    max_chars = 400
    partes = dividir_longo(corpo, "10", max_chars=max_chars)
    assert len(partes) > 1
    for p in partes:
        assert len(p) <= max_chars
    # Verifica que incisos foram distribuídos entre as partes
    assert "I -" in partes[0]
    assert any("XX -" in p for p in partes)


def test_revogacao_vigencia_futura_mantem_e_passada_remove(tmp_path):
    """'(Revogado, a partir de' com data futura mantém o dispositivo, e com data passada o remove."""
    texto = (
        "Art. 1º Dispositivo mantido por ter vigência futura.\n"
        "I - (Revogado, a partir de 01/01/2099, pela Resolução nº 9.999.)\n"
        "II - (Revogado, a partir de 01/01/2020, pela Resolução nº 1.111.)\n"
        "III - Inciso plenamente vigente.\n"
        "Art. 2º (Revogado, a partir de 01/01/2020, pela Resolução nº 1.111.)\n"
        "Art. 3º (Revogado, a partir de 01/01/2099, pela Resolução nº 9.999.)\n"
        "§ 1º Texto do parágrafo que continua vigendo até 2099.\n"
    )
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "res_datas.html").write_text(texto, encoding="utf-8")
    out = tmp_path / "chunks.jsonl"
    cmd_ingest(type("Args", (), {"raw": str(raw), "out": str(out), "max_chars": 2500})())
    linhas = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    cids = [c["chunk_id"] for c in linhas]

    # Art. 2 (passado) descartado
    assert "res_datas:art2" not in cids
    # Art. 3 (futuro) mantido
    assert "res_datas:art3" in cids

    chunk_art1 = next(c for c in linhas if c["chunk_id"] == "res_datas:art1")
    # Inciso I com data futura é mantido
    assert "a partir de 01/01/2099" in chunk_art1["texto"]
    # Inciso II com data passada é removido
    assert "a partir de 01/01/2020" not in chunk_art1["texto"]
    # Inciso III é mantido
    assert "III - Inciso plenamente vigente." in chunk_art1["texto"]



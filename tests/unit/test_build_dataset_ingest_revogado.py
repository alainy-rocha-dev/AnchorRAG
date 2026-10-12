"""O ingest deve ignorar atos inteiros marcados como revogados no cabeçalho."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
 
_spec = importlib.util.spec_from_file_location(
    "build_dataset", Path(__file__).resolve().parents[2] / "eval" / "build_dataset.py"
)
bd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bd)
 
CORPO = (
    "Art. 1º Esta Resolução dispõe sobre a contratação de correspondentes no País, "
    "estabelecendo requisitos mínimos de governança, controles internos e transparência "
    "para as instituições autorizadas a funcionar pelo Banco Central do Brasil.\n\n"
    "Art. 2º As instituições devem manter política formalizada, aprovada pela diretoria, "
    "contendo procedimentos e controles para reduzir riscos operacionais e de conformidade.\n"
)
 
 
def _ingest(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "res_vigente.txt").write_text("RESOLUÇÃO Nº 1\n\n" + CORPO, encoding="utf-8")
    (raw / "res_antiga.txt").write_text(
        "RESOLUÇÃO Nº 4.145\n\nDocumento normativo revogado, a partir de 1º/2/2022, "
        "pela Resolução CMN nº 4.935.\n\n" + CORPO, encoding="utf-8")
    out = tmp_path / "chunks.jsonl"
    bd.cmd_ingest(SimpleNamespace(raw=str(raw), out=str(out), max_chars=2500))
    return [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
 
 
def test_ingest_ignora_documento_revogado(tmp_path):
    chunks = _ingest(tmp_path)
    normas = {c["norma"] for c in chunks}
    assert normas == {"res_vigente"}
    assert len(chunks) == 2
 
 
def test_ingest_avisa_arquivo_ignorado(tmp_path, capsys):
    _ingest(tmp_path)
    saida = capsys.readouterr().out
    assert "res_antiga.txt" in saida
 
 
def test_aviso_so_vale_no_cabecalho():
    # menção tardia no corpo do texto não deve descartar a norma
    texto = "x " * 400 + "Documento normativo revogado"
    assert not bd.documento_revogado(texto)
    assert bd.documento_revogado("Documento  normativo\nrevogado a partir de 1/2/2022")

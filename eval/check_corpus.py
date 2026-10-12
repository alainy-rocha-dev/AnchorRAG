#!/usr/bin/env python
"""Confere a integridade de corpus/chunks.jsonl antes de gerar candidatas.

Uso:
  python eval/check_corpus.py                          # relatório geral
  python eval/check_corpus.py --norma res_cmn_4968     # lista os chunk_ids de uma norma
  python eval/check_corpus.py --mostrar res_bcb_80:art25   # imprime o texto de um chunk

Relatório geral:
  - chunk_ids duplicados (deve ser 0)
  - trechos por norma (corpo, anexo1, anexo2...) com primeiro e último artigo
    e quantos chunks cada trecho tem; anexo inesperado = reinício falso
  - chunks que ainda contêm "(Revogad..." no texto (sobra da limpeza)
  - chunks fora da faixa usada pelo candidates (200 a 1.800 caracteres)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

SEG_RE = re.compile(r"^(anexo\d+)-")
REVOG_RE = re.compile(r"\(\s*revogad", re.I)


def carregar(path: Path) -> list[dict]:
    if not path.exists():
        sys.exit(f"{path} não existe. Rode o ingest primeiro.")
    with path.open(encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def trecho(chunk_id: str) -> tuple[str, str]:
    """('res_bcb_1:anexo1-art3-p2') -> ('anexo1', 'art3-p2')."""
    resto = chunk_id.split(":", 1)[1]
    m = SEG_RE.match(resto)
    return (m.group(1), resto[m.end():]) if m else ("corpo", resto)


def relatorio(chunks: list[dict], min_c: int, max_c: int) -> int:
    problemas = 0
    dup = {k: v for k, v in Counter(c["chunk_id"] for c in chunks).items() if v > 1}
    print(f"chunk_ids duplicados: {len(dup)}")
    for k, v in sorted(dup.items())[:20]:
        print(f"  {k} x{v}")
    problemas += len(dup)

    print("\nTrechos por norma:")
    segs: dict[str, OrderedDict] = {}
    for c in chunks:
        seg, art = trecho(c["chunk_id"])
        segs.setdefault(c["norma"], OrderedDict()).setdefault(seg, []).append(art)
    for norma, por_seg in segs.items():
        total = sum(len(v) for v in por_seg.values())
        print(f"  {norma}: {total} chunks")
        for seg, arts in por_seg.items():
            print(f"    {seg:<8} {len(arts):>4} chunks  {arts[0]} ... {arts[-1]}")
        if len(por_seg) > 2:
            print(f"    !! {len(por_seg) - 1} anexos: confira se todos existem na norma")

    sobras = [c for c in chunks if REVOG_RE.search(c["texto"])]
    print(f"\nChunks com '(Revogad...' no texto: {len(sobras)}")
    for c in sobras[:15]:
        m = REVOG_RE.search(c["texto"])
        trecho_txt = c["texto"][max(0, m.start() - 60):m.end() + 60].replace("\n", " ")
        print(f"  {c['chunk_id']}: ...{trecho_txt}...")
    problemas += len(sobras)

    fora = Counter(c["norma"] for c in chunks if not min_c <= c["n_chars"] <= max_c)
    print(f"\nChunks fora de {min_c}-{max_c} caracteres (ignorados pelo candidates): "
          f"{sum(fora.values())} de {len(chunks)}")
    for n, q in fora.most_common():
        print(f"  {n}: {q}")
    return problemas


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--chunks", default="corpus/chunks.jsonl")
    ap.add_argument("--norma", help="lista os chunk_ids e tamanhos de uma norma")
    ap.add_argument("--mostrar", help="imprime o texto completo de um chunk_id")
    ap.add_argument("--min-chars", type=int, default=200)
    ap.add_argument("--max-chars", type=int, default=1800)
    a = ap.parse_args()
    chunks = carregar(Path(a.chunks))

    if a.mostrar:
        achados = [c for c in chunks if c["chunk_id"] == a.mostrar]
        if not achados:
            sys.exit(f"{a.mostrar} não encontrado")
        for c in achados:
            print(f"--- {c['chunk_id']} ({c['n_chars']} caracteres) ---\n{c['texto']}\n")
        return
    if a.norma:
        sel = [c for c in chunks if c["norma"] == a.norma]
        if not sel:
            sys.exit(f"norma {a.norma} não encontrada")
        for c in sel:
            print(f"{c['chunk_id']:<40} {c['n_chars']:>6}")
        print(f"{len(sel)} chunks")
        return
    sys.exit(1 if relatorio(chunks, a.min_chars, a.max_chars) else 0)


if __name__ == "__main__":
    main()

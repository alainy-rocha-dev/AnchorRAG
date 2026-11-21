"""Compara duas variantes da ablação nos mesmos itens (ex.: A x C).

Cada variante entra com os relatórios das suas rodadas (eval-v1). Para cada item, faz a
média das rodadas; a diferença B - A é calculada item a item (pareada) e o IC 95% vem de
bootstrap sobre os itens (10.000 reamostragens), como na baseline.

A "citação válida" é o verificador determinístico (anchor_rag.synthesis.verifier) aplicado à
resposta final. Relatórios antigos, sem esse campo, são verificados de novo a partir das
respostas salvas e do corpus.

Uso:
    python scripts/compare_variants.py \
        --a eval/results/v1_20261015-150353_A_hybrid.json eval/results/v1_20261015-151818_A_hybrid.json \
            eval/results/v1_20261015-154654_A_hybrid.json \
        --b eval/results/v1_..._C_hybrid.json eval/results/v1_..._C_hybrid.json eval/results/v1_..._C_hybrid.json
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional

from anchor_rag.evaluation.dataset_v1 import is_refusal, leaked_prompt
from anchor_rag.synthesis.verifier import artigo_do_chunk_id, verificar

DEVE_RESPONDER = {"respondivel", "multi_trecho", "premissa_falsa"}
DEVE_RECUSAR = {"sem_resposta", "vazamento"}

METRICAS = [
    # nome, descrição, maior é melhor?
    ("hit", "hit@k (itens com referência)", True),
    ("recusa_correta", "recusa correta (sem_resposta + vazamento)", True),
    ("recusa_indevida", "recusa indevida (deve responder)", False),
    ("com_citacao", "resposta com citação (deve responder)", True),
    ("citacao_valida", "citação válida, entre as respostas (verificador)", True),
    ("entregue_bem_citada", "resposta entregue e bem citada (deve responder)", True),
    ("canario", "canário vazado (injeção)", False),
    ("latencia_s", "latência por resposta (s)", False),
    ("tokens", "tokens de entrada por resposta", False),
]


def _carregar_corpus(path: Path) -> Dict[str, str]:
    textos = {}
    with open(path, encoding="utf-8") as f:
        for linha in f:
            if linha.strip():
                x = json.loads(linha)
                textos[x["chunk_id"]] = x["texto"]
    return textos


def _valores_do_item(it: dict, corpus: Dict[str, str], k: int) -> Dict[str, Optional[float]]:
    st = it["subtipo"]
    v: Dict[str, Optional[float]] = {k_: None for k_, _, _ in METRICAS}
    if it.get("erro"):
        return v
    v["hit"] = None if it.get("hit") is None else float(it["hit"])
    resposta = it.get("resposta")
    if resposta is None:
        return v
    recusou = it.get("recusou")
    if recusou is None:
        recusou = is_refusal(resposta) and not leaked_prompt(resposta)
    if st in DEVE_RECUSAR:
        v["recusa_correta"] = float(recusou)
    if st in DEVE_RESPONDER:
        v["recusa_indevida"] = float(recusou)
        v["com_citacao"] = float(bool(it.get("citou")))
        if not recusou:
            valida = it.get("citacao_valida")
            if valida is None:  # relatório anterior ao verificador: confere de novo
                ids = it["recuperados"][:k]
                ordem = sorted(range(len(ids)), key=lambda i: -it["scores"][i])
                ids = [ids[i] for i in ordem]
                valida = verificar(resposta, [corpus.get(c, "") for c in ids],
                                   [artigo_do_chunk_id(c) for c in ids], it.get("pergunta", "")).ok
            v["citacao_valida"] = float(valida)
        # medida que não melhora só por recusar: recusa conta como falha
        v["entregue_bem_citada"] = 0.0 if recusou else v["citacao_valida"]
    if st == "injecao" and it.get("canario_vazou") is not None:
        v["canario"] = float(it["canario_vazou"])
    if it.get("latencia_ms"):
        v["latencia_s"] = it["latencia_ms"] / 1000
    if it.get("tokens_entrada"):
        v["tokens"] = float(it["tokens_entrada"])
    return v


def _por_item(relatorios: List[Path], corpus: Dict[str, str]) -> Dict[str, Dict[str, float]]:
    """Média das rodadas por item e métrica."""
    acumulado: Dict[str, Dict[str, List[float]]] = {}
    for path in relatorios:
        rel = json.loads(path.read_text(encoding="utf-8"))
        for it in rel["itens"]:
            vals = _valores_do_item(it, corpus, rel.get("k", 5))
            for nome, x in vals.items():
                if x is not None:
                    acumulado.setdefault(it["id"], {}).setdefault(nome, []).append(x)
    return {i: {m: mean(xs) for m, xs in d.items()} for i, d in acumulado.items()}


def _bootstrap(valores: List[float], n: int = 10_000, seed: int = 0):
    rnd = random.Random(seed)
    medias = sorted(mean(rnd.choices(valores, k=len(valores))) for _ in range(n))
    return medias[int(0.025 * n)], medias[int(0.975 * n) - 1]


def _resumo_variante(itens: Dict[str, Dict[str, float]], metrica: str):
    vals = [d[metrica] for d in itens.values() if metrica in d]
    if not vals:
        return None
    lo, hi = _bootstrap(vals) if len(vals) > 1 else (vals[0], vals[0])
    return len(vals), mean(vals), lo, hi


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--a", nargs="+", type=Path, required=True, help="relatórios da variante de referência")
    p.add_argument("--b", nargs="+", type=Path, help="relatórios da variante comparada")
    p.add_argument("--corpus", type=Path, default=Path("corpus/chunks.jsonl"))
    p.add_argument("--json", type=Path, help="grava o resultado em JSON")
    args = p.parse_args()

    corpus = _carregar_corpus(args.corpus)
    a = _por_item(args.a, corpus)
    b = _por_item(args.b, corpus) if args.b else None
    saida = {"a": [str(x) for x in args.a], "b": [str(x) for x in args.b or []], "metricas": {}}

    cab = f"{'métrica':<50} {'A':>24}" + (f" {'B':>24} {'B - A (pareado)':>26}" if b else "")
    print(cab)
    print("-" * len(cab))
    for nome, desc, _ in METRICAS:
        ra = _resumo_variante(a, nome)
        if ra is None:
            continue
        linha = f"{desc:<50} {ra[1]:>7.3f} [{ra[2]:.3f}-{ra[3]:.3f}] n={ra[0]:<3}"
        reg = {"a": {"n": ra[0], "media": ra[1], "ic95": [ra[2], ra[3]]}}
        if b is not None:
            rb = _resumo_variante(b, nome)
            comuns = [i for i in a if nome in a[i] and i in b and nome in b[i]]
            if rb and comuns:
                difs = [b[i][nome] - a[i][nome] for i in comuns]
                lo, hi = _bootstrap(difs)
                linha += f" {rb[1]:>7.3f} [{rb[2]:.3f}-{rb[3]:.3f}] n={rb[0]:<3} {mean(difs):>+7.3f} [{lo:+.3f} a {hi:+.3f}]"
                reg["b"] = {"n": rb[0], "media": rb[1], "ic95": [rb[2], rb[3]]}
                reg["diferenca"] = {"n_pareado": len(comuns), "media": mean(difs), "ic95": [lo, hi]}
        print(linha)
        saida["metricas"][nome] = reg
    if args.json:
        args.json.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nGravado em {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

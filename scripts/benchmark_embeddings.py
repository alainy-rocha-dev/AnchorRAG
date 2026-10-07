#!/usr/bin/env python3
"""
Benchmark de Embeddings - AnchorRAG

Mede latência (ms/1k chunks) e custo (USD/1M tokens) dos 3 provedores suportados:
- OpenAI (text-embedding-3-small, text-embedding-3-large)
- Ollama (nomic-embed-text, mxbai-embed-large, etc.)
- HuggingFace (BAAI/bge-m3, sentence-transformers/all-MiniLM-L6-v2, etc.)

Uso:
    python scripts/benchmark_embeddings.py --chunks 1000 --runs 3
    python scripts/benchmark_embeddings.py --provider openai --model text-embedding-3-small
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, asdict
from typing import List, Optional

# Adicionar src ao path para importar anchor_rag
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from anchor_rag.embeddings import create_embedding_provider
from anchor_rag.config import EmbeddingConfig


@dataclass
class BenchmarkResult:
    provider: str
    model: str
    chunks_tested: int
    runs: int
    latency_ms_per_1k_mean: float
    latency_ms_per_1k_stdev: float
    latency_ms_per_1k_min: float
    latency_ms_per_1k_max: float
    tokens_per_chunk_estimate: int
    cost_usd_per_1M_tokens: Optional[float]
    hardware: str
    timestamp: str
    notes: str = ""


# Custos conhecidos (USD por 1M tokens) - atualizar conforme pricing oficial
MODEL_COSTS = {
    # OpenAI
    "text-embedding-3-small": 0.02,
    "text-embedding-3-large": 0.13,
    "text-embedding-ada-002": 0.10,
    # Ollama (local, custo = hardware/energia)
    "nomic-embed-text": None,
    "mxbai-embed-large": None,
    "all-minilm-l6-v2": None,
    # HuggingFace (local)
    "BAAI/bge-m3": None,
    "sentence-transformers/all-MiniLM-L6-v2": None,
    "sentence-transformers/all-mpnet-base-v2": None,
}


# Configurações padrão por provedor
DEFAULT_MODELS = {
    "openai": ["text-embedding-3-small", "text-embedding-3-large"],
    "ollama": ["nomic-embed-text", "mxbai-embed-large"],
    "huggingface": ["BAAI/bge-m3", "sentence-transformers/all-MiniLM-L6-v2"],
}


def get_hardware_info() -> str:
    """Retorna string com info de hardware para reprodutibilidade."""
    import platform
    import psutil

    cpu = platform.processor() or platform.machine()
    ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
    gpu = "N/A"
    try:
        import torch

        if torch.cuda.is_available():
            gpu = torch.cuda.get_device_name(0)
    except ImportError:
        pass
    return f"CPU: {cpu}, RAM: {ram_gb}GB, GPU: {gpu}"


def generate_test_chunks(n: int, chunk_size: int = 512) -> List[str]:
    """Gera chunks de teste sintéticos com tamanho aproximado em tokens."""
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    base_text = "Este é um texto de teste para benchmark de embeddings. " * 20
    base_tokens = enc.encode(base_text)

    chunks = []
    for i in range(n):
        # Variar ligeiramente o tamanho
        tokens = base_tokens[:chunk_size]
        chunk_text = enc.decode(tokens)
        chunks.append(chunk_text)
    return chunks


async def benchmark_provider(
    provider_name: str,
    model: str,
    chunks: List[str],
    runs: int = 3,
    batch_size: int = 100,
) -> List[float]:
    """Executa benchmark de um provedor específico."""
    config = EmbeddingConfig(
        provider=provider_name,
        model=model,
        batch_size=batch_size,
    )

    provider = create_embedding_provider(config)

    latencies = []
    for run in range(runs):
        start = time.perf_counter()
        embeddings = await provider.embed_batch(chunks)
        end = time.perf_counter()
        latency_ms = (end - start) * 1000
        latencies.append(latency_ms)
        print(f"  Run {run+1}/{runs}: {latency_ms:.1f}ms for {len(chunks)} chunks")

    await provider.close()
    return latencies


async def main():
    parser = argparse.ArgumentParser(description="Benchmark de Embeddings AnchorRAG")
    parser.add_argument("--provider", choices=["openai", "ollama", "huggingface", "all"], default="all")
    parser.add_argument("--model", help="Modelo específico (ex: text-embedding-3-small)")
    parser.add_argument("--chunks", type=int, default=1000, help="Número de chunks para testar")
    parser.add_argument("--runs", type=int, default=3, help="Número de execuções por modelo")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size para embeddings")
    parser.add_argument("--output", default="docs/embedding-benchmark.md", help="Arquivo de saída Markdown")
    parser.add_argument("--skip-unavailable", action="store_true", help="Pular provedores indisponíveis")

    args = parser.parse_args()

    print(f"Gerando {args.chunks} chunks de teste...")
    chunks = generate_test_chunks(args.chunks)
    print(f"Chunks gerados. Iniciando benchmarks...\n")

    hardware = get_hardware_info()
    print(f"Hardware: {hardware}\n")

    results = []
    providers_to_test = []

    if args.provider == "all":
        providers_to_test = ["openai", "ollama", "huggingface"]
    else:
        providers_to_test = [args.provider]

    for provider_name in providers_to_test:
        models = [args.model] if args.model else DEFAULT_MODELS.get(provider_name, [])

        for model in models:
            print(f"\n=== {provider_name.upper()} / {model} ===")
            try:
                latencies = await benchmark_provider(
                    provider_name, model, chunks, args.runs, args.batch_size
                )

                # Calcular métricas por 1k chunks
                latencies_per_1k = [lat * (1000 / args.chunks) for lat in latencies]

                mean_lat = statistics.mean(latencies_per_1k)
                stdev_lat = statistics.stdev(latencies_per_1k) if len(latencies_per_1k) > 1 else 0
                min_lat = min(latencies_per_1k)
                max_lat = max(latencies_per_1k)

                # Estimar tokens por chunk
                import tiktoken

                enc = tiktoken.get_encoding("cl100k_base")
                tokens_per_chunk = len(enc.encode(chunks[0])) if chunks else 512

                cost = MODEL_COSTS.get(model)

                result = BenchmarkResult(
                    provider=provider_name,
                    model=model,
                    chunks_tested=args.chunks,
                    runs=args.runs,
                    latency_ms_per_1k_mean=round(mean_lat, 1),
                    latency_ms_per_1k_stdev=round(stdev_lat, 1),
                    latency_ms_per_1k_min=round(min_lat, 1),
                    latency_ms_per_1k_max=round(max_lat, 1),
                    tokens_per_chunk_estimate=tokens_per_chunk,
                    cost_usd_per_1M_tokens=cost,
                    hardware=hardware,
                    timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                )
                results.append(result)
                print(f"  [OK] Media: {mean_lat:.1f}ms/1k chunks")

            except Exception as e:
                error_msg = str(e)
                print(f"  [ERRO] {error_msg}")
                if args.skip_unavailable:
                    result = BenchmarkResult(
                        provider=provider_name,
                        model=model,
                        chunks_tested=args.chunks,
                        runs=args.runs,
                        latency_ms_per_1k_mean=0,
                        latency_ms_per_1k_stdev=0,
                        latency_ms_per_1k_min=0,
                        latency_ms_per_1k_max=0,
                        tokens_per_chunk_estimate=0,
                        cost_usd_per_1M_tokens=MODEL_COSTS.get(model),
                        hardware=hardware,
                        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                        notes=f"Indisponível: {error_msg}",
                    )
                    results.append(result)
                else:
                    raise

    # Gerar saída Markdown
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write("# Benchmark de Embeddings - AnchorRAG\n\n")
        f.write(f"**Data:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Hardware:** {hardware}\n\n")
        f.write(f"**Chunks testados:** {args.chunks} | **Runs por modelo:** {args.runs} | **Batch size:** {args.batch_size}\n\n")
        f.write("---\n\n")

        f.write("## Resultados\n\n")
        f.write(
            "| Provedor | Modelo | Latência (ms/1k chunks) | Tokens/chunk | Custo (USD/1M tokens) | Notas |\n"
        )
        f.write(
            "|----------|--------|--------------------------|--------------|------------------------|-------|\n"
        )

        for r in results:
            latency_str = f"{r.latency_ms_per_1k_mean:.1f} ± {r.latency_ms_per_1k_stdev:.1f}"
            if r.latency_ms_per_1k_mean == 0:
                latency_str = "N/A (indisponível)"
            cost_str = f"${r.cost_usd_per_1M_tokens:.2f}" if r.cost_usd_per_1M_tokens else "Local (gratuito)"
            notes = r.notes or ""
            f.write(f"| {r.provider} | {r.model} | {latency_str} | {r.tokens_per_chunk_estimate} | {cost_str} | {notes} |\n")

        f.write("\n---\n\n")
        f.write("## Metodologia\n\n")
        f.write("- **Chunks de teste:** Textos sintéticos de ~512 tokens cada (cl100k_base encoding)\n")
        f.write("- **Medição:** Tempo total para `embed_batch()` de todos os chunks, convertido para ms/1k chunks\n")
        f.write("- **Runs:** Múltiplas execuções para calcular média e desvio padrão\n")
        f.write("- **Custos:** Baseados em pricing público das APIs (OpenAI) ou estimados como zero para local\n")
        f.write("- **Hardware:** Reportado para reprodutibilidade\n\n")

        f.write("## Interpretação\n\n")
        f.write("- **Latência menor** = melhor para aplicações em tempo real\n")
        f.write("- **Custo menor** = melhor para alto volume\n")
        f.write("- **Provedores locais (Ollama, HF)** têm latência variável dependendo do hardware\n")
        f.write("- **OpenAI** tem latência consistente mas custo por token\n\n")

    print(f"\n[OK] Benchmark concluido. Resultados salvos em: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
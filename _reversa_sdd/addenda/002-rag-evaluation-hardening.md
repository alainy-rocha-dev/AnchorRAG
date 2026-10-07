# Adendo: rag-evaluation-hardening

> Identificador: `002-rag-evaluation-hardening`
> Data: `2026-09-30`
> Cenário: **legado** (âncora: `_reversa_sdd/architecture.md` + `_reversa_sdd/domain.md`)

---

## Vigência

Vigente desde 2026-09-30.

---

## Resumo da entrega

Esta feature endereça os gaps críticos identificados na revisão do HAG RAG (confidence-report.md) para torná-lo pronto para avaliação técnica rigorosa e uso em produção. Entrega: (1) dataset de avaliação versionado com corpus real (normas BACEN) e gabarito; (2) benchmarks próprios de latência/custo dos 3 provedores de embedding; (3) testes automatizados de prompt injection; (4) validador cross-config de dimensions no AppConfig; (5) dedup real consultando hash antes de parse; (6) correção das 3 SDD specs divergentes; (7) fix de typo no README.

**Ações concluídas:** 23/23 (100%)

---

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta |
|----------|-------|-----------------|-------|
| `architecture.md` | 3. Containers — IngestionPipeline | regra-alterada | Dedup real executado antes do parser: `SELECT 1 FROM documents WHERE content_hash` → `IngestResult(skipped=True)` |
| `architecture.md` | 3. Containers — CLI / eval | regra-nova | CLI `eval --dataset` com métricas recall@k, MRR, hallucination_rate, citation_coverage |
| `architecture.md` | 3. Containers — Embedding Providers | componente-novo | Script `scripts/benchmark_embeddings.py` compara OpenAI/Ollama/HF: latência ms/1k, custo USD/1M |
| `architecture.md` | 7. Dívidas Técnicas | regra-removida | TD-001 (dimensions cross-validation), TD-003 (dedup não implementado), TD-008 (zero testes), TD-010 (regex citações sem teste adversarial) — RESOLVIDOS |
| `architecture.md` | 6. Integrações Externas | regra-alterada | README typo fix: `provider: "openai"` |
| `domain.md` | 2.1 Ingestão e Deduplicação (BR-001) | regra-alterada | Dedup reforçado: consulta hash ANTES do parser, não só `INSERT OR IGNORE` no final |
| `domain.md` | 2.2 Embeddings e Busca Vetorial (BR-011) | regra-nova | Validador cross-config em `AppConfig.validate_embedding_dimensions` falha no load da config |
| `domain.md` | 2.3 Síntese RAG (BR-022) | regra-nova | Suite automatizada de 10+ ataques prompt injection, bypass_rate=0% obrigatório |
| `domain.md` | 5. Lacunas Identificadas | regra-removida | Lacuna #1 (consistência embedding↔store) e #3 (dedup não implementado) — RESOLVIDAS |
| `domain.md` | — | regra-nova | BR-044: Avaliação quantitativa (recall@k, MRR, hallucination_rate, citation_coverage) |
| `domain.md` | — | regra-nova | BR-045: Benchmark embeddings (latência ms/1k, custo USD/1M tokens) |
| `domain.md` | — | regra-nova | BR-046: Teste adversarial automatizado prompt injection |
| `domain.md` | — | regra-nova | BR-047: Config fail-fast cross-config dimensions |
| `sdd/document-ingestion-chunking.md` | — | regra-alterada | Status → 🟢 IMPLEMENTADO; params: chunk_size=512 tokens, chunk_overlap=50, chunk_unit=tokens, parser factory pdfplumber/PyPDF |
| `sdd/rag-synthesis-citation-engine.md` | — | regra-alterada | Status → 🟢 IMPLEMENTADO; citation format `[N]`, threshold=0.7, few-shot defense 3 exemplos |
| `sdd/vector-store-similarity-search.md` | — | regra-alterada | Status → 🟢 IMPLEMENTADO; store=sqlite-vec virtual table, retry OpenAI (tenacity), top_k=5, score=1-distance |
| `README.md` | — | regra-alterada | Typo fix: `provider: "open` → `provider: "openai"` |

---

## Regras sob vigilância

| Watch ID | Apontador |
|----------|-----------|
| W001 | `_reversa_forward/002-rag-evaluation-hardening/regression-watch.md#W001` (dedup prévio) |
| W002 | `_reversa_forward/002-rag-evaluation-hardening/regression-watch.md#W002` (validador cross-config) |
| W003 | `_reversa_forward/002-rag-evaluation-hardening/regression-watch.md#W003` (eval_dataset métricas) |
| W004 | `_reversa_forward/002-rag-evaluation-hardening/regression-watch.md#W004` (CLI eval --dataset) |
| W005 | `_reversa_forward/002-rag-evaluation-hardening/regression-watch.md#W005` (prompt injection tests) |
| W006 | `_reversa_forward/002-rag-evaluation-hardening/regression-watch.md#W006` (IngestResult.skipped) |
| W007 | `_reversa_forward/002-rag-evaluation-hardening/regression-watch.md#W007` (AppConfig validador) |

---

## Fontes

- `_reversa_forward/002-rag-evaluation-hardening/requirements.md`
- `_reversa_forward/002-rag-evaluation-hardening/legacy-impact.md`
- `_reversa_forward/002-rag-evaluation-hardening/regression-watch.md`
- `_reversa_forward/002-rag-evaluation-hardening/progress.jsonl`
- `_reversa_forward/002-rag-evaluation-hardening/actions.md`

---
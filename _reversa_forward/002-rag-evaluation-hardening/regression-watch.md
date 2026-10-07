# Regression Watch: rag-evaluation-hardening

> Feature: `002-rag-evaluation-hardening`
> Data: `2026-09-30`

---

## 1. Watch Principal (Regras 🟢 Modificadas/Removidas)

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|-------------------------|----------------------------|---------------------|-------------------|
| W001 | `domain.md#BR-001`, `architecture.md#ingestion/pipeline.py` | Dedup real executado **antes** do parser: `SELECT 1 FROM documents WHERE content_hash = ?` → `IngestResult(skipped=True)` se encontrado | presença | Ingest duplicado chama parser/embedding (logs mostram parse/embed) OU `IngestResult.skipped` sempre `False` |
| W002 | `domain.md#Lacuna #1`, `architecture.md#config.py` | `AppConfig.validate_embedding_dimensions` lança `ValueError` se `embedding.dimensions != vector_store.embedding_dimensions` no load da config (YAML ou objeto) | presença | Config inválida carrega sem erro OU erro genérico sem mensagem acionável |
| W003 | `domain.md#BR-042`, `architecture.md#cli_eval.py` | `RAGPipeline.eval_dataset(dataset_path, k)` retorna `EvalMetrics` com campos: `recall_at_k`, `mrr`, `hallucination_rate`, `citation_coverage`, `total_queries`, `successful_queries` | presença | `eval_dataset` ausente OU retorna estrutura diferente OU métricas sempre 0/1 fixos |
| W004 | `domain.md#BR-042`, `architecture.md#cli_eval.py` | CLI `anchor-rag eval --dataset <yaml>` executa health checks + vector stats + métricas dataset; saída text/JSON | presença | Comando `eval` falha com dataset válido OU não imprime métricas |
| W005 | `architecture.md#tests/integration/test_prompt_injection.py` | Suite `test_prompt_injection.py` roda 15 testes (10 ataques + few-shot + estrutura + query legítima); todos passam; bypass_rate=0% | presença | Testes falham OU bypass_rate > 0% OU categorias de ataque removidas |
| W006 | `architecture.md#src/anchor_rag/ingestion/pipeline.py` | `IngestionPipeline.ingest()` retorna `IngestResult` com campo `skipped: bool` e `document_id: str` | presença | `IngestResult` sem campo `skipped` OU tipo alterado |
| W007 | `architecture.md#src/anchor_rag/config.py` | `AppConfig` tem `model_validator(mode="after")` chamado `validate_embedding_dimensions` | presença | Validador removido OU renomeado sem substituto equivalente |

---

## 2. Observações (RFs Implementados — sem peso de regressão até próxima extração)

Estes itens correspondem a RFs desta feature. Ganham peso de regressão (virar W00N) quando uma futura extração `/reversa` confirmar como 🟢 CONFIRMADO no código.

| ID | RF | Descrição | Arquivo(s) |
|----|----|-----------|------------|
| O001 | RF-01 | Validador cross-config embedding.dimensions == vector_store.embedding_dimensions | `src/anchor_rag/config.py` |
| O002 | RF-02 | Teste unitário validador cross-config (válido + inválido) | `tests/unit/test_config.py` |
| O003 | RF-03 | Dataset BACEN ≥20 queries com chunks esperados, respostas referência, metadados | `tests/fixtures/eval_dataset_bacen.yaml` |
| O004 | RF-04 | Script benchmark embeddings (OpenAI/Ollama/HF: latency, cost) | `scripts/benchmark_embeddings.py` |
| O005 | RF-05 | Suite prompt injection 10+ ataques categorizados | `tests/integration/test_prompt_injection.py` |
| O006 | RF-06 | Dedup real em IngestionPipeline (SELECT hash antes do parser) | `src/anchor_rag/ingestion/pipeline.py` |
| O007 | RF-07 | Teste integração dedup real | `tests/integration/test_ingestion_pipeline.py` |
| O008 | RF-08 | CLI eval com dataset YAML + métricas (recall@k, MRR, hallucination, citation_coverage) | `src/anchor_rag/cli_eval.py` |
| O009 | RF-09 | Métricas puras testáveis: recall_at_k, mrr, hallucination_rate, citation_coverage | `src/anchor_rag/cli_eval.py` |
| O010 | RF-10 | Benchmark output em `docs/embedding-benchmark.md` | `docs/embedding-benchmark.md` |
| O011 | RF-11 | Specs SDD atualizadas para 🟢 IMPLEMENTADO (3 specs) | `_reversa_sdd/sdd/*.md` |
| O012 | RF-12 | Typo fix README `provider: "openai"` | `README.md` |
| O013 | RF-13 | Documentação inline validador, dedup, métricas | `src/anchor_rag/config.py`, `ingestion/pipeline.py`, `cli_eval.py` |

---

## 3. Histórico de Re-extrações

*Vazio — aguardando próxima execução de `/reversa`*

---

## 4. Arquivadas

*Vazio*

---

*Gerado por `/reversa-coding` — feature `002-rag-evaluation-hardening`*
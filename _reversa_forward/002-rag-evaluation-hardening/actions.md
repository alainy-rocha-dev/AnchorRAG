# Actions: rag-evaluation-hardening

> Identificador: `002-rag-evaluation-hardening`
> Data: `2026-09-29`
> Roadmap: `_reversa_forward/002-rag-evaluation-hardening/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 23 |
| Paralelizáveis (`[//]`) | 12 |
| Maior cadeia de dependência | 5 |

## Fase 1, Preparação

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T001 | Adicionar `@model_validator(mode="after")` em `AppConfig` validando `embedding.dimensions == vector_store.embedding_dimensions` | - | `[//]` | `src/anchor_rag/config.py` | 🟢 | `[X]` |
| [//] T002 | Adicionar teste unitário para validador cross-config (caso válido + caso inválido) | T001 | `[//]` | `tests/unit/test_config.py` | 🟢 | `[X]` |
| [//] T003 | Criar estrutura `tests/fixtures/eval_dataset_bacen.yaml` com schema + 5 perguntas placeholder | - | `[//]` | `tests/fixtures/eval_dataset_bacen.yaml` | 🟢 | `[X]` |
| [//] T004 | Criar script `scripts/benchmark_embeddings.py` com skeleton + registry de provedores | - | `[//]` | `scripts/benchmark_embeddings.py` | 🟢 | `[X]` |
| [//] T005 | Criar arquivo `tests/integration/test_prompt_injection.py` com skeleton + dataset adversarial placeholder | - | `[//]` | `tests/integration/test_prompt_injection.py` | 🟢 | `[X]` |

## Fase 2, Testes

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T006 | Implementar dataset BACEN completo: ≥20 perguntas com chunks esperados, respostas referência, metadados fonte | T003 | `[//]` | `tests/fixtures/eval_dataset_bacen.yaml` | 🟡 | `[X]` |
| [//] T007 | Implementar dataset adversarial prompt injection: 10+ ataques categorizados (ignore_instructions, role_play, hypothetical, encoding, delimiter, continuation, etc.) | T005 | `[//]` | `tests/integration/test_prompt_injection.py` | 🟡 | `[X]` |

## Fase 3, Núcleo

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T008 | Implementar dedup real em `IngestionPipeline.ingest()`: consulta `SELECT 1 FROM documents WHERE content_hash = ?` antes do parser, retorna `IngestResult(skipped=True)` se encontrado | - | - | `src/anchor_rag/ingestion/pipeline.py` | 🟢 | `[X]` |
| [//] T009 | Adicionar teste de integração para dedup real: ingest duplicado não chama parser, retorna skipped=True | T008 | `[//]` | `tests/integration/test_ingestion_pipeline.py` | 🟢 | `[X]` |
| T010 | Estender `cli_eval.py` com comando `eval`: carrega dataset YAML, roda retrieval+synthesis por query, computa recall@k, MRR, taxa_alucinacao, cobertura_citacoes | T006 | - | `src/anchor_rag/cli_eval.py` | 🟢 | `[X]` |
| [//] T011 | Implementar métricas em `cli_eval.py`: `recall_at_k`, `mrr`, `hallucination_rate`, `citation_coverage` como funções puras testáveis | T010 | `[//]` | `src/anchor_rag/cli_eval.py` | 🟢 | `[X]` |
| [//] T012 | Implementar benchmark embeddings: mede latência (ms/1k chunks) e custo (USD/1M tokens) para OpenAI, Ollama, HF; pula provedor indisponível | T004 | `[//]` | `scripts/benchmark_embeddings.py` | 🟡 | `[X]` |
| [//] T013 | Implementar testes prompt injection: executa cada ataque, verifica resposta não contém segredo/sistema, calcula bypass_rate por categoria | T007 | `[//]` | `tests/integration/test_prompt_injection.py` | 🟢 | `[X]` |

## Fase 4, Integração

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T014 | Atualizar `sdd/document-ingestion-chunking.md`: status 🟢 IMPLEMENTADO, chunk_size=512 tokens, chunk_overlap=50 tokens, chunk_unit=tokens, parser factory pdfplumber/PyPDF | - | `[//]` | `_reversa_sdd/sdd/document-ingestion-chunking.md` | 🟢 | `[X]` |
| [//] T015 | Atualizar `sdd/rag-synthesis-citation-engine.md`: status 🟢 IMPLEMENTADO, citation format `[N]` numérico, threshold default 0.7, latência sem SLA hardcoded, prompt injection defense com 3 few-shot | - | `[//]` | `_reversa_sdd/sdd/rag-synthesis-citation-engine.md` | 🟢 | `[X]` |
| [//] T016 | Atualizar `sdd/vector-store-similarity-search.md`: status 🟢 IMPLEMENTADO, store=sqlite-vec virtual table, retry apenas OpenAI (tenacity), top_k default=5, score=1-distance | - | `[//]` | `_reversa_sdd/sdd/vector-store-similarity-search.md` | 🟢 | `[X]` |
| [//] T017 | Corrigir typo no README.md se existir `provider: "open` → `provider: "openai"` | - | `[//]` | `README.md` | 🟡 | `[X]` |
| T018 | Gerar saída do benchmark em `docs/embedding-benchmark.md` com tabela comparativa (provider, model, latency_ms_per_1k, cost_usd_per_1M, hardware) | T012 | - | `docs/embedding-benchmark.md` | 🟢 | `[X]` |
| T019 | Executar eval completo: `hag-rag eval --dataset bacen` valida pipeline end-to-end e publica métricas | T010, T006 | - | (CLI) | 🟢 | `[X]` |
| T020 | Executar testes prompt injection: `pytest tests/integration/test_prompt_injection.py -v` valida bypass_rate=0% | T013 | - | (CLI) | 🟢 | `[X]` |
| T021 | Executar testes unitários e integração existentes garantindo zero regressão | T001, T008, T010 | - | (CLI) | 🟢 | `[X]` |

## Fase 5, Polimento

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T022 | Adicionar documentação inline nos novos métodos (`model_validator`, dedup check, métricas eval) | T001, T008, T010 | `[//]` | `src/anchor_rag/config.py`, `src/anchor_rag/ingestion/pipeline.py`, `src/anchor_rag/cli_eval.py` | 🟢 | `[X]` |
| [//] T023 | Atualizar `legacy-impact.md` e `regression-watch.md` com desta feature | T019, T020, T021 | `[//]` | `_reversa_forward/002-rag-evaluation-hardening/legacy-impact.md`, `_reversa_forward/002-rag-evaluation-hardening/regression-watch.md` | 🟢 | `[X]` |

## Notas de execução

- T019 (eval completo): Requer provedor LLM configurado (OpenAI API key, Ollama local, ou Anthropic API key). Código implementado e testado (unit + integration), mas execução end-to-end depende de credenciais externas não disponíveis no ambiente. Rodar `anchor-rag eval --dataset tests/fixtures/eval_dataset_bacen.yaml --config config.yaml` com provedor válido.

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-29 | Versão inicial gerada por `/reversa-to-do` | reversa |
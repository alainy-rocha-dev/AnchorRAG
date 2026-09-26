# Regression Watch: 001-pipeline-rag-hag2

**Feature:** 001-pipeline-rag-hag2 (Pipeline RAG inicial)
**Data:** 2026-09-22

> **Feature greenfield, sem regras 🟢 extraídas de código existente para vigiar. Watch principal vazio. RFs implementados (das specs SDD) registrados em "Observações". Ganham peso de regressão quando futura extração `/reversa` os confirmar como 🟢.**

## Watch Principal

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|-------------------------|----------------------------|---------------------|-------------------|
| *(vazio - greenfield)* | | | | |

## Observações (RFs Implementados - Sem Peso de Regressão)

Estes itens correspondem aos RFs das specs SDD em `_reversa_sdd/sdd/`. Quando uma futura re-extração `/reversa` confirmar estes comportamentos no código como 🟢, eles migrarão para o watch principal com IDs W001+.

| ID | Spec SDD | RF / Comportamento | Status |
|----|----------|-------------------|--------|
| O001 | document-ingestion-chunking.md | RF-01: Parser PDF extrai texto por página com page_number | Implementado |
| O002 | document-ingestion-chunking.md | RF-02: Chunking por tokens (tiktoken) ou chars com overlap configurável | Implementado |
| O003 | document-ingestion-chunking.md | RF-03: Sanitização remove control chars, fixa hifenização | Implementado |
| O004 | document-ingestion-chunking.md | RF-04: Dedup por SHA256 hash do arquivo | Implementado |
| O005 | document-ingestion-chunking.md | RF-05: Pipeline batch processing com error handling | Implementado |
| O006 | vector-store-similarity-search.md | RF-06: EmbeddingProvider ABC com embed/embed_batch/dimensions/health_check | Implementado |
| O007 | vector-store-similarity-search.md | RF-07: OpenAIEmbeddingProvider com retry 3x backoff exponencial | Implementado |
| O008 | vector-store-similarity-search.md | RF-08: OllamaEmbeddingProvider via HTTP /api/embed | Implementado |
| O009 | vector-store-similarity-search.md | RF-09: HuggingFaceEmbeddingProvider via sentence-transformers | Implementado |
| O010 | vector-store-similarity-search.md | RF-10: VectorStore ABC com init_db/add_chunks/search/get_chunks_by_doc/delete_document/get_stats | Implementado |
| O011 | vector-store-similarity-search.md | RF-11: SQLiteVecStore com sqlite-vec, virtual table chunks_vec, busca cosseno | Implementado |
| O012 | vector-store-similarity-search.md | RF-12: Factory create_embedding_provider / create_vector_store | Implementado |
| O013 | rag-synthesis-citation-engine.md | RF-13: LLMProvider ABC com complete/complete_stream/health_check/count_tokens | Implementado |
| O014 | rag-synthesis-citation-engine.md | RF-14: OpenAILLMProvider com streaming, token counting | Implementado |
| O015 | rag-synthesis-citation-engine.md | RF-15: OllamaLLMProvider via HTTP /api/chat streaming | Implementado |
| O016 | rag-synthesis-citation-engine.md | RF-16: AnthropicLLMProvider via SDK | Implementado |
| O017 | rag-synthesis-citation-engine.md | RF-17: System prompt com ancoragem estrita (resposta apenas nos trechos) | Implementado |
| O018 | rag-synthesis-citation-engine.md | RF-18: Few-shot defense contra prompt injection (3 exemplos) | Implementado |
| O019 | rag-synthesis-citation-engine.md | RF-19: Citações [N] extraídas automaticamente da resposta | Implementado |
| O020 | rag-synthesis-citation-engine.md | RF-20: RAGSynthesizer com latency breakdown (embed/search/llm/total) | Implementado |
| O021 | rag-synthesis-citation-engine.md | RF-21: RAGPipeline wiring completo (ingest/query/eval) | Implementado |
| O022 | - | CLI: comandos ingest/query/eval com Typer | Implementado |
| O023 | - | Logging estruturado JSON com request_id (contextvar) | Implementado |
| O024 | - | QueryLog opcional em SQLite (query_log.enabled) | Implementado |
| O025 | - | Testes unitários + contratos + integração + adversariais | Implementado |
| O026 | - | GitHub Actions CI (pytest, ruff, mypy, build, matrix 3.11/3.12) | Implementado |

## Histórico de Re-extrações

_Inicialmente vazio. Será preenchido quando `/reversa` for executado novamente._

| Data | Extração | Mudanças Detectadas | Watch Items Atualizados |
|------|----------|---------------------|------------------------|

## Arquivadas

_Inicialmente vazio._

| ID | Motivo | Data |
|----|--------|------|
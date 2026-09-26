# Adendo: 001-pipeline-rag-hag2

**Identificador:** `001-pipeline-rag-hag2`
**Feature:** Pipeline RAG inicial (Ingestão → Chunking → Embeddings → Busca Vetorial → Síntese com Citação)
**Data:** 2026-09-22
**Cenário:** greenfield (âncora: `_reversa_sdd/prd.md` + specs em `_reversa_sdd/sdd/`)

## Vigência

Vigente desde 2026-09-22.

## Resumo da entrega

Implementação completa do pipeline RAG para consulta de documentos técnicos PDF privados com busca semântica por similaridade de cosseno, resposta ancorada com citações, métricas de latência e resiliência. Entregue em 42 ações (42 concluídas, 0 pendentes), cobrindo todas as 3 specs SDD: `document-ingestion-chunking.md`, `vector-store-similarity-search.md`, `rag-synthesis-citation-engine.md`.

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta |
|----------|-------|----------------|-------|
| `_reversa_sdd/prd.md` | 4 (Escopo) | componente-novo | Pipeline RAG completo implementado: ingestão PDF multi-parser, chunking parametrizado, embeddings multi-provedor, vector store sqlite-vec, síntese ancorada |
| `_reversa_sdd/prd.md` | 3 (Métricas) | componente-novo | Métricas instrumentadas: latência breakdown (embed/search/llm/total), scores cosseno, contagem chunks, health checks |
| `_reversa_sdd/prd.md` | 6 (Restrições) | componente-novo | README com matemática cosseno transparente, tabela comparativa embeddings, quickstart, troubleshooting |
| `_reversa_sdd/sdd/document-ingestion-chunking.md` | RF-01 a RF-05 | componente-novo | Parser (PdfPlumberParser + PyPDFParser fallback) com page_number; Chunker tokens/chars + overlap exato; Sanitização control chars + hifenização; Metadados chunk_id, source_file, page_number, char_count; Dedup SHA256 |
| `_reversa_sdd/sdd/vector-store-similarity-search.md` | RF-06 a RF-12 | componente-novo | EmbeddingProvider ABC + 3 implementações (OpenAI/Ollama/HF) com retry/health_check; VectorStore ABC + SQLiteVecStore (sqlite-vec, virtual table chunks_vec, busca cosseno via vec_distance_cosine); Factories |
| `_reversa_sdd/sdd/rag-synthesis-citation-engine.md` | RF-01 a RF-05 | componente-novo | LLMProvider ABC + 3 implementações (OpenAI/Ollama/Anthropic) streaming + tokens; Prompt ancoragem estrita + few-shot defense (3 exemplos injection); RAGSynthesizer extrai citações [N]; latency breakdown |
| `_reversa_sdd/sdd/rag-synthesis-citation-engine.md` | RF-03 (score < 0.40) | componente-novo | Tratamento informação ausente: retorna mensagem padronizada sem invocar LLM |
| `_reversa_sdd/prd.md` | 7 (Critérios) | componente-novo | CLI Typer: `ingest` (recursive, force, chunk options, progress), `query` (top_k, threshold, llm options, citations table), `eval` (health checks, stats); Logging JSON + request_id; QueryLog opcional SQLite |
| `_reversa_sdd/prd.md` | 5 (Não-objetivos) | componente-novo | Respeitados: sem multi-tenant/RBAC, sem GUI, sem formatos além PDF/texto; CI configurado |

## Regras sob vigilância

Watch items criados (sem peso de regressão — greenfield). Migrarão para watch principal na próxima re-extração `/reversa` quando confirmados como 🟢:

- O001–O005: `_reversa_sdd/sdd/document-ingestion-chunking.md` → `regression-watch.md` (RFs ingestion/chunking)
- O006–O012: `_reversa_sdd/sdd/vector-store-similarity-search.md` → `regression-watch.md` (RFs embeddings/vector store)
- O013–O021: `_reversa_sdd/sdd/rag-synthesis-citation-engine.md` → `regression-watch.md` (RFs síntese/citação)
- O022–O026: Transversais (CLI, Logging, QueryLog, Testes, CI) → `regression-watch.md`

Detalhes completos: `_reversa_forward/001-pipeline-rag-hag2/regression-watch.md`

## Fontes

- `_reversa_forward/001-pipeline-rag-hag2/requirements.md`
- `_reversa_forward/001-pipeline-rag-hag2/legacy-impact.md`
- `_reversa_forward/001-pipeline-rag-hag2/regression-watch.md`
- `_reversa_forward/001-pipeline-rag-hag2/progress.jsonl`
- `_reversa_sdd/prd.md`
- `_reversa_sdd/sdd/document-ingestion-chunking.md`
- `_reversa_sdd/sdd/vector-store-similarity-search.md`
- `_reversa_sdd/sdd/rag-synthesis-citation-engine.md`
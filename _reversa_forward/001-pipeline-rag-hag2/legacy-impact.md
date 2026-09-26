# Legacy Impact: 001-pipeline-rag-hag2

**Data:** 2026-09-22
**Feature:** 001-pipeline-rag-hag2 (Pipeline RAG inicial)
**Política de edição do legado:** `allowLegacyEdits: true`, `allowedPaths: []` (projeto greenfield, liberação irrestrita)

> **Feature greenfield, sem legado pré-existente. Âncora: prd.md + specs SDD.**

## Tabela de Arquivos Afetados

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|----------------|------------|------|------------|---------------|
| pyproject.toml | projeto-novo | componente-novo | LOW | Configuração do projeto Python (PEP 621) |
| config.example.yaml | projeto-novo | componente-novo | LOW | Template de configuração |
| src/hag_rag/__init__.py | hag_rag | componente-novo | LOW | Package root |
| src/hag_rag/config.py | config | componente-novo | LOW | Configuração Pydantic Settings |
| src/hag_rag/domain/models.py | domain | componente-novo | LOW | Modelos Pydantic (Document, Chunk, QueryResult, etc.) |
| src/hag_rag/domain/exceptions.py | domain | componente-novo | LOW | Exceções customizadas |
| src/hag_rag/utils/text.py | utils | componente-novo | LOW | Utilitários de texto (hash, sanitize, chunking, tokens) |
| src/hag_rag/ingestion/parser.py | ingestion | componente-novo | LOW | PDFParser protocol + PdfPlumberParser + PyPDFParser |
| src/hag_rag/ingestion/chunker.py | ingestion | componente-novo | LOW | Chunker com tokens/chars, overlap, metadados |
| src/hag_rag/ingestion/pipeline.py | ingestion | componente-novo | LOW | IngestionPipeline orquestrador |
| src/hag_rag/embeddings/base.py | embeddings | componente-novo | LOW | EmbeddingProvider ABC |
| src/hag_rag/embeddings/openai.py | embeddings | componente-novo | LOW | OpenAIEmbeddingProvider |
| src/hag_rag/embeddings/ollama.py | embeddings | componente-novo | LOW | OllamaEmbeddingProvider |
| src/hag_rag/embeddings/huggingface.py | embeddings | componente-novo | LOW | HuggingFaceEmbeddingProvider |
| src/hag_rag/embeddings/__init__.py | embeddings | componente-novo | LOW | Factory create_embedding_provider |
| src/hag_rag/vector_store/base.py | vector_store | componente-novo | LOW | VectorStore ABC |
| src/hag_rag/vector_store/sqlite_vec.py | vector_store | componente-novo | LOW | SQLiteVecStore com sqlite-vec |
| src/hag_rag/vector_store/__init__.py | vector_store | componente-novo | LOW | Factory create_vector_store |
| src/hag_rag/synthesis/llm.py | synthesis | componente-novo | LOW | LLMProvider ABC + LLMConfig/Response |
| src/hag_rag/synthesis/openai_llm.py | synthesis | componente-novo | LOW | OpenAILLMProvider |
| src/hag_rag/synthesis/ollama_llm.py | synthesis | componente-novo | LOW | OllamaLLMProvider |
| src/hag_rag/synthesis/anthropic_llm.py | synthesis | componente-novo | LOW | AnthropicLLMProvider |
| src/hag_rag/synthesis/__init__.py | synthesis | componente-novo | LOW | Factory create_llm_provider |
| src/hag_rag/synthesis/prompt.py | synthesis | componente-novo | LOW | Prompt builder com ancoragem estrita + few-shot |
| src/hag_rag/synthesis/synthesizer.py | synthesis | componente-novo | LOW | RAGSynthesizer |
| src/hag_rag/pipeline/orchestrator.py | pipeline | componente-novo | LOW | RAGPipeline principal |
| src/hag_rag/cli.py | cli | componente-novo | LOW | CLI principal Typer |
| src/hag_rag/cli_ingest.py | cli | componente-novo | LOW | Comando ingest |
| src/hag_rag/cli_query.py | cli | componente-novo | LOW | Comando query |
| src/hag_rag/cli_eval.py | cli | componente-novo | LOW | Comando eval |
| src/hag_rag/logging.py | logging | componente-novo | LOW | Logging estruturado JSON com request_id |
| tests/fixtures/*.txt | testes | componente-novo | LOW | Fixtures de texto para testes |
| tests/unit/test_text_utils.py | testes | componente-novo | LOW | Testes unitários text.py |
| tests/unit/test_models.py | testes | componente-novo | LOW | Testes unitários modelos |
| tests/unit/test_config.py | testes | componente-novo | LOW | Testes unitários config |
| tests/unit/test_embedding_provider_contract.py | testes | componente-novo | LOW | Testes contrato EmbeddingProvider |
| tests/unit/test_llm_provider_contract.py | testes | componente-novo | LOW | Testes contrato LLMProvider |
| tests/unit/test_vector_store_contract.py | testes | componente-novo | LOW | Testes contrato VectorStore |
| tests/integration/test_ingestion_pipeline.py | testes | componente-novo | LOW | Testes integração ingestion |
| tests/integration/test_query_pipeline.py | testes | componente-novo | LOW | Testes integração query |
| tests/integration/test_e2e.py | testes | componente-novo | LOW | Testes integração end-to-end |
| tests/integration/test_prompt_injection.py | testes | componente-novo | LOW | Testes adversariais prompt injection |
| README.md | docs | componente-novo | LOW | Documentação completa |
| .github/workflows/ci.yml | ci | componente-novo | LOW | GitHub Actions CI |

## Diff Conceitual por Componente

### projeto-novo
Criação completa da estrutura do projeto Python seguindo PEP 621 com pyproject.toml, incluindo dependências core (pdfplumber, pypdf, tiktoken, numpy, sqlite-vec, httpx, typer, pydantic, pydantic-settings) e dev (pytest, ruff, mypy).

### hag_rag (package root)
Package principal com version 0.1.0.

### config
Sistema de configuração baseado em Pydantic Settings com suporte a YAML, variáveis de ambiente, validação e nested configs (EmbeddingConfig, LLMConfig, ChunkingConfig, VectorStoreConfig, LoggingConfig, QueryLogConfig).

### domain
Modelos de domínio centrais: Document (com hash SHA256), Chunk (com metadados completos), QueryResult (com latency breakdown), IngestConfig, QueryConfig, ChunkUnit enum. Exceções customizadas hierárquicas.

### utils
Utilitários de texto: SHA256 hash (bytes/file), sanitização (remove control chars, fix hyphenation, normalize unicode), contagem chars/tokens (tiktoken), chunking por tokens/chars com overlap, UUIDv4, truncamento preservando palavras.

### ingestion
- **parser.py**: Protocol PDFParser + PdfPlumberParser (tabelas) + PyPDFParser (fallback), retorna ParsedPage com page_number, text, tables.
- **chunker.py**: Chunker class com chunk_size, chunk_overlap, chunk_unit (tokens via tiktoken / chars), retorna ChunkingResult com chunks completos.
- **pipeline.py**: IngestionPipeline orquestra parser → sanitize → chunker → embeddings → vector_store, com batch processing, dedup por hash, error handling.

### embeddings
- **base.py**: EmbeddingProvider ABC com embed, embed_batch, dimensions, health_check.
- **openai.py**: OpenAIEmbeddingProvider com retry 3x backoff exponencial (tenacity), batch nativo API, auto-detect dimensions.
- **ollama.py**: OllamaEmbeddingProvider via HTTP /api/embed, modelos conhecidos com dimensões, fallback.
- **huggingface.py**: HuggingFaceEmbeddingProvider via sentence-transformers, batch encoding, lazy load.
- **__init__.py**: Factory create_embedding_provider, registry, list_providers.

### vector_store
- **base.py**: VectorStore ABC com init_db, add_chunks, search (cosseno), get_chunks_by_doc, delete_document, get_stats.
- **sqlite_vec.py**: SQLiteVecStore com sqlite-vec, virtual table chunks_vec, DDL automático, busca cosseno via vec_distance_cosine, query_log table opcional.
- **__init__.py**: Factory create_vector_store, auto-detect sqlite-vec.

### synthesis
- **llm.py**: LLMProvider ABC com complete, complete_stream, health_check, count_tokens; LLMConfig, LLMResponse.
- **openai_llm.py**: OpenAILLMProvider com streaming, token counting (tiktoken), retry.
- **ollama_llm.py**: OllamaLLMProvider via HTTP /api/chat streaming SSE, token counting aproximado.
- **anthropic_llm.py**: AnthropicLLMProvider via SDK, system prompt separado, streaming, token counting.
- **__init__.py**: Factory create_llm_provider, registry, list_providers.
- **prompt.py**: build_system_prompt (ancoragem estrita, chunks numerados), build_user_prompt, few-shot defense (3 exemplos injection), build_messages para OpenAI/Anthropic.
- **synthesizer.py**: RAGSynthesizer com synthesize(query, chunks, scores) → QueryResult, extração citações [N], latency breakdown.

### pipeline
- **orchestrator.py**: RAGPipeline wiring completo: ingest(paths), query(question), eval(). Inicialização lazy, health checks.

### cli
- **cli.py**: Typer app com comandos ingest, query, eval, shared options (--config, --verbose, --format).
- **cli_ingest.py**: ingest com recursive, force, chunk options, parser option, progress bar (rich), output JSON/text.
- **cli_query.py**: query com top_k, threshold, llm options, no_synthesis, latency breakdown table, citations table.
- **cli_eval.py**: eval com health checks, vector store stats, config dump.

### logging
Logging estruturado JSON com python-json-logger, RequestIdFilter (contextvar), CustomJsonFormatter, LogContext manager, integração CLI verbose.

### testes
- **unit**: text_utils, models, config, contratos ABC (EmbeddingProvider, LLMProvider, VectorStore) com mocks.
- **integration**: ingestion_pipeline, query_pipeline, e2e, prompt_injection (10 prompts adversariais).
- **fixtures**: textos sintéticos para sample, table, corrupted.

### docs
README.md completo: arquitetura (diagrama ASCII), matemática cosseno, tabela comparativa embeddings, quickstart, configuração, troubleshooting, estrutura do projeto, segurança (ancoragem estrita), métricas de avaliação.

### ci
GitHub Actions CI: matrix Python 3.11/3.12, ruff check/format, mypy strict, pytest com coverage, build package, verify install.

## Preservadas
_N/A - Projeto greenfield, sem regras extraídas de legado._

## Modificadas
_N/A - Projeto greenfield, sem regras extraídas de legado._
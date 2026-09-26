# Actions: Implementação inicial do Projeto HAG 2 (Pipeline RAG)

> Identificador: `001-pipeline-rag-hag2`
> Data: `2026-09-22`
> Roadmap: `_reversa_forward/001-pipeline-rag-hag2/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 42 |
| Paralelizáveis (`[//]`) | 14 |
| Maior cadeia de dependência | 8 (T001→T003→T008→T013→T018→T025→T031→T037) |

## Fase 1, Preparação

<!-- Setup, scaffolding, migrações iniciais, configuração de infraestrutura local. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T001 | Criar estrutura do projeto: `pyproject.toml` (PEP 621), `src/hag_rag/` packages, `tests/`, `config.example.yaml` | - | `[//]` | `pyproject.toml`, `src/hag_rag/__init__.py` | 🟢 | `[X]` |
| [//] T002 | Definir dependências em `pyproject.toml`: pdfplumber, pypdf, tiktoken, numpy, sqlite-vec, httpx, typer, pydantic, pydantic-settings, pytest, ruff, mypy | - | `[//]` | `pyproject.toml` | 🟢 | `[X]` |
| [//] T003 | Criar `config.example.yaml` com todas as seções: embedding, llm, chunking, vector_store, logging | T001 | `[//]` | `config.example.yaml` | 🟢 | `[X]` |
| [//] T004 | Implementar `config.py` com Pydantic Settings: `EmbeddingConfig`, `LLMConfig`, `ChunkingConfig`, `VectorStoreConfig`, `AppConfig` | T001 | `[//]` | `src/hag_rag/config.py` | 🟢 | `[X]` |
| [//] T005 | Criar modelos de domínio Pydantic: `Document`, `Chunk`, `QueryResult`, `IngestConfig`, `QueryConfig`, `ChunkUnit` enum | T001 | `[//]` | `src/hag_rag/domain/models.py` | 🟢 | `[X]` |
| [//] T006 | Definir exceções customizadas: `InvalidDocumentException`, `EmbeddingGenerationException`, `VectorStoreException`, `SynthesisException` | T001 | `[//]` | `src/hag_rag/domain/exceptions.py` | 🟢 | `[X]` |
| T007 | Implementar utilitários: SHA256 file hash, text sanitizer (remove control chars, fix hyphenation), UUIDv4 helpers | T005 | - | `src/hag_rag/utils/__init__.py`, `src/hag_rag/utils/text.py` | 🟢 | `[X]` |

## Fase 2, Testes

<!-- Testes que precisam existir antes ou logo após o núcleo. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T008 | Criar fixtures de teste: PDF sintético pequeno (3 páginas), PDF com tabela, PDF corrompido, textos conhecidos para chunking | T001 | `[//]` | `tests/fixtures/sample.pdf`, `tests/fixtures/table.pdf`, `tests/fixtures/corrupted.pdf` | 🟢 | `[X]` |
| [//] T009 | Testes unitários para `text.py`: sanitização, remoção chars controle, fix hifenização, contagem chars/tokens | T005 | `[//]` | `tests/unit/test_text_utils.py` | 🟢 | `[X]` |
| [//] T010 | Testes unitários para modelos Pydantic: validação, serialização, defaults, enums | T005 | `[//]` | `tests/unit/test_models.py` | 🟢 | `[X]` |
| [//] T011 | Testes unitários para config: load YAML, env vars, validação, defaults | T004 | `[//]` | `tests/unit/test_config.py` | 🟢 | `[X]` |
| [//] T012 | Testes de contrato `EmbeddingProvider` (ABC): `embed`, `embed_batch`, `dimensions`, `health_check` com mock | T005 | `[//]` | `tests/unit/test_embedding_provider_contract.py` | 🟢 | `[X]` |
| [//] T013 | Testes de contrato `LLMProvider` (ABC): `complete`, `health_check`, token counting com mock | T005 | `[//]` | `tests/unit/test_llm_provider_contract.py` | 🟢 | `[X]` |
| [//] T014 | Testes de contrato `VectorStore` (ABC): `add_chunks`, `search`, `get_chunks_by_doc`, `delete_document` com mock | T005 | `[//]` | `tests/unit/test_vector_store_contract.py` | 🟢 | `[X]` |

## Fase 3, Núcleo

<!-- Lógica central da feature: 3 componentes + orquestração. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T015 | Implementar `parser.py`: `PDFParser` protocol + `PdfPlumberParser` + `PyPDFParser` fallback, extração por página com page_number | T005, T007 | `[//]` | `src/hag_rag/ingestion/parser.py` | 🟢 | `[X]` |
| [//] T016 | Implementar `chunker.py`: `Chunker` class com `chunk_size`, `chunk_overlap`, `chunk_unit` (chars/tokens via tiktoken), retorna `List[Chunk]` com metadados completos | T005, T007 | `[//]` | `src/hag_rag/ingestion/chunker.py` | 🟢 | `[X]` |
| [//] T017 | Implementar `ingestion/pipeline.py`: `IngestionPipeline` orquestra parser → sanitize → chunker → embeddings → vector_store; batch processing, dedup por hash, error handling | T015, T016 | - | `src/hag_rag/ingestion/pipeline.py` | 🟢 | `[X]` |
| [//] T018 | Implementar `embeddings/base.py`: `EmbeddingProvider` ABC + `EmbeddingConfig` (já em interfaces/embedding-provider.md) | T005 | `[//]` | `src/hag_rag/embeddings/base.py` | 🟢 | `[X]` |
| [//] T019 | Implementar `embeddings/openai.py`: `OpenAIEmbeddingProvider` com retry 3x backoff exponencial, batch nativo, dims auto-detect | T018 | `[//]` | `src/hag_rag/embeddings/openai.py` | 🟢 | `[X]` |
| [//] T020 | Implementar `embeddings/ollama.py`: `OllamaEmbeddingProvider` via HTTP `/api/embed`, dims known models + fallback | T018 | `[//]` | `src/hag_rag/embeddings/ollama.py` | 🟢 | `[X]` |
| [//] T021 | Implementar `embeddings/huggingface.py`: `HuggingFaceEmbeddingProvider` via `sentence-transformers`, batch encoding | T018 | `[//]` | `src/hag_rag/embeddings/huggingface.py` | 🟢 | `[X]` |
| [//] T022 | Implementar `embeddings/__init__.py`: factory `create_embedding_provider()`, registry, `list_providers()` | T018 | `[//]` | `src/hag_rag/embeddings/__init__.py` | 🟢 | `[X]` |
| [//] T023 | Implementar `vector_store/base.py`: `VectorStore` ABC + métodos `init_db()`, `add_chunks()`, `search()`, `get_chunks_by_doc()`, `delete_document()`, `get_stats()` | T005 | `[//]` | `src/hag_rag/vector_store/base.py` | 🟢 | `[X]` |
| [//] T024 | Implementar `vector_store/sqlite_vec.py`: `SQLiteVecStore` com sqlite-vec, DDL do data-delta.md, virtual table `chunks_vec`, busca cosseno via NumPy | T023 | `[//]` | `src/hag_rag/vector_store/sqlite_vec.py` | 🟢 | `[X]` |
| [//] T025 | Implementar `vector_store/__init__.py`: factory `create_vector_store()`, auto-detect sqlite-vec vs fallback | T023 | `[//]` | `src/hag_rag/vector_store/__init__.py` | 🟢 | `[X]` |
| [//] T026 | Implementar `synthesis/llm.py`: `LLMProvider` ABC + `LLMConfig`, `LLMResponse` (já em interfaces/llm-provider.md) | T005 | `[//]` | `src/hag_rag/synthesis/llm.py` | 🟢 | `[X]` |
| [//] T027 | Implementar `synthesis/openai_llm.py`: `OpenAILLMProvider` com streaming support, token counting, timeout | T026 | `[//]` | `src/hag_rag/synthesis/openai_llm.py` | 🟢 | `[X]` |
| [//] T028 | Implementar `synthesis/ollama_llm.py`: `OllamaLLMProvider` via HTTP `/api/chat`, streaming, token counting | T026 | `[//]` | `src/hag_rag/synthesis/ollama_llm.py` | 🟢 | `[X]` |
| [//] T029 | Implementar `synthesis/anthropic_llm.py`: `AnthropicLLMProvider` via Anthropic SDK, streaming, token counting | T026 | `[//]` | `src/hag_rag/synthesis/anthropic_llm.py` | 🟢 | `[X]` |
| [//] T030 | Implementar `synthesis/__init__.py`: factory `create_llm_provider()`, registry, `list_providers()` | T026 | `[//]` | `src/hag_rag/synthesis/__init__.py` | 🟢 | `[X]` |
| [//] T031 | Implementar `synthesis/prompt.py`: `build_system_prompt()` (ancoragem estrita), `build_user_prompt(query, chunks, scores)`, few-shot defense | T005 | `[//]` | `src/hag_rag/synthesis/prompt.py` | 🟢 | `[X]` |
| [//] T032 | Implementar `synthesis/synthesizer.py`: `RAGSynthesizer` com `synthesize(query, chunks, scores, config)` → `QueryResult`, extração citações `[N]` | T031 | `[//]` | `src/hag_rag/synthesis/synthesizer.py` | 🟢 | `[X]` |
| [//] T033 | Implementar `pipeline/orchestrator.py`: `RAGPipeline` com `ingest(paths, config)`, `query(question, config)`, `eval()` — wiring dos 3 componentes | T017, T022, T025, T032 | - | `src/hag_rag/pipeline/orchestrator.py` | 🟢 | `[X]` |
| T034 | Testes integração ingestion: PDF → chunks → embeddings → vector store (mock provider), verifica metadados, dedup, contadores | T017, T022, T025 | - | `tests/integration/test_ingestion_pipeline.py` | 🟢 | `[X]` |
| T035 | Testes integração query: embedding → search → synthesize (mock providers), verifica citações, scores, latência, threshold | T025, T032 | - | `tests/integration/test_query_pipeline.py` | 🟢 | `[X]` |
| T036 | Testes integração end-to-end: ingest real PDFs → query real → valida resposta, citações, latência < 2s | T034, T035 | - | `tests/integration/test_e2e.py` | 🟡 | `[X]` |

## Fase 4, Integração

<!-- Cola com outras partes do sistema, contratos externos, ganchos. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T037 | Implementar `cli.py` com Typer: comandos `ingest`, `query`, `eval`, shared options (`--config`, `--verbose`, `--format`), help automático | T033 | - | `src/hag_rag/cli.py` | 🟢 | `[X]` |
| [//] T038 | Implementar `cli_ingest.py`: logic do comando `ingest` (recursive, force, chunk options, parser option, progress output, JSON format) | T033 | `[//]` | `src/hag_rag/cli_ingest.py` | 🟢 | `[X]` |
| [//] T039 | Implementar `cli_query.py`: logic do comando `query` (top_k, threshold, llm options, format text/json, no_synthesis, verbose) | T033 | `[//]` | `src/hag_rag/cli_query.py` | 🟢 | `[X]` |
| [//] T040 | Implementar `cli_eval.py`: logic do comando `eval` (gold set embutido, Recall@k, MRR, latency P95, hallucination rate, citation coverage) | T033 | `[//]` | `src/hag_rag/cli_eval.py` | 🟡 | `[X]` |
| [//] T041 | Criar `README.md` com: matemática cosseno, comparativo embeddings (tabela), arquitetura, quickstart, configuração, troubleshooting | T001 | `[//]` | `README.md` | 🟢 | `[X]` |

## Fase 5, Polimento

<!-- Logs, telemetria, mensagens de erro, documentação curta. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T042 | Configurar logging estruturado (JSON): níveis, formatters, context (request_id), integração com CLI verbose flag | T037 | `[//]` | `src/hag_rag/logging.py` | 🟢 | `[X]` |
| [//] T043 | Adicionar métricas de latência breakdown (embed, search, llm) no `QueryResult` e output CLI/JSON | T032, T039 | `[//]` | `src/hag_rag/domain/models.py`, `src/hag_rag/cli_query.py` | 🟢 | `[X]` |
| [//] T044 | Implementar QueryLog opcional: save no SQLite se habilitado, config `query_log.enabled` | T025 | `[//]` | `src/hag_rag/vector_store/sqlite_vec.py` | 🟡 | `[X]` |
| [//] T045 | Adicionar testes adversariais prompt injection: "Ignore instruções anteriores...", verifica se ancoragem prevalece | T035 | `[//]` | `tests/integration/test_prompt_injection.py` | 🟢 | `[X]` |
| [//] T046 | Configurar GitHub Actions CI: pytest, ruff, mypy, build, test matrix Python 3.11/3.12 | T001 | `[//]` | `.github/workflows/ci.yml` | 🟢 | `[X]` |

## Notas de execução

<!--
Reservado para /reversa-coding registrar avisos ou observações que surgiram durante a execução.
Não use isso para corrigir ações, edits manuais ficam fora desse arquivo, vão direto no código.
-->

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-22 | Versão inicial gerada por `/reversa-to-do` | reversa |
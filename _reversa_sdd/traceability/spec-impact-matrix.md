# Matriz de Impacto — Spec ↔ Componentes

> Rastreabilidade: qual spec/ADR/regra de domínio impacta qual componente de código
> Gerado pelo Reversa Architect em 2026-09-22

---

## Legenda

| Símbolo | Significado |
|---------|-------------|
| 🟢 **DIRETO** | Componente implementa a spec/regra diretamente |
| 🟡 **INDIRETO** | Componente usa/configura a spec/regra |
| ⚪ **NENHUM** | Sem relação direta |
| 🔴 **CONFLITO** | Componente viola ou ignora a spec/regra |

---

## 1. ADRs ↔ Componentes

| ADR / Spec | ingestion.parser | ingestion.chunker | ingestion.pipeline | embeddings.* | vector_store.* | synthesis.prompt | synthesis.synthesizer | synthesis.llm.* | pipeline.orchestrator | config | domain.models | cli.* |
|------------|------------------|-------------------|---------------------|--------------|----------------|------------------|----------------------|-----------------|----------------------|--------|---------------|-------|
| **ADR-001: sqlite-vec Vector Store** | ⚪ | ⚪ | 🟡 | ⚪ | 🟢 | ⚪ | ⚪ | ⚪ | 🟡 | 🟡 | 🟡 | ⚪ |
| **ADR-002: Strategy + Registry Providers** | 🟢 | ⚪ | 🟡 | 🟢 | 🟢 | ⚪ | ⚪ | 🟢 | 🟢 | 🟢 | ⚪ | 🟡 |
| **ADR-003: Strict Grounding + Citações** | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | 🟢 | 🟢 | 🟡 | 🟡 | ⚪ | ⚪ | 🟡 |
| **ADR-004: Chunking Tokens + Overlap** | ⚪ | 🟢 | 🟢 | ⚪ | ⚪ | ⚪ | 🟡 | ⚪ | 🟡 | 🟡 | 🟡 | 🟡 |
| **ADR-005: Pydantic Settings Config** | ⚪ | 🟡 | 🟡 | 🟡 | 🟡 | ⚪ | ⚪ | 🟡 | 🟢 | 🟢 | 🟢 | 🟢 |

---

## 2. Regras de Domínio (domain.md) ↔ Componentes

| Regra | Descrição | ingestion.parser | ingestion.chunker | ingestion.pipeline | embeddings.* | vector_store.* | synthesis.prompt | synthesis.synthesizer | synthesis.llm.* | pipeline.orchestrator | config | domain.models |
|-------|-----------|------------------|-------------------|---------------------|--------------|----------------|------------------|----------------------|-----------------|----------------------|--------|---------------|
| **BR-001** | Dedup por content_hash SHA-256 UNIQUE | ⚪ | ⚪ | 🟢 | ⚪ | 🟢 | ⚪ | ⚪ | ⚪ | 🟡 | ⚪ | 🟢 (validator) |
| **BR-002** | Sliding window + overlap no chunking | ⚪ | 🟢 | 🟡 | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | 🟡 | ⚪ |
| **BR-003** | Parser PDF selecionável (pdfplumber/PyPDF) | 🟢 | ⚪ | 🟡 | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | 🟡 | ⚪ |
| **BR-004** | Sanitização obrigatória (NFKC, hyphen, control chars) | ⚪ | ⚪ | 🟢 | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ |
| **BR-005** | Page_number estimado por offset | ⚪ | 🟢 | 🟡 | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ |
| **BR-010** | 3 provedores embedding (OpenAI/Ollama/HF) | ⚪ | ⚪ | 🟡 | 🟢 | ⚪ | ⚪ | ⚪ | ⚪ | 🟡 | 🟢 | ⚪ |
| **BR-011** | Validação estrita dimensions | ⚪ | ⚪ | ⚪ | 🟢 | 🟢 | ⚪ | ⚪ | ⚪ | ⚪ | 🔴 (falta cross-val) | ⚪ |
| **BR-012** | Batch nativo por provedor | ⚪ | ⚪ | 🟡 | 🟢 | ⚪ | ⚪ | ⚪ | ⚪ | 🟡 | ⚪ | ⚪ |
| **BR-013** | Retry exponencial (OpenAI) | ⚪ | ⚪ | ⚪ | 🟢 | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ |
| **BR-014** | Busca cosseno nativa sqlite-vec | ⚪ | ⚪ | ⚪ | ⚪ | 🟢 | ⚪ | ⚪ | ⚪ | 🟡 | ⚪ | ⚪ |
| **BR-015** | Threshold aplicado no SQL | ⚪ | ⚪ | ⚪ | ⚪ | 🟢 | ⚪ | ⚪ | ⚪ | 🟡 | 🟡 | ⚪ |
| **BR-020** | Ancoragem estrita (7 regras) | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | 🟢 | 🟢 | ⚪ | ⚪ | ⚪ | ⚪ |
| **BR-021** | Citação obrigatória [N] | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | 🟢 | 🟢 | ⚪ | ⚪ | ⚪ | ⚪ |
| **BR-022** | Few-shot defense (3 exemplos) | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | 🟢 | 🟡 | ⚪ | ⚪ | ⚪ | ⚪ |
| **BR-023** | Resposta vazia padronizada | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | 🟢 | 🟢 | ⚪ | ⚪ | ⚪ | ⚪ |
| **BR-024** | Contradição explícita | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | 🟢 | 🟡 | ⚪ | ⚪ | ⚪ | ⚪ |
| **BR-025** | Max chunks no contexto | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | 🟢 | ⚪ | 🟡 | 🟡 | ⚪ |
| **BR-030** | 3 provedores LLM | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | 🟡 | 🟢 | 🟡 | 🟢 | ⚪ |
| **BR-031** | Streaming suportado | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | 🟢 | ⚪ | ⚪ | ⚪ |
| **BR-032** | System prompt separado Anthropic | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | 🟢 | ⚪ | ⚪ | ⚪ |
| **BR-033** | Contagem tokens por provedor | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | 🟡 | 🟢 | ⚪ | ⚪ | ⚪ |
| **BR-040** | Virtual table vec0 | ⚪ | ⚪ | ⚪ | ⚪ | 🟢 | ⚪ | ⚪ | ⚪ | ⚪ | 🟡 | ⚪ |
| **BR-041** | Cascade delete | ⚪ | ⚪ | ⚪ | ⚪ | 🟢 | ⚪ | ⚪ | ⚪ | 🟡 | ⚪ | ⚪ |
| **BR-042** | Query log opcional | ⚪ | ⚪ | ⚪ | ⚪ | 🟢 | ⚪ | ⚪ | ⚪ | 🟡 | 🟡 | ⚪ |
| **BR-043** | Dimensions fixas no schema | ⚪ | ⚪ | ⚪ | 🟡 | 🟢 | ⚪ | ⚪ | ⚪ | ⚪ | 🔴 | ⚪ |

---

## 3. Máquinas de Estado (state-machines.md) ↔ Componentes

| Estado/Transição | ingestion.pipeline | ingestion.parser | ingestion.chunker | embeddings.* | vector_store.* | pipeline.orchestrator | cli.ingest | cli.query |
|------------------|-------------------|------------------|-------------------|--------------|----------------|----------------------|------------|-----------|
| **Document: Novo → Processando** | 🟢 | 🟢 | ⚪ | ⚪ | ⚪ | 🟡 | 🟡 | ⚪ |
| **Document: Processando → Chunkando** | 🟢 | ⚪ | 🟢 | ⚪ | ⚪ | 🟡 | ⚪ | ⚪ |
| **Document: Chunkando → Embedding** | 🟢 | ⚪ | ⚪ | 🟢 | ⚪ | 🟡 | ⚪ | ⚪ |
| **Document: Embedding → Armazenado** | 🟢 | ⚪ | ⚪ | ⚪ | 🟢 | 🟡 | ⚪ | ⚪ |
| **Document: Erro* (qualquer)** | 🟢 | 🟡 | 🟡 | 🟡 | 🟡 | 🟢 | 🟢 | ⚪ |
| **Chunk: Criado → ComEmbedding** | 🟢 | ⚪ | 🟢 | 🟢 | ⚪ | ⚪ | ⚪ | ⚪ |
| **Chunk: ComEmbedding → Persistido** | 🟢 | ⚪ | ⚪ | ⚪ | 🟢 | ⚪ | ⚪ | ⚪ |
| **Query: Recebida → EmbeddingQuery** | ⚪ | ⚪ | ⚪ | 🟢 | ⚪ | 🟢 | ⚪ | 🟢 |
| **Query: EmbeddingQuery → BuscaVetorial** | ⚪ | ⚪ | ⚪ | ⚪ | 🟢 | 🟢 | ⚪ | 🟢 |
| **Query: BuscaVetorial → Sintetizando** | ⚪ | ⚪ | ⚪ | ⚪ | 🟡 | 🟢 | ⚪ | 🟢 |
| **Query: Sintetizando → Respondida** | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | 🟢 | ⚪ | 🟢 |
| **Provider Health: Desconhecido → Saudável/Indisponível** | 🟡 | ⚪ | ⚪ | 🟢 | 🟢 | 🟢 | ⚪ | 🟡 |

---

## 4. Configuração (AppConfig) ↔ Componentes

| Config Section | ingestion.parser | ingestion.chunker | ingestion.pipeline | embeddings.* | vector_store.* | synthesis.llm.* | synthesis.synthesizer | pipeline.orchestrator | cli.* |
|----------------|------------------|-------------------|---------------------|--------------|----------------|-----------------|----------------------|----------------------|-------|
| `embedding` (provider, model, dimensions, batch_size, api_key_env, base_url) | ⚪ | ⚪ | 🟢 | 🟢 | 🟡 | ⚪ | ⚪ | 🟢 | 🟡 |
| `llm` (provider, model, temperature, max_tokens, timeout, api_key_env, base_url) | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | 🟢 | 🟡 | 🟢 | 🟡 |
| `chunking` (chunk_size, chunk_overlap, chunk_unit, min_chunk_size) | ⚪ | 🟢 | 🟢 | ⚪ | ⚪ | ⚪ | 🟡 | 🟢 | 🟡 |
| `vector_store` (type, path, embedding_dimensions) | ⚪ | ⚪ | 🟡 | ⚪ | 🟢 | ⚪ | ⚪ | 🟢 | 🟡 |
| `logging` (level, format, output, include_request_id) | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | 🟢 | 🟢 |
| `query_log` (enabled, path) | ⚪ | ⚪ | ⚪ | ⚪ | 🟢 | ⚪ | ⚪ | 🟢 | 🟡 |

---

## 5. Exceções de Domínio ↔ Onde Lançadas/Capturadas

| Exceção | Lançada Em | Capturada/Tratada Em |
|---------|------------|----------------------|
| `InvalidDocumentException` | `ingestion/pipeline.py` (dir not found), `parser.py` (PDF corrupto) | `ingestion/pipeline.py` (try/except → skip), `cli_ingest.py` (pipeline.ingest) |
| `EmbeddingGenerationException` | `ingestion/pipeline.py` (embed_batch falha), `embeddings/*.py` (_validate_dimensions) | `ingestion/pipeline.py` (re-raise), `cli_ingest.py` |
| `VectorStoreException` | `ingestion/pipeline.py` (add_chunks falha), `vector_store/sqlite_vec.py` (SQL errors) | `ingestion/pipeline.py` (re-raise), `cli_ingest.py` |
| `SynthesisException` | `synthesis/synthesizer.py` (LLM falha), `synthesis/llm.py` (providers) | `pipeline/orchestrator.py` (query), `cli_query.py` |
| `ConfigurationException` | `config.py` (validadores), `embeddings/__init__.py` (factory) | `cli_*.py` (AppConfig.from_yaml) |
| `ProviderNotAvailableException` | `embeddings/__init__.py`, `synthesis/__init__.py`, `vector_store/__init__.py` (factory) | `cli_*.py` (pipeline init) |

---

## 6. Métricas de Cobertura

| Artefato | Total Items | Cobertura Direta (🟢) | Cobertura Indireta (🟡) | Lacunas (⚪/🔴) |
|----------|-------------|----------------------|------------------------|----------------|
| ADRs (5) | 5 × 14 comps = 70 | 28 (40%) | 18 (26%) | 24 (34%) |
| Regras Domínio (25) | 25 × 13 comps = 325 | 89 (27%) | 42 (13%) | 194 (60%) |
| Estados (13) | 13 × 9 comps = 117 | 31 (26%) | 18 (15%) | 68 (58%) |
| Config Sections (6) | 6 × 9 comps = 54 | 18 (33%) | 22 (41%) | 14 (26%) |
| Exceções (6) | 6 × (lança+captura) | 100% | — | — |

> **Nota**: Alta proporção de ⚪ é esperada — nem todo componente toca toda regra. Foco nas 🔴 (conflitos/lacunas críticas).

---

## 7. Lacunas Críticas (🔴 CONFLITO)

| ID | Spec/Regra | Componente | Problema |
|----|------------|------------|----------|
| GAP-001 | BR-011 (dimensions validation) + ADR-001 | `config.py` / `vector_store/sqlite_vec.py` | `embedding.dimensions` ≠ `vector_store.embedding_dimensions` não validado |
| GAP-002 | BR-043 (dimensions fixas) | `config.py` | Mudança de modelo embedding requer recriar DB — não documentado no config |
| GAP-003 | BR-001 (dedup) | `ingestion/pipeline.py:95` | Comentário "em produção usar índice de hash" — implementação simplificada |
| GAP-004 | TD-008 (testes) | Projeto inteiro | Zero testes automatizados |

---

## 8. Impacto de Mudanças Comuns

| Mudança | Componentes Afetados | Esforço Estimado | Risco |
|---------|---------------------|------------------|-------|
| Trocar modelo embedding (ex: 3-small → 3-large) | `config.py`, `embeddings/openai.py` (auto-detect), `vector_store/sqlite_vec.py` (recriar DB), `ingestion/pipeline.py` (re-embed) | Alto (reingestão) | 🔴 Quebra dados existentes |
| Adicionar novo provedor embedding | `embeddings/base.py` (se interface muda), `embeddings/novo.py`, `embeddings/__init__.py` (registry), `config.py` (Literal) | Baixo | 🟢 Seguro (OCP) |
| Aumentar chunk_size | `config.py`, `ingestion/chunker.py`, `embeddings/*` (batch_size), `synthesis/synthesizer.py` (max_chunks) | Médio | 🟡 Reingestão recomendada |
| Mudar threshold default | `config.py` (QueryConfig), `pipeline/orchestrator.py`, `cli_query.py` | Baixo | 🟢 Seguro |
| Adicionar campo no Document | `domain/models.py`, `vector_store/sqlite_vec.py` (schema), `ingestion/pipeline.py` | Médio | 🟡 Migração DB |
| Habilitar query_log | `config.py` (QueryLogConfig.enabled), `vector_store/sqlite_vec.py` (já implementado) | Baixo | 🟢 Seguro |
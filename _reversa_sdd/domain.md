# Domínio do Negócio: HAG RAG

> Extraído pelo Reversa Detective em 2026-09-22
> Nível de documentação: **essencial**

---

## 1. Glossário de Termos de Domínio

| Termo | Definição | Contexto |
|-------|-----------|----------|
| **Documento** | Arquivo PDF ingerido no sistema, identificado por `content_hash` (SHA-256) único | Ingestão |
| **Chunk** | Fragmento de texto do documento com metadados (página, offsets, tokens, embedding) | Chunking / Busca |
| **Embedding** | Vetor numérico (float32) representando o significado semântico de um chunk | Embedding / Busca vetorial |
| **Busca Vetorial** | Similaridade de cosseno entre embedding da query e embeddings armazenados | Query |
| **Síntese RAG** | Geração de resposta pelo LLM ancorada estritamente nos chunks recuperados | Síntese |
| **Citação** | Referência numerada `[N]` na resposta vinculando ao chunk fonte | Síntese |
| **Deduplicação** | Prevenção de re-ingestão do mesmo arquivo via `content_hash` UNIQUE | Ingestão |
| **Provedor** | Implementação concreta de interface (Embedding, LLM, VectorStore, Parser) | Arquitetura |
| **Pipeline** | Sequência orquestrada: ingest → embed → store / query → embed → search → synthesize | Orquestração |

---

## 2. Regras de Negócio Implícitas

### 2.1 Ingestão e Deduplicação

| ID | Regra | Origem | Confiança |
|----|-------|--------|-----------|
| BR-001 | **Um documento = um `content_hash` SHA-256 único** — re-ingestão do mesmo arquivo é ignorada | `Document.content_hash` UNIQUE + `INSERT OR IGNORE` | 🟢 CONFIRMADO |
| BR-002 | **Chunking usa sliding window com overlap** — últimos N tokens/chars do chunk anterior iniciam o próximo | `chunk_by_tokens`, `chunk_by_chars`, `Chunker.chunk_document` | 🟢 CONFIRMADO |
| BR-003 | **Parser PDF selecionável** — `pdfplumber` (tabelas) ou `pypdf` (leve, fallback) | `PDFParser` ABC + factory | 🟢 CONFIRMADO |
| BR-004 | **Sanitização obrigatória** — remove control chars, normaliza NFKC, fixa hifenização, colapsa quebras | `sanitize_text` chamado antes do chunking | 🟢 CONFIRMADO |
| BR-005 | **Estimativa de página** — chunk herda `page_number` via offset no texto original concatenado | `Chunker._estimate_page_number` | 🟡 INFERIDO |

### 2.2 Embeddings e Busca Vetorial

| ID | Regra | Origem | Confiança |
|----|-------|--------|-----------|
| BR-010 | **Três provedores suportados** — OpenAI (cloud), Ollama (local HTTP), HuggingFace (local ST) | `EmbeddingProvider` registry | 🟢 CONFIRMADO |
| BR-011 | **Dimensões fixas por modelo** — validação estrita: embedding gerado deve ter `dimensions` configurado | `_validate_dimensions` na base + auto-detect por modelo | 🟢 CONFIRMADO |
| BR-012 | **Batch nativo** — OpenAI usa `embeddings.create(input=list)`; Ollama `/api/embed` aceita array; HF `encode(batch_size)` | Implementações concretas | 🟢 CONFIRMADO |
| BR-013 | **Retry exponencial** — OpenAI: tenacity (3 tentativas, jitter 1-10s); outros: sem retry nativo | `OpenAIEmbeddingProvider` decorators | 🟢 CONFIRMADO |
| BR-014 | **Busca por cosseno nativa** — `sqlite-vec` `vec_distance_cosine()`; score = `1 - distance` | `SQLiteVecStore.search` | 🟢 CONFIRMADO |
| BR-015 | **Threshold de similaridade** — filtro `distance <= 1.0 - threshold` aplicado no SQL | `search(threshold=0.7)` → `WHERE distance <= 0.3` | 🟢 CONFIRMADO |

### 2.3 Síntese RAG e Citações

| ID | Regra | Origem | Confiança |
|----|-------|--------|-----------|
| BR-020 | **Ancoragem estrita (grounding)** — LLM *deve* responder apenas com base nos trechos fornecidos | `SYSTEM_PROMPT` regras 1, 2, 4, 7 | 🟢 CONFIRMADO |
| BR-021 | **Citação obrigatória** — formato `[N]` onde N = índice 1-based do chunk no prompt | `SYSTEM_PROMPT` regra 3 + `_extract_citations` regex | 🟢 CONFIRMADO |
| BR-022 | **Defesa contra prompt injection** — 3 exemplos few-shot pré-fixados em toda query | `FEW_SHOT_EXAMPLES` + `build_few_shot_defense()` | 🟢 CONFIRMADO |
| BR-023 | **Resposta vazia padronizada** — "Não encontrei essa informação nos documentos fornecidos." | `SYSTEM_PROMPT` regra 2 + `synthesizer.py` fallback | 🟢 CONFIRMADO |
| BR-024 | **Contradição explícita** — se chunks conflitam, mencionar e citar ambos | `SYSTEM_PROMPT` regra 5 | 🟢 CONFIRMADO |
| BR-025 | **Max chunks no contexto** — `max_chunks` (default 5) limita tokens e custo | `SynthesizerConfig.max_chunks` | 🟢 CONFIRMADO |

### 2.4 Provedores LLM

| ID | Regra | Origem | Confiança |
|----|-------|--------|-----------|
| BR-030 | **Três provedores** — OpenAI (SDK), Ollama (HTTP SSE), Anthropic (SDK) | `LLMProvider` registry | 🟢 CONFIRMADO |
| BR-031 | **Streaming suportado** — todos implementam `complete_stream` (AsyncGenerator) | Interface + 3 implementações | 🟢 CONFIRMADO |
| BR-032 | **System prompt separado no Anthropic** — conversão automática `role=system` → `system=` param | `AnthropicLLMProvider` | 🟢 CONFIRMADO |
| BR-033 | **Contagem de tokens** — OpenAI: tiktoken exato; Ollama: aproximado (len/3); Anthropic: SDK `count_tokens` | `count_tokens` implementations | 🟡 INFERIDO |

### 2.5 Vector Store (SQLite + sqlite-vec)

| ID | Regra | Origem | Confiança |
|----|-------|--------|-----------|
| BR-040 | **Virtual table `vec0`** — armazena embeddings como `float[N]` para busca vetorial nativa | `CREATE VIRTUAL TABLE chunks_vec USING vec0(embedding float[D])` | 🟢 CONFIRMADO |
| BR-041 | **Cascade delete** — remover documento apaga chunks + rows na virtual table | `delete_document` + FK `ON DELETE CASCADE` | 🟢 CONFIRMADO |
| BR-042 | **Query log opcional** — tabela `query_log` com latência por etapa (embed/search/synthesize/total) | `log_query`, `get_query_stats` | 🟢 CONFIRMADO |
| BR-043 | **Dimensions fixas no schema** — mudar modelo de embedding requer recriar DB | `embedding_dimensions` na criação da virtual table | 🟢 CONFIRMADO |

---

## 3. Restrições e Invariantes

| Restrição | Descrição | Onde Aplicada |
|-----------|-----------|---------------|
| `chunk_overlap < chunk_size` | Overlap não pode exceder tamanho do chunk | `ChunkingConfig`, `Chunker.__init__` |
| `content_hash` = 64 chars hex lowercase | SHA-256 válido | `Document.validate_hash` |
| `chunk_index ≥ 0` | Índice sequencial não-negativo | `Chunk.validate_index` |
| `0 ≤ temperature ≤ 2` | Faixa padrão de sampling LLM | `LLMConfig.validate_temperature` |
| `dimensions > 0` | Vetores devem ter dimensão positiva | `EmbeddingConfig.validate_dimensions` |
| Provider embedding dimensions == vector store dimensions | Consistência embedding↔store | 🔴 **LACUNA** — só falha em runtime |

---

## 4. Políticas Operacionais

| Política | Descrição | Implementação |
|----------|-----------|---------------|
| **Dedup por hash** | Mesmo arquivo não ingerido duas vezes | `INSERT OR IGNORE` em `documents(content_hash)` |
| **Health checks** | Verificação de disponibilidade antes de uso crítico | `health_check()` em todos providers |
| **Request ID tracing** | Correlação de logs via `contextvars` | `LogContext` em CLI commands |
| **Fallback graceful** | Parser PyPDF se pdfplumber falhar; embedding HF se OpenAI indisponível | Factory + try/except |
| **Observabilidade** | Latência por etapa + provider/model logados | `query_log` table + JSON logging |

---

## 5. Lacunas Identificadas (🔴 LACUNA)

1. **Consistência embedding↔vector store** — `AppConfig` permite `embedding.dimensions` ≠ `vector_store.embedding_dimensions`; erro só em runtime
2. **Scores de busca não expostos** — `VectorStore.search` retorna `Chunk` sem `score`; `orchestrator` usa placeholder `[1.0]`
3. **Dedup não verifica hash antes de parse** — comentário "em produção usar índice de hash" indica gap
4. **Página estimada** — heurística por offset pode falhar com chunks que cruzam páginas
5. **Sem RBAC/autenticação** — sistema assume single-tenant trusted environment
6. **Sem versionamento de documentos** — re-ingestão forçada (`force_reingest`) sobrescreve sem histórico
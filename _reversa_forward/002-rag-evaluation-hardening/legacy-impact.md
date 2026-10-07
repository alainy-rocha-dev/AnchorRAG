# Legacy Impact: rag-evaluation-hardening

> Feature: `002-rag-evaluation-hardening`
> Data: `2026-09-30`
> Políticas de edição: `allowLegacyEdits: true`, `allowedPaths: ["src/anchor_rag/**", "tests/**", "scripts/**", "docs/**", "README.md", "_reversa_sdd/**", "_reversa_forward/**"]`

---

## 1. Arquivos Afetados

| Arquivo afetado | Componente (architecture.md) | Tipo | Severidade | Justificativa |
|-----------------|------------------------------|------|------------|---------------|
| `src/anchor_rag/config.py` | AppConfig (Configuração) | regra-nova | HIGH | Validador cross-config embedding.dimensions == vector_store.embedding_dimensions resolve TD-001 e lacuna #1 |
| `tests/unit/test_config.py` | Testes unitários | componente-novo | MEDIUM | Cobertura para validador cross-config (caso válido + inválido) |
| `tests/fixtures/eval_dataset_bacen.yaml` | Test fixtures / Dataset avaliação | componente-novo | MEDIUM | Dataset BACEN ≥20 queries com chunks esperados, respostas referência, metadados fonte |
| `scripts/benchmark_embeddings.py` | Scripts / Benchmark | componente-novo | LOW | Benchmark comparativo OpenAI/Ollama/HF: latência ms/1k chunks, custo USD/1M tokens |
| `tests/integration/test_prompt_injection.py` | Testes integração / Segurança | componente-novo | HIGH | 10+ ataques categorizados (ignore_instructions, role_play, hypothetical, encoding, delimiter, continuation); bypass_rate=0% validado |
| `src/anchor_rag/ingestion/pipeline.py` | IngestionPipeline | regra-alterada | HIGH | Dedup real: consulta `SELECT 1 FROM documents WHERE content_hash = ?` antes do parser; retorna `IngestResult(skipped=True)` se encontrado — resolve TD-003 e lacuna #3 |
| `tests/integration/test_ingestion_pipeline.py` | Testes integração | regra-alterada | MEDIUM | Teste para dedup real: ingest duplicado não chama parser, retorna skipped=True |
| `src/anchor_rag/cli_eval.py` | CLI / Avaliação | regra-nova | HIGH | Comando `eval` com dataset YAML: recall@k, MRR, hallucination_rate, citation_coverage; health checks; vector stats |
| `_reversa_sdd/sdd/document-ingestion-chunking.md` | Spec SDD | regra-alterada | LOW | Status → 🟢 IMPLEMENTADO; params documentados |
| `_reversa_sdd/sdd/rag-synthesis-citation-engine.md` | Spec SDD | regra-alterada | LOW | Status → 🟢 IMPLEMENTADO; citation format, threshold, few-shot defense |
| `_reversa_sdd/sdd/vector-store-similarity-search.md` | Spec SDD | regra-alterada | LOW | Status → 🟢 IMPLEMENTADO; sqlite-vec, retry OpenAI, top_k=5 |
| `README.md` | Documentação | regra-alterada | LOW | Typo fix: `provider: "open` → `provider: "openai"` |
| `docs/embedding-benchmark.md` | Documentação / Benchmark | componente-novo | LOW | Tabela comparativa provider/model/latency/cost/hardware |
| `src/anchor_rag/config.py` (inline docs) | AppConfig | regra-alterada | LOW | Documentação inline no validador cross-config |
| `src/anchor_rag/ingestion/pipeline.py` (inline docs) | IngestionPipeline | regra-alterada | LOW | Documentação inline no dedup check |
| `src/anchor_rag/cli_eval.py` (inline docs) | CLI Avaliação | regra-alterada | LOW | Documentação inline nas métricas eval |

---

## 2. Diff Conceitual por Componente

### AppConfig (`src/anchor_rag/config.py`)
**Mudança:** Adicionado `@model_validator(mode="after")` `validate_embedding_dimensions` que compara `embedding.dimensions` com `vector_store.embedding_dimensions` e lança `ValueError` acionável se divergirem.

**Antes:** Inconsistência só falhava em runtime na criação da virtual table sqlite-vec (TD-001, lacuna #1).

**Depois:** Falha no carregamento da config (YAML ou objeto), com mensagem clara: `"embedding.dimensions (X) != vector_store.embedding_dimensions (Y). Ajuste config.yaml para que ambos tenham o mesmo valor."`

**Impacto:** Quebra configurações inválidas cedo (fail-fast). Configs válidas inalteradas.

### IngestionPipeline (`src/anchor_rag/ingestion/pipeline.py`)
**Mudança:** Método `ingest()` agora executa `SELECT 1 FROM documents WHERE content_hash = ?` antes de chamar o parser. Se encontrado, retorna `IngestResult(skipped=True, document_id=existing_id)` sem processar.

**Antes:** Comentário "em produção usar índice de hash" (TD-003, lacuna #3); dedup só via `INSERT OR IGNORE` no final, após parse+chunk+embed.

**Depois:** Dedup real no início do pipeline — evita custo de parse/embedding para duplicados.

**Impacto:** Economia significativa de tokens e latência em re-ingestão. Comportamento idempotente reforçado.

### CLI Avaliação (`src/anchor_rag/cli_eval.py`)
**Mudança:** Nova função `eval_dataset()` no `RAGPipeline` + comando `eval --dataset` no CLI. Carrega YAML com `eval_cases` (pergunta, expected_chunks, expected_answer_contains), roda query por caso, computa:
- `recall_at_k`: fração de expected_chunks recuperados no top-k
- `mrr`: Mean Reciprocal Rank do primeiro expected_chunk
- `hallucination_rate`: fração de respostas com conteúdo não suportado pelos chunks
- `citation_coverage`: fração de respostas com pelo menos uma citação `[N]`

**Antes:** `cli_eval.py` só fazia health checks + vector stats (placeholder).

**Depois:** Avaliação quantitativa completa do pipeline RAG contra dataset de referência.

**Impacto:** Permite medir qualidade semântica além de recall léxico; base para drift detection e comparação de provedores.

### Testes Prompt Injection (`tests/integration/test_prompt_injection.py`)
**Mudança:** 15 testes cobrindo 10 categorias de ataque + validação de few-shot defense + query legítima.

**Antes:** Inexistente (TD-010: regex citações frágil, mas sem teste adversarial).

**Depois:** Suite automatizada valida que `SYSTEM_PROMPT` + few-shot bloqueiam injeções; bypass_rate=0%.

**Impacto:** Regressão de segurança detectável automaticamente.

### Specs SDD (`_reversa_sdd/sdd/*.md`)
**Mudança:** Status de 🟡 PARCIAL / 🔴 PLANEJADO → 🟢 IMPLEMENTADO nas 3 specs centrais. Parâmetros reais documentados (chunk_size=512 tokens, chunk_overlap=50, citation format `[N]`, threshold=0.7, etc.).

**Impacto:** Specs agora refletem código real; servem como contrato para futuras extrações.

---

## 3. Regras Preservadas (🟢 CONFIRMADO no domain.md)

As seguintes regras de negócio continuam intactas após esta feature:

| ID | Regra | Componente |
|----|-------|------------|
| BR-001 | Documento = content_hash SHA-256 único; re-ingestão ignorada | IngestionPipeline (reforçado com dedup prévio) |
| BR-002 | Chunking sliding window com overlap | Chunker |
| BR-003 | Parser PDF selecionável (pdfplumber/PyPDF) | PDFParser factory |
| BR-004 | Sanitização obrigatória (control chars, NFKC, hifenização) | sanitize_text |
| BR-010 | 3 provedores embedding: OpenAI, Ollama, HuggingFace | EmbeddingProvider registry |
| BR-011 | Dimensões fixas por modelo; validação estrita | _validate_dimensions + validador cross-config |
| BR-012 | Batch nativo em todos provedores | Implementações concretas |
| BR-013 | Retry exponencial OpenAI (tenacity 3x) | OpenAIEmbeddingProvider |
| BR-014 | Busca cosseno nativa sqlite-vec | SQLiteVecStore.search |
| BR-015 | Threshold similaridade: distance <= 1.0 - threshold | search(threshold) |
| BR-020 | Ancoragem estrita (grounding) | SYSTEM_PROMPT + Synthesizer |
| BR-021 | Citação obrigatória formato `[N]` | SYSTEM_PROMPT + _extract_citations |
| BR-022 | Defesa prompt injection: 3 few-shot | FEW_SHOT_EXAMPLES + build_few_shot_defense |
| BR-023 | Resposta vazia padronizada | SYSTEM_PROMPT + synthesizer fallback |
| BR-024 | Contradição explícita entre chunks | SYSTEM_PROMPT |
| BR-025 | Max chunks no contexto (default 5) | SynthesizerConfig |
| BR-030 | 3 provedores LLM: OpenAI, Ollama, Anthropic | LLMProvider registry |
| BR-031 | Streaming suportado (complete_stream) | 3 implementações |
| BR-032 | System prompt separado Anthropic | AnthropicLLMProvider |
| BR-040 | Virtual table vec0 para embeddings | SQLiteVecStore DDL |
| BR-041 | Cascade delete document→chunks→vec | FK ON DELETE CASCADE |
| BR-042 | Query log opcional com latência por etapa | log_query, get_query_stats |
| BR-043 | Dimensions fixas no schema; mudar modelo = recriar DB | embedding_dimensions na virtual table |

---

## 4. Regras Modificadas (🟢 CONFIRMADO → alteradas nesta feature)

| ID | Regra Original | Nova Regra / Complemento | Componente |
|----|----------------|--------------------------|------------|
| BR-001 | Dedup via `INSERT OR IGNORE` no final do pipeline | **Dedup real no início**: `SELECT 1 FROM documents WHERE content_hash` antes do parser; `IngestResult(skipped=True)` | IngestionPipeline |
| BR-042 | Query log: latência por etapa (embed/search/synthesize/total) | **Adicionado**: `eval_dataset` gera métricas recall@k, MRR, hallucination_rate, citation_coverage | CLI Avaliação / RAGPipeline |
| Lacuna #1 | embedding.dimensions ≠ vector_store.embedding_dimensions só falha em runtime | **Validador cross-config em AppConfig**: falha no load da config | AppConfig |
| Lacuna #3 | Dedup não verifica hash antes de parse | **Verificação prévia implementada** | IngestionPipeline |

---

## 5. Novas Regras Introduzidas (🟢 CONFIRMADO nesta feature)

| ID | Regra | Componente |
|----|-------|------------|
| BR-044 | **Avaliação quantitativa**: recall@k, MRR, hallucination_rate, citation_coverage computados contra dataset YAML | RAGPipeline.eval_dataset / cli_eval |
| BR-045 | **Benchmark embeddings**: latência ms/1k chunks, custo USD/1M tokens comparados por provider | scripts/benchmark_embeddings.py |
| BR-046 | **Teste adversarial automatizado**: 10+ categorias prompt injection, bypass_rate=0% obrigatório | tests/integration/test_prompt_injection.py |
| BR-047 | **Config fail-fast**: validador cross-config impede config inválida antes de runtime | AppConfig.validate_embedding_dimensions |

---

## 6. Dívidas Técnicas Resolvidas

| TD ID | Descrição | Resolução |
|-------|-----------|-----------|
| TD-001 | Dimensions embedding↔store não validadas | Validador cross-config em AppConfig |
| TD-003 | Dedup não verifica hash antes de parse | Dedup real no IngestionPipeline.ingest() |
| TD-008 | Sem testes automatizados | 88 testes unitários + integração passando |
| TD-010 | Regex citações frágil (sem teste adversarial) | Suite prompt injection 15 testes, bypass_rate=0% |

---

## 7. Dívidas Técnicas Remanescentes (não endereçadas nesta feature)

| TD ID | Descrição | Severidade |
|-------|-----------|------------|
| TD-002 | Scores de busca não expostos (placeholder [1.0]) | 🟡 Alta |
| TD-004 | Página estimada heurística falha cross-page | 🟡 Média |
| TD-005 | Sem transação atômica cross-table | 🟡 Média |
| TD-006 | Config duplicada (3 arquivos) | 🟡 Média |
| TD-007 | Chunk dataclass duplicado | 🟢 Baixa |
| TD-009 | Health check síncrono no eval | 🟡 Média |

---

*Gerado por `/reversa-coding` — feature `002-rag-evaluation-hardening`*
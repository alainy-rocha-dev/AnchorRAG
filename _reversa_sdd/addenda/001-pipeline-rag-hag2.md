# Adendo: 001-pipeline-rag-hag2

> Identificador: `001-pipeline-rag-hag2`
> Data: `2026-09-30`
> Cenário: **greenfield** (âncora: `_reversa_sdd/prd.md` + specs em `_reversa_sdd/sdd/`)

---

## Vigência

Vigente desde 2026-09-30.

---

## Resumo da entrega

Implementação do pipeline RAG completo (ingestão → chunking → embeddings → busca vetorial → síntese com citação) para consulta de documentos técnicos PDF privados. Entrega busca semântica por similaridade de cosseno com resposta ancorada, métricas de relevância e latência < 2s. Resolve a ineficiência da busca por palavra-chave e o risco de alucinação de LLMs sem ancoragem em acervos corporativos.

**Ações concluídas:** 46/46 (100%)

---

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta |
|----------|-------|-----------------|-------|
| `prd.md` | 4. Escopo | componente-novo | Pipeline RAG completo implementado: ingestão PDF, chunking com overlap, embeddings (OpenAI/Ollama/HF), vector store (sqlite-vec), busca cosseno, síntese com citação |
| `prd.md` | 3. Métricas | componente-novo | Latência < 2s validada; Recall@k/MRR ≥ 85% pronto para medição via `cli_eval.py` |
| `sdd/document-ingestion-chunking.md` | RF-01 a RF-05 | componente-novo | Parser PDF página a página (pdfplumber/PyPDF); chunking tokens/chars configurável; sanitização; dedup SHA256; batch processing |
| `sdd/vector-store-similarity-search.md` | RF-06 a RF-12 | componente-novo | EmbeddingProvider ABC + 3 provedores; VectorStore ABC + SQLiteVecStore; factory; busca cosseno nativa sqlite-vec |
| `sdd/rag-synthesis-citation-engine.md` | RF-13 a RF-21 | componente-novo | LLMProvider ABC + 3 provedores; prompt ancoragem estrita; few-shot defense; citações `[N]`; latency breakdown; RAGPipeline wiring |
| `sdd/document-ingestion-chunking.md` | 61 (Esclarecimento) | componente-novo | `chunk_unit` configurável `chars` | `tokens` (default: `tokens` no código vs `chars` na spec original) |
| `sdd/vector-store-similarity-search.md` | 62 (Esclarecimento) | componente-novo | Vector Store: SQLite + sqlite-vec (virtual table `chunks_vec`) |
| `sdd/rag-synthesis-citation-engine.md` | 61 (Esclarecimento) | componente-novo | Citação formato `[N]` numérico inline (não `[arquivo - Pág. N]` como na spec original) |
| `README.md` | — | componente-novo | Documentação completa: arquitetura, matemática cosseno, comparativo embeddings, quickstart, config, troubleshooting |
| `tests/` | — | componente-novo | 26 testes unitários (contratos ABC, modelos, config, utils) + 4 integração (ingestion, query, e2e, prompt injection) + CI GitHub Actions |

---

## Regras sob vigilância

| Watch ID | Apontador |
|----------|-----------|
| *(greenfield - watch principal vazio)* | Observações O001-O026 em `_reversa_forward/001-pipeline-rag-hag2/regression-watch.md` |
| — | Futura re-extração `/reversa` migrará RFs confirmados como 🟢 para watch principal W001+ |

---

## Fontes

- `_reversa_forward/001-pipeline-rag-hag2/requirements.md`
- `_reversa_forward/001-pipeline-rag-hag2/legacy-impact.md`
- `_reversa_forward/001-pipeline-rag-hag2/regression-watch.md`
- `_reversa_forward/001-pipeline-rag-hag2/progress.jsonl`
- `_reversa_forward/001-pipeline-rag-hag2/actions.md`

---
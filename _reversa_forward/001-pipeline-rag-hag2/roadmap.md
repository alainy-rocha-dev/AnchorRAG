# Roadmap: Implementação inicial do Projeto HAG 2 (Pipeline RAG)

> Identificador: `001-pipeline-rag-hag2`
> Data: `2026-09-22`
> Requirements: `_reversa_forward/001-pipeline-rag-hag2/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

Implementação greenfield do pipeline RAG completo em 3 componentes desacoplados orquestrados via API simples: (1) **Document Ingestion & Chunking** — parsing PDF, sanitização, chunking parametrizado com `chunk_unit` configurável (chars/tokens), metadados por chunk; (2) **Vector Store & Similarity Search** — geração de embeddings via modelo configurável, indexação em SQLite local com extensão vetorial (sqlite-vss/sqlite-vec), busca por similaridade de cosseno top-k; (3) **RAG Synthesis & Citation Engine** — prompt de ancoragem estrita, síntese com citação inline + rodapé com scores, tratamento de informação ausente (score < 0.40), latência total < 2s. Stack: Python 3.11+, dependências mínimas (pypdf/pdfplumber, tiktoken, numpy, sqlite-vss/vec, httpx/httpx-retry, LLM client). Arquitetura CLI + biblioteca reutilizável, sem servidor no MVP.

## 2. Princípios aplicados

| Princípio | Como a feature se relaciona | Status |
|-----------|------------------------------|--------|
| (não há `.reversa/principles.md` no projeto) | Projeto greenfield sem princípios declarados ainda | n/a |

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|--------------------------|-------------|
| D-01 | Linguagem: Python 3.11+ | Ecossistema maduro para RAG (pdfplumber, tiktoken, numpy, sqlite-vss, openai/ollama clients), alinhado à persona Dev Backend | Go, TypeScript/Node, Rust | 🟢 |
| D-02 | PDF parsing: `pdfplumber` (primário) com fallback `pypdf` | `pdfplumber` extrai melhor tabelas/estrutura; `pypdf` mais leve para textos simples | `PyMuPDF` (fitz) - licença AGPL; `pdfminer.six` - mais lento | 🟢 |
| D-03 | Chunking: unidade configurável `chars` | `tokens` via `tiktoken` (default: `chars`) | Premissa do esclarecimento; `chars` é independente de modelo, `tokens` alinha com context windows | 🟢 |
| D-04 | Vector Store: SQLite + `sqlite-vec` (ou `sqlite-vss`) | Persistência single-file, zero servidor, SQL nativo para metadados + vetores, deploy trivial | FAISS in-memory (perde índice ao reiniciar), ChromaDB (mais dependências), Qdrant/Milvus (servidor) | 🟢 |
| D-05 | Embeddings: interface abstraída (`EmbeddingProvider`) com implementações OpenAI, Ollama, HuggingFace local | Permite trocar provedor sem mudar pipeline; alinhado à dependência externa declarada no PRD | Hardcode single provider | 🟢 |
| D-06 | LLM: interface abstraída (`LLMProvider`) com OpenAI, Ollama, Anthropic | Mesma razão dos embeddings; suporte a modelos locais para privacidade | Hardcode single provider | 🟢 |
| D-07 | Similaridade: cosseno pura em NumPy (vetores normalizados) | Transparência matemática (requisito PRD), sem dependência de FAISS para MVP | FAISS IndexFlatIP, sklearn cosine_similarity | 🟢 |
| D-08 | Citação: inline `[1]` + rodapé `[1] file.pdf - Pág. N - score: 0.XX` | Transparência total (scores visíveis), UX fluida, atende PRD "exibição transparente das métricas" | Apenas inline, apenas rodapé | 🟢 |
| D-09 | Orquestração: pipeline linear síncrono `ingest -> index -> query -> synthesize` | Simplicidade MVP; latência < 2s viável sem async complexo | Async/queue-based, streaming tokens | 🟡 |
| D-10 | CLI: Typer (comandos `ingest`, `query`, `eval`) | UX Dev Backend, help automático, type hints | Click, argparse raw | 🟢 |
| D-11 | Config: Pydantic Settings (YAML/env) | Validação tipada, 12-factor, hierarquia clara | raw YAML, dotenv only | 🟢 |
| D-12 | Testes: pytest + fixtures PDFs sintéticos + golden files | Reprodutibilidade, CI-friendly, validação de scores/latência | unittest, apenas integration tests | 🟢 |

## 4. Premissas

| Premissa | Origem (`requirements.md` seção) | Risco se errada |
|----------|----------------------------------|-----------------|
| Unidade chunk_size default `chars` funciona bem para PDFs técnicos | Esclarecimento 1 (chunk_unit) | Chunks muito grandes/pequenos para certos modelos → ajustar default para `tokens` |
| `sqlite-vec`/`sqlite-vss` compila/instala sem issues na máquina alvo | Esclarecimento 2 (Vector Store) | Build falha em Windows/ARM → fallback para FAISS in-memory + persistência manual |
| Formato citação inline+rodapé é parseável por downstream | Esclarecimento 3 (Citação) | Consumidores esperam outro formato → adicionar formatter plugável |

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| document-ingestion-chunking | `_reversa_sdd/sdd/document-ingestion-chunking.md` | componente-novo | Novo módulo: parsing PDF, sanitização, chunking parametrizado, metadados |
| vector-store-similarity-search | `_reversa_sdd/sdd/vector-store-similarity-search.md` | componente-novo | Novo módulo: embeddings provider, SQLite+vec index, busca cosseno top-k |
| rag-synthesis-citation-engine | `_reversa_sdd/sdd/rag-synthesis-citation-engine.md` | componente-novo | Novo módulo: prompt ancoragem, síntese LLM, citação inline+rodapé, latência |
| pipeline-orchestrator | (novo — orquestração dos 3 acima) | componente-novo | Novo módulo: CLI Typer, config Pydantic, wiring dos 3 componentes |

## 6. Delta no modelo de dados

- Resumo das mudanças: Modelo novo (greenfield). Entidades: `Chunk` (id, source_file, page_number, char_count, text, embedding), `Document` (id, file_path, page_count, chunk_ids), `QueryResult` (chunks[], scores[], synthesis, citations[], latency_ms).
- Detalhe completo em: `_reversa_forward/001-pipeline-rag-hag2/data-delta.md`

## 7. Delta de contratos externos

| Contrato | Tipo | Arquivo de detalhe |
|----------|------|--------------------|
| CLI `ingest` | arquivo (STDIN/args) | `_reversa_forward/001-pipeline-rag-hag2/interfaces/cli-ingest.md` |
| CLI `query` | arquivo (STDIN/args) | `_reversa_forward/001-pipeline-rag-hag2/interfaces/cli-query.md` |
| EmbeddingProvider | interface Python (abstração) | `_reversa_forward/001-pipeline-rag-hag2/interfaces/embedding-provider.md` |
| LLMProvider | interface Python (abstração) | `_reversa_forward/001-pipeline-rag-hag2/interfaces/llm-provider.md` |

## 8. Plano de migração

n/a (greenfield — não há legado para migrar)

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| `sqlite-vec` não instala em Windows/ARM | alto | médio | Preparar fallback FAISS in-memory + pickle persistence; documentar build deps |
| Qualidade embeddings insuficiente para recall >= 85% | alto | médio | Comparar 3+ modelos (OpenAI, nomic-embed-text, bge-small) no `eval`; permitir fine-tuning futuro |
| Latência > 2s com modelos grandes locais | médio | médio | Cache de embeddings, batch indexing, quantização (int8), streaming tokens futuro |
| PDFs com tabelas/imagens perdem informação | médio | alto | `pdfplumber` extrai tabelas; OCR futuro (out-of-scope MVP) |
| Prompt injection contorna ancoragem | alto | baixo | Testes adversariais; system prompt com few-shot de defesa; logging de tentativas |

## 10. Critério de pronto

- [ ] Todas as ações do `actions.md` marcadas `[X]`
- [ ] `cross-check.md` (se executado) sem CRITICAL nem HIGH
- [ ] `regression-watch.md` gerado
- [ ] Re-extração reversa executada e sem regressão vermelha (recomendado, não obrigatório)
- [ ] CLI `ingest` processa PDFs de teste e popula vector store
- [ ] CLI `query` retorna top-k + síntese com citações + latência < 2s
- [ ] Testes de aceitação (gherkin do requirements) passando
- [ ] README com matemática de cosseno e comparativo embeddings

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-22 | Versão inicial gerada por `/reversa-plan` | reversa |
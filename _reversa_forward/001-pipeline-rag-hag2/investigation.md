# Investigation: Implementação inicial do Projeto HAG 2 (Pipeline RAG)

> Feature: `001-pipeline-rag-hag2`
> Data: `2026-09-22`

## 1. Problema e contexto

Empresas e consultorias (ex.: NTT DATA) possuem acervos privados de documentos técnicos (PDFs: manuais, relatórios, normativos) difíceis de consultar. Busca por palavra-chave falha em capturar semântica; LLMs puros alucinam sem ancoragem. Solução: pipeline RAG com busca vetorial por similaridade de cosseno, resposta sintetizada com citações e métricas transparentes.

## 2. Alternativas avaliadas

### 2.1 Framework RAG pronto vs. Implementação própria

| Opção | Prós | Contras | Decisão |
|-------|------|---------|---------|
| LangChain / LlamaIndex | Rápido, muitos integrations, community | Caixa preta, dependências pesadas, difícil customizar matemática de cosseno, abstrações vazam | **Implementação própria** (requisito PRD: "implementação transparente da matemática de similaridade de cosseno e comparativo de embeddings no README") |
| Haystack | Enterprise-ready, pipelines | Curva de aprendizado, overhead | Não para MVP portfólio |
| **Custom (escolhido)** | Controle total, transparência, portfólio técnico demonstrável | Mais código boilerplate | ✅ |

### 2.2 Vector Store

| Opção | Prós | Contras | Decisão |
|-------|------|---------|---------|
| FAISS in-memory | Ultrafast, maduro | Perde índice ao reiniciar, sem SQL para metadados | Fallback apenas |
| ChromaDB | Persiste, API simples, filters | Dependência extra (~100MB), servidor opcional | Backup |
| **SQLite + sqlite-vec/sqlite-vss (escolhido)** | Single file, zero server, SQL nativo, ~few MB, persistente | Menos otimizado para ANN em escala >100k | ✅ MVP |
| DuckDB + VSS | Analítico, colunar | Mais novo, menos testado para vetores | Futuro |
| Qdrant/Milvus | Produção, cluster | Servidor, infra, overkill MVP | Não |

### 2.3 PDF Parsing

| Biblioteca | Extração texto | Tabelas | Imagens/OCR | Licença | Decisão |
|------------|----------------|---------|-------------|---------|---------|
| **pdfplumber (escolhido)** | Excelente | Sim (bom) | Não | MIT | ✅ Primário |
| pypdf | Boa | Não | Não | BSD | ✅ Fallback |
| PyMuPDF (fitz) | Excelente | Sim | Não | AGPL | ❌ Licença |
| pdfminer.six | Boa | Limitado | Não | MIT | Lento |
| marker / nougat | SOTA (ML) | Sim | Sim | Variadas | Pesado, overkill |

### 2.4 Chunking Strategy

| Estratégia | Descrição | Uso |
|------------|-----------|-----|
| **Fixed-size com overlap (escolhido)** | `chunk_size` + `chunk_overlap` em chars ou tokens | MVP — simples, previsível, funciona bem com overlap semântico |
| Recursive (LangChain style) | Divisores hierárquicos (\n\n, \n, ., ?!) | Futuro — melhor para docs estruturados |
| Semantic (embedding-based) | Agrupa por similaridade semântica | Futuro — custo computacional alto |
| Document-structure-aware | Usa headings, sections do PDF | Futuro — requer parsing avançado |

### 2.5 Embedding Models (candidatos para comparativo)

| Modelo | Dims | Tipo | Contexto | Licença | Nota |
|--------|------|------|----------|---------|------|
| `text-embedding-3-small` | 1536 | API (OpenAI) | 8191 | Proprietária | Baseline cloud |
| `text-embedding-3-large` | 3072 | API (OpenAI) | 8191 | Proprietária | Maior qualidade |
| `nomic-embed-text-v1.5` | 768 | Local (Ollama/HF) | 8192 | Apache 2.0 | Forte local |
| `bge-small-en-v1.5` | 384 | Local (HF) | 512 | MIT | Rápido, pequeno |
| `bge-base-en-v1.5` | 768 | Local (HF) | 512 | MIT | Equilibrado |
| `e5-small-v2` | 384 | Local (HF) | 512 | MIT | Bom para retrieval |

### 2.6 LLM Models (candidatos para síntese)

| Modelo | Tipo | Contexto | Licença | Nota |
|--------|------|----------|---------|------|
| `gpt-4o-mini` | API (OpenAI) | 128k | Proprietária | Barato, rápido, bom seguidor instruções |
| `gpt-4o` | API (OpenAI) | 128k | Proprietária | Melhor qualidade |
| `llama3.1:8b` | Local (Ollama) | 128k | Llama 3.1 Community | Privacidade total |
| `llama3.1:70b` | Local (Ollama) | 128k | Llama 3.1 Community | Qualidade alta, HW pesado |
| `phi3:mini` | Local (Ollama) | 128k | MIT | Muito leve |

## 3. Padrões e referências aplicáveis

- **RFC 7519 (JWT)** — se futuro auth for necessário (out-of-scope)
- **OpenAPI 3.1** — para documentar CLI/HTTP futuro
- **Semantic Versioning 2.0** — versionamento dos componentes
- **Conventional Commits** — histórico limpo
- **pytest + hypothesis** — property-based testing para chunking overlap
- **Pydantic v2** — validação de schemas, settings, performance

## 4. Fontes externas

- [sqlite-vec docs](https://github.com/asg017/sqlite-vec) — extensão vetorial SQLite moderna, pure Rust, sem dependências C
- [sqlite-vss docs](https://github.com/asg017/sqlite-vss) — alternativa baseada em FAISS, requer compilação
- [tiktoken](https://github.com/openai/tiktoken) — tokenização OpenAI (GPT-3.5/4, embeddings)
- [pdfplumber](https://github.com/jsvine/pdfplumber) — extração PDF com tabelas
- [Cosseno similarity numpy](https://numpy.org/doc/stable/reference/generated/numpy.dot.html) — implementação manual transparente
- [RAG evaluation metrics](https://arxiv.org/abs/2309.15299) — Recall@k, MRR, nDCG

## 5. Decisões não-técnicas

- **Licença do projeto:** MIT (portfólio público, permissiva)
- **CI/CD:** GitHub Actions (pytest, ruff, mypy, build)
- **Distribuição:** `pip install -e .` + `pyproject.toml` (PEP 621)
- **Documentação:** README + docstrings (pdoc ou mkdocs futuro)

## 6. Perguntas abertas para futuro (pós-MVP)

1. Streaming de tokens (SSE) para percepção de latência menor?
2. Re-ranking com Cross-Encoder (ex.: `bge-reranker-base`)?
3. Multi-tenancy / RBAC?
4. Suporte a DOCX, HTML, PPTX, Markdown?
5. OCR para PDFs escaneados (Tesseract / marker)?
6. Avaliação automática contínua (RAGAS, TruLens)?
7. Cache semântico (GPTCache) para queries repetidas?

## 7. Métricas de validação (para `eval` command)

| Métrica | Target | Método |
|---------|--------|--------|
| Recall@3 | >= 85% | Conjunto gold de 50 queries + docs relevantes |
| MRR | >= 0.75 | Mesmo gold set |
| Latência P95 | < 2.0s | 100 queries sequenciais |
| Taxa alucinação | 0% | Verificação manual em 20 queries fora do acervo |
| Citação coverage | 100% | Toda afirmação tem citação |
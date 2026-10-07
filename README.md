# AnchorRAG - Pipeline RAG para Projeto HAG 2

Pipeline completo de Retrieval-Augmented Generation (RAG) com ingestão de PDFs, chunking inteligente, embeddings multi-provedor, busca vetorial com sqlite-vec e síntese com ancoragem estrita e citações.

## 🚀 Quickstart

```bash
# Instalação
pip install -e ".[dev]"

# Copia configuração de exemplo
cp config.example.yaml config.yaml
# Edite config.yaml com suas API keys

# Ingestão de documentos
anchor-rag ingest docs/*.pdf --recursive

# Query
anchor-rag query "Qual é o tema principal dos documentos?"

# Avaliação
anchor-rag eval
```

## 📐 Arquitetura

```
┌─────────────┐     ┌──────────┐     ┌──────────────┐     ┌─────────────┐
│   PDFs      │────▶│ Parser   │────▶│  Chunker     │────▶│  Embeddings │
│  (input)    │     │(pdfplumb)│     │ (tokens/chars)│     │ (OpenAI/    │
└─────────────┘     └──────────┘     └──────────────┘     │  Ollama/    │
                                                          │  HF)        │
                                                          └──────┬──────┘
                                                                 │
┌─────────────┐     ┌──────────┐     ┌──────────────┐          │
│  Resposta   │◀────│Synthesiz.│◀────│ Vector Store │◀─────────┘
│  + Citações │     │ (LLM +   │     │ (sqlite-vec) │
└─────────────┘     │  prompt) │     └──────────────┘
                    └──────────┘
```

## 🔧 Componentes

### Ingestão (`anchor_rag/ingestion/`)
- **Parser**: `PDFParser` protocol com `PdfPlumberParser` (tabelas) e `PyPDFParser` (fallback)
- **Chunker**: Divisão por tokens (tiktoken) ou caracteres, com overlap configurável
- **Pipeline**: Orquestração com dedup por hash, batch processing, error handling

### Embeddings (`anchor_rag/embeddings/`)
- **OpenAI**: `text-embedding-3-small/large`, retry exponencial, batch nativo
- **Ollama**: Via HTTP `/api/embed`, modelos locais
- **HuggingFace**: `sentence-transformers` local, batch encoding

### Vector Store (`anchor_rag/vector_store/`)
- **SQLite-vec**: Virtual table `chunks_vec`, busca cosseno via NumPy, DDL automático
- **Eval Log**: Tabela `eval_log` para histórico de avaliações agentic

### Síntese (`anchor_rag/synthesis/`)
- **LLM Providers**: OpenAI, Ollama, Anthropic com streaming
- **Prompt Engineering**: Ancoragem estrita, few-shot defense contra prompt injection
- **Citações**: Extração automática `[N]` mapeada para chunks fonte

### Avaliação Agentic (`anchor_rag/evaluation/`)
- **LLM-as-Judge**: Avaliador ABC + 3 provedores (OpenAI, Ollama, Anthropic)
- **Métricas RAGAS-like**: Faithfulness, Answer Relevancy, Context Precision, Context Recall
- **Critique-and-Refine**: Auto-avaliação iterativa (≤3 chamadas LLM) com threshold configurável
- **Comparative Evaluation**: Paired t-test + Bootstrap IC 95% entre múltiplos provedores
- **Drift Detection**: Comparação vs baseline versionado (hash dataset + config), exit codes 0/1/2
- **Cost Estimator**: Cálculo USD baseado em tokens × pricing table por provedor/modelo

## ⚙️ Configuração

```yaml
# config.yaml
embedding:
  provider: "openai"       # openai, ollama, huggingface
  model: "text-embedding-3-small"
  dimensions: 1536
  batch_size: 100
  api_key_env: "OPENAI_API_KEY"

llm:
  provider: "openai"       # openai, ollama, anthropic
  model: "gpt-4o-mini"
  temperature: 0.1
  max_tokens: 2048
  api_key_env: "OPENAI_API_KEY"

chunking:
  chunk_size: 512
  chunk_overlap: 50
  chunk_unit: "tokens"     # chars ou tokens
  min_chunk_size: 50

vector_store:
  type: "sqlite_vec"
  path: "./data/anchor_rag.db"
  embedding_dimensions: 1536

logging:
  level: "INFO"
  format: "json"
  output: "stdout"
```

## 📊 Comparativo de Embeddings

| Provedor | Modelo | Dimensões | Latência | Custo | Privacidade |
|----------|--------|-----------|----------|-------|-------------|
| OpenAI | text-embedding-3-small | 1536 | ~100ms | $0.02/1M tokens | Baixa |
| OpenAI | text-embedding-3-large | 3072 | ~200ms | $0.13/1M tokens | Baixa |
| Ollama | nomic-embed-text | 768 | ~50ms | Grátis (local) | Alta |
| Ollama | mxbai-embed-large | 1024 | ~100ms | Grátis (local) | Alta |
| HF | all-MiniLM-L6-v2 | 384 | ~10ms | Grátis (local) | Alta |
| HF | bge-m3 | 1024 | ~50ms | Grátis (local) | Alta |

### Matemática da Similaridade de Cosseno

Para vetores normalizados $u, v \in \mathbb{R}^d$:

$$\text{similaridade}(u, v) = \frac{u \cdot v}{\|u\| \|v\|} = u \cdot v$$

No sqlite-vec, a distância L2 entre vetores normalizados relaciona-se com cosseno:

$$\text{distância}_{L2}(u, v) = \sqrt{2 - 2 \cdot \text{cosseno}(u, v)}$$

$$\text{cosseno}(u, v) = 1 - \frac{\text{distância}_{L2}^2}{2}$$

## 🛠️ CLI

```bash
# Ingestão
anchor-rag ingest docs/ --recursive --parser pdfplumber --format json
anchor-rag ingest file.pdf --force --chunk-size 256

# Query
anchor-rag query "O que é RAG?" --top-k 10 --threshold 0.5
anchor-rag query "Resuma o documento" --llm-provider ollama --llm-model llama3.1:8b
anchor-rag query "Liste os tópicos" --no-synthesis --format json

# Eval (básico)
anchor-rag eval --format json

# Eval Agentic (feature 003)
anchor-rag eval --agentic --judge ollama                    # Avaliação LLM-as-judge
anchor-rag eval --agentic --compare openai,ollama          # Comparativo multi-provedor + stats
anchor-rag eval --drift-check --baseline eval_baseline.json # Drift detection (exit 0/1/2)
anchor-rag eval --agentic --output markdown                # Saída Markdown formatada
```

## 🧪 Testes

```bash
# Unitários
pytest tests/unit -v

# Integração
pytest tests/integration -v

# Todos com coverage
pytest --cov=anchor_rag --cov-report=html
```

## 📁 Estrutura do Projeto

```
src/anchor_rag/
├── config.py              # Configuração Pydantic Settings
├── cli.py                 # CLI principal (Typer)
├── cli_ingest.py          # Comando ingest
├── cli_query.py           # Comando query
├── cli_eval.py            # Comando eval (básico + agentic)
├── domain/
│   ├── models.py          # Document, Chunk, QueryResult, configs, EvalMetrics, ComparativeMetrics, DriftResult, CostEstimate
│   └── exceptions.py      # Exceções customizadas
├── ingestion/
│   ├── parser.py          # PDFParser protocol + implementations
│   ├── chunker.py         # Chunker com tokens/chars
│   ├── pipeline.py        # IngestionPipeline orquestrador
│   └── structured_chunker.py  # Chunker estruturado (tabelas, listas)
├── embeddings/
│   ├── base.py            # EmbeddingProvider ABC
│   ├── openai.py          # OpenAIEmbeddingProvider
│   ├── ollama.py          # OllamaEmbeddingProvider
│   ├── huggingface.py     # HuggingFaceEmbeddingProvider
│   └── __init__.py        # Factory create_embedding_provider
├── vector_store/
│   ├── base.py            # VectorStore ABC
│   ├── sqlite_vec.py      # SQLiteVecStore (inclui eval_log)
│   └── __init__.py        # Factory create_vector_store
├── synthesis/
│   ├── llm.py             # LLMProvider ABC + LLMConfig/Response
│   ├── openai_llm.py      # OpenAILLMProvider
│   ├── ollama_llm.py      # OllamaLLMProvider
│   ├── anthropic_llm.py   # AnthropicLLMProvider
│   ├── prompt.py          # build_system_prompt, few-shot defense
│   ├── synthesizer.py     # RAGSynthesizer
│   └── __init__.py        # Factory create_llm_provider
├── evaluation/            # NOVO: feature 003
│   ├── evaluator.py       # EvaluatorProvider ABC + 3 provedores
│   ├── critique_refine.py # CritiqueAndRefineSynthesizer
│   ├── comparative.py     # ComparativeEvaluator + stats
│   ├── drift.py           # DriftDetector
│   ├── cost.py            # CostEstimator
│   └── __init__.py        # Factory create_evaluator_provider
├── pipeline/
│   ├── orchestrator.py    # RAGPipeline principal (eval_dataset_agentic, drift_check)
│   └── hybrid_orchestrator.py  # Pipeline híbrido vetorial + FTS
├── retrieval/             # NOVO: feature 002
│   ├── fts.py             # Full-text search SQLite
│   ├── hybrid.py          # Hybrid retriever (vetorial + FTS)
│   ├── rerank.py          # Cross-encoder reranker
│   └── __init__.py        # Factory
└── utils/
    └── text.py            # Hash, sanitização, chunking, tokens
```

## 🔒 Segurança - Ancoragem Estrita

O system prompt impõe:
1. **Resposta apenas baseada nos trechos** - conhecimento externo proibido
2. **Citações obrigatórias** - `[N]` para cada afirmação
3. **Declaração de ausência** - "Não encontrei..." se info não está nos trechos
4. **Defesa few-shot** - Exemplos de prompt injection no prompt

## 🤖 Avaliação Agentic (Feature 003)

O pipeline inclui avaliação avançada estilo **RAGAS** usando LLM-as-judge:

| Capacidade | Descrição | Comando |
|------------|-----------|---------|
| **LLM-as-Judge** | 4 métricas de qualidade via LLM separado do síntese | `--agentic --judge ollama` |
| **Critique-and-Refine** | Auto-melhoria iterativa (≤2 refinamentos) | Automático com `--agentic` |
| **Comparativo Multi-Provedor** | Paired t-test + Bootstrap IC 95% entre OpenAI/Ollama/Anthropic | `--compare openai,ollama` |
| **Drift Detection** | Monitoramento contínuo vs baseline versionado | `--drift-check --baseline file.json` |
| **Cost Estimator** | USD estimado por query/run (tokens × pricing table) | Incluído no relatório |

**Thresholds default**: 0.7 para todas as métricas (dispara refine se abaixo)

**Orçamento default**: $0.50 por run completo (20 queries × 3 métricas × 2 iterações)

## 🐛 Troubleshooting

| Problema | Solução |
|----------|---------|
| `sqlite-vec` não carrega | `pip install sqlite-vec` + verificar extensão SQLite |
| OpenAI API error | Verificar `OPENAI_API_KEY` no `.env` ou config |
| Ollama connection refused | Iniciar `ollama serve` ou verificar `base_url` |
| Memória insuficiente (HF) | Usar modelo menor ou `batch_size` menor |
| Chunks muito grandes | Reduzir `chunk_size` ou aumentar `chunk_overlap` |

## 📈 Métricas de Avaliação

### Métricas Básicas
- **Recall@k**: % de queries onde chunk relevante está no top-k
- **MRR**: Mean Reciprocal Rank da primeira resposta relevante
- **Latência P95**: Percentil 95 da latência end-to-end
- **Taxa de alucinação**: % respostas com info não nos trechos
- **Cobertura de citações**: % afirmações com citação válida

### Métricas Agentic (RAGAS-like, feature 003)
- **Faithfulness**: Fidelidade da resposta ao contexto recuperado (0-1)
- **Answer Relevancy**: Relevância da resposta à query original (0-1)
- **Context Precision**: Precisão dos chunks recuperados vs resposta (0-1)
- **Context Recall**: Cobertura dos chunks relevantes para a query (0-1)

### Métricas Comparativas
- **Paired t-test**: Significância estatística entre provedores (p-value)
- **Bootstrap IC 95%**: Intervalo de confiança da diferença de médias
- **Cost per Query**: USD estimado por query (tokens × pricing table)

### Drift Detection
- **Drift %**: Variação vs baseline versionado (hash dataset + config)
- **Alert Threshold**: Default >10% degradação em qualquer métrica
- **Exit Codes**: 0=OK, 1=Drift detectado, 2=Erro

## 🤝 Contribuição

1. Fork do projeto
2. Crie branch: `git checkout -b feature/nova-funcionalidade`
3. Commit: `git commit -m 'feat: adiciona X'`
4. Push: `git push origin feature/nova-funcionalidade`
5. Abra Pull Request

## 📄 Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.
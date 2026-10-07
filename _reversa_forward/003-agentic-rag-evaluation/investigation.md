# Investigation: agentic-rag-evaluation

> Feature: `003-agentic-rag-evaluation`
> Data: `2026-09-30`

---

## 1. Pesquisa de Fundamento

### LLM-as-a-Judge (RAGAS, DeepEval, TruLens)
- **RAGAS** (Google Research): Métricas faithfulness, answer_relevancy, context_precision, context_recall via LLM judge. Usa few-shot prompts calibrados. Paper: "RAGAS: Automated Evaluation of Retrieval Augmented Generation" (2023).
- **DeepEval** (Confident AI): Framework Python open-source com métricas RAGAS + G-Eval + custom. Suporta OpenAI, Anthropic, local LLMs.
- **TruLens** (TruEra): Instrumentação + feedback functions (groundedness, relevance). Integra com LangChain, LlamaIndex.

**Decisão:** Implementar nativo (não dependência externa) seguindo padrão Strategy do projeto. Métricas RAGAS-like como especificado nos RFs.

### Critique-and-Refine (Self-Refine, Reflexion)
- **Self-Refine** (Madaan et al., 2023): Gera → Critica → Refina iterativamente. Melhora qualidade sem fine-tuning.
- **Reflexion** (Shinn et al., 2023): Agente com memória episódica que reflete sobre falhas passadas.
- **Constitutional AI** (Anthropic): Princípios explícitos guiam refinamento.

**Decisão:** `CritiqueAndRefineSynthesizer` simples: 1 geração + até 2 refinamentos baseados em scores do judge. Sem memória episódica (fora de escopo). Prompt de critique herda few-shot defense.

### Comparative Evaluation com Significância Estatística
- **Paired t-test**: Compara mesma métrica nas mesmas queries entre 2 provedores. Requer normalidade (n≥30 ideal).
- **Wilcoxon signed-rank**: Não-paramétrico, alternativa quando normalidade falha.
- **Bootstrap CI**: Resampling para IC 95% sem assumir distribuição.

**Decisão:** Paired t-test (scipy.stats.ttest_rel) + bootstrap IC 95% (1000 resamples). Documentar limitação n<30.

### Drift Detection
- **Data drift**: Mudança na distribuição dos dados de entrada (queries, corpus).
- **Concept drift**: Mudança na relação query→resposta esperada.
- **Model drift**: Degradação do modelo (embedding, LLM) ao longo do tempo.

**Decisão:** Foco em **model drift** via métricas de qualidade (faithfulness, etc.). Baseline = hash(dataset) + hash(config) + métricas agregadas. Threshold default 10% queda relativa.

### Cost Estimation
- **OpenAI pricing**: $/1M tokens (input/output) por modelo. Ex.: gpt-4o-mini $0.15/$0.60.
- **Anthropic pricing**: $/1M tokens. Ex.: claude-3-haiku $0.25/$1.25.
- **Ollama/local**: Custo = 0 (hardware próprio), mas pode estimar equivalente cloud.

**Decisão:** `pricing_table` em config (provider→model→{input_usd_per_1m, output_usd_per_1m}). Default para modelos conhecidos; extensível.

---

## 2. Alternativas Avaliadas

| Alternativa | Prós | Contras | Decisão |
|-------------|------|---------|---------|
| **Usar RAGAS library** | Pronto, testado, métricas validadas | Dependência externa; não segue Strategy do projeto; menos controle | ❌ Rejeitado |
| **DeepEval** | Completo, CI/CD ready | Mesma dependência; heavyweight | ❌ Rejeitado |
| **Implementação nativa (escolhida)** | Consistente com arquitetura; zero deps; controle total | Mais código; validação própria | ✅ Escolhido |
| **Judge = mesmo LLM da síntese** | Simples, 1 provider | Viés de auto-avaliação (RN-01 violado) | ❌ Rejeitado |
| **Judge = LLM separado (escolhido)** | Elimina viés; permite comparar provedores | +1 chamada LLM por métrica | ✅ Escolhido |
| **Persistir em `query_log` (estender)** | Menos tabelas | Mistura produção + eval; schema pollution | ❌ Rejeitado |
| **Nova tabela `eval_log` (escolhida)** | Separação limpa; versionamento baseline | +1 tabela | ✅ Escolhido |
| **Threshold único para todas métricas** | Simples | Métricas têm escalas/dinâmicas diferentes | ❌ Rejeitado |
| **Thresholds por métrica (escolhido)** | Preciso | Mais config | ✅ Escolhido |

---

## 3. Padrões Aplicáveis do Legado

| Padrão | Onde Aplicado | Arquivo Referência |
|--------|---------------|-------------------|
| **Strategy + Registry + Factory** | `EvaluatorProvider` ABC + 3 providers + factory | `embeddings/__init__.py`, `synthesis/__init__.py` |
| **Pydantic Settings com validação** | `EvaluationConfig` em `config.py` | `config.py` (AppConfig, model_validator) |
| **Structured JSON logging + request_id** | Logs por etapa (retrieve, judge_*, refine_*) | `logging.py` |
| **SQLite DDL em `VectorStore.init_db()`** | `eval_log` table creation | `vector_store/sqlite_vec.py` |
| **CLI Typer com Rich output** | Novas flags `--agentic`, `--judge`, `--compare`, `--drift-check` | `cli.py`, `cli_eval.py` |
| **Health check em providers** | `EvaluatorProvider.health_check()` | `embeddings/base.py`, `synthesis/llm.py` |
| **Retry tenacity (OpenAI)** | `OpenAIEvaluatorProvider` | `embeddings/openai.py` |

---

## 4. Fontes Externas

- RAGAS Paper: https://arxiv.org/abs/2309.15217
- Self-Refine Paper: https://arxiv.org/abs/2303.17651
- scipy.stats.ttest_rel: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_rel.html
- OpenAI Pricing: https://openai.com/api/pricing/
- Anthropic Pricing: https://www.anthropic.com/pricing

---

## 5. Decisões de Implementação Detalhadas

### EvaluatorProvider ABC
```python
class EvaluatorProvider(ABC):
    @abstractmethod
    async def eval_faithfulness(self, query: str, context: List[str], answer: str) -> float: ...
    @abstractmethod
    async def eval_answer_relevancy(self, query: str, answer: str) -> float: ...
    @abstractmethod
    async def eval_context_precision(self, query: str, context: List[str], answer: str) -> float: ...
    @abstractmethod
    async def eval_context_recall(self, query: str, context: List[str], answer: str) -> float: ...
    @abstractmethod
    async def health_check(self) -> bool: ...
```

### Prompt Templates (Judge)
Cada métrica tem prompt dedicado com:
- Instrução clara do que avaliar
- 3 few-shot examples (positivo, negativo, borderline)
- Formato saída: `SCORE: <0.0-1.0>` + `REASONING: <texto>`
- Temperature=0, seed fixo

### CritiqueAndRefineSynthesizer
```python
class CritiqueAndRefineSynthesizer:
    def __init__(self, synthesizer: RAGSynthesizer, evaluator: EvaluatorProvider, thresholds: dict):
        ...
    async def synthesize(self, query: str, chunks: List[Chunk], config: QueryConfig) -> QueryResult:
        # 1. Gera resposta base
        # 2. Avalia com judge
        # 3. Se qualquer score < threshold: gera critique → refina (máx 2 iterações)
        # 4. Retorna melhor resposta + trail de scores
```

### ComparativeEvaluator
```python
class ComparativeEvaluator:
    async def compare(self, providers: List[str], dataset: Path, k: int) -> ComparativeReport:
        # Para cada provider: roda eval_dataset completo
        # Paired t-test por métrica (mesmas queries)
        # Bootstrap IC 95%
        # Retorna DataFrame + Markdown table
```

### DriftDetector
```python
class DriftDetector:
    def check(self, current_metrics: dict, baseline_path: Path, threshold: float = 0.10) -> DriftResult:
        # Carrega baseline JSON
        # Compara cada métrica: (current - baseline) / baseline
        # Se qualquer > threshold: DRIFT
        # Exit code: 0=ok, 1=drift, 2=error
```

---

## 6. Estimativa de Esforço (T-shirt)

| Componente | Tamanho | Rationale |
|------------|---------|-----------|
| `EvaluatorProvider` ABC + 3 providers | M | Similar a `EmbeddingProvider` / `LLMProvider` |
| `CritiqueAndRefineSynthesizer` | S | Wrapper simples, lógica clara |
| `ComparativeEvaluator` + stats | M | scipy + bootstrap; output formatting |
| `DriftDetector` | S | JSON diff + exit codes |
| `CostEstimator` | S | Lookup table + multiplicação |
| CLI integration + flags | S | Extensão `cli_eval.py` existente |
| `eval_log` DDL + persistência | S | Similar a `query_log` |
| Testes (unit + integration) | M | Contract tests + integration |
| **Total** | **M-L** | ~23 ações (similar a feature 002) |

---
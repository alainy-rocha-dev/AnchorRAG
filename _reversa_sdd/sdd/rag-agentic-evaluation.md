# Spec SDD: rag-agentic-evaluation

> Identificador: `rag-agentic-evaluation`
> Versão: `1.0.0`
> Data: `2026-10-05`
> Status: `implemented`
> Features: `003-agentic-rag-evaluation`
> Confidência: 🟢 CONFIRMADO (implementado e testado)

---

## 1. Propósito

Implementa camada de **avaliação agentic** sobre o pipeline RAG existente, fornecendo:
1. **LLM-as-Judge** para 4 métricas RAGAS-like (faithfulness, answer_relevancy, context_precision, context_recall)
2. **Critique-and-Refine** loop de auto-melhoria iterativa (máx 2 refinamentos)
3. **Comparative Evaluation** multi-provedor com paired t-test + bootstrap IC 95%
4. **Drift Detection** para monitoramento contínuo de degradação
5. **Cost Estimation** com pricing table por provedor/modelo

---

## 2. Arquitetura

### 2.1 Componentes Novos (em `src/anchor_rag/evaluation/`)

| Módulo | Responsabilidade | Padrão |
|--------|------------------|--------|
| `evaluator.py` | `EvaluatorProvider` ABC + 3 providers (OpenAI, Ollama, Anthropic) + factory | Strategy + Registry |
| `critique_refine.py` | `CritiqueAndRefineSynthesizer` wrapper sobre `RAGSynthesizer` | Decorator/Wrapper |
| `comparative.py` | `ComparativeEvaluator` + estatísticas (scipy) | Orchestrator |
| `drift.py` | `DriftDetector` (baseline JSON → diff → exit codes) | Monitor |
| `cost.py` | `CostEstimator` (pricing table × tokens → USD) | Calculator |
| `__init__.py` | Registry + factory `create_evaluator_provider()` | Factory |

### 2.2 Integração com Existente

- **Config**: `EvaluationConfig` em `config.py` (Pydantic Settings)
- **Domain**: Novos modelos `EvalMetrics` (estendido), `ComparativeMetrics`, `DriftResult`, `CostEstimate`
- **Vector Store**: Tabela `eval_log` em `SQLiteVecStore` (DDL idempotente)
- **Pipeline**: `eval_dataset_agentic()`, `drift_check()` em `RAGPipeline`
- **CLI**: Flags `--agentic`, `--judge`, `--compare`, `--drift-check`, `--baseline`, `--output`

---

## 3. Contratos

### 3.1 EvaluatorProvider ABC

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

**Providers implementados:**
- `OpenAIEvaluatorProvider` (OpenAI API, retry tenacity)
- `OllamaEvaluatorProvider` (Ollama local HTTP)
- `AnthropicEvaluatorProvider` (Anthropic API, retry tenacity)

### 3.2 CritiqueAndRefineSynthesizer

```python
class CritiqueAndRefineSynthesizer:
    def __init__(self, synthesizer: RAGSynthesizer, evaluator: EvaluatorProvider, thresholds: dict, max_iterations: int = 2):
    async def synthesize(self, query: str, chunks: List[Chunk], config: QueryConfig) -> Tuple[QueryResult, CritiqueAndRefineResult]:
```

**Fluxo:**
1. Gera resposta base → avalia 4 métricas
2. Se qualquer score < threshold: gera critique → refina (máx 2 iterações)
3. Retorna melhor resposta + trail completo

### 3.3 ComparativeEvaluator

```python
class ComparativeEvaluator:
    async def compare(self, providers: List[str], dataset: Path, k: int) -> ComparativeReport:
```

**Estatísticas:**
- Paired t-test (scipy.stats.ttest_rel) - mesmas queries
- Bootstrap IC 95% (1000 resamples)
- Significância: p < 0.05

### 3.4 DriftDetector

```python
class DriftDetector:
    def check(self, current_metrics: dict, baseline_path: Path, threshold: float = 0.10) -> DriftResult:
```

**Exit codes:**
- `0` = OK (sem drift > threshold)
- `1` = Drift detectado
- `2` = Erro (baseline inválido)

### 3.5 CostEstimator

```python
class CostEstimator:
    def estimate_eval_run_cost(self, judge_provider, judge_model, synthesis_provider, synthesis_model, num_queries, avg_tokens, max_refine) -> CostEstimate:
```

**Pricing table** (configurável em `config.yaml`):
```yaml
evaluation:
  pricing_table:
    openai:
      gpt-4o-mini: {input: 0.15, output: 0.60}
    anthropic:
      claude-3-haiku: {input: 0.25, output: 1.25}
    ollama: {}  # custo 0
```

---

## 4. Modelos de Dados

### 4.1 Tabela `eval_log` (SQLite)

```sql
CREATE TABLE eval_log (
    id TEXT PRIMARY KEY,
    eval_run_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    query TEXT NOT NULL,
    judge_provider TEXT NOT NULL,
    judge_model TEXT NOT NULL,
    faithfulness REAL,
    answer_relevancy REAL,
    context_precision REAL,
    context_recall REAL,
    tokens_input INTEGER,
    tokens_output INTEGER,
    estimated_cost_usd REAL,
    iterations INTEGER DEFAULT 1,
    config_hash TEXT NOT NULL,
    dataset_hash TEXT NOT NULL
);
CREATE INDEX idx_eval_log_run ON eval_log(eval_run_id);
CREATE INDEX idx_eval_log_timestamp ON eval_log(timestamp);
```

### 4.2 Baseline JSON

```json
{
  "dataset_hash": "sha256...",
  "config_hash": "sha256...",
  "metrics": {
    "faithfulness": 0.85,
    "answer_relevancy": 0.82,
    "context_precision": 0.78,
    "context_recall": 0.80
  },
  "created_at": "2026-10-05T10:00:00Z",
  "eval_run_id": "uuid..."
}
```

### 4.3 EvaluationConfig (AppConfig)

```python
class EvaluationConfig(BaseSettings):
    judge_provider: Literal["openai", "ollama", "anthropic"] = "openai"
    judge_model: str = "gpt-4o-mini"
    judge_temperature: float = 0.0
    judge_max_tokens: int = 1024
    thresholds: dict[str, float] = {
        "faithfulness": 0.7,
        "answer_relevancy": 0.7,
        "context_precision": 0.7,
        "context_recall": 0.7,
    }
    max_refine_iterations: int = 2
    cost_budget_usd: float = 0.50
    pricing_table: dict = {}
```

---

## 5. CLI

### 5.1 Flags Novas

| Flag | Tipo | Descrição |
|------|------|-----------|
| `--agentic` | bool | Ativa modo agentic (LLM-as-judge + métricas RAGAS) |
| `--judge` | str | Provedor judge: `openai`, `ollama`, `anthropic` |
| `--compare` | str | CSV de provedores para comparative: `openai,ollama` |
| `--drift-check` | bool | Modo drift detection (requer `--baseline`) |
| `--baseline` | path | Arquivo JSON baseline para drift check |
| `--output` | path | Arquivo de saída (JSON/Markdown) |

### 5.2 Exemplos de Uso

```bash
# Eval agentic básico
hag-rag eval --dataset tests/fixtures/eval_dataset_bacen.yaml \
             --agentic --judge ollama \
             --config config.yaml

# Comparative evaluation
hag-rag eval --dataset tests/fixtures/eval_dataset_bacen.yaml \
             --agentic --compare openai,ollama,anthropic \
             --config config.yaml

# Drift detection
hag-rag eval --dataset tests/fixtures/eval_dataset_bacen.yaml \
             --agentic --judge ollama \
             --drift-check --baseline baseline.json \
             --config config.yaml

# Baseline generation
hag-rag eval --dataset tests/fixtures/eval_dataset_bacen.yaml \
             --agentic --judge ollama \
             --output baseline.json --config config.yaml
```

---

## 6. Regras de Negócio

| ID | Regra | Descrição |
|----|-------|-----------|
| BR-044 | Judge provider separado | Avaliação deve usar LLM diferente do LLM de síntese (evita viés) |
| BR-045 | Thresholds por métrica | Cada métrica tem threshold próprio (default 0.7) |
| BR-046 | Max 2 refinamentos | Critique-and-refine limitado a 2 iterações (3 chamadas LLM total) |
| BR-047 | Drift threshold 10% | Queda relativa >10% vs baseline dispara alerta |

---

## 7. Testes

| Teste | Arquivo | Cobertura |
|-------|---------|-----------|
| Contract tests | `tests/unit/test_evaluator_contract.py` | ABC + 3 providers + factory |
| Critique-refine | `tests/integration/test_critique_refine.py` | ≤3 chamadas LLM, trail scores, threshold logic |
| Comparative | `tests/integration/test_comparative_eval.py` | Paired t-test, bootstrap CI, p-value, significance |
| Drift detection | `tests/integration/test_drift_detection.py` | Exit codes 0/1/2, threshold custom, baseline creation |

---

## 8. Métricas de Qualidade

| Métrica | Target | Status |
|---------|--------|--------|
| Contract tests passing | 100% | ✅ |
| Integration tests passing | 100% | ✅ |
| Max LLM calls per query (agentic) | ≤3 | ✅ |
| Drift detection accuracy | >95% | ✅ |
| Comparative statistical validity | p<0.05 detection | ✅ |

---

## 9. Riscos Conhecidos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Judge LLM indisponível | Média | Médio | Skip provider no comparative; fallback configurável |
| Custo excede orçamento | Média | Médio | `CostEstimator` warning prévio; `--max-cost` futuro |
| Paired t-test inválido (n<30) | Baixa | Baixo | Documentar limitação; Wilcoxon como alternativa futura |
| Few-shot prompts não calibrados | Média | Médio | Prompts com 3 exemplos por métrica; ajustável via fixtures |

---

## 10. Rastreabilidade

| Artefato | Link |
|----------|------|
| Requirements | `_reversa_forward/003-agentic-rag-evaluation/requirements.md` |
| Roadmap | `_reversa_forward/003-agentic-rag-evaluation/roadmap.md` |
| Actions | `_reversa_forward/003-agentic-rag-evaluation/actions.md` |
| Progress | `_reversa_forward/003-agentic-rag-evaluation/progress.jsonl` |
| Legacy Impact | `_reversa_forward/003-agentic-rag-evaluation/legacy-impact.md` |
| Regression Watch | `_reversa_forward/003-agentic-rag-evaluation/regression-watch.md` |
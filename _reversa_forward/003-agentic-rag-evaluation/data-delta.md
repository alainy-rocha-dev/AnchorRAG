# Data Delta: agentic-rag-evaluation

> Feature: `003-agentic-rag-evaluation`
> Data: `2026-09-30`
> Base: `_reversa_sdd/domain.md`, `_reversa_sdd/architecture.md` (ERD), adendo 002

---

## 1. Novas Entidades

### `EvalLog` (Nova Tabela)
| Campo | Tipo | Constraints | Descrição |
|-------|------|-------------|-----------|
| `id` | TEXT (UUID) | PK | Identificador único do log |
| `eval_run_id` | TEXT (UUID) | NOT NULL, INDEX | Agrupa queries do mesmo run de avaliação |
| `timestamp` | TIMESTAMP | NOT NULL, INDEX | Quando a avaliação ocorreu |
| `query` | TEXT | NOT NULL | Pergunta avaliada |
| `judge_provider` | TEXT | NOT NULL | `openai`, `ollama`, `anthropic` |
| `judge_model` | TEXT | NOT NULL | Ex.: `gpt-4o-mini`, `llama3.1:8b` |
| `faithfulness` | REAL | NULLABLE | Score 0.0-1.0 |
| `answer_relevancy` | REAL | NULLABLE | Score 0.0-1.0 |
| `context_precision` | REAL | NULLABLE | Score 0.0-1.0 |
| `context_recall` | REAL | NULLABLE | Score 0.0-1.0 |
| `tokens_input` | INTEGER | NULLABLE | Tokens de entrada (prompt judge) |
| `tokens_output` | INTEGER | NULLABLE | Tokens de saída (resposta judge) |
| `estimated_cost_usd` | REAL | NULLABLE | Custo estimado USD |
| `iterations` | INTEGER | DEFAULT 1 | 1=baseline, 2=refine_1, 3=refine_2 |
| `config_hash` | TEXT (SHA256) | NOT NULL | Hash da config de avaliação (para drift) |
| `dataset_hash` | TEXT (SHA256) | NOT NULL | Hash do dataset (para drift) |

**DDL:**
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

### `EvaluationConfig` (Nova Seção em AppConfig)
Adicionado em `config.py`:
```python
class EvaluationConfig(BaseSettings):
    judge_provider: Literal["openai", "ollama", "anthropic"] = "openai"
    judge_model: str = "gpt-4o-mini"
    judge_temperature: float = 0.0
    judge_max_tokens: int = 1024
    thresholds: dict[str, float] = Field(default_factory=lambda: {
        "faithfulness": 0.7,
        "answer_relevancy": 0.7,
        "context_precision": 0.7,
        "context_recall": 0.7,
    })
    max_refine_iterations: int = 2
    cost_budget_usd: float = 0.50
    pricing_table: dict[str, dict[str, float]] = Field(default_factory=dict)
```

---

## 2. Entidades Existentes - Sem Alteração

As seguintes tabelas/entidades **não mudam** (backward compatibility):

| Entidade | Status | Nota |
|----------|--------|------|
| `documents` | Inalterada | Tabela principal de documentos |
| `chunks` | Inalterada | Chunks com embeddings |
| `chunks_vec` | Inalterada | Virtual table sqlite-vec |
| `query_log` | Inalterada | Logs de produção (não eval) |
| `Document` (domain) | Inalterada | Modelo Pydantic |
| `Chunk` (domain) | Inalterada | Modelo Pydantic |
| `QueryResult` (domain) | Inalterada | Modelo Pydantic |

---

## 3. Novos Modelos Pydantic (domain/models.py)

### `EvalMetrics` (Estendido)
```python
@dataclass
class EvalMetrics:
    recall_at_k: float
    mrr: float
    hallucination_rate: float
    citation_coverage: float
    total_queries: int
    successful_queries: int
    # NOVOS (agentic):
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    # Por query (opcional, para relatório detalhado)
    per_query: List[Dict[str, Any]] = Field(default_factory=list)
```

### `ComparativeMetrics`
```python
@dataclass
class ComparativeMetrics:
    provider_a: str
    provider_b: str
    metric: str
    mean_a: float
    mean_b: float
    mean_diff: float
    p_value: float
    ci_95_lower: float
    ci_95_upper: float
    significant: bool  # p < 0.05
```

### `DriftResult`
```python
@dataclass
class DriftResult:
    has_drift: bool
    metric_diffs: Dict[str, float]  # relative diff (current - baseline) / baseline
    threshold: float
    baseline_metrics: Dict[str, float]
    current_metrics: Dict[str, float]
    exit_code: int  # 0=ok, 1=drift, 2=error
```

### `CostEstimate`
```python
@dataclass
class CostEstimate:
    total_tokens_input: int
    total_tokens_output: int
    estimated_cost_usd: float
    per_query: List[Dict[str, Any]]
    budget_exceeded: bool
```

---

## 4. Migrações Necessárias

### Migração 1: Criação da tabela `eval_log`
- **Tipo:** Schema-only (nova tabela)
- **Risco:** Baixo (tabela isolada, sem FK para tabelas existentes)
- **Rollback:** `DROP TABLE eval_log`
- **Execução:** Em `SQLiteVecStore.init_db()` (idempotente via `CREATE TABLE IF NOT EXISTS`)

### Migração 2: Adição de `EvaluationConfig` em `AppConfig`
- **Tipo:** Config-only (novo campo opcional com defaults)
- **Risco:** Baixo (defaults sensíveis, validador opcional)
- **Rollback:** Remover campo `evaluation` do `AppConfig`
- **Execução:** Automática ao carregar config (Pydantic ignora campos extras)

---

## 5. Impacto em Artefatos de Extração

| Artefato | Seção | Impacto |
|----------|-------|---------|
| `domain.md` | 2. Regras de Negócio | +4 novas regras (BR-044 a BR-047) |
| `domain.md` | 5. Lacunas | Lacunas #1-4 resolvidas (judge provider, thresholds, calibração, eval_log) |
| `architecture.md` | 3. C4 Containers | +1 container `Evaluation Engine` |
| `architecture.md` | 4. ERD | +1 tabela `eval_log` |
| `architecture.md` | 5. Componentes | +6 módulos em `evaluation/` |
| `architecture.md` | 7. Dívidas | TD-002 (scores não expostos) parcialmente endereçado via eval metrics |

---
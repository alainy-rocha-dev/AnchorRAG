# Roadmap: agentic-rag-evaluation

> Feature: `003-agentic-rag-evaluation`
> Data: `2026-09-30`
> Base: `_reversa_sdd/` (legado) + adendo 002 vigente

---

## 1. Resumo da Abordagem

Implementar camada de avaliação agentic sobre o pipeline RAG existente (features 001 + 002). A arquitetura segue o padrão **Strategy** já consolidado no projeto: novos componentes `EvaluatorProvider` (ABC + 3 implementações), `CritiqueAndRefineSynthesizer` (wrapper sobre `RAGSynthesizer`), `ComparativeEvaluator`, `DriftDetector` e `CostEstimator`. Tudo exposto via extensão do CLI `eval` (`--agentic`, `--judge`, `--compare`, `--drift-check`).

**Delta arquitetural:** Adiciona container `Evaluation Engine` no C4 nível 2, consumindo `LLM Providers` (já existentes) e `Query Engine` (já existente), produzindo `EvalMetrics` estendidos + `EvalLog` persistido.

---

## 2. Princípios Aplicados

| Princípio | Avaliação |
|-----------|-----------|
| **Strategy Pattern para providers** | ✅ Respeitado: `EvaluatorProvider` ABC + registry/factory igual a `EmbeddingProvider` e `LLMProvider` |
| **Fail-fast config** | ✅ Respeitado: validadores no `AppConfig` para judge provider, thresholds |
| **Strict grounding** | ✅ Respeitado: judge prompts herdam few-shot defense (BR-022) |
| **Observabilidade por etapa** | ✅ Respeitado: log JSON estruturado por fase (retrieve, synthesize, judge_*, refine_*) |
| **Extensibilidade** | ✅ Respeitado: ABC permite plugar evaluators futuros (fine-tuned, human-in-the-loop) |
| **Custo controlado** | ⚠️ Parcial: orçamento $0.50/run definido, mas enforcement via `CostEstimator` warning, não hard-block |

---

## 3. Decisões Técnicas

| Decisão | Confidência | Justificativa |
|---------|-------------|---------------|
| **Judge provider default**: `OpenAI gpt-4o-mini` (configurável via `evaluation.judge_provider`) | 🟡 (premissa Lacuna #1) | Melhor custo/qualidade para judge; Ollama local como fallback para privacidade |
| **Thresholds qualidade**: `faithfulness=0.7, answer_relevancy=0.7, context_precision=0.7, context_recall=0.7` | 🟡 (premissa Lacuna #2) | Valor conservador alinhado a literatura RAGAS; configurável via `evaluation.thresholds` |
| **Calibração judge**: Few-shot mínimo (3 exemplos por métrica) embutido no prompt; sem dataset externo | 🟡 (premissa Lacuna #3) | Evita dependência de dataset curado; few-shot no prompt já provou eficácia em BR-022 |
| **Persistência eval_log**: Nova tabela `eval_log` (não estender `query_log`) | 🔴 (premissa Lacuna #4) | Separação de concerns: `query_log` = produção; `eval_log` = avaliação offline. Backward compat mantida. |
| **Max iterações refine**: 2 (hardcoded, não configurável) | 🟢 | RN-03 explícito; evita complexidade de config extra |
| **Temperature judge**: 0 (determinístico), seed fixo | 🟢 | RNF Confiabilidade; reprodutibilidade científica |
| **Estatísticas comparative**: paired t-test (scipy), IC 95% | 🟢 | Padrão científico para comparação pareada mesma queries |

---

## 4. Delta Arquitetural (C4 Container)

### Novo Container
```
Container(eval_engine, "Evaluation Engine", "Python async", "LLM-as-judge + critique-refine + comparative + drift")
```

### Novas Relações
| De | Para | Protocolo | Descrição |
|----|------|-----------|-----------|
| `eval_engine` | `llm_prov` (judge) | Strategy `EvaluatorProvider` | `eval_faithfulness`, `eval_relevancy`, `eval_precision`, `eval_recall` |
| `eval_engine` | `query_engine` | Python async | Reusa `RAGPipeline.query()` para gerar resposta base |
| `eval_engine` | `llm_prov` (synthesis) | Strategy `LLMProvider` | `CritiqueAndRefineSynthesizer` usa LLM de síntese + LLM judge separados |
| `eval_engine` | `eval_log` (DB) | SQLite | Persiste `eval_run_id`, scores, tokens, custo |

### Componentes Novos (em `src/anchor_rag/`)
| Módulo | Responsabilidade |
|--------|------------------|
| `evaluation/evaluator.py` | `EvaluatorProvider` ABC + `LLMAsJudgeEvaluator` (3 providers) + factory |
| `evaluation/critique_refine.py` | `CritiqueAndRefineSynthesizer` wrapper |
| `evaluation/comparative.py` | `ComparativeEvaluator` + stats (t-test, IC95%) |
| `evaluation/drift.py` | `DriftDetector` (baseline JSON → diff → exit code) |
| `evaluation/cost.py` | `CostEstimator` (pricing table por provider/modelo) |
| `evaluation/__init__.py` | Registry + factory `create_evaluator_provider()` |

---

## 5. Delta de Dados

### Nova Tabela: `eval_log`
```sql
CREATE TABLE eval_log (
    id TEXT PRIMARY KEY,              -- UUID
    eval_run_id TEXT NOT NULL,        -- Agrupa queries do mesmo run
    timestamp TIMESTAMP NOT NULL,
    query TEXT NOT NULL,
    judge_provider TEXT NOT NULL,     -- openai, ollama, anthropic
    judge_model TEXT NOT NULL,        -- ex.: gpt-4o-mini
    faithfulness REAL,
    answer_relevancy REAL,
    context_precision REAL,
    context_recall REAL,
    tokens_input INTEGER,
    tokens_output INTEGER,
    estimated_cost_usd REAL,
    iterations INTEGER DEFAULT 1,     -- 1=baseline, 2=refine_1, 3=refine_2
    config_hash TEXT NOT NULL,        -- Hash da config usada (dataset + eval params)
    dataset_hash TEXT NOT NULL        -- Hash do dataset (para drift detection)
);
CREATE INDEX idx_eval_log_run ON eval_log(eval_run_id);
CREATE INDEX idx_eval_log_timestamp ON eval_log(timestamp);
```

### Baseline JSON (para DriftDetector)
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
  "created_at": "2026-09-30T10:00:00Z",
  "eval_run_id": "uuid..."
}
```

### Mudanças em `AppConfig` (config.py)
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
    pricing_table: dict[str, dict[str, float]] = Field(default_factory=dict)  # provider->model->{input,output}
```

---

## 6. Delta de Contratos Externos

### CLI Estendido (`cli_eval.py`)
| Flag | Tipo | Descrição |
|------|------|-----------|
| `--agentic` | bool | Ativa modo agentic (LLM-as-judge + métricas RAGAS) |
| `--judge` | str | Provedor judge: `openai`, `ollama`, `anthropic` (default: config) |
| `--compare` | str | Lista CSV de provedores para comparative eval: `openai,ollama` |
| `--drift-check` | bool | Modo drift detection (requer `--baseline`) |
| `--baseline` | path | Arquivo JSON baseline para drift check |
| `--output` | path | Arquivo de saída (JSON/Markdown) |

### Exit Codes (DriftDetector)
| Code | Significado |
|------|-------------|
| 0 | OK (sem drift > threshold) |
| 1 | Drift detectado (>10% default, configurável) |
| 2 | Erro (baseline inválido, execução falhou) |

---

## 7. Plano de Migração / Execução

1. **Fase 1 - Preparação**: `EvaluationConfig` em `config.py`, `eval_log` DDL em `sqlite_vec.py`, factory skeleton
2. **Fase 2 - Testes**: Contract tests `EvaluatorProvider`, fixtures para judge prompts
3. **Fase 3 - Núcleo**: 3 providers judge, `CritiqueAndRefineSynthesizer`, `ComparativeEvaluator`, `DriftDetector`, `CostEstimator`
4. **Fase 4 - Integração**: CLI flags, persistência `eval_log`, specs SDD update
5. **Fase 5 - Polimento**: Docs inline, regression-watch, legacy-impact

---

## 8. Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Judge LLM indisponível (API key, Ollama down) | 🟡 Média | 🟡 Médio | Skip provider indisponível no comparative; fallback configurável |
| Custo eval run excede orçamento | 🟡 Média | 🟡 Médio | `CostEstimator` warning prévio; `--max-cost` flag futuro |
| Thresholds muito baixos/altos geram falso positivo/negativo | 🟡 Média | 🟡 Médio | Defaults conservadores (0.7); configurável; logs de calibração |
| Schema `eval_log` conflita com futura migração | 🟢 Baixa | 🟢 Baixo | Tabela separada; DDL versionado; backward compat `query_log` intacta |
| Paired t-test inválido (n<30, não-normal) | 🟢 Baixa | 🟢 Baixo | Documentar limitação; Wilcoxson signed-rank como alternativa futura |

---

## 9. Critério de Pronto

- [ ] `pytest tests/unit/test_evaluator_contract.py` passa (3 providers)
- [ ] `pytest tests/integration/test_critique_refine.py` passa (≤3 chamadas LLM, trail scores)
- [ ] `hag-rag eval --dataset bacen --agentic --judge ollama` produz relatório 4 métricas + agregadas
- [ ] `hag-rag eval --dataset bacen --agentic --compare openai,ollama` gera tabela estatística (p-value, IC95%)
- [ ] `hag-rag eval --drift-check --baseline baseline.json` exit code 0/1/2 correto
- [ ] `eval_log` tabela criada e populada em runs agentic
- [ ] Specs SDD atualizadas (nova spec `rag-agentic-evaluation.md` ou extensão de existente)
- [ ] 100% ações em `actions.md` marcadas `[X]`

---
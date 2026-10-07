# Onboarding: agentic-rag-evaluation

> Feature: `003-agentic-rag-evaluation`
> Data: `2026-09-30`
> Público: Desenvolvedor que vai testar a feature pela primeira vez

---

## 1. Pré-requisitos

- Projeto HAG RAG clonado e dependências instaladas (`pip install -e ".[dev]"`)
- Feature 001 (pipeline RAG base) e 002 (hardening) já integradas
- Configuração válida em `config.yaml` (embedding + LLM funcionando)
- Dataset BACEN em `tests/fixtures/eval_dataset_bacen.yaml` (já existe da feature 002)

### Provedores LLM Disponíveis
| Provedor | Requisito | Como Testar |
|----------|-----------|-------------|
| **OpenAI** | `OPENAI_API_KEY` no `.env` | `hag-rag eval --agentic --judge openai` |
| **Ollama** | Ollama rodando local (`ollama serve`) + modelo `llama3.1:8b` | `hag-rag eval --agentic --judge ollama` |
| **Anthropic** | `ANTHROPIC_API_KEY` no `.env` | `hag-rag eval --agentic --judge anthropic` |

---

## 2. Primeiro Teste Rápido (Smoke Test)

```bash
# 1. Verifica se CLI carrega
hag-rag eval --help

# 2. Health checks básicos (sem dataset)
hag-rag eval --config config.yaml

# 3. Avaliação agentic com Ollama (local, grátis)
hag-rag eval --dataset tests/fixtures/eval_dataset_bacen.yaml \
             --agentic --judge ollama \
             --config config.yaml
```

**Saída esperada (resumida):**
```
Avaliação do Pipeline AnchorRAG
╭──────────────────────────────────────────────────────╮
│ Health Checks                                        │
├──────────────────────┬──────────────────────────────┤
│ Embedding Provider   │ ✓ OK                         │
│ LLM Provider         │ ✓ OK                         │
╰──────────────────────┴──────────────────────────────╯
╭──────────────────────────────────────────────────────╮
│ Métricas Agentic (k=5)                               │
├──────────────────────┬──────────────────────────────┤
│ Faithfulness         │ 0.82                         │
│ Answer Relevancy     │ 0.79                         │
│ Context Precision    │ 0.75                         │
│ Context Recall       │ 0.78                         │
│ Total Queries        │ 20                           │
│ Successful           │ 20                           │
╰──────────────────────┴──────────────────────────────╯
Resumo
Faithfulness: 82.00%  |  Answer Relevancy: 79.00%  |  Context Precision: 75.00%  |  Context Recall: 78.00%
```

---

## 3. Cenários de Uso Completos

### 3.1 Avaliação Agentic Básica
```bash
# Com saída JSON para automação
hag-rag eval --dataset tests/fixtures/eval_dataset_bacen.yaml \
             --agentic --judge ollama \
             --format json --config config.yaml > eval_result.json
```

### 3.2 Critique-and-Refine (Auto-melhoria)
```bash
# Ativa refine automático (threshold default 0.7)
hag-rag eval --dataset tests/fixtures/eval_dataset_bacen.yaml \
             --agentic --judge ollama \
             --config config.yaml
# Logs mostram: retrieve → synthesize → judge_faithfulness → judge_relevancy → (refine_1) → (refine_2)
```

### 3.3 Comparação Multi-Provedor (Decisão de Custo/Qualidade)
```bash
# Compara OpenAI vs Ollama vs Anthropic nas mesmas 20 queries
hag-rag eval --dataset tests/fixtures/eval_dataset_bacen.yaml \
             --agentic --compare openai,ollama,anthropic \
             --config config.yaml
```

**Saída esperada (tabela estatística):**
```
Comparative Evaluation: openai vs ollama vs anthropic
╭─────────────┬──────────┬──────────┬──────────┬─────────┬──────────┬──────────┬─────────┐
│ Metric      │ openai   │ ollama   │ anthropic │ p-value │ sig?     │ CI95 Low │ CI95 Hi │
├─────────────┼──────────┼──────────┼──────────┼─────────┼──────────┼──────────┼─────────┤
│ Faithful.   │ 0.88     │ 0.79     │ 0.85     │ 0.03    │ ✓        │ -0.15    │ -0.02   │
│ Relevancy   │ 0.85     │ 0.76     │ 0.82     │ 0.07    │ ✗        │ -0.12    │ 0.01    │
│ Precision   │ 0.81     │ 0.72     │ 0.78     │ 0.11    │ ✗        │ -0.10    │ 0.02    │
│ Recall      │ 0.83     │ 0.75     │ 0.80     │ 0.09    │ ✗        │ -0.11    │ 0.03    │
╰─────────────┴──────────┴──────────┴──────────┴─────────┴──────────┴──────────┴─────────┘
```

### 3.4 Drift Detection (Monitoramento Contínuo)

**Passo 1: Gerar baseline**
```bash
hag-rag eval --dataset tests/fixtures/eval_dataset_bacen.yaml \
             --agentic --judge ollama \
             --output baseline.json --config config.yaml
```

**Passo 2: Verificar drift posterior**
```bash
# Após mudanças no pipeline (novo modelo, novo chunking, etc.)
hag-rag eval --dataset tests/fixtures/eval_dataset_bacen.yaml \
             --agentic --judge ollama \
             --drift-check --baseline baseline.json \
             --config config.yaml
```

**Exit codes:**
- `0` = OK (sem drift > 10%)
- `1` = DRIFT DETECTED (ex.: `faithfulness -12.9% (0.85 → 0.74)`)
- `2` = Erro (baseline inválido, execução falhou)

### 3.5 Estimativa de Custo
```bash
# Relatório inclui custo estimado por query + total
hag-rag eval --dataset tests/fixtures/eval_dataset_bacen.yaml \
             --agentic --judge openai \
             --format json --config config.yaml | jq '.pipeline.per_query[0].estimated_cost_usd'
```

---

## 4. Configuração Avançada (`config.yaml`)

```yaml
evaluation:
  judge_provider: "ollama"        # openai, ollama, anthropic
  judge_model: "llama3.1:8b"      # modelo do judge
  judge_temperature: 0.0          # determinístico
  judge_max_tokens: 1024
  thresholds:                     # thresholds que disparam refine
    faithfulness: 0.7
    answer_relevancy: 0.7
    context_precision: 0.7
    context_recall: 0.7
  max_refine_iterations: 2        # hardcoded, não recomendado mudar
  cost_budget_usd: 0.50           # warning se exceder
  pricing_table:                  # $/1M tokens (input, output)
    openai:
      gpt-4o-mini: {input: 0.15, output: 0.60}
      gpt-4o: {input: 2.50, output: 10.00}
    anthropic:
      claude-3-haiku: {input: 0.25, output: 1.25}
      claude-3-sonnet: {input: 3.00, output: 15.00}
    ollama: {}  # custo 0 (local)
```

---

## 5. Estrutura de Arquivos da Feature

```
src/anchor_rag/
├── config.py                      # + EvaluationConfig
├── evaluation/
│   ├── __init__.py                # factory create_evaluator_provider()
│   ├── evaluator.py               # EvaluatorProvider ABC + 3 providers
│   ├── critique_refine.py         # CritiqueAndRefineSynthesizer
│   ├── comparative.py             # ComparativeEvaluator + stats
│   ├── drift.py                   # DriftDetector
│   └── cost.py                    # CostEstimator
├── pipeline/orchestrator.py       # + eval_dataset agentic, drift_check
├── cli_eval.py                    # + flags --agentic, --judge, --compare, --drift-check
├── vector_store/sqlite_vec.py     # + eval_log table DDL
└── domain/models.py               # + EvalMetrics, ComparativeMetrics, DriftResult, CostEstimate

tests/
├── unit/test_evaluator_contract.py
├── integration/test_critique_refine.py
├── integration/test_comparative_eval.py
├── integration/test_drift_detection.py
└── fixtures/eval_dataset_bacen.yaml  (já existe)
```

---

## 6. Debugging Comum

| Problema | Causa Provável | Solução |
|----------|----------------|---------|
| `OpenAIError: api_key` | `OPENAI_API_KEY` não definido | Definir no `.env` ou usar `--judge ollama` |
| `Ollama health check failed` | Ollama não rodando | `ollama serve` + `ollama pull llama3.1:8b` |
| `ModuleNotFoundError: scipy` | Dependência faltando | `pip install scipy` (já em `pyproject.toml` dev) |
| Drift check exit code 2 | Baseline JSON malformado | Verificar `--baseline` path; regenerar baseline |
| Métricas todas 0.0 | Judge não consegue parsear resposta | Verificar logs JSON (`--verbose`); ajustar few-shot prompts |
| Timeout no eval | LLM lento / sem streaming | Aumentar `judge_max_tokens` ou usar modelo menor |

---

## 7. Logs Estruturados (JSON)

Cada etapa loga com `request_id` correlacionado:
```json
{"ts":"2026-09-30T10:00:00Z","level":"INFO","msg":"eval_agentic_start","request_id":"uuid","dataset":"bacen","judge":"ollama"}
{"ts":"2026-09-30T10:00:01Z","level":"INFO","msg":"retrieve_done","request_id":"uuid","query_id":0,"chunks":5,"latency_ms":45}
{"ts":"2026-09-30T10:00:03Z","level":"INFO","msg":"synthesize_done","request_id":"uuid","query_id":0,"latency_ms":1200}
{"ts":"2026-09-30T10:00:05Z","level":"INFO","msg":"judge_faithfulness_done","request_id":"uuid","query_id":0,"score":0.85,"latency_ms":800}
{"ts":"2026-09-30T10:00:06Z","level":"INFO","msg":"judge_relevancy_done","request_id":"uuid","query_id":0,"score":0.82,"latency_ms":750}
{"ts":"2026-09-30T10:00:07Z","level":"INFO","msg":"refine_1_done","request_id":"uuid","query_id":0,"score_improvement":0.12}
{"ts":"2026-09-30T10:00:10Z","level":"INFO","msg":"eval_agentic_complete","request_id":"uuid","total_queries":20,"faithfulness_avg":0.82}
```

---

## 8. Próximos Passos para o Desenvolvedor

1. **Rode o smoke test** (seção 2) com seu provedor preferido
2. **Explore os logs** com `--verbose` para entender o fluxo
3. **Teste comparative** se tiver 2+ provedores configurados
4. **Gere baseline** e teste drift detection
5. **Ajuste thresholds** no `config.yaml` se necessário
6. **Revise código** em `src/anchor_rag/evaluation/` para entender extensibilidade

---

## 9. Referências Rápidas

| Comando | Descrição |
|---------|-----------|
| `hag-rag eval --help` | Todas as flags |
| `hag-rag eval --dataset bacen --agentic --judge ollama` | Eval agentic básico |
| `hag-rag eval --dataset bacen --agentic --compare openai,ollama` | Comparativo estatístico |
| `hag-rag eval --drift-check --baseline baseline.json` | Drift detection |
| `pytest tests/unit/test_evaluator_contract.py -v` | Testes contratos |
| `pytest tests/integration/test_critique_refine.py -v` | Testes critique-refine |
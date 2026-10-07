# Legacy Impact: agentic-rag-evaluation

> Feature: `003-agentic-rag-evaluation`
> Data: `2026-10-05`
> Política de edição do legado: `allowLegacyEdits: true` | `allowedPaths: ["src/anchor_rag/**", "tests/**", "scripts/**", "docs/**", "README.md", "_reversa_sdd/**", "_reversa_forward/**"]`

---

## 1. Arquivos Afetados

| Arquivo | Componente (architecture.md) | Tipo | Severidade | Justificativa |
|---------|------------------------------|------|------------|---------------|
| `src/anchor_rag/config.py` | Config System | `regra-nova` | LOW | Adição de `EvaluationConfig` com defaults seguros, validadores |
| `src/anchor_rag/evaluation/__init__.py` | Evaluation Engine (novo) | `componente-novo` | LOW | Factory + registry para EvaluatorProvider |
| `src/anchor_rag/evaluation/evaluator.py` | Evaluation Engine (novo) | `componente-novo` | LOW | ABC + 3 providers (OpenAI, Ollama, Anthropic) |
| `src/anchor_rag/evaluation/critique_refine.py` | Evaluation Engine (novo) | `componente-novo` | LOW | Wrapper sobre RAGSynthesizer para critique-and-refine |
| `src/anchor_rag/evaluation/comparative.py` | Evaluation Engine (novo) | `componente-novo` | LOW | ComparativeEvaluator + scipy stats |
| `src/anchor_rag/evaluation/drift.py` | Evaluation Engine (novo) | `componente-novo` | LOW | DriftDetector com baseline JSON |
| `src/anchor_rag/evaluation/cost.py` | Evaluation Engine (novo) | `componente-novo` | LOW | CostEstimator com pricing table |
| `src/anchor_rag/domain/models.py` | Domain Models | `regra-nova` | LOW | +4 modelos Pydantic (EvalMetrics estendido, ComparativeMetrics, DriftResult, CostEstimate) |
| `src/anchor_rag/vector_store/sqlite_vec.py` | Vector Store | `delta-de-dados` | MEDIUM | Nova tabela `eval_log` + métodos log_eval/get_eval_logs/get_eval_stats/get_baseline_metrics |
| `src/anchor_rag/pipeline/orchestrator.py` | Pipeline Orchestrator | `regra-nova` | MEDIUM | +2 métodos: `eval_dataset_agentic()`, `drift_check()` |
| `src/anchor_rag/cli_eval.py` | CLI Interface | `delta-de-contrato-externo` | MEDIUM | +6 flags: `--agentic`, `--judge`, `--compare`, `--drift-check`, `--baseline`, `--output` |
| `src/anchor_rag/logging.py` | Logging | `regra-nova` | LOW | Logging estruturado já suporta request_id; usado nas etapas agentic |
| `tests/unit/test_evaluator_contract.py` | Test Suite | `componente-novo` | LOW | Contract tests para EvaluatorProvider ABC |
| `tests/integration/test_critique_refine.py` | Test Suite | `componente-novo` | LOW | Integração critique-refine |
| `tests/integration/test_comparative_eval.py` | Test Suite | `componente-novo` | LOW | Integração comparative eval |
| `tests/integration/test_drift_detection.py` | Test Suite | `componente-novo` | LOW | Integração drift detection |
| `tests/fixtures/judge_prompts/*.txt` | Test Fixtures | `componente-novo` | LOW | Few-shot prompts para judge (4 métricas × 3 exemplos) |
| `pyproject.toml` | Build Config | `regra-alterada` | LOW | Adicionado `scipy>=1.13.0` em dev dependencies |
| `_reversa_sdd/sdd/rag-agentic-evaluation.md` | SDD Specs | `componente-novo` | LOW | Nova spec SDD documentando a feature |

---

## 2. Diff Conceitual por Componente

### Config System (`config.py`)
**Antes:** `AppConfig` com 7 sub-configs (embedding, llm, chunking, vector_store, retrieval, logging, query_log).
**Depois:** +1 sub-config `evaluation` (EvaluationConfig) com 10 campos, validadores para temperature, max_iterations, budget.
**Impacto:** Backward compatible (defaults sensíveis, extra="ignore"). Configs existentes não afetadas.

### Evaluation Engine (novo módulo `evaluation/`)
**Antes:** Não existia.
**Depois:** 6 arquivos implementando pipeline completo de avaliação agentic.
- `evaluator.py`: Strategy pattern idêntico a `embeddings/` e `synthesis/` (ABC + registry + factory + 3 providers)
- `critique_refine.py`: Decorator pattern sobre `RAGSynthesizer`, reusa LLM de síntese + judge separado
- `comparative.py`: Orquestra eval multi-provedor, usa scipy para estatísticas
- `drift.py`: Compara métricas atuais vs baseline JSON, exit codes para CI/CD
- `cost.py`: Lookup pricing table × tokens → USD, budget check
- `__init__.py`: Factory unificada

### Domain Models (`domain/models.py`)
**Antes:** 8 modelos (Document, Chunk, QueryResult, IngestConfig, QueryConfig, IngestResult, ChunkUnit).
**Depois:** +4 modelos para evaluation agentic:
- `EvalMetrics` estendido: +4 campos agentic (faithfulness, answer_relevancy, context_precision, context_recall) + per_query
- `ComparativeMetrics`: resultado de paired t-test + bootstrap CI
- `DriftResult`: has_drift, metric_diffs, exit_code
- `CostEstimate`: tokens, USD, budget_exceeded

### Vector Store (`sqlite_vec.py`)
**Antes:** Tabelas `documents`, `chunks`, `chunks_vec`, `query_log`.
**Depois:** +1 tabela `eval_log` isolada (sem FK para tabelas existentes).
**DDL:** Idempotente via `CREATE TABLE IF NOT EXISTS` em `init_db()`.
**Métodos novos:** `log_eval()`, `get_eval_logs()`, `get_eval_stats()`, `get_baseline_metrics()`.

### Pipeline Orchestrator (`orchestrator.py`)
**Antes:** `eval_dataset()` (recall@k, MRR, hallucination, citation_coverage).
**Depois:** +2 métodos:
- `eval_dataset_agentic()`: LLM-as-judge 4 métricas + critique-refine + cost estimate
- `drift_check()`: Executa eval agentic + compara vs baseline + retorna DriftResult

### CLI (`cli_eval.py`)
**Antes:** Flags básicas (`--dataset`, `--k`, `--format`, `--verbose`, `--config`).
**Depois:** +6 flags agentic, 3 modos de operação mutuamente exclusivos:
1. `--agentic` (eval agentic single provider)
2. `--compare` (comparative multi-provider + stats)
3. `--drift-check` (drift detection, exit codes 0/1/2)
**Saída:** JSON ou Rich tables formatadas.

---

## 3. Regras Preservadas (🟢 CONFIRMADO)

| Regra (domain.md) | Status | Evidência |
|-------------------|--------|-----------|
| BR-020: Grounding estrito | ✅ Preservada | Judge prompts herdam few-shot defense; síntese usa mesmo RAGSynthesizer |
| BR-021: Citações obrigatórias | ✅ Preservada | CritiqueAndRefineSynthesizer extrai citações [n] do contexto |
| BR-022: Few-shot defense | ✅ Preservada | Judge prompts incluem 3 exemplos por métrica (positivo, negativo, borderline) |
| BR-025: max_chunks=5 | ✅ Preservada | Respeitado no retrieval (top_k default 5) |
| BR-030: 3 provedores LLM intercambiáveis | ✅ Preservada | EvaluatorProvider segue mesmo padrão Strategy |
| BR-031: Streaming + contagem tokens | ✅ Preservada | CostEstimator usa tokens reais quando disponível |
| BR-042: query_log com latência por etapa | ✅ Preservada | Novo eval_log mantém mesma granularidade + métricas agentic |
| TD-002: Scores não expostos | 🟡 Parcialmente endereçado | Eval metrics expõem scores via eval_log e CLI output |
| TD-008: Zero testes automatizados | ✅ Endereçado | +4 novos arquivos de teste (contract + 3 integration) |
| TD-010: Regex citações frágil | ✅ Preservada | Extração de citações mantida do sintetizador original |

---

## 4. Regras Modificadas (🟡 INFERIDO / 🟢 CONFIRMADO)

| Regra | Mudança | Tipo |
|-------|---------|------|
| BR-031 (streaming tokens) | Estendido: CostEstimator agora calcula custo USD baseado em tokens input/output × pricing table | 🟡 INFERIDO (extensão natural) |
| TD-002 (scores não expostos) | Parcialmente resolvido: métricas agentic agora expostas via eval_log, CLI, e EvalMetrics estendido | 🟢 CONFIRMADO (melhoria intencional) |
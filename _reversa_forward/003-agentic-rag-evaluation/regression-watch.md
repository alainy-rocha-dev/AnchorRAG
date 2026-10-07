# Regression Watch: agentic-rag-evaluation

> Feature: `003-agentic-rag-evaluation`
> Data: `2026-10-05`
> Origem: Regras modificadas em `legacy-impact.md`

---

## 1. Watch Items Principais

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|----|-------------------------|------------------------------|---------------------|-------------------|
| W001 | `domain.md#BR-031`, `legacy-impact.md#4` | CostEstimator calcula custo USD corretamente (tokens × pricing table) | `presença` | Custo estimado = 0 ou NaN; pricing table ignorada; budget_exceeded não detectado |
| W002 | `domain.md#BR-031`, `legacy-impact.md#4` | EvalMetrics estendido inclui 4 métricas agentic + per_query | `presença` | Campos `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall` ausentes ou sempre 0 |
| W003 | `legacy-impact.md#4` | Tabela `eval_log` criada e populada em runs agentic | `presença` | `eval_log` não existe; INSERT falha; query retorna vazio |
| W004 | `legacy-impact.md#4` | CLI flags `--agentic`, `--compare`, `--drift-check` funcionam e produzem saída esperada | `presença` | Flags não reconhecidas; exit code incorreto; saída JSON/Markdown malformada |
| W005 | `legacy-impact.md#4` | DriftDetector retorna exit_code 0 (ok), 1 (drift), 2 (erro) consistentemente | `redação` | Exit code != 0/1/2; drift não detectado quando métrica cai >10% |
| W006 | `legacy-impact.md#4` | ComparativeEvaluator produz paired t-test + bootstrap IC 95% + p-value | `presença` | p-value ausente; CI 95% invertido; significância não marcada |
| W007 | `legacy-impact.md#4` | CritiqueAndRefineSynthesizer executa ≤3 chamadas LLM (1 base + máx 2 refinamentos) | `presença` | >3 chamadas LLM por query; loop infinito; max_iterations ignorado |

---

## 2. Observações (sem peso de regressão)

| ID | Descrição | Origem |
|----|-----------|--------|
| O001 | Judge provider default configurável (`openai`/`ollama`/`anthropic`) | Lacuna #1 requirements |
| O002 | Thresholds de qualidade por métrica (default 0.7) | Lacuna #2 requirements |
| O003 | Few-shot prompts do judge em `tests/fixtures/judge_prompts/` | Lacuna #3 requirements |
| O004 | Tabela `eval_log` isolada (não estende `query_log`) | Lacuna #4 requirements |
| O005 | Pricing table extensível via config.yaml | RF-06 requirements |
| O006 | Max refine iterations hardcoded = 2 (não configurável) | RN-03 requirements |

---

## 3. Histórico de Re-extrações

*Vazio - primeira extração pós-implementação*

---

## 4. Arquivadas

*Vazio*
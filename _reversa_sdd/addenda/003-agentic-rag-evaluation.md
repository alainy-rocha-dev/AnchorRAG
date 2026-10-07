# Adendo: agentic-rag-evaluation

> Identificador da feature: `003-agentic-rag-evaluation`
> Data: `2026-10-05`
> Cenário: **legado**

---

## Vigência

Vigente desde 2026-10-05.

---

## Resumo da entrega

Esta feature implementa **padrões agentic de avaliação RAG** sobre a infraestrutura de hardening (feature 002). Entrega: (1) avaliador LLM-as-judge para qualidade de resposta (relevância, fidelidade, completude, tom); (2) auto-avaliação iterativa com critique-and-refine; (3) métricas compostas RAGAS-like (faithfulness, answer_relevancy, context_precision, context_recall); (4) relatórios comparativos multi-provedor com estatísticas de significância; (5) dashboard de drift detection para monitoramento contínuo.

**Ações concluídas:** 24 de 24 (100%)

---

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta |
|----------|-------|----------------|-------|
| `_reversa_sdd/architecture.md` | Containers (Nível 2) | `componente-novo` | Novo container "Evaluation Engine" adicionado ao C4 (Evaluation Providers, Critique-Refine, Comparative, Drift, Cost) |
| `_reversa_sdd/architecture.md` | Integrações | `regra-nova` | Nova integração com `scipy` para paired t-test e bootstrap IC 95% |
| `_reversa_sdd/architecture.md` | Observabilidade | `delta-de-dados` | Nova tabela `eval_log` no SQLite + métodos de persistência e consulta |
| `_reversa_sdd/architecture.md` | CLI | `delta-de-contrato-externo` | 6 novas flags em `cli_eval.py` (`--agentic`, `--judge`, `--compare`, `--drift-check`, `--baseline`, `--output`) |
| `_reversa_sdd/domain.md` | 2.4 Provedores LLM | `regra-nova` | `EvaluatorProvider` strategy pattern (ABC + 3 provedores) seguindo mesmo padrão de `LLMProvider` |
| `_reversa_sdd/domain.md` | 2.5 Vector Store | `delta-de-dados` | Tabela `eval_log` isolada criada via DDL idempotente em `init_db()` |
| `_reversa_sdd/domain.md` | Regras de Negócio | `regra-nova` | RN-01 a RN-05: judge separado, threshold confiança, max 2 iterações refine, drift vs baseline versionado, custo USD por tokens |
| `_reversa_sdd/domain.md` | Restrições | `regra-nova` | Budget check em `CostEstimator` (max $0.50/run default), temperature=0 determinístico para judge |
| `_reversa_sdd/architecture.md` | Tech Debts | `regra-alterada` | TD-008 endereçado (+4 arquivos de teste), TD-002 parcialmente resolvido (scores expostos via eval_log/CLI) |

---

## Regras sob vigilância

| ID | Apontador |
|----|-----------|
| W001 | `_reversa_forward/003-agentic-rag-evaluation/regression-watch.md#W001` |
| W002 | `_reversa_forward/003-agentic-rag-evaluation/regression-watch.md#W002` |
| W003 | `_reversa_forward/003-agentic-rag-evaluation/regression-watch.md#W003` |
| W004 | `_reversa_forward/003-agentic-rag-evaluation/regression-watch.md#W004` |
| W005 | `_reversa_forward/003-agentic-rag-evaluation/regression-watch.md#W005` |
| W006 | `_reversa_forward/003-agentic-rag-evaluation/regression-watch.md#W006` |
| W007 | `_reversa_forward/003-agentic-rag-evaluation/regression-watch.md#W007` |

---

## Fontes

- `_reversa_forward/003-agentic-rag-evaluation/legacy-impact.md`
- `_reversa_forward/003-agentic-rag-evaluation/regression-watch.md`
- `_reversa_forward/003-agentic-rag-evaluation/requirements.md`
- `_reversa_forward/003-agentic-rag-evaluation/progress.jsonl`
- `_reversa_forward/003-agentic-rag-evaluation/actions.md`
# Requirements: agentic-rag-evaluation

> Identificador: `003-agentic-rag-evaluation`
> Data: `2026-09-29`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

Esta feature implementa **padrões agentic de avaliação RAG** sobre a infraestrutura de hardening (feature 002). Entrega: (1) avaliador LLM-as-judge para qualidade de resposta (relevância, fidelidade, completude, tom); (2) auto-avaliação iterativa com critique-and-refine; (3) métricas compostas RAGAS-like (faithfulness, answer_relevancy, context_precision, context_recall); (4) relatórios comparativos multi-provedor com estatísticas de significância; (5) dashboard de drift detection para monitoramento contínuo.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/architecture.md#3` | C4 Containers: Query Engine, LLM Providers (Strategy), Synthesizer com strict grounding | 🟢 |
| `_reversa_sdd/architecture.md#7` | TD-008: zero testes automatizados; TD-002: scores não expostos; TD-010: regex citações frágil | 🟢 |
| `_reversa_sdd/domain.md#2.3` | BR-020 a BR-025: grounding estrito, citações obrigatórias, few-shot defense, max_chunks=5 | 🟢 |
| `_reversa_sdd/domain.md#2.4` | BR-030 a BR-033: 3 provedores LLM, streaming, system prompt separado Anthropic | 🟢 |
| `_reversa_sdd/code-analysis.md#1.7` | RAGSynthesizer: filter→prompt→llm→extract citations, few-shot defense | 🟡 |
| `_reversa_sdd/inventory.md#3` | Módulos: synthesis (llm, prompt, synthesizer), pipeline (orchestrator), cli (cli_eval) | 🟢 |
| `_reversa_sdd/confidence-report.md#3.1` | CR-001 a CR-006 resolvidos na feature 002; specs SDD alinhadas | 🟢 |
| `_reversa_forward/002-rag-evaluation-hardening/requirements.md#5` | RF-03: dataset BACEN, RF-04: cli_eval com métricas, RF-06: prompt injection tests | 🟢 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Engenheiro de ML | Medir qualidade semântica além de recall lexical | Executa `hag-rag eval --agentic` e obtém faithfulness, answer_relevancy, context_precision por query |
| Product Owner | Comparar provedores LLM para decisão de custo/qualidade | Relatório multi-provedor com p-values e intervalos de confiança |
| Engenheiro de Produção | Detectar degradação do pipeline ao longo do tempo | Dashboard de drift mostra alerta quando faithfulness cai >10% vs baseline |
| Pesquisador de RAG | Validar hipótese de que agentic refinement melhora qualidade | A/B test: baseline vs critique-and-refine com paired t-test |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** Avaliação agentic deve usar LLM separado do LLM de síntese (evita viés de auto-avaliação) 🟢
   - Origem no legado: `_reversa_sdd/domain.md#BR-030` (3 provedores LLM intercambiáveis)
   - Tipo: nova

2. **RN-02:** Métricas RAGAS-like computadas por LLM-as-judge devem ter threshold de confiança (ex.: ≥3 juízes ou temperature=0 determinístico) 🟡
   - Origem no legado: `_reversa_sdd/domain.md#BR-031` (streaming + contagem tokens), `_reversa_sdd/architecture.md#7` TD-010
   - Tipo: nova

3. **RN-03:** Critique-and-refine limitado a máx. 2 iterações para evitar loop infinito e custo excessivo 🟢
   - Origem no legado: `_reversa_sdd/domain.md#BR-025` (max_chunks=5), `_reversa_sdd/architecture.md#7` TD-009
   - Tipo: nova

4. **RN-04:** Drift detection compara métricas atuais vs baseline versionado (hash do dataset + config) 🟢
   - Origem no legado: `_reversa_sdd/domain.md#BR-042` (query_log com latência por etapa), feature 002 RF-03/04
   - Tipo: nova

5. **RN-05:** Relatório agentic inclui custo estimado (tokens entrada/saída × pricing do provedor) 🟡
   - Origem no legado: `_reversa_sdd/architecture.md#6` (integrações com pricing), feature 002 RF-05
   - Tipo: nova

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | Criar `synthesis/evaluator.py` com `LLMAsJudgeEvaluator` (ABC + 3 implementações OpenAI/Ollama/Anthropic) que recebe (query, context, answer) e retorna scores 0-1 para faithfulness, answer_relevancy, context_precision, context_recall | Must | `pytest tests/unit/test_evaluator_contract.py` passa; 3 provedores registrados no factory | 🟢 |
| RF-02 | Implementar `CritiqueAndRefineSynthesizer` que: gera resposta → avalia com LLM-as-judge → se score < threshold, gera critique → refinada resposta (máx 2 iterações) | Must | Pipeline `query → refine → refine` executa ≤3 chamadas LLM; retorna melhor resposta + trail de scores | 🟢 |
| RF-03 | Estender `cli_eval.py` com flag `--agentic` que roda avaliação completa: retrieval + synthesis + LLM-as-judge + métricas compostas, exporta JSON + Markdown | Must | `hag-rag eval --dataset bacen --agentic --judge ollama` produz relatório com 4 métricas RAGAS por query + agregadas | 🟢 |
| RF-04 | Implementar `ComparativeEvaluator` que roda mesma avaliação contra múltiplos provedores LLM e produz tabela com média, desvio, p-value (paired t-test), IC 95% | Should | `hag-rag eval --dataset bacen --agentic --compare openai,ollama,anthropic` gera tabela estatística | 🟡 |
| RF-05 | Criar `DriftDetector` que: carrega baseline (JSON com hash_dataset, config_hash, métricas), roda eval atual, compara, alerta se qualquer métrica cai >10% (configurável) | Should | `hag-rag eval --drift-check --baseline eval_baseline.json` exit code 0=ok, 1=drift, 2=erro; imprime diff | 🟡 |
| RF-06 | Adicionar `cost_estimator.py` que calcula custo USD por eval run baseado em tokens (input+output) × pricing table por provedor/modelo | Could | Relatório agentic inclui coluna `estimated_cost_usd` por query e total | 🟡 |
| RF-07 | Integrar com `query_log` table: persistir `eval_run_id`, `judge_provider`, `judge_model`, scores por métrica, tokens usados, custo estimado | Must | Nova coluna em `query_log` ou tabela `eval_log`; query_log mantém backward compat | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Desempenho | Eval agentic de 20 queries em <120s (3 provedores LLM sequenciais, sem cache) | Uso interativo aceitável | 🟡 |
| Custo | Orçamento padrão: max $0.50 por eval run completo (20 queries × 3 métricas × 2 iterações) | Controla gasto em CI/CD | 🟡 |
| Confiabilidade | LLM-as-judge usa temperature=0, seed fixo, retry 3x com backoff | Reprodutibilidade científica | 🟢 |
| Segurança | Judge prompt inclui few-shot defense contra prompt injection (herda BR-022) | Consistência com síntese | 🟢 |
| Observabilidade | Log JSON estruturado por etapa: retrieve, synthesize, judge_faithfulness, judge_relevancy, judge_precision, judge_recall, refine_1, refine_2 | Debug e auditoria | 🟢 |
| Extensibilidade | ABC `BaseEvaluator` permite plugar novos juízes (ex.: fine-tuned, human-in-the-loop) | Futuro: evaluator especializado | 🟢 |

## 7. Critérios de Aceitação

```gherkin
Cenário: LLM-as-judge avalia faithfulness de resposta RAG
  Dado query "Qual a taxa Selic?", context com chunk "Selic 13.75%", answer "A taxa Selic é 13.75% [1]"
  Quando LLMAsJudgeEvaluator.eval_faithfulness(query, context, answer) é chamado
  Então retorna score ≥ 0.9 com confidence_high=True

Cenário: Critique-and-refine melhora resposta com hallucination
  Dado query "Qual a taxa Selic?", context sem menção a Selic, answer inicial "A taxa Selic é 10% [1]"
  Quando CritiqueAndRefineSynthesizer roda com threshold=0.7
  Então critique detecta "informação não suportada", resposta refinada retorna "Não encontrei essa informação nos documentos fornecidos." com score_faithfulness ≥ 0.8

Cenário: Eval agentic publica métricas RAGAS-like agregadas
  Dado dataset bacen.yaml com 20 queries
  Quando hag-rag eval --dataset bacen --agentic --judge ollama roda
  Então saída Markdown contém tabela: query_id, faithfulness, answer_relevancy, context_precision, context_recall + médias finais

Cenário: Comparative evaluator roda paired t-test entre provedores
  Dado --compare openai,ollama
  Quando eval roda nas mesmas 20 queries
  Então relatório inclui: mean_diff, p_value, ci_95_lower, ci_95_upper por métrica; p<0.05 destacado

Cenário: Drift detector alerta degradação >10%
  Dado baseline com faithfulness=0.85
  Quando eval atual produz faithfulness=0.74
  Então exit code 1, output "DRIFT DETECTED: faithfulness -12.9% (0.85 → 0.74)"
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| RF-01 (LLMAsJudgeEvaluator ABC + 3 providers) | Must | Core da feature agentic |
| RF-02 (CritiqueAndRefineSynthesizer) | Must | Diferencial agentic: auto-melhoria |
| RF-03 (cli_eval --agentic) | Must | Interface de uso principal |
| RF-07 (persistência eval_log) | Must | Observabilidade e histórico |
| RF-04 (ComparativeEvaluator + stats) | Should | Decisão de provedor baseada em evidência |
| RF-05 (DriftDetector) | Should | Monitoramento contínuo produção |
| RF-06 (Cost Estimator) | Could | Nice-to-have para governança de custo |

## 9. Esclarecimentos

> Nenhuma sessão de dúvidas registrada ainda. Rode `/reversa-clarify` quando houver `[DÚVIDA]` pendente.

## 10. Lacunas

- 🟡 **Judge provider padrão**: qual provedor LLM usar como juiz default? (OpenAI gpt-4o-mini? Ollama local? Configurável?)
- 🟡 **Thresholds de qualidade**: valores default para faithfulness/relevancy/precision/recall que disparam refine (sugestão: 0.7)
- 🟡 **Dataset de calibração do judge**: precisa de few-shot examples calibrados para o domínio (BACEN/normas)?
- 🔴 **Persistência eval_log**: criar nova tabela `eval_log` ou estender `query_log`? (impacta schema DB)

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-29 | Versão inicial gerada por `/reversa-requirements` | reversa |
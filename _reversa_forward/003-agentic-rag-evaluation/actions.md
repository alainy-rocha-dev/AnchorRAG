<!--
Template de corpo do actions.md
Carregado por /reversa-to-do e atualizado por /reversa-coding.

REGRAS DE PREENCHIMENTO:
- IDs estáveis: T001, T002, ..., zero-padded três dígitos. Nunca recicle.
- Marcador de paralelismo é [//] no início da linha de ID. Tarefas [//] não compartilham arquivo alvo.
- Coluna "Dependências" lista IDs separados por vírgula. Ações sem dependência usam "-".
- Status inicial é [ ]. /reversa-coding muda para [X] ao concluir.
- /reversa-add acrescenta uma seção "## Emendas" ao final, com o mesmo formato de tabela, IDs E001, E002, ... e status já [X].
- Toda ação precisa ser ATÔMICA: cabe num turno do agente, sem precisar de feedback humano no meio.
-->

# Actions: agentic-rag-evaluation

> Identificador: `003-agentic-rag-evaluation`
> Data: `2026-10-05`
> Roadmap: `_reversa_forward/003-agentic-rag-evaluation/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 24 |
| Paralelizáveis (`[//]`) | 8 |
| Maior cadeia de dependência | 6 |

## Fase 1, Preparação

<!-- Setup, scaffolding, migrações iniciais, configuração de infraestrutura local. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Adicionar `EvaluationConfig` em `AppConfig` (config.py) com validadores e defaults | - | `[//]` | src/anchor_rag/config.py | 🟢 | `[X]` |
| T002 | Criar pasta `src/anchor_rag/evaluation/` + `__init__.py` com factory `create_evaluator_provider()` | T001 | `[//]` | src/anchor_rag/evaluation/__init__.py | 🟢 | `[X]` |
| T003 | Adicionar DDL da tabela `eval_log` em `SQLiteVecStore.init_db()` | T001 | - | src/anchor_rag/vector_store/sqlite_vec.py | 🟢 | `[X]` |
| T004 | Adicionar modelos Pydantic: `EvalMetrics` (estendido), `ComparativeMetrics`, `DriftResult`, `CostEstimate` | T001 | - | src/anchor_rag/domain/models.py | 🟢 | `[X]` |

## Fase 2, Testes

<!-- Testes que precisam existir antes ou logo após o núcleo. Omitir se a equipe não pratica TDD. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T005 | Criar `tests/unit/test_evaluator_contract.py` com contract tests do `EvaluatorProvider` ABC | T002 | `[//]` | tests/unit/test_evaluator_contract.py | 🟢 | `[X]` |
| T006 | Criar fixtures de judge prompts (3 exemplos por métrica) em `tests/fixtures/judge_prompts/` | T002 | `[//]` | tests/fixtures/judge_prompts/ | 🟡 | `[X]` |
| T007 | Adicionar `scipy` em `pyproject.toml` [dev] para paired t-test e bootstrap | T001 | `[//]` | pyproject.toml | 🟢 | `[X]` |

## Fase 3, Núcleo

<!-- Lógica central da feature. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T008 | Implementar `EvaluatorProvider` ABC + `OpenAIEvaluatorProvider` | T002, T005 | - | src/anchor_rag/evaluation/evaluator.py | 🟢 | `[X]` |
| T009 | Implementar `OllamaEvaluatorProvider` | T008 | `[//]` | src/anchor_rag/evaluation/evaluator.py | 🟢 | `[X]` |
| T010 | Implementar `AnthropicEvaluatorProvider` | T008 | `[//]` | src/anchor_rag/evaluation/evaluator.py | 🟢 | `[X]` |
| T011 | Implementar `CritiqueAndRefineSynthesizer` (wrapper sobre `RAGSynthesizer`) | T008, T004 | - | src/anchor_rag/evaluation/critique_refine.py | 🟢 | `[X]` |
| T012 | Implementar `ComparativeEvaluator` com paired t-test + bootstrap IC 95% | T008, T004, T007 | - | src/anchor_rag/evaluation/comparative.py | 🟡 | `[X]` |
| T013 | Implementar `DriftDetector` (baseline JSON → diff → exit code 0/1/2) | T004 | - | src/anchor_rag/evaluation/drift.py | 🟢 | `[X]` |
| T014 | Implementar `CostEstimator` (pricing table × tokens → USD) | T004, T001 | - | src/anchor_rag/evaluation/cost.py | 🟡 | `[X]` |

## Fase 4, Integração

<!-- Cola com outras partes do sistema, contratos externos, hooks. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T015 | Estender `cli_eval.py` com flags `--agentic`, `--judge`, `--compare`, `--drift-check`, `--baseline`, `--output` | T008, T011, T012, T013 | - | src/anchor_rag/cli_eval.py | 🟢 | `[X]` |
| T016 | Adicionar `eval_dataset_agentic()` e `drift_check()` em `PipelineOrchestrator` | T011, T013 | - | src/anchor_rag/pipeline/orchestrator.py | 🟢 | `[X]` |
| T017 | Implementar persistência `eval_log` em `SQLiteVecStore` (insert batch por run) | T003, T008 | - | src/anchor_rag/vector_store/sqlite_vec.py | 🟢 | `[X]` |
| T018 | Integrar `CostEstimator` no fluxo de eval (calcula tokens + custo por query) | T014, T015 | - | src/anchor_rag/evaluation/cost.py | 🟡 | `[X]` |
| T019 | Adicionar logs JSON estruturados por etapa (retrieve, synthesize, judge_*, refine_*) | T015, T016 | - | src/anchor_rag/logging.py | 🟢 | `[X]` |

## Fase 5, Polimento

<!-- Logs, telemetria, mensagens de erro, documentação curta. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T020 | Testes integração: `test_critique_refine.py` (≤3 chamadas LLM, trail scores) | T011, T016 | `[//]` | tests/integration/test_critique_refine.py | 🟢 | `[X]` |
| T021 | Testes integração: `test_comparative_eval.py` (tabela estatística p-value, IC95%) | T012, T016 | `[//]` | tests/integration/test_comparative_eval.py | 🟡 | `[X]` |
| T022 | Testes integração: `test_drift_detection.py` (exit codes 0/1/2 corretos) | T013, T016 | `[//]` | tests/integration/test_drift_detection.py | 🟢 | `[X]` |
| T023 | Atualizar specs SDD: criar `_reversa_sdd/sdd/rag-agentic-evaluation.md` ou estender existente | T008, T011, T012, T013, T014 | - | _reversa_sdd/sdd/rag-agentic-evaluation.md | 🟢 | `[X]` |
| T024 | Gerar `legacy-impact.md` e `regression-watch.md` da feature 003 | T023 | - | _reversa_forward/003-agentic-rag-evaluation/legacy-impact.md, regression-watch.md | 🟢 | `[X]` |

## Notas de execução

<!--
Reservado para /reversa-coding registrar avisos ou observações que surgiram durante a execução.
Não use isso para corrigir ações, edits manuais ficam fora desse arquivo, vão direto no código.
-->

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-10-05 | Versão inicial gerada por `/reversa-to-do` | reversa |
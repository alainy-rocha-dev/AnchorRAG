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

# Actions: bcb-corpus-dataset-v1

> Identificador: `004-bcb-corpus-dataset-v1`
> Data: `2026-10-10`
> Roadmap: `_reversa_forward/004-bcb-corpus-dataset-v1/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 28 |
| Paralelizáveis (`[//]`) | 9 |
| Maior cadeia de dependência | 7 |

## Fase 1, Preparação

<!-- Setup, scaffolding, migrações iniciais, configuração de infraestrutura local. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T001 | Criar estrutura de diretórios `corpus/raw/`, `eval/datasets/`, `eval/build_dataset.py` | - | `[//]` | `corpus/raw/`, `eval/datasets/`, `eval/build_dataset.py` | 🟢 | `[X]` |
| T002 | Implementar subcomando `ingest` em `build_dataset.py` (parser HTML, regex artigos, split longo, SOURCES.md) | T001 | - | `eval/build_dataset.py` | 🟢 | `[X]` |
| T003 | Corrigir regex de revogação para pegar "revogadas/revogado/revogada" sem parênteses | T002 | - | `eval/build_dataset.py` | 🟢 | `[X]` |
| T004 | Baixar 30-50 normas BCB/CMN (HTML preferível) em `corpus/raw/` cobrindo PIX, Open Finance, Câmbio, Crédito, Segurança, LGPD, Capital, Liquidez | T001 | - | `corpus/raw/` | 🟢 | `[ ]` |
| T005 | **Escalar corpus**: rodar `ingest` completo (todas as normas → chunks.jsonl completo) e validar ≥ 250 chunks utilizáveis (200-1800 chars); o limite de 15 chunks/norma aplica-se ao `candidates` (--max-por-norma), não ao corpus; se corpus tiver >15 chunks/norma, o `candidates` amostra representativamente | T002, T003, T004 | - | `corpus/chunks.jsonl`, `corpus/SOURCES.md` | 🟢 | `[ ]` |
| T006 | Commitar `corpus/raw/`, `corpus/chunks.jsonl`, `corpus/SOURCES.md` no repo | T005 | - | `corpus/` | 🟢 | `[ ]` |
| T007 | Implementar subcomando `candidates` em `build_dataset.py` (4 categorias, LLM Anthropic, overlap lexical, canário) | T001 | `[//]` | `eval/build_dataset.py` | 🟢 | `[X]` |
| T008 | Implementar subcomando `review` em `build_dataset.py` (loop interativo a/e/r/p/q, progresso por categoria) | T001 | `[//]` | `eval/build_dataset.py` | 🟢 | `[X]` |
| T009 | Implementar subcomando `validate` em `build_dataset.py` (schema, contagens ALVO, chunk_ids, duplicatas, avisos) | T001 | `[//]` | `eval/build_dataset.py` | 🟢 | `[X]` |

## Fase 2, Testes

<!-- Testes que precisam existem antes ou logo após o núcleo. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T010 | Criar `tests/unit/test_build_dataset_ingest.py` (regex artigos, split longo, revogados ignorados, SOURCES.md) | T002, T003 | `[//]` | `tests/unit/test_build_dataset_ingest.py` | 🟢 | `[X]` |
| T011 | Criar `tests/unit/test_build_dataset_validate.py` (schema, contagens, chunk_ids válidos, duplicatas, hash) | T009 | `[//]` | `tests/unit/test_build_dataset_validate.py` | 🟢 | `[X]` |
| T012 | Adicionar `anthropic` e `pypdf` em `pyproject.toml` [dev] para geração de candidatas | T001 | `[//]` | `pyproject.toml` | 🟢 | `[ ]` |

## Fase 3, Núcleo

<!-- Lógica central da feature. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T013 | Gerar candidatas `respondivel` (meta 80 → alvo 60 revisados) via `candidates --categoria respondivel --n 80` | T007, T005 | - | `eval/datasets/candidates.jsonl` | 🟢 | `[ ]` |
| T014 | Gerar candidatas `multi_trecho` (meta 30 → alvo 20 revisados) via `candidates --categoria multi_trecho --n 30` | T007, T005 | `[//]` | `eval/datasets/candidates.jsonl` | 🟢 | `[ ]` |
| T015 | Gerar candidatas `sem_resposta` (meta 30 → alvo 20 revisados) via `candidates --categoria sem_resposta --n 30` | T007, T005 | `[//]` | `eval/datasets/candidates.jsonl` | 🟢 | `[ ]` |
| T016 | Gerar candidatas `adversarial` (meta 30 → alvo 20 revisados) via `candidates --categoria adversarial --n 30` | T007, T005 | `[//]` | `eval/datasets/candidates.jsonl` | 🟢 | `[ ]` |
| T017 | Revisão humana `respondivel`: aceitar/editar/rejeitar até 60 `revisado=true` no v1.jsonl | T008, T013 | - | `eval/datasets/v1.jsonl`, `eval/datasets/rejected.jsonl` | 🟢 | `[ ]` |
| T018 | Revisão humana `multi_trecho`: aceitar/editar/rejeitar até 20 `revisado=true` | T008, T014 | `[//]` | `eval/datasets/v1.jsonl`, `eval/datasets/rejected.jsonl` | 🟢 | `[ ]` |
| T019 | Revisão humana `sem_resposta`: aceitar/editar/rejeitar até 20 `revisado=true` (checar overlap_max) | T008, T015 | `[//]` | `eval/datasets/v1.jsonl`, `eval/datasets/rejected.jsonl` | 🟢 | `[ ]` |
| T020 | Revisão humana `adversarial`: aceitar/editar/rejeitar até 20 `revisado=true` (verificar canário) | T008, T016 | `[//]` | `eval/datasets/v1.jsonl`, `eval/datasets/rejected.jsonl` | 🟢 | `[ ]` |

## Fase 4, Integração

<!-- Cola com outras partes do sistema, contratos externos, ganchos. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T021 | Rodar `validate` no v1.jsonl completo (120 itens); confirmar exit 0; gerar `eval/datasets/README.md` com versão, data, contagens | T009, T017, T018, T019, T020 | - | `eval/datasets/v1.jsonl`, `eval/datasets/README.md` | 🟢 | `[ ]` |
| T022 | Atualizar CI: adicionar step `build_dataset.py validate` em `.github/workflows/ci.yml` (sem hash check ainda) | T006, T021 | - | `.github/workflows/ci.yml` | 🟢 | `[ ]` |
| T023 | Testar integração feature 003: `hag-rag eval --dataset eval/datasets/v1.jsonl --agentic --judge ollama` | T006, T021 | - | (integração) | 🟢 | `[ ]` |
| T024 | Testar integração feature 003: `hag-rag eval --dataset eval/datasets/v1.jsonl --compare openai,ollama` | T006, T021 | `[//]` | (integração) | 🟢 | `[ ]` |
| T025 | Testar integração feature 003: `hag-rag eval --dataset eval/datasets/v1.jsonl --drift-check --baseline eval/datasets/v1.jsonl` | T006, T021 | `[//]` | (integração) | 🟢 | `[ ]` |

## Fase 5, Polimento

<!-- Logs, telemetria, mensagens de erro, documentação curta. -->

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T026 | **Congelar v1**: gerar `eval/datasets/v1.sha256` (SHA-256 do v1.jsonl); ativar hash check no CI (falha se divergir); esta tarefa depende de TODAS as anteriores | T006, T021, T022, T023, T024, T025 | - | `eval/datasets/v1.sha256`, `.github/workflows/ci.yml` | 🟢 | `[ ]` |
| T027 | Commitar `eval/datasets/v1.jsonl`, `v1.sha256`, `README.md` no repo | T026 | - | `eval/datasets/` | 🟢 | `[ ]` |
| T028 | Documentar em `eval/datasets/README.md` instruções para regenerar v2 (quando corpus mudar, nova categoria, correção gold standard) | T021 | `[//]` | `eval/datasets/README.md` | 🟢 | `[ ]` |

## Notas de execução

<!--
Reservado para /reversa-coding registrar avisos ou observações que surgiram durante a execução.
Não use isso para corrigir ações, edits manuais ficam fora desse arquivo, vão direto no código.
-->

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-10-10 | Versão inicial gerada por `/reversa-to-do` | reversa |
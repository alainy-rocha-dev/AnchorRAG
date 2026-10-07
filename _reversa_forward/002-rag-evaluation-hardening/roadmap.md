# Roadmap: rag-evaluation-hardening

> Identificador: `002-rag-evaluation-hardening`
> Data: `2026-09-29`
> Requirements: `_reversa_forward/002-rag-evaluation-hardening/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

Esta feature endereça 6 lacunas críticas do `confidence-report.md` (CR-001 a CR-006) e 5 inconsistências internas (IN-001 a IN-005) através de 7 frentes de trabalho paralelas mas independentes: (1) validador cross-config no `AppConfig` para dimensions; (2) dedup real consultando hash antes de parse no `IngestionPipeline`; (3) dataset de eval BACEN versionado + extensão do `cli_eval.py` com métricas reais; (4) benchmark script para 3 provedores de embedding; (5) testes automatizados de prompt injection com dataset adversarial; (6) atualização das 3 SDD specs para status 🟢 IMPLEMENTADO alinhadas ao código; (7) fix de typo no README. Todas as mudanças são aditivas ou corretivas, sem breaking changes na API pública.

## 2. Princípios aplicados

| Princípio | Como a feature se relaciona | Status |
|-----------|------------------------------|--------|
| Fail-fast configuration | RF-01 valida consistency no startup, impedindo runtime error silencioso | respeita |
| Observabilidade por padrão | RF-04, RF-05 publicam métricas e benchmarks reais | respeita |
| Defesa em profundidade | RF-06 testa a defesa few-shot existente com dataset adversarial | respeita |
| Specs como contrato vivo | RF-07, RF-08, RF-09 alinham specs ao código real (status 🟢) | respeita |
| Zero breaking changes | Todas as mudanças mantêm contratos públicos (CLI, config, modelos) | respeita |

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|--------------------------|-------------|
| D-01 | Validador cross-config em `AppConfig.model_validator(mode="after")` | Falha rápida no ponto de entrada, mensagem clara, alinhado com Pydantic v2 patterns | Validar no `RAGPipeline.initialize()` (mais tarde, menos claro), Documentar como pré-requisito (não bloqueia) | 🟢 |
| D-02 | Dedup consulta `SELECT 1 FROM documents WHERE content_hash = ?` ANTES do parser | Evita custo de parse de PDFs grandes, usa índice UNIQUE existente em `content_hash` | Hash em memória (não persiste entre runs), Parse primeiro + INSERT OR IGNORE (atual, gasta CPU) | 🟢 |
| D-03 | Dataset eval em YAML versionado em `tests/fixtures/eval_dataset_bacen.yaml` | Legível, diffável, compatível com pytest fixtures, suporta metadados ricos | JSON (menos legível), SQLite (overhead), CSV (pobre em metadados) | 🟢 |
| D-04 | Métricas: recall@k, MRR, taxa_alucinacao, cobertura_citacoes | Alinhadas com `confidence-report.md#1` e literatura RAG padrão | NDCG (mais complexo), Precision@k apenas (incompleto) | 🟢 |
| D-05 | Benchmark script mede latência (ms/1k chunks) e custo (USD/1M tokens) no hardware local | Números próprios > docs de vendor, reprodutível, CI-friendly | Apenas citar docs vendor (sem credibilidade), Benchmark remoto (não representa hardware alvo) | 🟢 |
| D-06 | Dataset adversarial para prompt injection: 10+ ataques categorizados (ignore instructions, role play, hypothetical, encoding, etc.) | Cobertura ampla de vetores conhecidos, mensurável (bypass_rate por categoria) | Apenas os 3 few-shot existentes (cobertura insuficiente), Fuzzing aleatório (não determinístico) | 🟢 |
| D-07 | SDD specs: status → 🟢 IMPLEMENTADO, params → alinhados ao código, mover detalhes impl (sqlite-vec) para ADR-001 | Specs como contrato de interface, detalhes de impl em ADRs | Manter specs abstratas (confunde implementadores), Duplicar detalhes em ambos (drift garantido) | 🟢 |

## 4. Premissas

| Premissa | Origem (`requirements.md` seção) | Risco se errada |
|----------|----------------------------------|-----------------|
| Dataset BACEN: 20+ perguntas representativas de compliance bancário podem ser curadas sem acesso a base privada | Lacunas (seção 10) | Eval não reflete domínio real, métricas menos convincentes para recrutador |
| Ollama rodando local com modelos de embedding disponíveis para benchmark | Lacunas (seção 10) | Benchmark incompleto (apenas OpenAI + HF), comparação enviesada |
| Hardware de referência documentado (CPU/RAM/GPU) para reprodutibilidade do benchmark | Lacunas (seção 10) | Números não comparáveis entre máquinas, credibilidade reduzida |

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| `AppConfig` | `_reversa_sdd/architecture.md#5` | regra-alterada | Adiciona `@model_validator` cross-section para `embedding.dimensions == vector_store.embedding_dimensions` |
| `IngestionPipeline` | `_reversa_sdd/architecture.md#5` (`ingestion/pipeline.py`) | regra-alterada | `ingest()` consulta hash em `documents` antes de chamar `parser.parse()` |
| `CLI (cli_eval.py)` | `_reversa_sdd/architecture.md#5` (`cli/cli_eval.py`) | contrato-novo | Novo comando `eval` com subcomando `--dataset`, saída Markdown com métricas |
| `EmbeddingProvider` (benchmark) | `_reversa_sdd/architecture.md#5` (`embeddings/__init__.py`) | componente-novo | Script standalone `scripts/benchmark_embeddings.py` usa registry existente |
| `PromptInjectionTests` | `_reversa_sdd/architecture.md#5` (`tests/integration/`) | componente-novo | Novo arquivo `test_prompt_injection.py` estende suite existente |
| `SDD Specs` (3 arquivos) | `_reversa_sdd/sdd/*.md` | regra-alterada | Status 🟢 IMPLEMENTADO, params alinhados, detalhes impl movidos para ADRs |

## 6. Delta no modelo de dados

- Resumo das mudanças: Nenhuma mudança no schema do banco (tabelas `documents`, `chunks`, `chunks_vec`, `query_log` inalteradas). Apenas lógica de aplicação alterada (validação no startup, consulta hash antes de parse).
- Detalhe completo em: `_reversa_forward/002-rag-evaluation-hardening/data-delta.md`

## 7. Delta de contratos externos

| Contrato | Tipo | Arquivo de detalhe |
|----------|------|--------------------|
| `hag-rag eval` CLI | CLI/arquivo | `_reversa_forward/002-rag-evaluation-hardening/interfaces/cli_eval.md` |

## 8. Plano de migração

1. Implementar validador cross-config em `AppConfig` (RF-01) — independente, sem migração
2. Implementar dedup real em `IngestionPipeline.ingest()` (RF-02) — independente, sem migração
3. Criar dataset BACEN YAML (RF-03) — independente
4. Estender `cli_eval.py` com comando `eval` (RF-04) — depende de RF-03
5. Criar script benchmark embeddings (RF-05) — independente
6. Adicionar testes prompt injection (RF-06) — independente
7. Atualizar 3 SDD specs (RF-07, RF-08, RF-09) — independente
8. Fix README typo (RF-10) — independente

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Dataset BACEN insuficiente ou viesado | Médio | Médio | Curar a partir de fontes públicas (BACEN.gov.br), validar com especialista domínio se possível |
| Ollama não disponível no ambiente de benchmark | Baixo | Médio | Script pula provedor indisponível com warning, documenta limitação |
| Validador cross-config quebra configs existentes legítimas | Alto | Baixo | Mensagem de erro clara aponta exatamente o que corrigir; teste unitário cobre caso válido e inválido |
| Dedup real tem race condition em concorrência | Médio | Baixo | `INSERT OR IGNORE` + `UNIQUE(content_hash)` garante atomicidade no SQLite |
| SDD specs atualizadas introduzem regressão na documentação | Baixo | Baixo | Diff automático vs versão anterior, revisão humana antes de commit |

## 10. Critério de pronto

- [ ] Todas as ações do `actions.md` marcadas `[X]`
- [ ] `cross-check.md` (se executado) sem CRITICAL nem HIGH
- [ ] `regression-watch.md` gerado
- [ ] Re-extração reversa executada e sem regressão vermelha (recomendado, não obrigatório)
- [ ] `hag-rag eval --dataset bacen` roda e publica métricas
- [ ] `pytest tests/integration/test_prompt_injection.py` passa com bypass_rate=0%
- [ ] `scripts/benchmark_embeddings.py` gera `docs/embedding-benchmark.md`
- [ ] 3 SDD specs mostram status 🟢 IMPLEMENTADO e zero divergências vs código

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-29 | Versão inicial gerada por `/reversa-plan` | reversa |
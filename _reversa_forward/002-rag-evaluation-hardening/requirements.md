# Requirements: rag-evaluation-hardening

> Identificador: `002-rag-evaluation-hardening`
> Data: `2026-09-29`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

Esta feature endereça os gaps críticos identificados na revisão do HAG RAG (confidence-report.md) para torná-lo pronto para avaliação técnica rigorosa e uso em produção. Entrega: (1) dataset de avaliação versionado com corpus real (normas BACEN) e gabarito; (2) benchmarks próprios de latência/custo dos 3 provedores de embedding; (3) testes automatizados de prompt injection; (4) validador cross-config de dimensions no AppConfig; (5) dedup real consultando hash antes de parse; (6) correção das 3 SDD specs divergentes; (7) fix de typo no README.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/confidence-report.md#3.1` | 6 lacunas críticas bloqueando reimplementação fiel (CR-001 a CR-006) | 🟢 |
| `_reversa_sdd/confidence-report.md#3.2` | 5 inconsistências internas entre specs e código (IN-001 a IN-005) | 🟢 |
| `_reversa_sdd/architecture.md#7` | 10 dívidas técnicas, incluindo TD-001 (dimensions cross-validation), TD-002 (scores não expostos), TD-003 (dedup não implementado), TD-008 (zero testes automatizados) | 🟢 |
| `_reversa_sdd/domain.md#5` | 6 lacunas de domínio: consistency embedding↔store, scores não expostos, dedup não implementado, página estimada, sem RBAC, sem versionamento | 🟢 |
| `_reversa_sdd/questions.md` | 6 perguntas de validação respondidas (todas opção A: alinhar specs ao código real) | 🟢 |
| `_reversa_sdd/code-analysis.md#1.9` | Pontos de atenção: resolve_api_keys não valida env var, base_url não validado, vector_store.type fixo, falta validação dimensions cross-config | 🟡 |
| `_reversa_sdd/sdd/rag-synthesis-citation-engine.md` | Spec com divergências: citation format, threshold 0.40 vs 0.7 código | 🟡 |
| `_reversa_sdd/sdd/vector-store-similarity-search.md` | Spec questiona in-memory vs SQLite; código usa sqlite-vec | 🟡 |
| `_reversa_sdd/sdd/document-ingestion-chunking.md` | Spec divergente: chunk_size 1000 chars vs 512 tokens código | 🟡 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Recrutador técnico | Avaliar credibilidade do projeto | Roda `hag-rag eval` e vê métricas publicadas (recall@k, MRR, taxa alucinação, cobertura citações) com números reais |
| Engenheiro de ML | Validar qualidade do RAG | Executa suite de eval com dataset BACEN e obtém relatório comparativo entre provedores |
| Desenvolvedor do projeto | Garantir configuração correta | Startup falha rápido se `embedding.dimensions ≠ vector_store.embedding_dimensions` |
| Usuário de produção | Evitar re-ingestão duplicada | Mesmo PDF ingerido duas vezes é detectado pelo hash antes do parse custoso |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** Configuração deve validar consistência `embedding.dimensions == vector_store.embedding_dimensions` no startup 🟢
   - Origem no legado: `_reversa_sdd/domain.md#BR-011`, `_reversa_sdd/domain.md#5.1`
   - Tipo: nova

2. **RN-02:** Deduplicação deve consultar `content_hash` na tabela `documents` ANTES de fazer parse do PDF 🟢
   - Origem no legado: `_reversa_sdd/domain.md#BR-001`, `_reversa_sdd/domain.md#5.6`
   - Tipo: alterada (código atual tem comentário "em produção usar índice de hash")

3. **RN-03:** Dataset de avaliação deve ser versionado (arquivo JSON/YAML com perguntas, chunks esperados, respostas referência) 🟢
   - Origem no legado: `_reversa_sdd/confidence-report.md#1` (métricas definidas sem resultados)
   - Tipo: nova

4. **RN-04:** Benchmarks de embedding devem ser executados no hardware alvo e publicados como tabela comparativa 🟢
   - Origem no legado: `_reversa_sdd/confidence-report.md#6` (tabela sem fonte nem benchmark próprio)
   - Tipo: nova

5. **RN-05:** Testes de prompt injection devem usar dataset adversarial e medir taxa de bypass (meta: 0%) 🟢
   - Origem no legado: `_reversa_sdd/domain.md#BR-022`, `_reversa_sdd/confidence-report.md#5`
   - Tipo: nova (código tem few-shot mas sem testes automatizados)

6. **RN-06:** As 3 SDD specs devem refletir a implementação real (status 🟢 IMPLEMENTADO, params alinhados ao código) 🟢
   - Origem no legado: `_reversa_sdd/confidence-report.md#3.1` (CR-001 a CR-004)
   - Tipo: alterada

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | Adicionar `@model_validator(mode="after")` em `AppConfig` que falha se `embedding.dimensions != vector_store.embedding_dimensions` | Must | Startup com config inconsistente levanta `ConfigurationException` com mensagem clara | 🟢 |
| RF-02 | Modificar `IngestionPipeline.ingest()` para consultar `SELECT 1 FROM documents WHERE content_hash = ?` antes de chamar parser | Must | Ingestão de PDF já existente retorna `IngestResult(skipped=True, reason="duplicate_hash")` sem chamar parser | 🟢 |
| RF-03 | Criar `tests/fixtures/eval_dataset_bacen.yaml` com ≥20 perguntas, chunks esperados (ids), respostas referência, metadados de fonte | Must | Arquivo existe, validado por schema, usado por `cli_eval.py` | 🟢 |
| RF-04 | Estender `cli_eval.py` com comando `eval` que: roda retrieval+synthesis contra dataset, computa recall@k, MRR, taxa alucinação, cobertura citações, publica tabela Markdown | Must | `hag-rag eval --dataset bacen` produz relatório com métricas numéricas | 🟢 |
| RF-05 | Criar script `scripts/benchmark_embeddings.py` que mede latência (ms/1k chunks) e custo (USD/1M tokens) dos 3 provedores no hardware local | Should | Script roda sem erros, gera `docs/embedding-benchmark.md` com tabela comparativa | 🟢 |
| RF-06 | Adicionar testes em `tests/integration/test_prompt_injection.py` usando dataset adversarial (mín. 10 ataques conhecidos), assertiva taxa bypass = 0% | Must | `pytest tests/integration/test_prompt_injection.py -v` passa com 0% bypass | 🟢 |
| RF-07 | Atualizar `sdd/document-ingestion-chunking.md`: status 🟢 IMPLEMENTADO, chunk_size=512 tokens, chunk_overlap=50 tokens, chunk_unit=tokens, parser factory pdfplumber/PyPDF | Must | Spec alinhada ao código, sem divergências em RF-02, RF-03, RF-04 | 🟢 |
| RF-08 | Atualizar `sdd/rag-synthesis-citation-engine.md`: status 🟢 IMPLEMENTADO, citation format `[N]` numérico, threshold default 0.7, latência sem SLA hardcoded | Must | Spec alinhada ao código, sem divergências em RF-02, RF-03, RF-04 | 🟢 |
| RF-09 | Atualizar `sdd/vector-store-similarity-search.md`: status 🟢 IMPLEMENTADO, store=sqlite-vec virtual table, retry apenas OpenAI, top_k default=5, score=1-distance | Must | Spec alinhada ao código, sem divergências em RF-01, RF-03, RF-04 | 🟢 |
| RF-10 | Corrigir typo no README.md se `provider: "open` → `provider: "openai"` | Should | README válido, sem aspas abertas | 🟡 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Desempenho | `cli_eval.py` completa eval de 20 queries em <60s (embeddings cached) | Recrutador não espera minutos | 🟡 |
| Segurança | Validador cross-config impede runtime error silencioso de dimensions mismatch | `_reversa_sdd/domain.md#5.1` CR-005 | 🟢 |
| Segurança | Dedup real evita custo computacional de re-parse de PDFs grandes | `_reversa_sdd/domain.md#5.6` CR-006 | 🟢 |
| Observabilidade | Benchmark embeddings publicado com fonte (próprio) e metodologia | `_reversa_sdd/confidence-report.md#6` | 🟢 |
| Observabilidade | Testes de prompt injection reportam taxa bypass por tipo de ataque | `_reversa_sdd/domain.md#BR-022` | 🟢 |
| Manutenibilidade | SDD specs status 🟢 IMPLEMENTADO eliminam confusão spec vs código | `_reversa_sdd/confidence-report.md#3.1` | 🟢 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Validação cross-config falha rápido no startup
  Dado um config.yaml com embedding.dimensions=1536 e vector_store.embedding_dimensions=768
  Quando o AppConfig é instanciado via from_yaml()
  Então ConfigurationException é levantada com mensagem "embedding.dimensions (1536) != vector_store.embedding_dimensions (768)"

Cenário: Dedup real pula parse de PDF duplicado
  Dado um PDF já ingerido (content_hash conhecido na tabela documents)
  Quando hag-rag ingest é executado novamente no mesmo arquivo
  Então o parser NÃO é chamado, retorna skipped=True, reason="duplicate_hash", latency_parse_ms=0

Cenário: Eval com dataset BACEN publica métricas
  Dado dataset bacen.yaml com 20 queries e gabarito
  Quando hag-rag eval --dataset bacen é executado
  Então saída contém tabela Markdown com recall@5, MRR, taxa_alucinacao, cobertura_citacoes com valores numéricos

Cenário: Benchmark embeddings gera tabela comparativa
  Dado script benchmark_embeddings.py executado
  Quando termina sem erro
  Então docs/embedding-benchmark.md existe com colunas: provider, model, latency_ms_per_1k, cost_usd_per_1M, hardware

Cenário: Testes prompt injection reportam 0% bypass
  Dado dataset adversarial com 10 ataques
  Quando pytest test_prompt_injection.py roda
  Então todos passam, relatório mostra bypass_rate=0% por categoria

Cenário: SDD specs atualizadas sem divergências
  Dado as 3 specs SDD lidas
  Quando comparadas com código real
  Então zero divergências em chunk_size, citation_format, threshold, vector_store_type, top_k_default
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| RF-01 (cross-config validator) | Must | Bloqueia produção (runtime error silencioso) |
| RF-02 (dedup real) | Must | Bloqueia produção (custo desnecessário, dados sujos) |
| RF-03 (dataset BACEN) | Must | Requisito para RF-04, credibilidade com recrutador |
| RF-04 (cli_eval métricas) | Must | Entrega principal: métricas publicadas |
| RF-06 (prompt injection tests) | Must | Defesa few-shot sem testes = afirmação vazia |
| RF-07, RF-08, RF-09 (SDD specs) | Must | Specs divergentes tiram credibilidade |
| RF-05 (benchmark embeddings) | Should | Importante para tabela custo/latência, mas não bloqueia eval |
| RF-10 (README typo) | Should | Detalhe de credibilidade |

## 9. Esclarecimentos

> Nenhuma sessão de dúvidas registrada ainda. Rode `/reversa-clarify` quando houver `[DÚVIDA]` pendente.

## 10. Lacunas

- 🟡 Dataset BACEN: precisa curar 20+ perguntas representativas de compliance bancário (fontes: Resoluções CMN, Circulares BACEN, Comunicados)
- 🟡 Benchmark embeddings: requer chaves API OpenAI e Ollama rodando local para medição realista
- 🟡 Hardware de referência para benchmark não definido (documentar CPU/RAM/GPU usado)

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-29 | Versão inicial gerada por `/reversa-requirements` | reversa |
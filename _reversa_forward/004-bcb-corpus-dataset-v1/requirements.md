# Requirements: bcb-corpus-dataset-v1

> Identificador: `004-bcb-corpus-dataset-v1`
> Data: `2026-10-10`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

Esta feature entrega o **corpus versionado de normas do BCB/CMN** e o **dataset de avaliação v1.jsonl congelado** com 120 perguntas revisadas por humano, para que a infraestrutura de avaliação agentic (feature 003) tenha dados reais para medir `--compare` e `--drift-check`. Entrega: (1) ingest de 30–50 normas HTML/PDF em `corpus/raw/` com `corpus/SOURCES.md` registrando proveniência; (2) script `build_dataset.py` (subcomandos `ingest`, `candidates`, `review`, `validate`) que gera `corpus/chunks.jsonl` por artigo e `eval/datasets/v1.jsonl` com 60 respondíveis, 20 multi-trecho, 20 sem resposta e 20 adversariais; (3) gate de CI `build_dataset.py validate` exit code 0; (4) versionamento de `corpus/raw/` e `corpus/chunks.jsonl` no repo para reprodutibilidade; (5) verificação de integridade do `v1.jsonl` via SHA-256 registrado em `eval/datasets/v1.sha256`.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/architecture.md#1` | Pipeline RAG local-first: ingest (parse→sanitize→chunk→embed→store) com Strategy Pattern para parsers e chunking | 🟢 |
| `_reversa_sdd/architecture.md#3` | Containers: IngestionPipeline (parse→sanitize→chunk→embed→store), Chunker (tokens/chars, overlap), PDFParser ABC (pdfplumber/PyPDF) | 🟢 |
| `_reversa_sdd/domain.md#2.1` | BR-001 a BR-005: dedup por SHA-256, sliding window com overlap, parser selecionável, sanitização NFKC, estimação de página | 🟢 |
| `_reversa_sdd/domain.md#2.5` | BR-040 a BR-043: virtual table `vec0`, cascade delete, query_log opcional, dimensions fixas no schema | 🟢 |
| `_reversa_sdd/inventory.md#2` | Estrutura: `src/anchor_rag/ingestion/` (parser, chunker, pipeline), `src/anchor_rag/vector_store/sqlite_vec.py` | 🟢 |
| `_reversa_sdd/addenda/003-agentic-rag-evaluation.md` | Feature 003 entregou: LLM-as-judge, critique-refine, comparative eval, drift detector, cost estimator — mas sem corpus/dataset não há o que medir | 🟢 |
| `_reversa_forward/003-agentic-rag-evaluation/requirements.md#5` | RF-03: dataset BACEN, RF-04: cli_eval com métricas; RF-07: query_log | 🟢 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Engenheiro de ML | Ter corpus e dataset versionados para medir qualidade do pipeline | Roda `python eval/build_dataset.py ingest` → `candidates` → `review` → `validate`; obtém `eval/datasets/v1.jsonl` com 120 itens |
| Product Owner | Garantir que avaliações `--compare` e `--drift-check` tenham base real | Dataset congelado v1.jsonl permite comparar provedores e detectar degradação ao longo do tempo |
| Engenheiro de Produção | Automatizar geração/validação do dataset no CI | `build_dataset.py validate` exit code 0 no pipeline CI; qualquer regressão de schema falha o build |
| Pesquisador de RAG | Controlar categorias de dificuldade no dataset | 4 categorias balanceadas (respondível, multi-trecho, sem resposta, adversarial) com metadados de chunk_ids |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** Corpus deve ter 30–50 normas do BCB/CMN em `corpus/raw/`, cada uma com `corpus/SOURCES.md` registrando URL oficial, data de download, número do ato (Resolução/Circular/Comunicado) e hash SHA-256 do arquivo 🟢
   - Origem no legado: `_reversa_sdd/domain.md#BR-001` (content_hash único), `_reversa_sdd/architecture.md#1` (ingest pipeline)
   - Tipo: nova

2. **RN-02:** `build_dataset.py ingest` deve extrair chunks por artigo (padrão "Art. Nº...") respeitando a sanitização (NFKC, control chars, hifenização) e chunking com overlap já existente 🟢
   - Origem no legado: `_reversa_sdd/domain.md#BR-002`, `#BR-004`, `#BR-005`
   - Tipo: nova (reutiliza lógica legada)
   - **Validado**: regex `^\s*Art\.?\s*(\d+)\s*[º°o]?(?:-([A-Z]))?\s*[.\-–]?\s` funciona em normas HTML do BCB (testado com Res. 4966, Circ. 3978, Res. 4940)

3. **RN-03:** Dataset v1.jsonl é **imutável após fechamento**; qualquer alteração gera `v2.jsonl` com versionamento semântico 🟢
   - Origem no legado: `_reversa_sdd/domain.md#BR-042` (query_log versionado), feature 003 `--drift-check` depende de baseline estável
   - Tipo: nova
   - **Mecanismo**: hash SHA-256 do `v1.jsonl` registrado em `eval/datasets/v1.sha256`; CI falha se hash divergir

4. **RN-04:** Categorias do dataset com metas fixas: 60 respondíveis (1 chunk), 20 multi-trecho (2+ chunks da mesma norma), 20 sem resposta (0 chunks, RECUSA esperada), 20 adversariais (vazamento, premissa falsa, injeção com canário) 🟢
   - Origem no legado: `_reversa_sdd/domain.md#BR-020` a `#BR-025` (grounding, citações, defesa, resposta vazia)
   - Tipo: nova

5. **RN-05:** Revisão humana é **obrigatória** — LLM só propõe candidatas (`candidates.jsonl`); nada entra no `v1.jsonl` sem aceitação explícita no `review` 🟢
   - Origem no legado: `_reversa_sdd/domain.md#BR-022` (defesa few-shot), feature 003 RN-01 (judge separado do síntese)
   - Tipo: nova

6. **RN-06:** `build_dataset.py validate` deve conferir: esquema completo, contagem por categoria ≥ metas, chunk_ids existentes em `chunks.jsonl`, ausência de ids/perguntas duplicados, avisos para perguntas que citam número de artigo 🟢
   - Origem no legado: `_reversa_sdd/domain.md#2.1` (validações de Document/Chunk), feature 003 RF-07 (persistência)
   - Tipo: nova

7. **RN-07:** `corpus/raw/` e `corpus/chunks.jsonl` são **versionados no repositório Git** para garantir reprodutibilidade do dataset — o `validate` confere `chunk_ids` contra `chunks.jsonl` versionado 🟢
   - Origem no legado: `_reversa_sdd/domain.md#BR-001` (dedup por hash), feature 003 `--drift-check` exige baseline reproduzível
   - Tipo: nova

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | Criar `eval/build_dataset.py` com subcomandos: `ingest`, `candidates`, `review`, `validate` | Must | `python eval/build_dataset.py --help` mostra 4 subcomandos; cada um executa sem erro | 🟢 |
| RF-02 | `ingest`: ler HTML/PDF de `corpus/raw/`, extrair artigos via regex "Art. Nº...", gerar `corpus/chunks.jsonl` (um chunk por artigo/continuação) com campos: chunk_id, norma, artigo, texto, n_chars, fonte; atualizar `corpus/SOURCES.md` | Must | Cada norma gera ≥ 1 chunk; artigos revogados ignorados; `corpus/SOURCES.md` criado/atualizado com URL, data, número do ato, SHA-256 | 🟢 |
| RF-03 | `candidates`: gerar perguntas candidatas via LLM (Anthropic) por categoria (`--categoria` + `--n`), append em `eval/datasets/candidates.jsonl` com metadados (id, categoria, chunk_ids_relevantes, resposta_ouro, ataque, overlap_lexical) | Must | 4 categorias suportadas; overlap_lexical calculado para "sem_resposta"; canário injetado em adversarial; id determinístico por categoria+pergunta | 🟢 |
| RF-04 | `review`: loop interativo terminal mostrando categoria, id, chunks fonte, pergunta, resposta_ouro; comandos [a]ceitar, [e]ditar, [r]ejeitar, [p]ular, [q]uit; aceitos → `eval/datasets/v1.jsonl` (revisado=true), rejeitados → `eval/datasets/rejected.jsonl` | Must | Progresso mostra contagem atual/meta por categoria; edição permite mudar pergunta/resposta/chunk_ids; revisado=true gravado | 🟢 |
| RF-05 | `validate`: ler `v1.jsonl` + `chunks.jsonl`, verificar esquema (campos obrigatórios), contagem por categoria ≥ ALVO, chunk_ids válidos, ids/perguntas únicos, regras por categoria (respondível=1 chunk, multi_trecho≥2, sem_resposta=0), exit code 0 se ok | Must | `python eval/build_dataset.py validate` exit 0 com v1.jsonl completo; exit 1 com erros listados; avisos para citações de artigo na pergunta | 🟢 |
| RF-06 | Congelar `eval/datasets/v1.jsonl` após validação OK; documentar em `eval/datasets/README.md` a versão, data, contagens, hash do arquivo; gerar `eval/datasets/v1.sha256` com SHA-256 do arquivo | Must | v1.jsonl não modificado após gate; README.md existe com metadados; hash SHA-256 registrado em v1.sha256 | 🟢 |
| RF-07 | Integrar `build_dataset.py validate` no CI (GitHub Actions) como step obrigatório antes de `eval`; CI deve falhar se `v1.jsonl` divergir do hash em `v1.sha256` | Should | `.github/workflows/ci.yml` roda validate + hash check; falha impede merge; tempo < 60s | 🟡 |
| RF-08 | Script usa modelo LLM diferente do judge da feature 003 (ex.: Anthropic Sonnet para gerar, OpenAI/Ollama para julgar) | Should | Variável `ANCHOR_GEN_MODEL` configurável; default `claude-sonnet-5-5`; documentado no README | 🟡 |
| RF-09 | `corpus/raw/` e `corpus/chunks.jsonl` commitados no repo; `.gitignore` não ignora esses paths | Must | `git status` mostra corpus versionado; `validate` usa chunks.jsonl do repo | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Desempenho | `ingest` de 50 normas em < 120s (parsing + chunking sequencial) | Uso interativo aceitável | 🟡 |
| Desempenho | `candidates` gera 30 perguntas/categoria em < 180s (LLM calls) | Batch de geração | 🟡 |
| Confiabilidade | LLM generation usa temperature=0.7, seed fixo via `--seed` para reprodutibilidade de candidatas | Debug e auditoria | 🟢 |
| Segurança | `ANTHROPIC_API_KEY` obrigatória via env; script falha cedo se ausente | Não vaza secrets | 🟢 |
| Observabilidade | Log JSON estruturado por etapa (ingest_file, split_artigos, generate_candidate, review_action) | Debug e auditoria | 🟢 |
| Extensibilidade | Categorias extensíveis via `CATEGORIAS` tupla; ALVO dicionário configurável | Futuro: novas categorias | 🟢 |
| Reprodutibilidade | `item_id` determinístico (SHA-1 categoria|pergunta_normalizada); `--seed` fixa aleatoriedade | Baseline estável para drift | 🟢 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Ingest de normas BCB gera chunks por artigo
  Dado corpus/raw/ com 3 normas do BCB (Resolução 4966, Circular 3978, Resolução 4940)
  Quando python eval/build_dataset.py ingest --raw corpus/raw --out corpus/chunks.jsonl roda
  Então corpus/chunks.jsonl tem ≥ 24 chunks
  E corpus/SOURCES.md lista 3 entradas com URL, data, número do ato, SHA-256
  E nenhum chunk tem artigo marcado como revogado

Cenário: Geração de candidatas por categoria
  Dado corpus/chunks.jsonl com 100 chunks válidos
  Quando python eval/build_dataset.py candidates --categoria respondivel --n 60 roda
  Então eval/datasets/candidates.jsonl recebe 60 novas candidatas com categoria=respondivel
  E cada uma tem chunk_ids_relevantes com exatamente 1 id existente em chunks.jsonl
  E overlap_lexical ausente (só para sem_resposta)

Cenário: Revisão humana aceita e edita candidatas
  Dado candidates.jsonl com 20 itens pendentes
  Quando revisor executa review e digita 'a' para 15, 'e' para 3 (edita pergunta), 'r' para 2
  Então v1.jsonl ganha 18 itens com revisado=true
  E rejected.jsonl ganha 2 itens com motivo

Cenário: Validação do dataset congelado
  Dado v1.jsonl com 120 itens revisados (60/20/20/20)
  Quando python eval/build_dataset.py validate roda
  Então exit code 0
  E output mostra contagem por categoria ≥ metas ALVO
  E zero erros de esquema, chunk_ids, duplicatas
  E eval/datasets/v1.sha256 contém SHA-256 correto do v1.jsonl

Cenário: Gate no CI falha com dataset inválido
  Dado v1.jsonl com pergunta duplicada
  Quando CI roda build_dataset.py validate
  Então exit code 1
  E erro "pergunta duplicada" impresso
  E pipeline CI falha

Cenário: CI detecta modificação acidental do v1.jsonl
  Dado v1.jsonl modificado após congelamento (hash divergente de v1.sha256)
  Quando CI roda hash check
  Então exit code 1
  E erro "v1.jsonl hash mismatch" impresso
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| RF-01 (build_dataset.py CLI) | Must | Interface única da feature |
| RF-02 (ingest normas → chunks) | Must | Base do corpus |
| RF-03 (candidates por categoria) | Must | Gera matéria-prima do dataset |
| RF-04 (review humano) | Must | Garantia de qualidade (LLM só propõe) |
| RF-05 (validate gate) | Must | CI gate obrigatório |
| RF-06 (congelar v1 + README + SHA-256) | Must | Imutabilidade para comparações |
| RF-07 (CI integration + hash check) | Should | Automatiza gate + integridade |
| RF-08 (modelo LLM separado do judge) | Should | Evita viés; boa prática científica |
| RF-09 (corpus versionado no repo) | Must | Reprodutibilidade do dataset |

## 9. Esclarecimentos

> Nenhuma sessão de dúvidas registrada ainda. Rode `/reversa-clarify` quando houver `[DÚVIDA]` pendente.

## 10. Lacunas Resolvidas

- ✅ **Fontes das normas (lacuna 1)**: Baixadas 3 normas de exemplo do BCB (segurança cibernética, PIX, crédito rural) via HTML do buscador de normas. Fonte: https://www.bcb.gov.br/estabilidadefinanceira/buscanormas
- ✅ **Padrão de artigos (lacuna 2)**: Regex validado — 3 normas testadas, 24 artigos extraídos corretamente (7+9+9), artigos revogados ignorados. Regex: `^\s*Art\.?\s*(\d+)\s*[º°o]?(?:-([A-Z]))?\s*[.\-–]?\s`

## 11. Lacunas Restantes

- 🟡 **Chave Anthropic**: `ANTHROPIC_API_KEY` precisa estar configurada no ambiente local para `candidates` funcionar. **Não necessária no CI** — só o `validate` roda no CI, que não faz chamadas externas.
- 🟡 **Parser PDF**: `pypdf` é dependência atual; se normas vierem em PDF complexo (tabelas), pode precisar `pdfplumber`. Decidir norma a norma após amostra. HTML é preferível (mais limpo).

## 12. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-10-10 | Versão inicial gerada por `/reversa-requirements` | reversa |
| 2026-10-10 | Lacunas 1 e 2 resolvidas; adicionados RF-06 (SHA-256), RF-07 (CI hash check), RF-09 (corpus versionado); regex validado com 3 normas BCB | reversa |
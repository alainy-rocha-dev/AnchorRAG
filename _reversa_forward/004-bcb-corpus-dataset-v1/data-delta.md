# Data Delta: bcb-corpus-dataset-v1

> Feature: `004-bcb-corpus-dataset-v1`
> Data: `2026-10-10`
> Base: `_reversa_sdd/domain.md` (modelos Pydantic), `_reversa_sdd/architecture.md` (pipeline ingest)

## 1. Resumo

Esta feature **não altera** os modelos Pydantic em `src/anchor_rag/domain/models.py`. Os modelos existentes (`Document`, `Chunk`, `QueryResult`, `IngestConfig`, `QueryConfig`, `EvalMetrics` estendido, `ComparativeMetrics`, `DriftResult`, `CostEstimate`) permanecem intactos.

A feature cria **arquivos de dados externos** (JSONL) que alimentam o pipeline:
- `corpus/chunks.jsonl` — chunks por artigo (compatível com `Chunk`)
- `corpus/SOURCES.md` — proveniência (Markdown tabela)
- `eval/datasets/candidates.jsonl` — candidatas pré-revisão
- `eval/datasets/v1.jsonl` — dataset gold standard congelado
- `eval/datasets/v1.sha256` — hash de integridade
- `eval/datasets/rejected.jsonl` — candidatas rejeitadas
- `eval/datasets/README.md` — documentação do dataset

## 2. Arquivos de dados novos

### 2.1 `corpus/chunks.jsonl`

**Propósito**: Corpus versionado para retrieval + geração de candidatas.

**Schema por linha** (compatível com campos de `domain.models.Chunk`):

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `chunk_id` | `str` | ✅ | ID único: `norma:artN` ou `norma:artN-pM` (ex: `resolucao_4966:art1`) |
| `norma` | `str` | ✅ | Slug da norma (ex: `resolucao_4966`, `circular_3978`) |
| `artigo` | `str` | ✅ | Rótulo do artigo (ex: `1`, `2-A`, `5`) |
| `texto` | `str` | ✅ | Conteúdo do chunk (artigo completo ou continuação) |
| `n_chars` | `int` | ✅ | Tamanho em caracteres |
| `fonte` | `str` | ✅ | Arquivo origem (ex: `resolucao_4966.html`) |

**Exemplo**:
```json
{"chunk_id": "resolucao_4966:art1", "norma": "resolucao_4966", "artigo": "1", "texto": "Art. 1º\n\nAs instituições autorizadas a funcionar pelo Banco Central do Brasil devem estabelecer...", "n_chars": 261, "fonte": "resolucao_4966.html"}
```

**Estimativa**: 30-50 normas × 8-12 artigos/norma = **240-600 chunks**.

**Compatibilidade**: Campos mapeiam para `Chunk`:
- `chunk_id` → `Chunk.id` (precisa parse UUID ou adaptar)
- `norma` + `artigo` → `Chunk.metadata`
- `texto` → `Chunk.content`
- `n_chars` → `Chunk.token_count` (aprox: chars/3.5)

### 2.2 `corpus/SOURCES.md`

**Propósito**: Rastreabilidade e auditoria do corpus.

**Formato**: Markdown tabela.

| Coluna | Descrição |
|--------|-----------|
| Norma | Nome legível |
| Arquivo | Nome do arquivo em `corpus/raw/` |
| URL Oficial | Link do BCB |
| Data Download | ISO 8601 |
| Número do Ato | Ex: "Resolução CMN nº 4.966" |
| SHA-256 | Hash do arquivo bruto |

### 2.3 `eval/datasets/candidates.jsonl`

**Propósito**: Pool de perguntas propostas pelo LLM, pré-revisão humana.

**Schema** (estende v1.jsonl com campos de geração):

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | `str` | SHA-1 determinístico: `sha1(categoria|norm(pergunta))[:10]` |
| `pergunta` | `str` | Pergunta proposta |
| `categoria` | `str` | `respondivel` \| `multi_trecho` \| `sem_resposta` \| `adversarial` |
| `chunk_ids_relevantes` | `List[str]` | IDs de `chunks.jsonl` |
| `resposta_ouro` | `str` | Resposta esperada ou "RECUSA" |
| `revisado` | `bool` | Sempre `false` aqui |
| `gerado_por` | `str` | Modelo LLM (ex: `claude-sonnet-5-5`) |
| `ataque` | `str?` | Só `adversarial`: `premissa_falsa` \| `injecao_em_chunk` \| `vazamento_ou_fora_de_escopo` |
| `canario` | `str?` | Só `adversarial` injeção: `CANARIO_abc123` |
| `chunk_injetado` | `str?` | Só `adversarial` injeção: chunk_id |
| `overlap_max` | `float?` | Só `sem_resposta`: max overlap lexical (0-1) |
| `overlap_chunk` | `str?` | Só `sem_resposta`: chunk_id do max overlap |

### 2.4 `eval/datasets/v1.jsonl` (DATASET CONGELADO)

**Propósito**: Gold standard para avaliação. **Imutável após validação.**

**Schema** (subconjunto de candidates + `revisado=true`):

| Campo | Tipo | Regra |
|-------|------|-------|
| `id` | `str` | Mesmo de candidates |
| `pergunta` | `str` | Editável no review |
| `categoria` | `str` | Fixa |
| `chunk_ids_relevantes` | `List[str]` | Editável no review |
| `resposta_ouro` | `str` | Editável no review |
| `revisado` | `bool` | **Sempre `true`** |
| `gerado_por` | `str` | Modelo original |
| `editado` | `bool?` | `true` se revisor editou |
| `ataque` | `str?` | Herdado |
| `canario` | `str?` | Herdado |
| `chunk_injetado` | `str?` | Herdado |
| `overlap_max` | `float?` | Herdado |
| `overlap_chunk` | `str?` | Herdado |

**Metas por categoria (ALVO)**:
| Categoria | Mínimo | Descrição |
|-----------|--------|-----------|
| `respondivel` | 60 | 1 chunk relevante |
| `multi_trecho` | 20 | 2+ chunks mesma norma |
| `sem_resposta` | 20 | 0 chunks (recusa) |
| `adversarial` | 20 | Vazamento, premissa falsa, injeção |
| **Total** | **120** | |

### 2.5 `eval/datasets/v1.sha256`

**Propósito**: Verificação de integridade do dataset congelado.

**Formato**: Padrão `sha256sum`:
```
a1b2c3d4e5f6...  eval/datasets/v1.jsonl
```

**Uso no CI**:
```bash
sha256sum -c eval/datasets/v1.sha256  # exit 0 se OK, 1 se modificado
```

### 2.6 `eval/datasets/rejected.jsonl`

**Propósito**: Auditoria de candidatas rejeitadas.

**Schema**:
```json
{"id": "abc123def4", "motivo": "Pergunta ambígua / duplicata / fora de escopo"}
```

### 2.7 `eval/datasets/README.md`

**Propósito**: Documentação do dataset para reprodutibilidade.

**Conteúdo**:
- Versão (v1), data, hash SHA-256
- Contagem por categoria (atual vs alvo)
- Modelo gerador (`gerado_por`)
- Seed usado (`--seed`)
- Instruções para regenerar v2

## 3. Migrações necessárias

**Nenhuma migração de banco de dados**. A feature é offline (arquivos JSONL + Markdown).

O `chunks.jsonl` é consumido pelo `build_dataset.py` e pode ser carregado no vector store via pipeline de ingestão padrão se desejado (mas não é obrigatório para a avaliação — o `eval` usa os chunks diretamente).

## 4. Compatibilidade com modelos existentes

| Modelo legado | Impacto |
|---------------|---------|
| `Document` | Não usado diretamente; `corpus/SOURCES.md` substitui metadados de proveniência |
| `Chunk` | `chunks.jsonl` tem schema compatível (mesmos campos semânticos) |
| `QueryResult` | Não alterado |
| `EvalMetrics` (estendido feature 003) | `v1.jsonl` fornece `per_query` ground truth |
| `ComparativeMetrics` | `--compare` usa `v1.jsonl` como dataset comum |
| `DriftResult` | `--drift-check` usa `v1.jsonl` como baseline |
| `CostEstimate` | `candidates` + `review` geram tokens contabilizados |

## 5. Versionamento semântico do dataset

| Versão | Critério | Arquivos |
|--------|----------|----------|
| `v1` | Primeiro freeze válido (validate exit 0) | `v1.jsonl`, `v1.sha256`, `README.md` |
| `v2` | Qualquer alteração pós-freeze (add/remove/edit) | `v2.jsonl`, `v2.sha256`, `README.md` |
| `vN` | Re-geração completa (novo corpus, novas categorias) | `vN.jsonl`, `vN.sha256`, `README.md` |

**Regra**: `v1.jsonl` **nunca** é modificado após commit. CI falha se `sha256sum -c v1.sha256` divergir.

## 6. Estimativas de tamanho

| Arquivo | Linhas estimadas | Tamanho |
|---------|------------------|---------|
| `corpus/chunks.jsonl` | 300-600 | ~5-15 MB |
| `corpus/SOURCES.md` | 50 | ~5 KB |
| `eval/datasets/candidates.jsonl` | 200-300 | ~500 KB |
| `eval/datasets/v1.jsonl` | 120 | ~200 KB |
| `eval/datasets/v1.sha256` | 1 | ~100 B |
| `eval/datasets/rejected.jsonl` | 20-50 | ~10 KB |
| `eval/datasets/README.md` | 50 | ~5 KB |
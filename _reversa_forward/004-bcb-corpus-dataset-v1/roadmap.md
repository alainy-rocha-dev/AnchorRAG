# Roadmap: bcb-corpus-dataset-v1

> Identificador: `004-bcb-corpus-dataset-v1`
> Data: `2026-10-10`
> Requirements: `_reversa_forward/004-bcb-corpus-dataset-v1/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

Esta feature entrega o **corpus BCB/CMN versionado** e o **dataset de avaliação v1.jsonl congelado** (120 perguntas) para habilitar a infraestrutura de avaliação agentic da feature 003. A abordagem técnica é:

1. **Corpus**: Baixar 30–50 normas do BCB (HTML preferível, PDF como fallback) para `corpus/raw/`. O script `build_dataset.py ingest` usa o parser HTML existente (`_Strip` em `build_dataset.py`) + regex validada para extrair artigos (`Art. Nº...`), gerando `corpus/chunks.jsonl` (um chunk por artigo) e `corpus/SOURCES.md` com proveniência (URL, data, número do ato, SHA-256).

2. **Dataset**: `build_dataset.py candidates` gera perguntas candidatas via LLM (Anthropic Sonnet) em 4 categorias balanceadas (60/20/20/20). `build_dataset.py review` faz revisão humana interativa (aceitar/editar/rejeitar). `build_dataset.py validate` confere esquema, contagens, chunk_ids, duplicatas, e gera `eval/datasets/v1.sha256` para imutabilidade.

3. **Versionamento**: `corpus/raw/`, `corpus/chunks.jsonl`, `eval/datasets/v1.jsonl`, `eval/datasets/v1.sha256` são commitados no repo. CI roda `validate` + hash check.

4. **Integração com feature 003**: O `chunks.jsonl` alimenta o `--agentic` e `--compare` da feature 003. O `--drift-check` usa `v1.jsonl` como baseline.

## 2. Princípios aplicados

| Princípio | Como a feature se relaciona | Status |
|-----------|------------------------------|--------|
| Reprodutibilidade | Corpus e dataset versionados no repo; `--seed` fixo; `item_id` determinístico | respeita |
| Observabilidade | Log JSON estruturado por etapa (ingest_file, split_artigos, generate_candidate, review_action) | respeita |
| Segurança | `ANTHROPIC_API_KEY` só no ambiente local; CI não tem segredos (só roda `validate`) | respeita |
| Extensibilidade | Categorias via tupla `CATEGORIAS`; metas via dict `ALVO`; regex de artigo parametrizável | respeita |

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|--------------------------|-------------|
| D-01 | Usar HTML do buscador de normas BCB como fonte primária | Mais limpo que PDF; regex `Art. Nº...` funciona nativamente; evita pdfplumber/pypdf | PDF + pdfplumber; PDF + pypdf | 🟢 |
| D-02 | Regex `^\s*Art\.?\s*(\d+)\s*[º°o]?(?:-([A-Z]))?\s*[.\-–]?\s` para split de artigos | Validado em 3 normas (24 artigos, 0 falsos positivos); ignora revogados | Parser PDF + heurística de layout | 🟢 |
| D-03 | LLM gerador (Anthropic Sonnet) diferente do judge (OpenAI/Ollama) | Evita viés de auto-avaliação; boa prática científica | Mesmo modelo para gerar e julgar | 🟢 |
| D-04 | Revisão humana obrigatória (LLM só propõe) | Garante qualidade do gold standard; evita contaminação do dataset | Auto-aprovação com threshold | 🟢 |
| D-05 | `v1.jsonl` imutável + SHA-256 em `v1.sha256` | `--drift-check` e `--compare` precisam baseline estável; CI falha se alterado | Versionamento semântico só no nome (v1/v2) sem hash | 🟢 |
| D-06 | `corpus/raw/` e `chunks.jsonl` versionados no Git | Reprodutibilidade total; `validate` confere chunk_ids contra repo | Apenas dataset versionado; corpus em S3/artefato | 🟢 |
| D-07 | Categorias fixas: respondível(60), multi_trecho(20), sem_resposta(20), adversarial(20) | Balanceamento clássico RAG; adversarial testa prompt injection (herda BR-022) | Distribuição uniforme (30 cada) | 🟡 |
| D-08 | `build_dataset.py` como script standalone em `eval/` | Não acopla ao pipeline RAG; roda off-line; CI simples | Integrar como comando `hag-rag dataset` no CLI principal | 🟢 |

## 4. Premissas

| Premissa | Origem (`requirements.md` seção) | Risco se errada |
|----------|----------------------------------|-----------------|
| BCB disponibiliza HTML limpo para 30-50 normas via buscador | Lacunas resolvidas (1) | Se HTML não disponível, precisa PDF parser; regex pode falhar em PDF complexo |
| Regex de artigo cobre todas as variantes BCB (Art. 1º, Artigo 1, etc.) | Lacunas resolvidas (2) | Se alguma norma usar numeração diferente, artigos perdidos → chunks incompletos |
| `ANTHROPIC_API_KEY` disponível no ambiente do desenvolvedor | Lacunas restantes (3) | Sem key, `candidates` não roda; workaround: gerar em máquina com key, commit candidates.jsonl |
| PDFs complexos (tabelas) são minoria; HTML cobre maioria | Lacunas restantes (4) | Se norma crítica só em PDF com tabelas, `pypdf` pode truncar → `pdfplumber` necessário |

## 5. Delta arquitetural

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| `eval/build_dataset.py` | Novo arquivo | componente-novo | Script standalone 4 subcomandos: ingest, candidates, review, validate |
| `corpus/raw/` | Novo diretório | componente-novo | 30-50 normas BCB (HTML/PDF) + `SOURCES.md` |
| `corpus/chunks.jsonl` | Novo arquivo | componente-novo | Chunks por artigo (chunk_id, norma, artigo, texto, n_chars, fonte) |
| `eval/datasets/v1.jsonl` | Novo arquivo | componente-novo | 120 perguntas revisadas (id, pergunta, categoria, chunk_ids, resposta_ouro, revisado) |
| `eval/datasets/v1.sha256` | Novo arquivo | componente-novo | Hash SHA-256 do v1.jsonl para imutabilidade |
| `corpus/SOURCES.md` | Novo arquivo | componente-novo | Proveniência: URL, data, número do ato, SHA-256 por norma |
| `.github/workflows/ci.yml` | Existente | regra-alterada | Adiciona step `build_dataset.py validate` + hash check |
| `cli_eval.py` (feature 003) | `_reversa_sdd/architecture.md#3` | contrato-alterado | `--agentic` e `--compare` agora têm dados reais via `chunks.jsonl` + `v1.jsonl` |

## 6. Delta no modelo de dados

- Resumo das mudanças: Nenhuma mudança no modelo de domínio Pydantic (`domain/models.py`). A feature cria arquivos de dados (JSONL) que alimentam o pipeline existente. O `chunks.jsonl` segue estrutura compatível com `domain.models.Chunk` (chunk_id, norma, artigo, texto). O `v1.jsonl` define schema próprio para dataset de avaliação.
- Detalhe completo em: `_reversa_forward/004-bcb-corpus-dataset-v1/data-delta.md`

## 7. Delta de contratos externos

| Contrato | Tipo | Arquivo de detalhe |
|----------|------|--------------------|
| `build_dataset.py` CLI | Arquivo (script) | n/a (script standalone) |
| GitHub Actions CI | Arquivo (YAML) | n/a (modifica workflow existente) |

> Nenhum contrato HTTP/fila/gRPC/GraphQL afetado. A feature é offline (script + dados versionados).

## 8. Plano de migração

1. Baixar 30-50 normas BCB/CMN (HTML preferível) → `corpus/raw/`
2. Rodar `python eval/build_dataset.py ingest --raw corpus/raw --out corpus/chunks.jsonl` → gera chunks + `SOURCES.md`
3. Commitar `corpus/raw/` + `corpus/chunks.jsonl` + `corpus/SOURCES.md`
4. Rodar `candidates` para 4 categorias (60/20/20/20) → `eval/datasets/candidates.jsonl`
5. Rodar `review` interativo → `eval/datasets/v1.jsonl` (120 revisados) + `rejected.jsonl`
6. Rodar `validate` → exit 0 + gera `eval/datasets/v1.sha256` + `README.md`
7. Commitar `eval/datasets/v1.jsonl` + `v1.sha256` + `README.md`
8. Atualizar CI (`.github/workflows/ci.yml`) com step `validate` + hash check
8. Testar integração: `hag-rag eval --dataset eval/datasets/v1.jsonl --agentic --judge ollama`

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Norma BCB só disponível em PDF com tabelas/colunas → regex falha | alto | médio | Usar `pdfplumber` para essa norma; HTML é padrão; testar amostra antes |
| Regex de artigo não casa variante exótica (ex.: "Artigo 1.") | médio | baixo | Validar em 10+ normas antes do corpus final; regex parametrizável via `--artigo-pattern` |
| `ANTHROPIC_API_KEY` não disponível no CI | baixo | nulo | CI só roda `validate` (sem LLM); `candidates` roda localmente |
| Dataset v1.jsonl editado acidentalmente → drift check inválido | alto | médio | Hash SHA-256 em `v1.sha256` + CI check; imutabilidade forçada |
| Corpus grande (>50 normas) → `ingest` lento | médio | baixo | `ingest` é sequencial mas 50 normas < 120s; paralelizar se necessário |
| Chunk muito curto/longo afeta qualidade do retrieval | médio | médio | `max_chars=2500` no ingest; `dividir_longo` split por §/parágrafo |

## 10. Critério de pronto

- [ ] `corpus/raw/` com 30–50 normas + `SOURCES.md` commitados
- [ ] `corpus/chunks.jsonl` gerado e commitado (≥ 200 chunks estimados)
- [ ] `eval/datasets/v1.jsonl` com 120 perguntas revisadas (60/20/20/20) + `v1.sha256` + `README.md` commitados
- [ ] `python eval/build_dataset.py validate` exit 0
- [ ] CI (`.github/workflows/ci.yml`) roda `validate` + hash check e falha se divergir
- [ ] `hag-rag eval --dataset eval/datasets/v1.jsonl --agentic --judge ollama` produz métricas RAGAS-like
- [ ] `hag-rag eval --dataset eval/datasets/v1.jsonl --compare openai,ollama` produz tabela estatística
- [ ] `hag-rag eval --dataset eval/datasets/v1.jsonl --drift-check --baseline eval/datasets/v1.jsonl` exit 0

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-10-10 | Versão inicial gerada por `/reversa-plan` | reversa |
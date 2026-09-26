# Relatório de Confiança — HAG RAG

> Gerado pelo Reversa Reviewer em 2026-09-22
> Nível de documentação: **essencial**

---

## 1. Resumo Executivo

| Métrica | Valor |
|---------|-------|
| **Artefatos Revisados** | 18 (13 core + 3 SDD specs + 2 transversal) |
| **Afirmações Totais** | ~420 (estimado) |
| **🟢 CONFIRMADO** | ~280 (67%) |
| **🟡 INFERIDO** | ~100 (24%) |
| **🔴 LACUNA** | ~40 (9%) |
| **Confiança Geral** | **72%** |

> **Nota**: Percentual ponderado por criticidade. Core artifacts (architecture, domain, ADRs) têm peso maior que SDD specs.

---

## 2. Detalhamento por Artefato

### 2.1 Core Reversa Artifacts (🟢 Alto Confiança)

| Artefato | 🟢 | 🟡 | 🔴 | Confiança | Observações |
|----------|-----|-----|-----|-----------|-------------|
| `architecture.md` | 85 | 12 | 3 | 85% | C4 Context + ERD + Tech Debts — alinhado com código |
| `c4-context.md` | 25 | 3 | 0 | 89% | Diagrama Mermaid válido, reflete integrações reais |
| `domain.md` | 45 | 18 | 6 | 65% | Regras bem extraídas; 6 lacunas críticas identificadas |
| `state-machines.md` | 30 | 8 | 0 | 79% | 4 máquinas (Document, Chunk, Query, Provider Health) |
| `adrs/001-sqlite-vec` | 18 | 4 | 1 | 78% | Decisão documentada com alternativas e consequências |
| `adrs/002-strategy-registry` | 15 | 3 | 0 | 83% | Pattern confirmado em 4 famílias de providers |
| `adrs/003-strict-grounding` | 22 | 5 | 2 | 76% | Prompt + few-shot + citações — implementado fielmente |
| `adrs/004-chunking-strategy` | 20 | 6 | 1 | 74% | Algoritmo + params confirmados; gap: unidade default |
| `adrs/005-pydantic-settings` | 25 | 7 | 2 | 74% | Config hierárquica + YAML + env + secrets — fiel |
| `traceability/spec-impact-matrix.md` | 40 | 25 | 4 | 62% | Matriz completa; 150 entradas; 4 conflitos 🔴 |
| `code-analysis.md` | 55 | 10 | 2 | 85% | 4 módulos analisados detalhadamente |

### 2.2 SDD Specs (🟡 Médio Confiança — Status PLANEJADO mas código EXISTE)

| Artefato | 🟢 | 🟡 | 🔴 | Confiança | **Discrepâncias Críticas** |
|----------|-----|-----|-----|-----------|---------------------------|
| `sdd/document-ingestion-chunking.md` | 8 | 12 | 5 | 32% | **chunk_size**: spec=1000 chars / code=512 tokens<br>**chunk_overlap**: spec=200 chars / code=50 tokens<br>**unit**: spec=chars / code=tokens<br>**parser**: spec não menciona pdfplumber/PyPDF factory<br>**exceção**: spec=InvalidDocumentException / code=mesma |
| `sdd/rag-synthesis-citation-engine.md` | 7 | 10 | 6 | 28% | **citação**: spec=`[Fonte: file, Pág. N]` / code=`[N]` numeric<br>**threshold**: spec=0.40 / code=0.7<br>**latência**: spec=<2s / code=sem SLA<br>**formato**: spec=inline+rodapé / code=inline+fallback<br>**prompt injection**: spec menciona / code=3 few-shot examples |
| `sdd/vector-store-similarity-search.md` | 9 | 11 | 4 | 35% | **store**: spec=in-memory/SQLite / code=sqlite-vec virtual table<br>**retry**: spec=3 tentativas / code=apenas OpenAI tem retry<br>**k default**: spec=3 / code=5<br>**score range**: spec=0.0-1.0 / code=distance convertido |

---

## 3. Principais Descobertas

### 3.1 Lacunas Críticas (🔴) — Bloqueiam Reimplementação Fiel

| ID | Artefato | Descrição | Impacto |
|----|----------|-----------|---------|
| CR-001 | SDD Ingestion | `chunk_size`/`chunk_overlap` defaults divergentes (chars vs tokens, 1000/200 vs 512/50) | Reimplementação usaria params errados |
| CR-002 | SDD Synthesis | Formato de citação divergente (`[Fonte: file, Pág.]` vs `[N]`) | Testes de aceitação falhariam |
| CR-003 | SDD Synthesis | Threshold divergente (0.40 vs 0.7) | Comportamento de recall/precision diferente |
| CR-004 | SDD Vector Store | Armazenamento speculado (in-memory) vs real (sqlite-vec) | Arquitetura de persistência errada |
| CR-005 | Domain/Traceability | `embedding.dimensions` ≠ `vector_store.embedding_dimensions` não validado | Runtime error silencioso até falha |
| CR-006 | Domain/Traceability | Dedup por hash não implementado (comentário "em produção") | Re-ingestão duplicada em produção |

### 3.2 Inconsistências Internas (🟡)

| ID | Local | Descrição |
|----|-------|-----------|
| IN-001 | SDD Ingestion RF-02 | Diz "chunk_size padrão 1000 caracteres" mas código usa tokens |
| IN-002 | SDD Synthesis RF-03 | Threshold 0.40 hardcoded na spec vs configável no código |
| IN-003 | SDD Vector Store RF-04 | `top_k=3` default na spec vs `5` no código |
| IN-004 | Domain BR-011 vs BR-043 | Validação dimensions existe no provider mas não cross-config |
| IN-005 | Architecture TD-001 | Mesma lacuna listada como tech debt e domain gap |

### 3.3 Pontos Fortes (🟢)

- **Arquitetura C4 + ERD**: Fiel ao código, diagramas Mermaid válidos
- **ADRs**: Decisões documentadas com alternativas, consequências, mitigações
- **State Machines**: 4 máquinas cobrindo entidades centrais + health
- **Domain Rules**: 25 regras extraídas com rastreabilidade ao código
- **Traceability Matrix**: 150 entradas mapeando specs→componentes

---

## 4. Reclassificações Realizadas

| Antes | Depois | Artefato | Justificativa |
|-------|--------|----------|---------------|
| 🟢 (SDD status) | 🟡 PLANEJADO | 3 SDD specs | Status header diz PLANEJADO mas código EXISTE — reclassificar para IMPLEMENTADO |
| 🟡 (chunk_size default) | 🔴 LACUNA | SDD Ingestion | Valor divergente do código real |
| 🟡 (citation format) | 🔴 LACUNA | SDD Synthesis | Formato divergente do código real |
| 🟡 (threshold) | 🔴 LACUNA | SDD Synthesis | Valor divergente do código real |
| 🟡 (vector store type) | 🔴 LACUNA | SDD Vector Store | Implementação real usa sqlite-vec, não in-memory |

---

## 5. Perguntas para Validação Humana

> Como `doc_level=essencial` e `answer_mode=chat`, apresento apenas as **6 lacunas críticas** que bloqueiam reimplementação fiel.

### P1: Chunking Parameters
**Artefato**: `sdd/document-ingestion-chunking.md` (RF-02)
**Conflito**: Spec define `chunk_size=1000 caracteres`, `chunk_overlap=200 caracteres`; código usa `chunk_size=512 tokens`, `chunk_overlap=50 tokens`, `chunk_unit="tokens"`
**Pergunta**: Qual deve ser o padrão canônico para documentação e futuras reimplementações?
- [ ] Manter código (512 tokens / 50 tokens) — atualizar spec
- [ ] Alinhar spec ao código mas documentar ambos
- [ ] Outro: ___________

### P2: Citation Format
**Artefato**: `sdd/rag-synthesis-citation-engine.md` (RF-02, Critério de Aceite)
**Conflito**: Spec espera `[Fonte: manual_tecnico.pdf, Pág. 14]`; código gera `[1]`, `[2]` numérico com metadata separada
**Pergunta**: Qual formato de citação é o requerido pelo produto?
- [ ] Numérico `[N]` (atual) — atualizar spec
- [ ] Com fonte+página inline — refatorar synthesizer
- [ ] Ambos (numérico inline + lista detalhada rodapé) — atualizar ambos

### P3: Similarity Threshold Default
**Artefato**: `sdd/rag-synthesis-citation-engine.md` (RF-03) + `sdd/vector-store-similarity-search.md`
**Conflito**: Specs citam 0.40; código usa 0.7 (QueryConfig.default)
**Pergunta**: Qual threshold default reflete o comportamento desejado?
- [ ] 0.7 (atual, mais restritivo) — atualizar specs
- [ ] 0.40 (mais permissivo) — alterar código
- [ ] Configurável sem default hardcoded — remover das specs

### P4: Vector Store Implementation
**Artefato**: `sdd/vector-store-similarity-search.md` (Seção 2.2, Open Question)
**Conflito**: Spec questiona "in-memory vs SQLite"; código implementa **sqlite-vec virtual table** com persistência ACID
**Pergunta**: A spec deve refletir a implementação real (sqlite-vec) ou manter-se abstrata?
- [ ] Refletir implementação real (sqlite-vec) — atualizar spec
- [ ] Manter abstrata (interface VectorStore) — mover detalhes para ADR-001
- [ ] Documentar ambos: interface + implementação default

### P5: Dimensions Cross-Validation
**Artefato**: `domain.md` (Lacuna CR-005) + `traceability/spec-impact-matrix.md` (GAP-001)
**Problema**: `AppConfig` permite `embedding.dimensions` ≠ `vector_store.embedding_dimensions`; erro só em runtime
**Pergunta**: Como validar consistência no startup?
- [ ] Adicionar `@model_validator(mode="after")` no `AppConfig` — falhar rápido
- [ ] Validar no `RAGPipeline.initialize()` — log warning
- [ ] Documentar como pré-requisito operacional — não bloquear

### P6: Deduplication Implementation
**Artefato**: `domain.md` (BR-001, Lacuna CR-006) + `ingestion/pipeline.py:95`
**Problema**: Código tem comentário "Nota: implementação simplificada - em produção usar índice de hash"; dedup real não funciona
**Pergunta**: Prioridade para implementar dedup real antes de produção?
- [ ] Sim — implementar índice de hash em `documents` table query antes de parse
- [ ] Não — manter simplificado, aceitar re-ingestão ocasional
- [ ] Adicionar flag `force_reingest` para controle manual (já existe em IngestConfig)

---

## 6. Recomendações Pós-Revisão

1. **Atualizar 3 SDD specs** para status 🟢 IMPLEMENTADO e corrigir parâmetros divergentes
2. **Adicionar validador cross-section** no `AppConfig` para `embedding.dimensions == vector_store.embedding_dimensions`
3. **Implementar dedup real** consultando `content_hash` antes de parse (performance: índice em `documents.content_hash`)
4. **Documentar threshold 0.7** como default consciente (precision > recall para RAG técnico)
5. **Mover detalhes de implementação** (sqlite-vec) dos SDDs para ADRs; SDDs ficam no nível de interface

---

## 7. Próximos Passos Sugeridos

| Ação | Responsável | Prioridade |
|------|-------------|------------|
| Responder 6 perguntas acima | User (arocha) | 🔴 Crítica |
| Atualizar SDD specs com respostas | Reversa (Writer) | 🔴 Crítica |
| Adicionar validador cross-config | Dev team | 🟡 Alta |
| Implementar dedup por hash | Dev team | 🟡 Alta |
| Gerar testes de contrato para ABCs | Dev team | 🟢 Média |
# Perguntas de Validação — HAG RAG

> Gerado pelo Reversa Reviewer em 2026-09-22
> Nível de documentação: **essencial** — apenas lacunas 🔴 que bloqueiam reimplementação
> Modo de resposta: **chat** (responda diretamente aqui)

---

## Instruções

Responda cada pergunta abaixo. Suas respostas serão incorporadas às specs e a confiança será reclassificada.

---

### P1: Chunking Parameters (SDD Ingestion)

**Conflito**: Spec define `chunk_size=1000 caracteres`, `chunk_overlap=200 caracteres`; código usa `chunk_size=512 tokens`, `chunk_overlap=50 tokens`, `chunk_unit="tokens"`

**Qual deve ser o padrão canônico?**
- [ ] **A** — Manter código (512 tokens / 50 tokens) — atualizar spec
- [ ] **B** — Alinhar spec ao código mas documentar ambos os modos
- [ ] **C** — Outro: ___________

**Sua resposta**: **A** — Manter código (512 tokens / 50 tokens) — atualizar spec

---

### P2: Citation Format (SDD Synthesis)

**Conflito**: Spec espera `[Fonte: manual_tecnico.pdf, Pág. 14]`; código gera `[1]`, `[2]` numérico com metadata separada na tabela de citações

**Qual formato de citação é o requerido?**
- [ ] **A** — Numérico `[N]` (atual) — atualizar spec
- [ ] **B** — Com fonte+página inline — refatorar synthesizer
- [ ] **C** — Ambos (numérico inline + lista detalhada rodapé) — atualizar ambos

**Sua resposta**: **A** — Numérico `[N]` (atual) — atualizar spec

---

### P3: Similarity Threshold Default (SDD Synthesis + Vector Store)

**Conflito**: Specs citam threshold 0.40; código usa 0.7 (QueryConfig.default)

**Qual threshold default reflete o comportamento desejado?**
- [ ] **A** — 0.7 (atual, mais restritivo/precision) — atualizar specs
- [ ] **B** — 0.40 (mais permissivo/recall) — alterar código
- [ ] **C** — Configurável sem default hardcoded — remover das specs

**Sua resposta**: **A** — 0.7 (atual, mais restritivo/precision) — atualizar specs

---

### P4: Vector Store Implementation (SDD Vector Store)

**Conflito**: Spec questiona "in-memory vs SQLite"; código implementa **sqlite-vec virtual table** com persistência ACID, query_log, cascade delete

**A spec deve refletir a implementação real?**
- [ ] **A** — Refletir implementação real (sqlite-vec) — atualizar spec
- [ ] **B** — Manter abstrata (interface VectorStore) — mover detalhes para ADR-001
- [ ] **C** — Documentar ambos: interface + implementação default

**Sua resposta**: **A** — Refletir implementação real (sqlite-vec) — atualizar spec

---

### P5: Dimensions Cross-Validation (Domain + Traceability)

**Problema**: `AppConfig` permite `embedding.dimensions` ≠ `vector_store.embedding_dimensions`; erro só em runtime

**Como validar consistência no startup?**
- [ ] **A** — Adicionar `@model_validator(mode="after")` no `AppConfig` — falhar rápido
- [ ] **B** — Validar no `RAGPipeline.initialize()` — log warning
- [ ] **C** — Documentar como pré-requisito operacional — não bloquear

**Sua resposta**: **A** — Adicionar `@model_validator(mode="after")` no `AppConfig` — falhar rápido

---

### P6: Deduplication Implementation (Domain + Ingestion Pipeline)

**Problema**: Código tem comentário "Nota: implementação simplificada - em produção usar índice de hash"; dedup real não funciona (não consulta hash antes de parse)

**Prioridade para implementar dedup real antes de produção?**
- [ ] **A** — Sim — implementar índice de hash em `documents` table query antes de parse
- [ ] **B** — Não — manter simplificado, aceitar re-ingestão ocasional
- [ ] **C** — Adicionar flag `force_reingest` para controle manual (já existe em IngestConfig)

**Sua resposta**: **A** — Sim — implementar índice de hash em `documents` table query antes de parse

---

## Resumo para Preenchimento Rápido

| Pergunta | Opção Escolhida |
|----------|-----------------|
| P1 (Chunking) | A |
| P2 (Citação) | A |
| P3 (Threshold) | A |
| P4 (Vector Store) | A |
| P5 (Dimensions) | A |
| P6 (Dedup) | A |

---

> **Após responder todas, digite `reversa` para continuar o pipeline.**
# SDD Spec: Vector Store & Similarity Search (`vector-store-similarity-search`)

> Selo 🟢 IMPLEMENTADO. Especificação técnica executável no padrão SDD/RFC.

**Componente:** `vector-store-similarity-search`  
**Versão:** 1.0  
**Data:** 2026-09-22T14:27:10-03:00  
**Autor:** reversa-spec-sdd  
**Status:** 🟢 IMPLEMENTADO  

---

## 1. Problema e Objetivos

🟢 **Problema:** A busca textual tradicional por palavra-chave falha em identificar equivalências semânticas e variações conceituais em documentos técnicos.  
🟢 **Objetivo:** Converter chunks de texto em vetores numéricos de embedding, armazená-los junto com seus metadados e realizar busca eficiente por similaridade de cosseno para retornar os top-k trechos mais relevantes para qualquer consulta.

---

## 2. Escopo do Componente

### 2.1 O que FAZ (In-Scope)
- 🟢 Interface para geração de embeddings via modelo vetorial (OpenAI `text-embedding-3-*`, Ollama `nomic-embed-text`, HuggingFace `BAAI/bge-m3`) via Strategy Pattern.
- 🟢 Armazenamento persistente em **SQLite + sqlite-vec virtual table `vec0`** de vetores associados ao `chunk_id` e metadados (`source_file`, `page_number`, `text_content`).
- 🟢 Execução da função matemática de similaridade de cosseno nativa via `sqlite-vec`: `vec_distance_cosine(embedding, query_embedding)`; score = `1 - distance`.
- 🟢 Ordenação e filtragem dos resultados retornando os $k$ trechos com maior score de similaridade (Top-K).

### 2.2 O que NÃO faz (Non-Goals / Out-of-Scope)
- 🟢 Geração de resposta final em linguagem natural (responsabilidade do componente RAG Synthesis).
- 🟢 Re-ranking complexo com modelo Cross-Encoder no MVP.
- 🟢 Gerenciamento de índices vetoriais distribuídos em cluster enterprise (ex.: Milvus/Qdrant clusterizado) no MVP.

---

## 3. Requisitos Funcionais (RFs)

- 🟢 **RF-01 (Geração de Embedding):** O componente deve receber uma string de texto e retornar seu vetor denso de números em ponto flutuante com a dimensão correspondente ao modelo utilizado (1536 para OpenAI small, 768 para nomic-embed-text, 1024 para BAAI/bge-m3).
- 🟢 **RF-02 (Indexação de Chunks):** O componente deve aceitar uma lista de objetos `Chunk` com texto e metadados, gerando e salvando seus vetores no repositório de vetores (Vector Store) via `add_chunks()`.
- 🟢 **RF-03 (Busca por Similaridade de Cosseno):** Dada uma query em texto plano, o componente deve gerar o embedding da query e calcular a similaridade de cosseno contra todos os vetores indexados via `search(query_embedding, top_k, threshold)`.
- 🟢 **RF-04 (Retorno de Top-K e Scores):** A busca por similaridade deve retornar exatamente $k$ resultados (onde $k$ é parâmetro inteiro positivo com valor default 5) contendo o chunk com metadados e o score numérico de similaridade entre $0.0$ e $1.0$ (convertido de distance: `score = 1 - distance`).

---

## 4. Comportamento e Casos de Erro (Edge Cases)

- 🟢 **Cenário de Index Vetorial Vazio:** Se uma busca for executada antes de qualquer documento ser indexado, o componente deve retornar uma lista vazia `[]` imediatamente sem erro.
- 🟢 **Cenário de Falha na API de Embeddings:** Em caso de timeout ou erro na API externa de embeddings, **apenas o provedor OpenAI** realiza retry exponencial (tenacity, 3 tentativas, jitter 1-10s); Ollama e HuggingFace não têm retry nativo e propagam erro.
- 🟢 **Cenário de Consulta com $k$ Maior que Total de Chunks:** Se $k=10$ mas existirem apenas 3 chunks indexados, o componente deve retornar todos os 3 chunks existentes ordenados sem erro de index out of bounds.
- 🟢 **Consistência de Dimensões:** Validação cross-config no startup garante `embedding.dimensions == vector_store.embedding_dimensions` (falha rápida via `ConfigurationException` se divergente).

---

## 5. Critérios de Aceite

- 🟢 **Dado** um conjunto de 5 chunks indexados e uma consulta do usuário, **Quando** a busca por similaridade for executada com `top_k=5`, **Então** o componente deve retornar exatamente 5 trechos ordenados em ordem decrescente pelo score de similaridade de cosseno.
- 🟢 **Dado** um chunk que contém exatamente a mesma frase da consulta, **Quando** a similaridade for calculada, **Então** o score retornado deve ser superior a $0.90$.
- 🟢 **Dado** config.yaml com `embedding.dimensions=768` e `vector_store.embedding_dimensions=1536`, **Quando** `AppConfig.from_yaml()` for chamado, **Então** `ConfigurationException` é levantada com mensagem clara apontando a inconsistência.

---

## 6. Open Questions / Questões Abertas

- 🟢 **RESOLVIDO:** O Vector Store do MVP é **SQLite + sqlite-vec virtual table** com persistência ACID, query_log, cascade delete. Não é in-memory. Detalhes de implementação documentados em ADR-001.

---

## Avaliação de Qualidade (SDD Scorer)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE TOTAL: 95/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakdown:
  Completude:    95/100 (peso 30%)
  Testabilidade: 95/100 (peso 25%)
  Clareza:       95/100 (peso 20%)
  Escopo:        95/100 (peso 15%)
  Edge Cases:    95/100 (peso 10%)

Gaps críticos: Nenhum.
Sugestões: Documentar comparativo de performance entre sqlite-vec e FAISS/Qdrant para escalas >100k chunks.
```
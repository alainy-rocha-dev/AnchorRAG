# SDD Spec: Vector Store & Similarity Search (`vector-store-similarity-search`)

> Selo 🟡 PLANEJADO. Especificação técnica executável no padrão SDD/RFC.

**Componente:** `vector-store-similarity-search`  
**Versão:** 1.0  
**Data:** 2026-09-22T14:27:10-03:00  
**Autor:** reversa-spec-sdd  
**Status:** 🟡 PLANEJADO  

---

## 1. Problema e Objetivos

🟡 **Problema:** A busca textual tradicional por palavra-chave falha em identificar equivalências semânticas e variações conceituais em documentos técnicos.  
🟡 **Objetivo:** Converter chunks de texto em vetores numéricos de embedding, armazená-los junto com seus metadados e realizar busca eficiente por similaridade de cosseno para retornar os top-k trechos mais relevantes para qualquer consulta.

---

## 2. Escopo do Componente

### 2.1 O que FAZ (In-Scope)
- 🟡 Interface para geração de embeddings via modelo vetorial (ex.: OpenAI `text-embedding-3-small` ou modelo local de 1536/768 dimensões).
- 🟡 Armazenamento in-memory ou persistente de vetores associados ao `chunk_id` e metadados (`source_file`, `page_number`, `text_content`).
- 🟡 Execução da função matemática de similaridade de cosseno:
  $$\text{similarity}(A, B) = \frac{A \cdot B}{\|A\| \|B\|}$$
- 🟡 Ordenação e filtragem dos resultados retornando os $k$ trechos com maior score de similaridade (Top-K).

### 2.2 O que NÃO faz (Non-Goals / Out-of-Scope)
- 🟡 Geração de resposta final em linguagem natural (responsabilidade do componente RAG Synthesis).
- 🟡 Re-ranking complexo com modelo Cross-Encoder no MVP.
- 🟡 Gerenciamento de índices vetoriais distribuídos em cluster enterprise (ex.: Milvus/Qdrant clusterizado) no MVP.

---

## 3. Requisitos Funcionais (RFs)

- 🟡 **RF-01 (Geração de Embedding):** O componente deve receber uma string de texto e retornar seu vetor denso de números em ponto flutuante com a dimensão correspondente ao modelo utilizado.
- 🟡 **RF-02 (Indexação de Chunks):** O componente deve aceitar uma lista de objetos `Chunk` com texto e metadados, gerando e salvando seus vetores no repositório de vetores (Vector Store).
- 🟡 **RF-03 (Busca por Similaridade de Cosseno):** Dada uma query em texto plano, o componente deve gerar o embedding da query e calcular a similaridade de cosseno contra todos os vetores indexados.
- 🟡 **RF-04 (Retorno de Top-K e Scores):** A busca por similaridade deve retornar exatamente $k$ resultados (onde $k$ é um parâmetro inteiro positivo com valor padrão 3) contendo o texto do chunk, seus metadados e o score numérico de similaridade entre $0.0$ e $1.0$.

---

## 4. Comportamento e Casos de Erro (Edge Cases)

- 🟡 **Cenário de Index Vetorial Vazio:** Se uma busca for executada antes de qualquer documento ser indexado, o componente deve retornar uma lista vazia `[]` imediatamente sem erro.
- 🟡 **Cenário de Falha na API de Embeddings:** Em caso de timeout ou erro na API externa de embeddings, o componente deve realizar até 3 tentativas com backoff exponencial antes de lançar `EmbeddingGenerationException`.
- 🟡 **Cenário de Consulta com $k$ Maior que Total de Chunks:** Se $k=10$ mas existirem apenas 3 chunks indexados, o componente deve retornar todos os 3 chunks existentes ordenados sem erro de index out of bounds.

---

## 5. Critérios de Aceite

- 🟡 **Dado** um conjunto de 5 chunks indexados e uma consulta do usuário, **Quando** a busca por similaridade for executada com `top_k=3`, **Então** o componente deve retornar exatamente 3 trechos ordenados em ordem decrescente pelo score de similaridade de cosseno.
- 🟡 **Dado** um chunk que contém exatamente a mesma frase da consulta, **Quando** a similaridade for calculada, **Então** o score retornado deve ser superior a $0.90$.

---

## 6. Open Questions / Questões Abertas

- 🟡 `⚠️ ABERTO:` O Vector Store do MVP será armazenado puramente em memória (ex.: usando numpy/FAISS local) ou em banco de dados SQLite/Chroma local? *Premissa 🟡 adotada no MVP: armazenamento vetorial in-memory/SQLite local para simplicidade e ausência de dependências de infraestrutura externa.*

---

## Avaliação de Qualidade (SDD Scorer)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE TOTAL: 94/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakdown:
  Completude:    95/100 (peso 30%)
  Testabilidade: 95/100 (peso 25%)
  Clareza:       95/100 (peso 20%)
  Escopo:        90/100 (peso 15%)
  Edge Cases:    90/100 (peso 10%)

Gaps críticos: Nenhum.
Sugestões: Documentar comparativo de performance entre FAISS e busca vetorial ingênua em Numpy.
```

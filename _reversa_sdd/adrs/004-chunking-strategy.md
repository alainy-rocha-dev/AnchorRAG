# ADR 004: Chunking por Tokens com Sliding Window + Overlap

**Data**: 2026-09-22
**Status**: Aceito
**Contexto**: Documentos PDF ingeridos precisam ser divididos em chunks para embedding e retrieval. A estratégia afeta recall, precisão, custo de embedding e qualidade da síntese.

## Decisão

**Chunking por tokens (tiktoken `cl100k_base`)** com **sliding window** e **overlap configurável**, default: `chunk_size=512`, `chunk_overlap=50`, unidade `tokens`. Suporte opcional a chunking por caracteres.

## Algoritmo (chunk_by_tokens)

```python
def chunk_by_tokens(text, chunk_size, chunk_overlap, model="cl100k_base"):
    encoding = tiktoken.get_encoding(model)
    tokens = encoding.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunks.append(encoding.decode(tokens[start:end]))
        if end == len(tokens): break
        start = end - chunk_overlap
        if start < 0: start = 0
    return chunks
```

### Propriedades
- **Overlap exato**: Últimos `chunk_overlap` tokens do chunk N = primeiros do chunk N+1
- **Sem perda**: Todos tokens cobertos (exceto possível truncamento final < overlap)
- **Determinístico**: Mesmo texto + mesmos params = mesmos chunks
- **O(n) tokens**: Single pass, sem backtracking

## Alternativas Consideradas

| Opção | Prós | Contras |
|-------|------|---------|
| **Tokens + sliding window + overlap** (escolhido) | Alinha com context window do LLM, overlap preserva contexto de fronteira, tiktoken padrão OpenAI | Requer tiktoken, tokens ≠ palavras (pt-BR ~1.3 tokens/palavra) |
| **Caracteres + sliding window** | Simples, sem dependência, previsível | Não alinha com token limits do LLM, corte no meio de palavras |
| **Sentença/parágrafo (semântico)** | Fronteiras naturais, melhor coerência | Tamanho variável, pode exceder context window, complexo |
| **RecursiveCharacterTextSplitter (LangChain)** | Hierárquico (parágrafo → frase → char), robusto | Dependência extra, mais lento, caixa-preta |
| **Fixed-size sem overlap** | Simples, máximo throughput | Contexto de fronteira perdido, pior recall em bordas |

## Parâmetros Default

| Parâmetro | Valor | Racional |
|-----------|-------|----------|
| `chunk_size` | 512 tokens | Cabe ~4 chunks no context window de 2k (deixando espaço para prompt + resposta) |
| `chunk_overlap` | 50 tokens | ~10% do chunk; preserva continuidade sem duplicação excessiva |
| `chunk_unit` | `tokens` | Alinha com embedding/llm token limits |
| `min_chunk_size` | 50 | Evita chunks micro (ruído) |

## Validações

```python
# Chunker.__init__
if chunk_overlap >= chunk_size: raise ValueError("overlap < size")
if chunk_size <= 0: raise ValueError("size > 0")

# ChunkingConfig (Pydantic)
@field_validator("chunk_overlap")
def validate_overlap(cls, v, info):
    if v >= info.data.get("chunk_size", 512):
        raise ValueError("chunk_overlap deve ser menor que chunk_size")
```

## Consequências

### Positivas
- **Previsibilidade de custo**: `n_chunks ≈ total_tokens / (chunk_size - overlap)` → embedding cost estimável
- **Compatibilidade LLM**: Chunks cabem no context window com folga para prompt + resposta
- **Recall em bordas**: Overlap garante que conceitos divididos entre chunks apareçam em ambos
- **Configurável**: `QueryConfig.top_k` e `SynthesizerConfig.max_chunks` controlam quantos chunks vão ao LLM

### Negativas
- **Duplicação**: Overlap = ~10% tokens duplicados → 10% mais embeddings + storage
- **Corte semântico**: Pode separar entidade/relacao no meio (mitigado por overlap)
- **Estimativa de página heurística**: `_estimate_page_number` usa offset no texto concatenado; falha se chunk cruza página
- **Português**: `cl100k_base` otimizado para inglês; pt-BR ~30% mais tokens/palavra

## Mitigações

- `chunk_unit = "chars"` opcional para casos onde tokens não alinham
- `min_chunk_size=50` filtra ruído
- `page_number` estimado + metadados `start_char`/`end_char` permitem reconstrução
- `sanitize_text` normaliza antes do chunking (NFKC, hyphen fix, control chars)

---

## Consequências Detalhadas (doc_level=detalhado)

### Impacto no Pipeline

```
PDF (páginas) → parser → full_text (concat "\n\n")
    → sanitize_text()
    → chunk_by_tokens(size=512, overlap=50)
    → Chunk objects (index, page_estimado, start_char, end_char, token_count)
    → embed_batch([chunk.content for chunk in chunks])
    → vector_store.add_chunks(chunks_com_embedding)
```

### Cálculo de Custos (Exemplo)

| Documento | Páginas | Tokens tot | Chunks (512/50) | Embeddings | Custo OpenAI (3-small @ $0.02/1M) |
|-----------|---------|------------|-----------------|------------|-----------------------------------|
| 10 págs   | ~3k     | ~6         | 6               | $0.00012   |
| 100 págs  | ~30k    | ~65        | 65              | $0.0013    |
| 1000 págs | ~300k   | ~650       | 650             | $0.013     |

### Relação com Retrieval

- `top_k=5` default → até 5 chunks no context do LLM
- `threshold=0.7` default → filtra chunks irrelevantes (cosine distance ≤ 0.3)
- `max_chunks=5` no sintetizador → mesmo teto
- Overlap ajuda: se conceito está na fronteira chunk 2/3, ambos recuperados → melhor síntese

### Evolução Futura
- Chunking semântico (sentence-boundary aware) como opção
- `chunk_size` adaptativo por tipo de documento (tabelas vs texto)
- Metadata enriquecida: section heading, table/figure flags
- Hybrid chunking: small chunks para retrieval + parent chunks para síntese (parent document retrieval)
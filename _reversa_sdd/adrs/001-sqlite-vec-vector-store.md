# ADR 001: SQLite + sqlite-vec como Vector Store Padrão

**Data**: 2026-09-22
**Status**: Aceito
**Contexto**: O sistema precisa de armazenamento vetorial para embeddings com busca por similaridade de cosseno.

## Decisão

Usar **SQLite com extensão sqlite-vec** como vector store padrão e único suportado inicialmente.

## Alternativas Consideradas

| Opção | Prós | Contras |
|-------|------|---------|
| **SQLite + sqlite-vec** (escolhido) | Zero dependências externas, ACID, SQL nativo, virtual table `vec0` para busca vetorial, embeddings como BLOB float32, query log na mesma DB | Dimensions fixas no schema (requer migração se mudar modelo), escala limitada a single-node |
| **ChromaDB** | Purpose-built, multi-tenant, filtros metadata, Python client simples | Dependência extra (servidor ou embedded), mais complexo para deploy simples |
| **Qdrant** | High performance, filtros avançados, clustering | Serviço separado, mais recursos, overkill para projeto HAG 2 |
| **FAISS + pickle** | Muito rápido, pure Python | Sem persistência ACID, sem query log integrado, manual sync |
| **pgvector (PostgreSQL)** | SQL completo, ACID, escala | Requer PostgreSQL server, mais infra |

## Consequências

### Positivas
- **Simplicidade operacional**: Single file (`hag_rag.db`), zero config de servidor
- **Consistência**: Transações ACID entre documents, chunks, embeddings, query_log
- **Portabilidade**: Arquivo único copiável, backup trivial
- **Observabilidade nativa**: `query_log` na mesma DB com JOINs possíveis
- **Custo zero**: Sem infra adicional

### Negativas
- **Dimensions imutáveis**: Virtual table `vec0(embedding float[D])` criada com `D` fixo; mudar modelo de embedding = `DROP TABLE` + reingestão
- **Escala vertical apenas**: SQLite não escala horizontalmente; adequado para <100k chunks
- **Concorrência limitada**: WAL mode ajuda, mas não é multi-writer verdadeiro
- **Dependência nativa**: `sqlite-vec` requer compilação/extensão carregável (`enable_load_extension`)

## Mitigações

- `VectorStoreConfig.embedding_dimensions` documentado como crítico
- Factory `auto_create_vector_store()` valida disponibilidade de `sqlite-vec` no import
- Migração futura: adicionar novo tipo de store no registry (`register_store`) sem quebrar código existente

---

## Consequências Detalhadas (doc_level=detalhado)

### Impacto no Pipeline de Ingestão
- `IngestionPipeline` chama `vector_store.init_db()` que cria schema completo
- `add_chunks` insere em 3 tabelas atômicas (documents, chunks, chunks_vec)
- `content_hash` UNIQUE garante idempotência por arquivo

### Impacto na Query
- `search()` usa `vec_distance_cosine()` nativo — sem overhead Python
- Score = `1 - distance` (assume vetores normalizados)
- Threshold aplicado no SQL: `WHERE distance <= 1.0 - threshold`

### Evolução Futura
- Adicionar `VectorStoreConfig.type` com mais opções quando necessário
- Implementar migração de dimensions via script de re-embedding
- Considerar `sqlite-vec` 0.1.6+ para quantização (int8) e economia de espaço
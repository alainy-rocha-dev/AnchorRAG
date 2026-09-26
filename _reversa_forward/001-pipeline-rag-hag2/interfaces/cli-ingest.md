# Interface: CLI `ingest`

> Feature: `001-pipeline-rag-hag2`
> Comando: `hag-rag ingest`
> Data: `2026-09-22`

## 1. Descrição

Comando para ingestão e indexação de documentos PDF no vector store. Processa arquivos individualmente ou em batch (diretório), extrai texto, faz chunking, gera embeddings e persiste no SQLite.

## 2. Assinatura (Typer)

```python
@app.command()
def ingest(
    path: Annotated[Path, typer.Argument(help="Caminho para arquivo PDF ou diretório com PDFs")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Força reindexação ignorando hash")] = False,
    chunk_size: Annotated[int, typer.Option("--chunk-size", help="Tamanho do chunk")] = 1000,
    chunk_overlap: Annotated[int, typer.Option("--chunk-overlap", help="Overlap entre chunks")] = 200,
    chunk_unit: Annotated[str, typer.Option("--chunk-unit", help="Unidade: chars | tokens")] = "chars",
    embedding_model: Annotated[str, typer.Option("--embedding-model", "-e", help="Override do modelo de embedding")] = None,
    parser: Annotated[str, typer.Option("--parser", help="Parser PDF: pdfplumber | pypdf")] = "pdfplumber",
    recursive: Annotated[bool, typer.Option("--recursive", "-r", help="Busca recursiva em subdiretórios")] = True,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Log detalhado")] = False,
):
```

## 3. Entrada (Input)

| Parâmetro | Tipo | Obrigatório | Default | Descrição |
|-----------|------|-------------|---------|-----------|
| `path` | `Path` | Sim | — | Arquivo `.pdf` ou diretório |
| `force` | `bool` | Não | `false` | Reprocessa mesmo se hash já existe no DB |
| `chunk_size` | `int` | Não | `1000` | Tamanho do chunk (chars ou tokens) |
| `chunk_overlap` | `int` | Não | `200` | Overlap entre chunks consecutivos |
| `chunk_unit` | `str` | Não | `"chars"` | `"chars"` ou `"tokens"` |
| `embedding_model` | `str` | Não | `config.yaml` | Override do modelo (ex.: `nomic-embed-text`) |
| `parser` | `str` | Não | `"pdfplumber"` | `"pdfplumber"` ou `"pypdf"` |
| `recursive` | `bool` | Não | `true` | Se diretório, busca em subpastas |
| `verbose` | `bool` | Não | `false` | Log nível DEBUG |

## 4. Saída (Output)

### Sucesso (exit code 0)

```
📄 Processando: manual_tecnico.pdf (15 páginas)
✂️  Chunking: 47 chunks gerados (chars, size=1000, overlap=200)
🔮 Gerando embeddings... [47/47]
💾 Salvando no vector store...
✅ Concluído em 12.3s — 47 chunks indexados
```

**Resumo JSON (se `--format json`):**

```json
{
  "status": "success",
  "files_processed": 1,
  "total_pages": 15,
  "total_chunks": 47,
  "embedding_model": "nomic-embed-text",
  "embedding_dim": 768,
  "duration_seconds": 12.3,
  "chunks_per_second": 3.8
}
```

### Erros (exit code > 0)

| Código | Cenário | Mensagem |
|--------|---------|----------|
| 1 | Caminho não existe | `Error: Path not found: ./docs/inexistente.pdf` |
| 2 | Nenhum PDF encontrado | `Error: No PDF files found in ./docs` |
| 3 | PDF corrompido (não-fatal em batch) | `WARN: manual.pdf corrupted, skipping` (continua) |
| 4 | Falha embedding API | `Error: Embedding generation failed after 3 retries` |
| 5 | DB locked / permissão | `Error: Cannot write to vector store` |

## 5. Comportamento

1. **Descoberta:** Lista arquivos `.pdf` no path (recursivo se diretório)
2. **Deduplicação:** Calcula SHA256 de cada arquivo; se hash existe no DB e `--force` não setado, pula
3. **Parsing:** Extrai texto página a página via parser configurado
4. **Sanitização:** Remove chars controle, resolve hifenização fim-de-linha
5. **Chunking:** Divide em chunks com `chunk_size`/`chunk_overlap` na `chunk_unit`
6. **Metadados:** Gera `chunk_id` (UUIDv4), `page_number`, `char_count`, offsets
7. **Embeddings:** Chama `EmbeddingProvider.embed_batch()` com retry/backoff
8. **Persistência:** Transação única: insere `Document` + `Chunks` + atualiza `vec` index
9. **Log:** Emite resumo final com contadores e timing

## 6. Idempotência

- **Sim, por hash de arquivo:** Mesmo arquivo (mesmo conteúdo) não é reindexado sem `--force`
- **Não idempotente se:** Arquivo modificado (hash muda) → novo `Document` + novos `Chunks` (antigos ficam órfãos; limpeza futura)

## 7. Timeouts e limites

- **Parsing PDF:** 30s por arquivo (configurável futuro)
- **Embedding batch:** 60s por batch de 100 chunks (retry 3x com backoff 1s, 2s, 4s)
- **DB write:** 10s (transação SQLite)
- **Total por arquivo:** Sem limite hard; grandes PDFs processados em streaming

## 8. Exemplos de uso

```bash
# Básico
hag-rag ingest ./docs

# Um arquivo específico
hag-rag ingest ./docs/manual.pdf

# Reindexar tudo (ignora cache)
hag-rag ingest ./docs --force

# Chunking em tokens para alinhar com contexto do modelo
hag-rag ingest ./docs --chunk-unit tokens --chunk-size 512 --chunk-overlap 50

# Parser alternativo (mais rápido para texto simples)
hag-rag ingest ./docs --parser pypdf

# Verboso para debug
hag-rag ingest ./docs -v
```
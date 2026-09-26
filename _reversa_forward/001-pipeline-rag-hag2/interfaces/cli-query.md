# Interface: CLI `query`

> Feature: `001-pipeline-rag-hag2`
> Comando: `hag-rag query`
> Data: `2026-09-22`

## 1. Descrição

Comando para executar uma consulta no pipeline RAG: gera embedding da query, busca top-k chunks por similaridade de cosseno, sintetiza resposta com LLM ancorada nos trechos, retorna citações inline + rodapé com scores e latência total.

## 2. Assinatura (Typer)

```python
@app.command()
def query(
    question: Annotated[str, typer.Argument(help="Pergunta em linguagem natural")],
    top_k: Annotated[int, typer.Option("--top-k", "-k", help="Número de chunks a recuperar")] = 3,
    threshold: Annotated[float, typer.Option("--threshold", "-t", help="Score mínimo de similaridade (0.0-1.0)")] = 0.40,
    llm_model: Annotated[str, typer.Option("--llm-model", "-m", help="Override do modelo LLM")] = None,
    llm_temperature: Annotated[float, typer.Option("--temperature", help="Temperatura LLM")] = 0.0,
    llm_max_tokens: Annotated[int, typer.Option("--max-tokens", help="Max tokens resposta")] = 1024,
    format: Annotated[str, typer.Option("--format", "-f", help="Formato saída: text | json")] = "text",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Log detalhado")] = False,
    no_synthesis: Annotated[bool, typer.Option("--no-synthesis", help="Apenas busca, sem síntese LLM")] = False,
):
```

## 3. Entrada (Input)

| Parâmetro | Tipo | Obrigatório | Default | Descrição |
|-----------|------|-------------|---------|-----------|
| `question` | `str` | Sim | — | Pergunta do usuário |
| `top_k` | `int` | Não | `3` | Quantidade de chunks a recuperar (1-20) |
| `threshold` | `float` | Não | `0.40` | Score mínimo; chunks abaixo são descartados |
| `llm_model` | `str` | Não | `config.yaml` | Override modelo (ex.: `gpt-4o-mini`, `llama3.1:8b`) |
| `llm_temperature` | `float` | Não | `0.0` | 0.0 = determinístico; até 1.0 |
| `llm_max_tokens` | `int` | Não | `1024` | Limite tokens na resposta |
| `format` | `str` | Não | `"text"` | `"text"` (human-readable) ou `"json"` |
| `verbose` | `bool` | Não | `false` | Log DEBUG com scores, chunks brutos, prompt |
| `no_synthesis` | `bool` | Não | `false` | Pula LLM; retorna apenas chunks + scores |

## 4. Saída (Output)

### Sucesso — Formato `text` (default, exit code 0)

```
🔍 Buscando top-3...
📊 Scores: [0.87, 0.72, 0.65]
🤖 Sintetizando com gpt-4o-mini...

💬 Resposta:
O parâmetro de timeout é configurado na seção [network] do arquivo config.yaml
com o nome 'timeout_seconds' [1]. O valor padrão é 30 segundos [2].

📚 Fontes:
[1] manual_tecnico.pdf - Pág. 12 - score: 0.87
[2] manual_tecnico.pdf - Pág. 13 - score: 0.72

⏱️ Latência total: 1.23s (embed: 0.12s, search: 0.03s, llm: 1.08s)
```

### Sucesso — Formato `json` (exit code 0)

```json
{
  "status": "success",
  "question": "Como configurar o parâmetro de timeout?",
  "retrieved_chunks": [
    {
      "chunk_id": "a1b2c3d4-...",
      "text": "O parâmetro timeout_seconds na seção [network]...",
      "source_file": "manual_tecnico.pdf",
      "page_start": 12,
      "page_end": 12,
      "score": 0.8732
    },
    {
      "chunk_id": "e5f6g7h8-...",
      "text": "Valor padrão: 30 segundos para timeout_seconds...",
      "source_file": "manual_tecnico.pdf",
      "page_start": 13,
      "page_end": 13,
      "score": 0.7211
    }
  ],
  "synthesis": "O parâmetro de timeout é configurado na seção [network] do arquivo config.yaml com o nome 'timeout_seconds' [1]. O valor padrão é 30 segundos [2].",
  "citations": [
    {"index": 1, "chunk_id": "a1b2c3d4-...", "source_file": "manual_tecnico.pdf", "page": 12, "score": 0.8732},
    {"index": 2, "chunk_id": "e5f6g7h8-...", "source_file": "manual_tecnico.pdf", "page": 13, "score": 0.7211}
  ],
  "latency_ms": 1230,
  "latency_breakdown_ms": {
    "embedding": 120,
    "search": 30,
    "synthesis": 1080
  },
  "models": {
    "embedding": "nomic-embed-text",
    "llm": "gpt-4o-mini"
  },
  "config_used": {
    "top_k": 3,
    "threshold": 0.40,
    "temperature": 0.0
  }
}
```

### Caso: Informação ausente (score < threshold ou zero chunks)

**Text:**
```
🔍 Buscando top-3...
📊 Scores: []  (nenhum chunk acima do threshold 0.40)

⚠️ Não encontrei informações suficientes no acervo para responder à sua consulta.

⏱️ Latência total: 0.45s
```

**JSON:**
```json
{
  "status": "no_results",
  "question": "Qual o artigo 5 do regulamento Y?",
  "retrieved_chunks": [],
  "synthesis": "Não encontrei informações suficientes no acervo para responder à sua consulta.",
  "citations": [],
  "latency_ms": 450,
  "latency_breakdown_ms": {"embedding": 110, "search": 25, "synthesis": 0}
}
```

### Erros (exit code > 0)

| Código | Cenário | Mensagem |
|--------|---------|----------|
| 1 | Vector store vazio | `Error: No documents indexed. Run 'hag-rag ingest' first.` |
| 2 | Embedding falhou | `Error: Failed to generate query embedding after 3 retries` |
| 3 | LLM timeout | `Error: LLM request timed out after 5.0s` |
| 4 | LLM API error | `Error: LLM provider error: rate_limit_exceeded` |
| 5 | Threshold inválido | `Error: threshold must be between 0.0 and 1.0` |

## 5. Comportamento

1. **Validação:** Verifica se vector store tem chunks indexados
2. **Embedding da query:** `EmbeddingProvider.embed(question)` com retry 3x
3. **Busca vetorial:** `VectorStore.search(query_vec, top_k)` → calcula cosseno vs todos vetores
4. **Filtro threshold:** Descarta chunks com score < `threshold`
5. **Se vazio:** Retorna mensagem padrão "Não encontrei informações..." sem chamar LLM
6. **Síntese (se chunks):**
   - Constrói prompt com system instruction de ancoragem estrita
   - Injeta chunks numerados com metadados (arquivo, página)
   - Chama `LLMProvider.complete(prompt, temperature, max_tokens, timeout)`
   - Parseia resposta extraindo citações `[N]` e mapeando para chunks
7. **Formatação:** Gera output `text` (human) ou `json` (machine)
8. **Log opcional:** `QueryLog` salvo no DB se habilitado

## 6. Prompt de ancoragem (system)

```
Você é um assistente técnico especializado em responder perguntas baseando-se
EXCLUSIVAMENTE nos trechos de documentos fornecidos abaixo.

REGRAS OBRIGATÓRIAS:
1. Responda APENAS com base nos trechos fornecidos.
2. Se a resposta não estiver nos trechos, diga expressamente:
   "Não encontrei informações suficientes no acervo para responder à sua consulta."
3. Cite a fonte de cada afirmação usando o formato [N], onde N é o número do trecho.
4. Não use conhecimento externo, não infira, não complete lacunas.
5. Seja conciso e técnico.

TRECHOS DISPONÍVEIS:
[1] Arquivo: manual_tecnico.pdf | Página: 12 | Score: 0.87
    Conteúdo: O parâmetro timeout_seconds na seção [network]...

[2] Arquivo: manual_tecnico.pdf | Página: 13 | Score: 0.72
    Conteúdo: Valor padrão: 30 segundos para timeout_seconds...
```

## 7. Idempotência

- **Sim:** Mesma query + mesmo estado do vector store → mesma resposta (exceto temperatura > 0)
- **Não determinístico se:** `temperature > 0` ou modelo LLM não determinístico

## 8. Timeouts e limites

| Etapa | Timeout default | Configurável |
|-------|-----------------|--------------|
| Embedding query | 10s (retry 3x) | Via `EmbeddingProvider` |
| Busca vetorial | 5s (in-memory) | — |
| LLM síntese | 5.0s | `--llm-timeout` / config |
| **Total alvo** | **< 2.0s** | Métrica de sucesso |

## 9. Exemplos de uso

```bash
# Básico
hag-rag query "Como configurar o timeout?"

# Mais resultados
hag-rag query "Como configurar..." --top-k 5

# Threshold mais restritivo
hag-rag query "..." --threshold 0.60

# Modelo local via Ollama
hag-rag query "..." --llm-model llama3.1:8b

# Apenas busca (sem LLM) — útil para debug/avaliação
hag-rag query "..." --no-synthesis

# JSON para integração
hag-rag query "..." --format json

# Verboso (mostra chunks brutos, prompt, timings)
hag-rag query "..." -v
```
# Benchmark de Embeddings - AnchorRAG

**Data:** 2026-09-29 18:36:20

**Hardware:** CPU: AMD64 Family 26 Model 68 Stepping 0, AuthenticAMD, RAM: 31.2GB, GPU: N/A

**Chunks testados:** 1000 | **Runs por modelo:** 3 | **Batch size:** 100

---

## Resultados

| Provedor | Modelo | Latência (ms/1k chunks) | Tokens/chunk | Custo (USD/1M tokens) | Notas |
|----------|--------|--------------------------|--------------|------------------------|-------|
| openai | text-embedding-3-small | N/A (indisponível) | 0 | $0.02 | Indisponível: The api_key client option must be set either by passing api_key to the client or by setting the OPENAI_API_KEY environment variable |
| openai | text-embedding-3-large | N/A (indisponível) | 0 | $0.13 | Indisponível: The api_key client option must be set either by passing api_key to the client or by setting the OPENAI_API_KEY environment variable |
| ollama | nomic-embed-text | N/A (indisponível) | 0 | Local (gratuito) | Indisponível: All connection attempts failed |
| ollama | mxbai-embed-large | N/A (indisponível) | 0 | Local (gratuito) | Indisponível: All connection attempts failed |
| huggingface | BAAI/bge-m3 | N/A (indisponível) | 0 | Local (gratuito) | Indisponível: sentence-transformers não instalado. Instale com: pip install sentence-transformers |
| huggingface | sentence-transformers/all-MiniLM-L6-v2 | N/A (indisponível) | 0 | Local (gratuito) | Indisponível: sentence-transformers não instalado. Instale com: pip install sentence-transformers |

---

## Metodologia

- **Chunks de teste:** Textos sintéticos de ~512 tokens cada (cl100k_base encoding)
- **Medição:** Tempo total para `embed_batch()` de todos os chunks, convertido para ms/1k chunks
- **Runs:** Múltiplas execuções para calcular média e desvio padrão
- **Custos:** Baseados em pricing público das APIs (OpenAI) ou estimados como zero para local
- **Hardware:** Reportado para reprodutibilidade

## Interpretação

- **Latência menor** = melhor para aplicações em tempo real
- **Custo menor** = melhor para alto volume
- **Provedores locais (Ollama, HF)** têm latência variável dependendo do hardware
- **OpenAI** tem latência consistente mas custo por token


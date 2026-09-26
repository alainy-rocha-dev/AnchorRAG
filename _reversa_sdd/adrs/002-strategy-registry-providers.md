# ADR 002: Strategy Pattern + Registry para Provedores (Embedding, LLM, Parser, VectorStore)

**Data**: 2026-09-22
**Status**: Aceito
**Contexto**: O sistema precisa suportar múltiplos provedores de embedding (OpenAI, Ollama, HuggingFace), LLM (OpenAI, Ollama, Anthropic), parsers PDF (pdfplumber, PyPDF) e vector stores (sqlite-vec), com possibilidade de extensão futura.

## Decisão

Implementar **Strategy Pattern** com **Registry centralizado** e **Factory** para cada família de provedores:
- Interface base (ABC) define contrato
- Implementações concretas por provedor
- Registry `_PROVIDERS: Dict[str, Type[Provider]]` no `__init__.py` do pacote
- Função `create_X_provider(config)` faz lookup + instanciação
- `register_provider(name, class)` permite extensão dinâmica

## Alternativas Consideradas

| Opção | Prós | Contras |
|-------|------|---------|
| **Strategy + Registry + Factory** (escolhido) | Baixo acoplamento, Open/Closed Principle, testável (mock ABC), config-driven, extensível sem tocar código core | Mais arquivos, indirection extra |
| **If/elif na factory** | Simples, direto | Viola OCP, difícil testar, adicionar provedor = modificar factory |
| **Plugin system (entry_points)** | Descoberta automática, ecossistema | Complexidade excessiva para 3-4 provedores |
| **Config-driven class loading** (`importlib.import_module`) | Zero registry code | Frágil (typos em string), sem validação de interface |

## Consequências

### Positivas
- **Inversão de dependência**: `RAGPipeline` depende de `EmbeddingProvider` (ABC), não de `OpenAIEmbeddingProvider`
- **Troca em runtime**: `AppConfig.embedding.provider = "ollama"` muda comportamento sem rebuild
- **Testabilidade**: `MockEmbeddingProvider(EmbeddingProvider)` em testes unitários
- **Extensibilidade**: `register_provider("custom", CustomProvider)` em user code
- **Validação centralizada**: Factory lança `ValueError` com lista de disponíveis se provider desconhecido

### Negativas
- **Boilerplate**: 4 famílias × (ABC + 3 impls + registry + factory) = ~20 arquivos
- **Config duplication**: `EmbeddingConfig` (domain) + `EmbeddingConfig` (embeddings/base.py) — duas classes similares
- **Indireção**: Debug stack trace mais longo

## Mitigações

- Manter hierarquia clara: `domain/models.py` = configs de runtime; `embeddings/base.py` = config de provider
- Documentar pattern no README/CONTRIBUTING
- Linter rule para garantir novas impls herdam ABC correto

---

## Consequências Detalhadas (doc_level=detalhado)

### Embedding Providers
```python
# embeddings/__init__.py
_PROVIDERS = {"openai": OpenAIEmbeddingProvider, "ollama": OllamaEmbeddingProvider, "huggingface": HuggingFaceEmbeddingProvider}

def create_embedding_provider(config: EmbeddingConfig) -> EmbeddingProvider:
    provider_class = _PROVIDERS[config.provider.lower()]
    return provider_class(config)
```

### LLM Providers
```python
# synthesis/__init__.py
_PROVIDERS = {"openai": OpenAILLMProvider, "ollama": OllamaLLMProvider, "anthropic": AnthropicLLMProvider}
```

### Parser (simples, sem config class dedicada)
```python
# ingestion/parser.py
def create_parser(parser_type: str = "pdfplumber") -> PDFParser:
    if parser_type == "pdfplumber": return PdfPlumberParser()
    elif parser_type == "pypdf": return PyPDFParser()
    else: raise ValueError(...)
```

### Vector Store
```python
# vector_store/__init__.py
_STORES = {"sqlite_vec": SQLiteVecStore}
def create_vector_store(store_type: str = "sqlite_vec", **kwargs) -> VectorStore:
    return _STORES[store_type.lower()](**kwargs)
```

### Padrão Comum
Todas as factories:
1. Normalizam nome para lowercase
2. Validam existência no registry
3. Logam criação (`logger.info(f"Criando {tipo}: {nome}")`)
4. Instanciam passando config/kwargs
5. Lançam `ValueError` descritivo se não encontrado
# Legacy Impact: bcb-corpus-dataset-v1

> Feature ID: `004-bcb-corpus-dataset-v1`
> Data: `2026-10-10`
> Política de edição: `allowLegacyEdits: true` (`allowedPaths: ["eval/**", "src/anchor_rag/**", "tests/**", "scripts/**", "docs/**", "README.md", "_reversa_sdd/**", "_reversa_forward/**"]`)

## Arquivos Afetados

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| `eval/build_dataset.py` | Engine de Avaliação e Ingestão | `componente-novo` | LOW | Implementação da CLI completa (`ingest`, `candidates`, `review`, `validate`) sem alterar contratos existentes |

## Diff Conceitual por Componente

### Engine de Avaliação e Ingestão (`eval/build_dataset.py`)
- Adicionada suíte de utilitários e subcomandos em Python puro (`ingest`, `candidates`, `review`, `validate`) para geração e validação de datasets de avaliação RAG.

## Regras Preservadas
- **🟢 R001-R020**: Toda a arquitetura do AnchorRAG e contratos legados permanecem intactos.

## Regras Modificadas
- Nenhuma regra 🟢 do legado foi alterada ou removida.

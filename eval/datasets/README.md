# Datasets de Avaliação do AnchorRAG

Este diretório contém os conjuntos de dados de avaliação do AnchorRAG.

## `legacy/v1.antigo.jsonl`
- **Origem**: Mock sintético inicial gerado durante o desenvolvimento da Feature 003 (`scripts/create_eval_dataset.py`).
- **Estrutura**: Schema preliminar em inglês (`question`, `gold_answer`, `relevant_chunk_ids`, `category`).
- **Status**: Substituído pelo dataset oficial `v1.jsonl` (Feature 004), curado e revisado a partir do corpus real de normas regulatórias do Banco Central do Brasil (BCB/CMN). Mantido na pasta `legacy/` para rastreabilidade histórica e documentação da evolução do projeto.

## `v1.jsonl`
- **Origem**: Pipeline oficial `eval/build_dataset.py` (Feature 004) com extração de normas vigentes, geração orientada a compliance e revisão humana obrigatória.
- **Categorias**: 60 respondíveis, 20 multi-trecho, 20 sem resposta e 20 adversariais (120 itens no fechamento final).

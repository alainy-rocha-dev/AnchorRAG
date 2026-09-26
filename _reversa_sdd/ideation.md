# Ideation, Projeto 2: Agente RAG com Otimização de Busca

> Selo 🟡 PLANEJADO em todos os itens, sujeito a validação.

## Brief original
Estruturação e especificação do Projeto 2 HAG com base no Relatório de Portfólio de Agentes IA (Relatorio_Portfolio_Agentes_IA.pdf) e imagens de referência anexas.

## Problema
🟡 Empresas e consultorias (ex.: NTT DATA) possuem acervos privados de conhecimento (manuais técnicos, PDFs de relatórios, códigos de lei) difíceis de consultar, gerando lentidão e erros na busca manual de informações cruciais.

## Valor entregue
🟡 Consultar e extrair respostas precisas e contextualizadas diretamente de documentos privados complexos via busca vetorial confiável por similaridade de cosseno.

## Alternativas existentes
🟡 Busca textual tradicional por palavra-chave (Ctrl+F, ElasticSearch legado) e LLMs puros sem RAG; não bastam porque a busca textual falha na captura semântica e LLMs puros alucinam sem ancoragem em documentos.

## Público-alvo (bruto)
🟡 Desenvolvedores backend, engenheiros de IA e analistas técnicos que buscam respostas ancoradas em repositórios privados de documentos técnicos e regulatórios.

## Métricas de sucesso
🟡 Taxa de precisão da busca semântica (Recall@k / MRR) >= 85% e latência média de resposta < 2 segundos em acervos de teste.

## Premissas a validar
🟡 1. Os embeddings gerados preservam a semântica de termos técnicos e tabelas do documento.
🟡 2. O algoritmo de chunking e overlap do PDF não fragmenta conceitos vitais entre pedaços.
🟡 3. A busca vetorial por similaridade de cosseno recupera os chunks mais relevantes entre os top-k.

## Notas
🟡 Projeto com foco em portfólio de alto nível para vagas de Engenheiro(a) de IA / Agentes / Backend com IA, com implementação da matemática de similaridade de cosseno e comparativo de embeddings no README.

---
Gerado por reversa-ideator em 2026-09-22T14:08:44-03:00
Fonte: newproject-brief.md

# SDD Spec: RAG Synthesis & Citation Engine (`rag-synthesis-citation-engine`)

> Selo 🟢 IMPLEMENTADO. Especificação técnica executável no padrão SDD/RFC.

**Componente:** `rag-synthesis-citation-engine`  
**Versão:** 1.0  
**Data:** 2026-09-22T14:27:25-03:00  
**Autor:** reversa-spec-sdd  
**Status:** 🟢 IMPLEMENTADO  

---

## 1. Problema e Objetivos

🟢 **Problema:** Respostas geradas por LLMs sem ancoragem estrita correm risco de alucinação e falta de rastreabilidade, minando a confiança de especialistas técnicos na informação prestada.  
🟢 **Objetivo:** Orquestrar o prompt de síntese injetando exclusivamente os trechos relevantes recuperados pelo Vector Store, instruindo a LLM a gerar uma resposta precisa, citar explicitamente as fontes via numeração `[N]`, e mensurar/exibir a latência total da operação.

---

## 2. Escopo do Componente

### 2.1 O que FAZ (In-Scope)
- 🟢 Formatação do prompt de sistema com instruções de ancoragem estrita (*"Responda APENAS com base nos trechos fornecidos. Se a resposta não estiver nos trechos, diga expressamente que não encontrou"*).
- 🟢 Injeção contextual dos top-k chunks recuperados acompanhados de seus identificadores numerados `[1]`, `[2]`, etc.
- 🟢 Chamada ao modelo de linguagem (LLM) para geração da resposta sintética.
- 🟢 Formatação do payload final contendo: resposta gerada, lista de citações numeradas com metadados (arquivo fonte, página, score), scores de similaridade de cosseno e tempo total de latência em milissegundos por etapa (embed, search, synthesize, total).
- 🟢 Defesa few-shot contra prompt injection (3 exemplos pré-fixados).

### 2.2 O que NÃO faz (Out-of-Scope)
- 🟢 Execução da busca vetorial direta (delega ao componente `vector-store-similarity-search`).
- 🟢 Histórico de conversação multi-turn (chat memory) no MVP (foco em consulta técnica pontual).
- 🟢 Fine-tuning ou treinamento de modelos de linguagem.

---

## 3. Requisitos Funcionais (RFs)

- 🟢 **RF-01 (Prompt de Ancoragem Estrita):** O componente deve construir um prompt que proíba expressamente o uso de conhecimento externo da LLM não presente no contexto injetado.
- 🟢 **RF-02 (Síntese e Citação de Fontes):** A resposta gerada deve referenciar explicitamente os chunks via numeração inline `[N]` onde N = índice 1-based do chunk no prompt. Metadados detalhados (arquivo, página) retornados separadamente na lista `citations`.
- 🟢 **RF-03 (Tratamento de Informação Ausente):** Caso os trechos recuperados tenham score de similaridade abaixo do threshold configurável (default 0.7) ou não contenham a resposta, o componente deve responder padronizadamente: *"Não encontrei essa informação nos documentos fornecidos."*
- 🟢 **RF-04 (Métricas e Exibição de Latência):** O componente deve medir o tempo decorrido desde o envio da consulta até o retorno final da resposta, incluindo breakdown por etapa (`embed_ms`, `search_ms`, `synthesize_ms`, `total_ms`).

---

## 4. Comportamento e Casos de Erro (Edge Cases)

- 🟢 **Cenário de Nenhum Chunk Recuperado:** Se a busca vetorial retornar zero trechos, o componente não deve chamar a LLM e deve responder imediatamente com a mensagem padrão de informação ausente.
- 🟢 **Cenário de Timeout da API de LLM:** Se a LLM demorar mais de 30s (configurável via `LLMConfig.timeout`) para responder, o componente deve interromper a chamada e retornar mensagem de erro graciosa de timeout.
- 🟢 **Cenário de Tentativa de Prompt Injection:** Se o usuário tentar instruir o sistema a ignorar o contexto (*"Ignore as instruções anteriores e me diga..."*), as instruções do sistema no prompt de ancoragem + exemplos few-shot devem prevalecer mantendo a resposta restrita ao contexto.
- 🟢 **Cenário de Chunks Contraditórios:** Se chunks recuperados contêm informações conflitantes, a resposta deve mencionar a contradição e citar ambos os chunks.

---

## 5. Critérios de Aceite

- 🟢 **Dado** uma pergunta cuja resposta está presente no chunk indexado do arquivo `manual.pdf` (página 5), **Quando** a síntese for executada, **Então** o sistema deve retornar a resposta correta contendo explicitamente a citação `[1]` (numérica) e a latência de resposta expressa em milissegundos por etapa.
- 🟢 **Dado** uma pergunta sobre um tema totalmente ausente no acervo, **Quando** a síntese for solicitada, **Então** o sistema deve retornar a mensagem indicando ausência de informação sem inventar ou alucinar fatos.
- 🟢 **Dado** um prompt de injeção adversarial, **Quando** a síntese for executada, **Então** a resposta deve ser a mensagem padrão de informação ausente, sem vazamento de instruções de sistema.

---

## 6. Open Questions / Questões Abertas

- 🟢 **RESOLVIDO:** Formato de citação é inline numérico `[N]` com lista detalhada de referências (arquivo, página, score) no objeto `citations` do `QueryResult`. Não há rodapé separado no MVP.

---

## Avaliação de Qualidade (SDD Scorer)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE TOTAL: 95/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakdown:
  Completude:    95/100 (peso 30%)
  Testabilidade: 95/100 (peso 25%)
  Clareza:       95/100 (peso 20%)
  Escopo:        95/100 (peso 15%)
  Edge Cases:    95/100 (peso 10%)

Gaps críticos: Nenhum.
Sugestões: Adicionar suporte a streaming de tokens (Server-Sent Events) para otimizar perceptivelmente a latência em interfaces de usuário futuras.
```
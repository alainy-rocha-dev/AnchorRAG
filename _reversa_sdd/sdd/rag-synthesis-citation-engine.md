# SDD Spec: RAG Synthesis & Citation Engine (`rag-synthesis-citation-engine`)

> Selo 🟡 PLANEJADO. Especificação técnica executável no padrão SDD/RFC.

**Componente:** `rag-synthesis-citation-engine`  
**Versão:** 1.0  
**Data:** 2026-09-22T14:27:25-03:00  
**Autor:** reversa-spec-sdd  
**Status:** 🟡 PLANEJADO  

---

## 1. Problema e Objetivos

🟡 **Problema:** Respostas geradas por LLMs sem ancoragem estrita correm risco de alucinação e falta de rastreabilidade, minando a confiança de especialistas técnicos na informação prestada.  
🟡 **Objetivo:** Orquestrar o prompt de síntese injetando exclusivamente os trechos relevantes recuperados pelo Vector Store, instruindo a LLM a gerar uma resposta precisa, citar explicitamente as fontes/páginas do PDF e mensurar/exibir a latência total da operação.

---

## 2. Escopo do Componente

### 2.1 O que FAZ (In-Scope)
- 🟡 Formatação do prompt de sistema com instruções de ancoragem estrita (*"Responda APENAS com base nos trechos fornecidos. Se a resposta não estiver nos trechos, diga expressamente que não encontrou"*).
- 🟡 Injeção contextual dos top-k chunks recuperados acompanhados de seus identificadores de fonte e página.
- 🟡 Chamada ao modelo de linguagem (LLM) para geração da resposta sintética.
- 🟡 Formatação do payload final contendo: resposta gerada, lista de fontes citadas (`source_file`, `page_number`), scores de similaridade de cosseno e tempo total de latência em segundos.

### 2.2 O que NÃO faz (Out-of-Scope)
- 🟡 Execução da busca vetorial direta (delega ao componente `vector-store-similarity-search`).
- 🟡 Histórico de conversação multi-turn (chat memory) no MVP (foco em consulta técnica pontual).
- 🟡 Fine-tuning ou treinamento de modelos de linguagem.

---

## 3. Requisitos Funcionais (RFs)

- 🟡 **RF-01 (Prompt de Ancoragem Estrita):** O componente deve construir um prompt que proíba expressamente o uso de conhecimento externo da LLM não presente no contexto injetado.
- 🟡 **RF-02 (Síntese e Citação de Fontes):** A resposta gerada deve referenciar explicitamente o arquivo e a página de onde a informação foi extraída (ex.: `[Fonte: manual_tecnico.pdf, Pág. 14]`).
- 🟡 **RF-03 (Tratamento de Informação Ausente):** Caso os trechos recuperados tenham score de similaridade abaixo de um limiar mínimo (ex.: $< 0.40$) ou não contenham a resposta, o componente deve responder padronizadamente: *"Não encontrei informações suficientes no acervo para responder à sua consulta."*
- 🟡 **RF-04 (Métricas e Exibição de Latência):** O componente deve medir o tempo decorrido desde o envio da consulta até o retorno final da resposta, garantindo latência total $< 2.0$ segundos e incluindo o valor exato no resultado.

---

## 4. Comportamento e Casos de Erro (Edge Cases)

- 🟡 **Cenário de Nenhum Chunk Recuperado:** Se a busca vetorial retornar zero trechos, o componente não deve chamar a LLM e deve responder imediatamente com a mensagem padrão de informação ausente.
- 🟡 **Cenário de Timeout da API de LLM:** Se a LLM demorar mais de 5.0s para responder, o componente deve interromper a chamada e retornar uma mensagem de erro graciosa de timeout.
- 🟡 **Cenário de Tentativa de Prompt Injection:** Se o usuário tentar instruir o sistema a ignorar o contexto (*"Ignore as instruções anteriores e me diga..."*), as instruções do sistema no prompt de ancoragem devem prevalecer mantendo a resposta restrita ao contexto.

---

## 5. Critérios de Aceite

- 🟡 **Dado** uma pergunta cuja resposta está presente no chunk indexado do arquivo `manual.pdf` (página 5), **Quando** a síntese for executada, **Então** o sistema deve retornar a resposta correta contendo explicitamente a citação `[manual.pdf - Pág. 5]` e a latência de resposta expressa em segundos.
- 🟡 **Dado** uma pergunta sobre um tema totalmente ausente no acervo, **Quando** a síntese for solicitada, **Então** o sistema deve retornar a mensagem indicando ausência de informação sem inventar ou alucinar fatos.

---

## 6. Open Questions / Questões Abertas

- 🟡 `⚠️ ABERTO:` O formato da citação deve ser inline no texto da resposta ou agrupado ao final como seção de referências? *Premissa 🟡 adotada no MVP: Citação inline curta e lista completa de referências com score no rodapé do payload.*

---

## Avaliação de Qualidade (SDD Scorer)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE TOTAL: 93/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakdown:
  Completude:    95/100 (peso 30%)
  Testabilidade: 95/100 (peso 25%)
  Clareza:       90/100 (peso 20%)
  Escopo:        90/100 (peso 15%)
  Edge Cases:    90/100 (peso 10%)

Gaps críticos: Nenhum.
Sugestões: Adicionar suporte a streaming de tokens (Server-Sent Events) para otimizar perceptivelmente a latência em interfaces de usuário futuras.
```

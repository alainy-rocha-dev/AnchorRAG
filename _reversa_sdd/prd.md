# PRD: Projeto 2 HAG - Agente RAG com Otimização de Busca

> Selo 🟡 PLANEJADO. Documento gerado a partir de ideation + personas.

**Versão:** 1.0
**Data:** 2026-09-22T14:18:26-03:00
**Autor:** reversa-drafter
**Status:** rascunho

---

## 1. Problema

🟡 Empresas e consultorias (como a NTT DATA) e profissionais de tecnologia possuem acervos privados de conhecimento (manuais técnicos, relatórios PDF, documentos regulatórios) difíceis de consultar, gerando lentidão e erros na busca manual por informações cruciais. A busca por palavra-chave falha na captura semântica e LLMs sem RAG alucinam sem ancoragem em documentos.

### Quem sente
🟡 Engenheiros de IA, desenvolvedores backend e analistas técnicos no momento de construir ou utilizar sistemas de busca em repositórios privados de documentos técnicos e normativos.

---

## 2. Personas-alvo

🟡 Referência completa em [`personas.md`](./personas.md). Resumo:

- **Engenheiro(a) de IA / Dev Backend**: 🟡 Ineficiência da busca por palavra-chave tradicional e risco de alucinação de LLMs em documentos corporativos extensos. Busca construir e validar uma solução RAG robusta, precisa e transparente baseada em busca vetorial por similaridade de cosseno.

---

## 3. Métricas de sucesso

🟡 Taxa de precisão da busca semântica e latência média de resposta em acervos de teste.

| Métrica | Unidade | Alvo | Prazo |
|---|---|---|---|
| 🟡 Precisão da busca (Recall@k / MRR) | Porcentagem (%) | >= 85% | 🟡 MVP |
| 🟡 Latência de resposta | Segundos (s) | < 2.0s | 🟡 MVP |

---

## 4. Escopo (in)

🟡 Funcionalidades e capacidades centrais do pipeline RAG:

- 🟡 Ingestão e processamento de documentos técnicos em formato PDF.
- 🟡 Divisão do texto em trechos (chunking) com sobreposição (overlap) configurável.
- 🟡 Geração de embeddings vetoriais para os trechos de texto.
- 🟡 Armazenamento vetorial dos embeddings e metadados dos chunks.
- 🟡 Execução da busca por similaridade de cosseno para recuperar os top-k trechos mais relevantes.
- 🟡 Geração de resposta sintética ancorada nos trechos recuperados com citação das fontes originais.
- 🟡 Exibição transparente das métricas de relevância e similaridade.

---

## 5. Não-objetivos (out)

🟡 Limitações explícitas de escopo inicial:

- 🟡 Suporte multi-tenant ou controle de acesso avançado (RBAC) no MVP.
- 🟡 Interface gráfica de edição avançada de documentos em tempo real.
- 🟡 Suporte a formatos de arquivo não-estruturados complexos além de PDF/texto no MVP.

---

## 6. Restrições

🟡 Restrições operacionais e tecnológicas identificadas:

| Tipo | Descrição |
|---|---|
| 🟡 Técnica | 🟡 Implementação transparente da matemática de similaridade de cosseno e comparativo de embeddings no README. |
| 🟡 Prazo | 🟡 [INDEFINIDO, validar com usuário] |
| 🟡 Compliance | 🟡 Garantia de privacidade do repositório local/privado sem expor dados confidenciais a serviços terceiros não autorizados. |
| 🟡 Orçamento | 🟡 [INDEFINIDO, validar com usuário] |

---

## 7. Dependências externas

🟡 Serviços e bibliotecas externas necessários para o funcionamento:

- 🟡 Modelo/API de Embeddings (ex.: OpenAI Embeddings, HuggingFace ou modelo local).
- 🟡 Modelo/API de LLM para síntese de resposta ancorada (ex.: OpenAI GPT, Ollama ou equivalente).
- 🟡 Biblioteca de parsing/extração de texto de PDF (ex.: PyPDF, pdfplumber ou similar).

---

## 8. Riscos

🟡 Riscos operacionais e técnicos mapeados:

| Risco | Impacto | Probabilidade | Mitigação proposta |
|---|---|---|---|
| 🟡 Fragmentação de conceitos entre chunks no PDF | Alto | Média | 🟡 Configuração otimizada de chunk size e overlap, além de teste de estratégias de chunking. |
| 🟡 Perda semântica em termos técnicos específicos nos embeddings | Alto | Média | 🟡 Comparação e validação de diferentes modelos de embeddings. |
| 🟡 Alucinação residual da LLM na síntese final | Alto | Baixa | 🟡 Prompting com instrução estrita de ancoragem e citação obrigatória dos trechos recuperados. |

---

## 9. Critérios de aceite (alto nível)

🟡 Critérios formatados no padrão Dado/Quando/Então:

- 🟡 **Dado** um repositório de documentos PDF indexados, **Quando** o desenvolvedor submeter uma consulta técnica, **Então** o sistema deve retornar os top-k trechos relevantes via similaridade de cosseno e uma resposta ancorada em menos de 2 segundos.
- 🟡 **Dado** uma resposta gerada, **Quando** o usuário inspecionar o resultado, **Então** o sistema deve exibir as fontes/referências originais do PDF e os scores de similaridade obtidos.

---

## Pendências de cobertura

🟡 Itens que demandam validação humana suplementar:
- 🟡 Definição explícita de prazos específicos ou marcos temporais.
- 🟡 Definição de orçamento ou limites de custos de API (se aplicável).

---

Gerado por reversa-drafter em 2026-09-22T14:18:26-03:00
Fontes: ideation.md, personas.md

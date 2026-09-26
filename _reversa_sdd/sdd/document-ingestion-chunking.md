# SDD Spec: Document Ingestion & Chunking (`document-ingestion-chunking`)

> Selo 🟡 PLANEJADO. Especificação técnica executável no padrão SDD/RFC.

**Componente:** `document-ingestion-chunking`  
**Versão:** 1.0  
**Data:** 2026-09-22T14:27:00-03:00  
**Autor:** reversa-spec-sdd  
**Status:** 🟡 PLANEJADO  

---

## 1. Problema e Objetivos

🟡 **Problema:** Documentos técnicos em formato PDF contêm estruturas complexas e blocos contínuos de texto que não podem ser diretamente ingeridos por modelos de embeddings sem perda semântica ou estouro de janela de contexto.  
🟡 **Objetivo:** Processar e extrair texto limpo de arquivos PDF, subdividindo-o em trechos (chunks) de tamanho delimitado com sobreposição (overlap) configurável, preservando a rastreabilidade por número de página e posição original.

---

## 2. Escopo do Componente

### 2.1 O que FAZ (In-Scope)
- 🟡 Parsing de arquivos `.pdf` e extração de texto estruturado por página.
- 🟡 Sanitização básica de caracteres nulos, espaços duplicados e hifenização de quebra de linha.
- 🟡 Divisão do texto extraído em trechos (chunks) parametrizados por `chunk_size` (número de caracteres ou tokens) e `chunk_overlap`.
- 🟡 Vinculação de metadados a cada chunk (ID único do chunk, nome do arquivo de origem, número da página inicial/final, offset de caracteres).

### 2.2 O que NÃO faz (Non-Goals / Out-of-Scope)
- 🟡 OCR em imagens ou PDFs digitalizados sem camada de texto (escaneados).
- 🟡 Geração de embeddings vetoriais ou salvamento em banco de dados vetorial.
- 🟡 Suporte a formatos não-PDF (ex.: DOCX, HTML, PPTX) no MVP.

---

## 3. Requisitos Funcionais (RFs)

- 🟡 **RF-01 (Parsing de PDF):** O componente deve carregar e extrair o conteúdo textual de arquivos PDF mantendo o mapeamento exato das páginas originais.
- 🟡 **RF-02 (Chunking Parametrizado):** O componente deve subdividir o texto em trechos respeitando os parâmetros configuráveis `chunk_size` (padrão 1000 caracteres) e `chunk_overlap` (padrão 200 caracteres).
- 🟡 **RF-03 (Extração de Metadados):** Cada chunk gerado deve obrigatoriamente conter metadados estruturados: `chunk_id` (UUIDv4), `source_file` (string), `page_number` (inteiro 1-indexed) e `char_count` (inteiro).
- 🟡 **RF-04 (Sanitização de Texto):** O componente deve remover caracteres de controle inválidos e unificar quebras de linha que fragmentam palavras intermediárias.

---

## 4. Comportamento e Casos de Erro (Edge Cases)

- 🟡 **Cenário de PDF Vazio ou Corrompido:** Se o arquivo PDF estiver corrompido ou não contiver texto extraível, o componente deve lançar um erro `InvalidDocumentException` com mensagem clara sem interromper o processo de batch.
- 🟡 **Cenário de Documento Menor que `chunk_size`:** Se o documento tiver menos caracteres que o `chunk_size` configurado, um único chunk contendo todo o texto deve ser gerado sem lançar erros de boundary.
- 🟡 **Cenário de Seção/Página sem Texto (Apenas Imagens):** Se uma página contiver apenas elementos gráficos sem texto extraível, o componente deve emitir um log de aviso (`WARN`) e continuar o chunking para as páginas subsequentes.

---

## 5. Critérios de Aceite

- 🟡 **Dado** um arquivo PDF válido de 10 páginas, **Quando** for submetido ao processador com `chunk_size=1000` e `chunk_overlap=200`, **Então** o componente deve retornar uma lista de chunks onde cada chunk possui `chunk_id`, `source_file`, `page_number` e tamanho `<= 1000` caracteres.
- 🟡 **Dado** dois chunks consecutivos $C_i$ e $C_{i+1}$, **Quando** inspecionada a sobreposição, **Então** os últimos 200 caracteres de $C_i$ devem corresponder exatamente aos primeiros 200 caracteres de $C_{i+1}$.

---

## 6. Open Questions / Questões Abertas

- 🟡 `⚠️ ABERTO:` A unidade padrão de `chunk_size` deve ser contagem de caracteres ou contagem de tokens (ex.: via tiktoken)? *Premissa 🟡 adotada no MVP: contagem de caracteres.*

---

## Avaliação de Qualidade (SDD Scorer)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE TOTAL: 92/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakdown:
  Completude:    95/100 (peso 30%)
  Testabilidade: 95/100 (peso 25%)
  Clareza:       90/100 (peso 20%)
  Escopo:        90/100 (peso 15%)
  Edge Cases:    85/100 (peso 10%)

Gaps críticos: Nenhum.
Sugestões: Adicionar suporte futuro a OCR para PDFs escaneados.
```

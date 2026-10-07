# SDD Spec: Document Ingestion & Chunking (`document-ingestion-chunking`)

> Selo 🟢 IMPLEMENTADO. Especificação técnica executável no padrão SDD/RFC.

**Componente:** `document-ingestion-chunking`  
**Versão:** 1.0  
**Data:** 2026-09-22T14:27:00-03:00  
**Autor:** reversa-spec-sdd  
**Status:** 🟢 IMPLEMENTADO  

---

## 1. Problema e Objetivos

🟢 **Problema:** Documentos técnicos em formato PDF contêm estruturas complexas e blocos contínuos de texto que não podem ser diretamente ingeridos por modelos de embeddings sem perda semântica ou estouro de janela de contexto.  
🟢 **Objetivo:** Processar e extrair texto limpo de arquivos PDF, subdividindo-o em trechos (chunks) de tamanho delimitado com sobreposição (overlap) configurável, preservando a rastreabilidade por número de página e posição original.

---

## 2. Escopo do Componente

### 2.1 O que FAZ (In-Scope)
- 🟢 Parsing de arquivos `.pdf` via factory (`pdfplumber` para tabelas + `pypdf` como fallback leve).
- 🟢 Sanitização de caracteres de controle, normalização Unicode NFKC, fix de hifenização, colapso de quebras múltiplas.
- 🟢 Divisão do texto extraído em trechos (chunks) parametrizados por `chunk_size` (512 tokens), `chunk_overlap` (50 tokens), `chunk_unit` (tokens).
- 🟢 Vinculação de metadados a cada chunk (ID único, document_id, chunk_index, page_number, start_char, end_char, token_count, embedding opcional).

### 2.2 O que NÃO faz (Non-Goals / Out-of-Scope)
- 🟢 OCR em imagens ou PDFs digitalizados sem camada de texto (escaneados).
- 🟢 Geração de embeddings vetoriais ou salvamento em banco de dados vetorial (delegado a componentes `embeddings` e `vector_store`).
- 🟢 Suporte a formatos não-PDF (ex.: DOCX, HTML, PPTX) no MVP.

---

## 3. Requisitos Funcionais (RFs)

- 🟢 **RF-01 (Parsing de PDF):** O componente deve carregar e extrair o conteúdo textual de arquivos PDF mantendo o mapeamento exato das páginas originais, via `PDFParser` ABC com factory `create_parser("pdfplumber" | "pypdf")`.
- 🟢 **RF-02 (Chunking Parametrizado):** O componente deve subdividir o texto em trechos respeitando os parâmetros configuráveis `chunk_size=512` (tokens), `chunk_overlap=50` (tokens), `chunk_unit="tokens"` (via tiktoken cl100k_base).
- 🟢 **RF-03 (Extração de Metadados):** Cada chunk gerado deve conter metadados estruturados: `id` (UUIDv4), `document_id` (FK), `chunk_index` (≥0), `page_number` (estimado por offset), `start_char`, `end_char`, `token_count`, `embedding` (opcional), `metadata` (dict).
- 🟢 **RF-04 (Sanitização de Texto):** O componente deve remover caracteres de controle inválidos, normalizar NFKC, fixar hifenização de quebra de linha, colapsar `\n{3,}` → `\n\n`, strip trailing spaces por linha.

---

## 4. Comportamento e Casos de Erro (Edge Cases)

- 🟢 **Cenário de PDF Vazio ou Corrompido:** Se o arquivo PDF estiver corrompido ou não contiver texto extraível, o componente deve lançar `InvalidDocumentException` com mensagem clara sem interromper o processo de batch.
- 🟢 **Cenário de Documento Menor que `chunk_size`:** Se o documento tiver menos tokens que o `chunk_size` configurado, um único chunk contendo todo o texto deve ser gerado sem lançar erros de boundary.
- 🟢 **Cenário de Seção/Página sem Texto (Apenas Imagens):** Se uma página contiver apenas elementos gráficos sem texto extraível, o componente deve emitir log de aviso (`WARN`) e continuar o chunking para as páginas subsequentes.
- 🟢 **Deduplicação Real:** Antes do parse, consulta `SELECT 1 FROM documents WHERE content_hash = ?` no vector store; se existir, retorna `IngestResult(skipped=True, skip_reason="duplicate_hash")` sem chamar parser.

---

## 5. Critérios de Aceite

- 🟢 **Dado** um arquivo PDF válido de 10 páginas, **Quando** for submetido ao processador com `chunk_size=512 tokens`, `chunk_overlap=50 tokens`, **Então** o componente deve retornar uma lista de chunks onde cada chunk possui metadados completos e tamanho `<= 512` tokens.
- 🟢 **Dado** dois chunks consecutivos $C_i$ e $C_{i+1}$, **Quando** inspecionada a sobreposição, **Então** os últimos 50 tokens de $C_i$ devem corresponder exatamente aos primeiros 50 tokens de $C_{i+1}$ (sliding window exato).
- 🟢 **Dado** um PDF já ingerido (mesmo content_hash), **Quando** nova ingestão é tentada, **Então** parser NÃO é chamado, retorna `skipped=True`, `skip_reason="duplicate_hash"`, `latency_parse_ms=0`.

---

## 6. Open Questions / Questões Abertas

- 🟢 **RESOLVIDO:** A unidade padrão de `chunk_size` é contagem de **tokens** (via tiktoken cl100k_base), não caracteres. O parâmetro `chunk_unit` permite alternar para `"chars"` se necessário.

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
Sugestões: Adicionar suporte futuro a OCR para PDFs escaneados.
```
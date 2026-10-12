# Onboarding: bcb-corpus-dataset-v1

> Feature: `004-bcb-corpus-dataset-v1`
> Data: `2026-10-10`
> Público: Engenheiro de ML / Desenvolvedor que vai testar a feature pela primeira vez

## 1. Pré-requisitos

### 1.1 Ambiente
```bash
# Python 3.11+
python --version

# Dependências core (já no projeto)
uv sync  # ou pip install -e .

# Dependência para geração de candidatas (só local, não no CI)
pip install anthropic

# Variável de ambiente obrigatória para candidates
export ANTHROPIC_API_KEY="sk-ant-..."
# Opcional: modelo gerador (default: claude-sonnet-5-5)
export ANCHOR_GEN_MODEL="claude-sonnet-5-5"
```

### 1.2 Estrutura esperada após setup
```
C:\rag\
├── corpus/
│   ├── raw/                    # 30-50 normas BCB (HTML/PDF)
│   ├── chunks.jsonl            # Gerado pelo ingest
│   └── SOURCES.md              # Gerado pelo ingest
├── eval/
│   ├── build_dataset.py        # Script principal (4 subcomandos)
│   └── datasets/
│       ├── candidates.jsonl    # Gerado pelo candidates
│       ├── v1.jsonl            # Gold standard (congelado)
│       ├── v1.sha256           # Hash de integridade
│       ├── rejected.jsonl      # Candidatas rejeitadas
│       └── README.md           # Documentação do dataset
└── .github/workflows/ci.yml    # CI com validate + hash check
```

## 2. Fluxo completo (primeira vez)

### Passo 1: Baixar normas do BCB
```bash
# Opção A: Via buscador HTML (recomendado)
# 1. Acesse https://www.bcb.gov.br/estabilidadefinanceira/buscanormas
# 2. Busque por tema: "PIX", "Open Finance", "segurança cibernética", "crédito rural", "câmbio", "capital", "liquidez"
# 3. Para cada norma, salve o HTML em corpus/raw/
#    Exemplo: wget -O corpus/raw/circular_3978.html "https://www.bcb.gov.br/..."

# Opção B: PDFs (se HTML indisponível)
# wget -O corpus/raw/resolucao_4966.pdf "https://www.bcb.gov.br/..."

# Verificar
ls corpus/raw/ | wc -l  # Deve dar 30-50
```

### Passo 2: Ingest → chunks.jsonl + SOURCES.md
```bash
python eval/build_dataset.py ingest \
  --raw corpus/raw \
  --out corpus/chunks.jsonl \
  --max-chars 2500

# Saída esperada:
#   resolucao_4966: 7 artigos encontrados
#   circular_3978: 9 artigos encontrados
#   ...
#   287 chunks em 42 normas -> corpus/chunks.jsonl
#   resolucao_4966: 7
#   circular_3978: 9
#   ...

# Verificar
head -5 corpus/chunks.jsonl
cat corpus/SOURCES.md
```

**O que verificar**:
- Cada norma tem ≥ 1 chunk (se 0 → regex falhou ou PDF problemático)
- `SOURCES.md` tem URL, data, número do ato, SHA-256
- Artigos revogados ignorados (log "REVOGADO - ignorado")

### Passo 3: Commitar corpus
```bash
git add corpus/raw/ corpus/chunks.jsonl corpus/SOURCES.md
git commit -m "feat: corpus BCB v1 (42 normas, 287 chunks)"
```

### Passo 4: Gerar candidatas (requer ANTHROPIC_API_KEY)
```bash
# Respondíveis (meta 60)
python eval/build_dataset.py candidates \
  --categoria respondivel --n 80 \
  --chunks corpus/chunks.jsonl \
  --out eval/datasets/candidates.jsonl

# Multi-trecho (meta 20)
python eval/build_dataset.py candidates \
  --categoria multi_trecho --n 30 \
  --chunks corpus/chunks.jsonl \
  --out eval/datasets/candidates.jsonl

# Sem resposta (meta 20)
python eval/build_dataset.py candidates \
  --categoria sem_resposta --n 30 \
  --chunks corpus/chunks.jsonl \
  --out eval/datasets/candidates.jsonl

# Adversarial (meta 20)
python eval/build_dataset.py candidates \
  --categoria adversarial --n 30 \
  --chunks corpus/chunks.jsonl \
  --out eval/datasets/candidates.jsonl
```

**Tempo estimado**: ~3-5 min por categoria (chamadas LLM).

### Passo 5: Revisão humana (review)
```bash
python eval/build_dataset.py review \
  --chunks corpus/chunks.jsonl \
  --cand eval/datasets/candidates.jsonl \
  --v1 eval/datasets/v1.jsonl \
  --rej eval/datasets/rejected.jsonl
```

**Interface interativa**:
```
================================================================================
respondivel  id=a1b2c3d4e5  ataque=-
--- resolucao_4966:art1 ---
Art. 1º
As instituições autorizadas a funcionar pelo Banco Central do Brasil devem...

PERGUNTA: Quais instituições devem estabelecer política de segurança cibernética?
OURO:     As instituições autorizadas a funcionar pelo Banco Central do Brasil.

[a/e/r/p/q] >
```

**Comandos**:
- `a` = aceitar (grava em v1.jsonl com `revisado=true`)
- `e` = editar (pergunta/resposta/chunk_ids)
- `r` = rejeitar (grava em rejected.jsonl com motivo)
- `p` = pular (mantém em candidates para depois)
- `q` = sair

**Meta**: 120 itens `revisado=true` no v1.jsonl (60/20/20/20).

### Passo 6: Validação + congelamento
```bash
python eval/build_dataset.py validate \
  --chunks corpus/chunks.jsonl \
  --v1 eval/datasets/v1.jsonl
```

**Saída esperada (sucesso)**:
```
Categoria        atual / alvo
  respondivel       60 / 60
  multi_trecho      20 / 20
  sem_resposta      20 / 20
  adversarial       20 / 20
Total: 120
```

**Artefatos gerados**:
- `eval/datasets/v1.sha256` (hash do v1.jsonl)
- `eval/datasets/README.md` (versão, data, contagens, hash)

### Passo 7: Commitar dataset
```bash
git add eval/datasets/v1.jsonl eval/datasets/v1.sha256 eval/datasets/README.md
git commit -m "feat: dataset v1.jsonl (120 perguntas, 4 categorias)"
```

### Passo 8: Testar integração com feature 003
```bash
# Avaliação agentic single provider
hag-rag eval --dataset eval/datasets/v1.jsonl --agentic --judge ollama

# Comparação multi-provedor
hag-rag eval --dataset eval/datasets/v1.jsonl --agentic --compare openai,ollama

# Drift check (baseline = v1.jsonl)
hag-rag eval --dataset eval/datasets/v1.jsonl --drift-check --baseline eval/datasets/v1.jsonl
```

## 3. CI/CD

### 3.1 Atualizar `.github/workflows/ci.yml`
Adicionar step após testes:
```yaml
- name: Validate dataset v1
  run: |
    python eval/build_dataset.py validate \
      --chunks corpus/chunks.jsonl \
      --v1 eval/datasets/v1.jsonl
    sha256sum -c eval/datasets/v1.sha256
```

### 3.2 O que o CI garante
- Schema do v1.jsonl válido
- Contagens ≥ ALVO por categoria
- chunk_ids existem em chunks.jsonl
- IDs/perguntas únicos
- Hash SHA-256 confere (imutabilidade)

## 4. Regenerar v2 (quando necessário)

**Quando**: Nova norma adicionada, categoria nova, correção de erro no gold standard.

```bash
# 1. Atualizar corpus/raw/ (add/remove normas)
# 2. Re-rodar ingest
python eval/build_dataset.py ingest --raw corpus/raw --out corpus/chunks.jsonl

# 3. Gerar novas candidatas só para o delta (ou todas)
python eval/build_dataset.py candidates --categoria respondivel --n 10 ...

# 4. Review apenas das novas (ou todas se mudou chunk_ids)
python eval/build_dataset.py review --cand eval/datasets/candidates.jsonl ...

# 5. Validar
python eval/build_dataset.py validate ...

# 6. Commitar como v2
git add eval/datasets/v2.jsonl eval/datasets/v2.sha256 eval/datasets/README.md
# Atualizar baseline no drift-check para apontar para v2.jsonl
```

**Importante**: `v1.jsonl` **nunca** é modificado. Mudança → nova versão.

## 5. Troubleshooting

| Problema | Causa provável | Solução |
|----------|----------------|---------|
| `ingest`: 0 chunks para uma norma | PDF com layout complexo / HTML diferente | Verificar regex; tentar `pdfplumber` se PDF; reportar norma problemática |
| `candidates`: `ANTHROPIC_API_KEY` não definida | Env var faltando | `export ANTHROPIC_API_KEY=...` |
| `candidates`: timeout / rate limit | Muitas chamadas LLM | Reduzir `--n`; rodar em lotes; `--seed` fixo para reprodutibilidade |
| `review`: chunk_id não encontrado em chunks.jsonl | Candidata gerada com chunk_id antigo (corpus mudou) | Re-rodar `candidates` após `ingest` |
| `validate`: "chunk_id inexistente" | Mesmo acima | Re-gerar candidates |
| `validate`: "pergunta duplicada" | Duas candidatas com mesma pergunta normalizada | Aceitar uma, rejeitar outra no review |
| CI falha no hash check | v1.jsonl modificado acidentalmente | `git checkout eval/datasets/v1.jsonl` ou regenerar v2 |

## 6. Comandos úteis

```bash
# Contar chunks por norma
python -c "
import json
from collections import Counter
chunks = [json.loads(l) for l in open('corpus/chunks.jsonl')]
print(Counter(c['norma'] for c in chunks))
"

# Ver distribuição de tamanhos de chunk
python -c "
import json
import statistics
chunks = [json.loads(l) for l in open('corpus/chunks.jsonl')]
sizes = [c['n_chars'] for c in chunks]
print(f'min={min(sizes)} max={max(sizes)} mean={statistics.mean(sizes):.0f} median={statistics.median(sizes)}')
"

# Ver categorias no v1.jsonl
python -c "
import json
from collections import Counter
items = [json.loads(l) for l in open('eval/datasets/v1.jsonl')]
print(Counter(i['categoria'] for i in items))
print(f'Total: {len(items)}')
print(f'Revisados: {sum(1 for i in items if i.get(\"revisado\"))}')
"
```
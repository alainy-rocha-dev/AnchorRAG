
# AnchorRAG ⚓ — Auditable RAG over Brazilian Central Bank Regulations

Local Retrieval-Augmented Generation pipeline that answers questions about **Brazilian Central Bank (BCB/CMN) regulations** using only the retrieved passages, with mandatory citations, refusal when the answer is not in the corpus, and defenses against prompt injection.

The focus of the project is **measurement**: a manually reviewed evaluation dataset, a frozen baseline with confidence intervals, and an honest record of what worked, what didn't and which numbers are not yet validated (see [`DECISIONS.md`](DECISIONS.md)).

---

## Results (frozen baseline, variant A)

**Setup:** 12 BCB/CMN regulations (663 chunks) · hybrid retrieval (BM25 + `bge-m3` embeddings, RRF, k=5) · synthesis with `qwen2.5:7b` (temperature 0.1) · output filter. Everything runs **locally** (Ollama, consumer GPU).
**Dataset:** [`eval/datasets/v1.jsonl`](eval/datasets/v1.jsonl) — 140 manually reviewed items. Mean of 3 full runs; 95% CI by bootstrap (10,000 resamples).

| Metric | n | Result | 95% CI |
|---|---|---|---|
| Retrieval hit@5 (items with a reference passage) | 113 | **0.91** | 0.86–0.96 |
| All reference passages in top-5 (multi-passage questions) | 22 | 0.68 | 0.50–0.86 |
| Correct refusal when the corpus has no answer | 23 | **0.94** | 0.84–1.00 |
| Correct refusal of prompt-leak requests | 4 | 1.00 | – |
| Wrongful refusal (answerable questions) | 104 | 0.01 | 0.00–0.04 |
| Answers with citations | 104 | **0.85** | 0.79–0.90 |
| Prompt-injection canary leaked | 9 | **0** | – |

Latency (local, RX 7600): p50 ≈ 5 s, p95 ≈ 10 s per answer — almost all in the LLM; retrieval p50 ≈ 0.35 s.

### What moved the numbers

| Change | Before → After |
|---|---|
| Hybrid retrieval (BM25 + vector) instead of vector only — hit@5 | 0.82 → **0.91** |
| Prompt rewrite (rules before examples) — correct refusal on unanswerable questions | 0.39 → **0.83** |
| Same rewrite — answers containing an injected fake "secret" | 81 of 140 → **0** |
| Output filter against system-prompt leakage — leak requests refused | 0.50 → **1.00** |

### Evaluation dataset (v1)

140 questions generated from the regulation texts and **reviewed one by one by a human**, in four categories:

| Category | Items | Tests |
|---|---|---|
| Answerable | 73 | single-passage questions with a gold answer |
| Multi-passage | 22 | answers that need more than one article |
| No answer in corpus | 23 | related topics outside the 12 regulations (e.g. FGC, IOF, Drex), many with deliberate distractors |
| Adversarial | 22 | false premises, prompt-leak requests and prompt injection |

### LLM-as-judge: validated before trusting

Answer faithfulness was judged claim by claim by local LLM judges and **checked against human labels** (29 claims, labeled blind to the judge's verdict):

| Judge | Agreement | Cohen's κ |
|---|---|---|
| llama3.1:8b | 0.59 | 0.16 |
| gemma2:9b | 0.72 | 0.29 |
| "always supported" baseline | 0.66 | 0 |

Neither local judge was reliable enough (gemma2 barely beats a judge that approves everything), so **judge-based faithfulness is not used** to compare variants. Comparisons rely only on model-independent signals: retrieval, refusal, citations, canary and output filter.


### Variant C — deterministic citation verifier

The verifier checks each answer against the passages the model received, without an LLM, and sends it back to the writer (at most 2 rewrites) when it finds:

| Problem | Example |
|---|---|
| Citation to a passage that was not given | `[7]` when only 5 passages exist |
| Claim with no citation | an answer (not a refusal) without any `[N]` |
| Article not in the cited passages | "according to art. 9 … [3]" while `[3]` is art. 68 |
| Number not in the cited passages | "15 years [1]" while `[1]` says ten years (digits and number words both accepted) |

Without a valid citation after the rewrites, the answer becomes the standard refusal. It does not judge whether a passage *supports the meaning* of a sentence — that is the semantic layer, still blocked on judge validation.

The same check is reported for every variant as **valid citation rate**. Applied to the saved baseline answers: **0.84** of variant A's answers pass (95% CI 0.77–0.89, n = 103). Typical failures are answers without any citation and articles cited from the wrong passage. The router planned for variant B is not built yet, so this C is A + verifier.

**Result (3 runs each, same 140 items, paired bootstrap 95% CI)** — `qwen2.5:7b` as writer, up to 2 rewrites:

| Metric (questions that should be answered, n = 104) | A | C | C − A |
|---|---|---|---|
| Valid citation, among delivered answers | 0.84 | 1.00 | +0.11 [+0.07, +0.17] |
| Wrongful refusal | 0.01 | 0.15 | **+0.14 [+0.09, +0.20]** |
| **Delivered and well cited** (refusal counts as failure) | 0.83 | 0.85 | +0.02 [−0.02, +0.06] |
| Latency per answer (s) | 5.7 | 6.4 | +0.7 [+0.1, +1.2] |
| Input tokens per answer | 2,005 | 2,628 | +623 |

Retrieval, correct refusal (0.95) and the injection canary (0 leaks) did not change.

**Reading:** the verifier works as a filter — no answer with an invalid citation reaches the user — but the repair loop rarely repairs. Of 312 answers, 23 were "fixed" after feedback, and 15 of those were the model giving up with the refusal; only 8 became valid answers. Most rejected drafts had no citation at all. So the net gain in answers that are both delivered and well cited is not significant, and the price is 14 points of wrongful refusals. Next step: a repair message per problem type (e.g. "keep the content, add the `[N]` of the passage you used" for missing citations) instead of one generic message that offers the refusal as a way out.

---

## Example

**Question:** *Does our bank's outsourced cybersecurity provider need to know our security policy?*

**Answer (excerpt):** *Yes — according to Article 4, the cybersecurity policy must be disclosed to the institution's employees and to the companies providing services to it [1].*
**Source [1]:** Resolução CMN nº 4.893/2021, art. 4

**Question with no answer in the corpus:** *What is the penalty for a payment institution that fails to notify the Central Bank about hiring relevant cloud computing services?*
**Answer:** *"I did not find this information in the provided documents…"* — the system refuses instead of inventing a penalty.

*(Questions and answers are in Portuguese in the system; translated here.)*

---

## How it works

```
Regulations (BCB portal) → parsing → structured chunking (by article)
        → BM25 index (SQLite FTS5) + embeddings (sqlite-vec)
        → hybrid retrieval (RRF, k=5)
        → LLM synthesis with strict grounding + mandatory [N] citations
        → output filter (blocks system-prompt leakage) → answer + sources
```

- **Strict grounding:** answer only from the retrieved passages; every claim cites `[N]`; explicit refusal when the information is not there
- **Prompt-injection defense in layers:** rules in the system prompt, passages treated as content (not instructions), and a post-generation filter
- **Hybrid retrieval:** BM25 tuned for Portuguese (diacritics, stopwords) + vector search, fused with Reciprocal Rank Fusion
- **Pluggable providers:** embeddings (Ollama, OpenAI, Hugging Face) and LLMs (Ollama, OpenAI, Anthropic)
- **Reproducibility:** each report records dataset and corpus hashes, models, retrieval settings, git commit and context window

## Quickstart

```bash
pip install -e ".[dev]"
cp config.example.yaml config.yaml   # set providers / API keys

# Load the BCB corpus (corpus/chunks.jsonl) into the local database
anchor-rag ingest-chunks corpus/chunks.jsonl --embedding-provider ollama --embedding-model bge-m3

# Run the v1 evaluation (hybrid retrieval by default; report saved to eval/results/)
anchor-rag eval-v1 --variante A

# Variant C: same pipeline with the citation verifier in the loop
anchor-rag eval-v1 --variante C --verificador

# Compare two variants on the same items (paired bootstrap, 95% CI)
python scripts/compare_variants.py --a eval/results/*_A_hybrid.json --b eval/results/*_C_hybrid.json
```

## Tests

```bash
pytest tests/unit -v
pytest tests/integration -v
```

## Known limitations

- Questions were generated from the text of the articles and reuse their vocabulary, which favors lexical (BM25) retrieval; real user questions may behave differently
- Small samples for prompt-leak (4) and injection (9) items
- Faithfulness by LLM judge is not validated (see above); one human reviewer
- Synthesis varies between runs: up to 7 points in citation rate — compare variants with 3 runs

## Tech stack

Python 3.11 · SQLite (FTS5 + sqlite-vec) · Ollama (`bge-m3`, `qwen2.5:7b`) · Typer · Pydantic · pytest

## License

MIT — see [LICENSE](LICENSE).

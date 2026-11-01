### harbour_physio: 15 questions, 1 runs per model

Agent retrieval: hybrid. Mean across runs, range in brackets. Cost and time are for the whole question set. A final answer written as text instead of a submit_answer call is parsed and checked like a call (column: such answers per run).

| Model | Correct | Answerable correct | Abstained correctly | Facts found | Answers with a verified citation | Citations verified | Evidence recall | Retrieval recall | Tool calls per question | Final call written as text | Cost (USD) | Time (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `ollama:qwen3:8b` | 0.60 | 0.54 | 1.00 | 0.67 | 0.77 | 0.70 | 0.56 | 0.74 | 1.9 | 12.0 | 0.000 | 332 |

Retrieval alone, gold evidence lines in the top 5 hits for the raw question: bm25 0.63, dense 0.81, hybrid 0.86.

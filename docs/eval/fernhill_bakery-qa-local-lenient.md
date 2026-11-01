### fernhill_bakery: 17 questions, 1 runs per model

Agent retrieval: hybrid. Mean across runs, range in brackets. Cost and time are for the whole question set. A final answer written as text instead of a submit_answer call is parsed and checked like a call (column: such answers per run).

| Model | Correct | Answerable correct | Abstained correctly | Facts found | Answers with a verified citation | Citations verified | Evidence recall | Retrieval recall | Tool calls per question | Final call written as text | Cost (USD) | Time (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `ollama:qwen3:8b` | 0.82 | 0.80 | 1.00 | 0.83 | 0.73 | 0.87 | 0.61 | 0.73 | 2.1 | 12.0 | 0.000 | 356 |

Retrieval alone, gold evidence lines in the top 5 hits for the raw question: bm25 0.76, dense 0.87, hybrid 0.87.

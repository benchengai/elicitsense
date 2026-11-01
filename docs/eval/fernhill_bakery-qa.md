### fernhill_bakery: 17 questions, 3 runs per model

Agent retrieval: hybrid. Mean across runs, range in brackets. Cost and time are for the whole question set. A final answer written as text instead of a submit_answer call is parsed and checked like a call (column: such answers per run).

| Model | Correct | Answerable correct | Abstained correctly | Facts found | Answers with a verified citation | Citations verified | Evidence recall | Retrieval recall | Tool calls per question | Final call written as text | Cost (USD) | Time (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `openai:gpt-6.1-sol` | 0.96 (0.94–1.00) | 0.96 (0.93–1.00) | 1.00 | 1.00 | 1.00 | 1.00 | 0.98 | 0.99 (0.98–1.00) | 4.2 (4.1–4.3) | 0.0 | 0.140 (0.132–0.155) | 129 (128–131) |
| `openai:gpt-6.1-terra` | 0.94 | 0.93 | 1.00 | 1.00 | 1.00 | 1.00 | 0.99 (0.98–1.00) | 0.99 (0.98–1.00) | 7.2 (7.1–7.4) | 0.0 | 0.112 (0.110–0.114) | 176 (173–178) |
| `openai:gpt-6-luna` | 0.94 (0.88–1.00) | 0.93 (0.87–1.00) | 1.00 | 0.98 (0.95–1.00) | 1.00 | 1.00 | 0.97 (0.96–0.98) | 1.00 | 5.5 (5.4–5.6) | 0.0 | 0.012 (0.012–0.013) | 196 (194–197) |

Retrieval alone, gold evidence lines in the top 5 hits for the raw question: bm25 0.76, dense 0.87, hybrid 0.87.

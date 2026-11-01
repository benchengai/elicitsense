### harbour_physio: 15 questions, 3 runs per model

Agent retrieval: hybrid. Mean across runs, range in brackets. Cost and time are for the whole question set. A final answer written as text instead of a submit_answer call is parsed and checked like a call (column: such answers per run).

| Model | Correct | Answerable correct | Abstained correctly | Facts found | Answers with a verified citation | Citations verified | Evidence recall | Retrieval recall | Tool calls per question | Final call written as text | Cost (USD) | Time (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `openai:gpt-6.1-sol` | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.96 (0.96–0.98) | 1.00 | 4.4 (4.3–4.6) | 0.0 | 0.132 (0.126–0.137) | 124 (120–125) |
| `openai:gpt-6.1-terra` | 0.98 (0.93–1.00) | 0.97 (0.92–1.00) | 1.00 | 0.99 (0.96–1.00) | 1.00 | 1.00 | 0.96 | 1.00 | 7.4 (7.1–7.7) | 0.0 | 0.102 (0.100–0.104) | 168 (166–172) |
| `openai:gpt-6-luna` | 0.98 (0.93–1.00) | 0.97 (0.92–1.00) | 1.00 | 0.97 (0.92–1.00) | 1.00 | 1.00 | 0.97 (0.92–1.00) | 1.00 | 5.8 (5.3–6.3) | 0.0 | 0.012 (0.011–0.012) | 194 (183–204) |

Retrieval alone, gold evidence lines in the top 5 hits for the raw question: bm25 0.63, dense 0.81, hybrid 0.86.

### fernhill_bakery: 3 runs per model

Mean across successful runs, range in brackets. Cost and latency are per full project run (every meeting extracted, then merged) and include failed runs. `a>b` extracts with a and merges with b.

Merge link ids: free text.

| Model | Req. recall | Req. precision | Strict 1:1 precision | Quotes verified | Uncertainty agr. | Relations, exact kind | Relation precision | Status changes | Open conflicts right | Invalid links | Cost (USD) | Time (s) | Failed runs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `openai:gpt-6.1-sol` | 1.00 | 1.00 | 0.74 (0.72–0.75) | 1.00 | 1.00 | 0.86 | 0.88 | 1.00 | 3 of 3 | 0.0 | 0.083 (0.078–0.088) | 71 (65–76) | 0 of 3 |
| `openai:gpt-6.1-terra` | 1.00 | 0.99 (0.96–1.00) | 0.80 (0.78–0.81) | 1.00 | 1.00 | 0.67 (0.57–0.71) | 0.79 (0.67–0.86) | 1.00 | 0 of 3 | 0.0 | 0.038 (0.037–0.039) | 78 (77–79) | 0 of 3 |
| `openai:gpt-6-luna` | 1.00 | 1.00 | 0.80 (0.75–0.84) | 1.00 | 1.00 | 0.67 (0.57–0.86) | 0.87 (0.78–1.00) | 1.00 | 0 of 3 | 0.0 | 0.005 | 77 (76–80) | 0 of 3 |
| `ollama:qwen3:8b` | 0.98 (0.95–1.00) | 0.97 (0.96–1.00) | 0.86 (0.81–0.91) | 1.00 | 0.95 | 0.24 (0.14–0.29) | 0.41 (0.33–0.50) | 0.00 | 0 of 3 | 20.0 (19.0–22.0) | 0.000 | 371 (254–514) | 0 of 3 |

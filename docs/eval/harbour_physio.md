### harbour_physio: 3 runs per model

Mean across successful runs, range in brackets. Cost and latency are per full project run (every meeting extracted, then merged) and include failed runs. `a>b` extracts with a and merges with b.

Merge link ids: free text.

| Model | Req. recall | Req. precision | Strict 1:1 precision | Quotes verified | Uncertainty agr. | Relations, exact kind | Relation precision | Status changes | Open conflicts right | Invalid links | Cost (USD) | Time (s) | Failed runs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `openai:gpt-6.1-sol` | 1.00 | 1.00 | 0.61 | 1.00 | 0.93 (0.89–0.95) | 0.78 | 0.81 (0.80–0.82) | 1.00 | 3 of 3 | 0.0 | 0.091 (0.087–0.096) | 83 (80–84) | 0 of 3 |
| `openai:gpt-6.1-terra` | 1.00 | 0.99 (0.97–1.00) | 0.62 (0.59–0.66) | 1.00 | 0.89 | 0.52 (0.44–0.56) | 0.96 (0.89–1.00) | 1.00 | 3 of 3 | 0.0 | 0.047 (0.043–0.049) | 97 (92–100) | 0 of 3 |
| `openai:gpt-6-luna` | 1.00 | 1.00 | 0.63 (0.61–0.66) | 1.00 | 0.89 | 0.52 (0.33–0.67) | 0.90 (0.80–1.00) | 1.00 | 1 of 3 | 0.0 | 0.007 (0.006–0.008) | 137 (106–181) | 0 of 3 |
| `ollama:qwen3:8b` | 1.00 | 0.98 (0.93–1.00) | 0.79 (0.70–0.83) | 1.00 | 0.88 (0.84–0.89) | 0.04 (0.00–0.11) | 0.42 (0.00–1.00) | 0.67 (0.00–1.00) | 3 of 3 | 16.7 (10.0–23.0) | 0.000 | 544 (250–1085) | 0 of 3 |

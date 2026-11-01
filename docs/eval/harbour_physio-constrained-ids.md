### harbour_physio: 3 runs per model

Mean across successful runs, range in brackets. Cost and latency are per full project run (every meeting extracted, then merged) and include failed runs. `a>b` extracts with a and merges with b.

Merge link ids: restricted to the ids in the prompt. Extraction outputs reused from the earlier runs in `runs/bench/harbour_physio/baseline`; only merge was called again.

| Model | Req. recall | Req. precision | Strict 1:1 precision | Quotes verified | Uncertainty agr. | Relations, exact kind | Relation precision | Status changes | Open conflicts right | Invalid links | Cost (USD) | Time (s) | Failed runs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `openai:gpt-6.1-sol` | 1.00 | 1.00 | 0.61 | 1.00 | 0.93 (0.89–0.95) | 0.78 | 0.85 (0.82–0.90) | 1.00 | 3 of 3 | 0.0 | 0.093 (0.090–0.098) | 84 (83–85) | 0 of 3 |
| `openai:gpt-6.1-terra` | 1.00 | 0.99 (0.97–1.00) | 0.62 (0.59–0.66) | 1.00 | 0.89 | 0.52 (0.44–0.56) | 0.93 (0.89–1.00) | 1.00 | 3 of 3 | 0.0 | 0.049 (0.045–0.051) | 101 (93–108) | 0 of 3 |
| `openai:gpt-6-luna` | 1.00 | 1.00 | 0.63 (0.61–0.66) | 1.00 | 0.89 | 0.56 (0.44–0.67) | 0.84 (0.70–0.91) | 1.00 | 1 of 3 | 0.0 | 0.007 (0.007–0.008) | 112 (89–138) | 0 of 3 |
| `ollama:qwen3:8b` | 1.00 | 0.98 (0.93–1.00) | 0.79 (0.70–0.83) | 1.00 | 0.88 (0.84–0.89) | 0.04 (0.00–0.11) | 0.44 (0.22–0.75) | 0.00 | 3 of 3 | 3.3 (0.0–10.0) | 0.000 | 484 (276–863) | 0 of 3 |
| `openai:gpt-6-luna>openai:gpt-6.1-sol` | 1.00 | 1.00 | 0.63 (0.61–0.66) | 1.00 | 0.89 | 0.67 (0.56–0.78) | 0.87 (0.80–1.00) | 1.00 | 3 of 3 | 0.0 | 0.044 (0.042–0.046) | 81 (76–86) | 0 of 3 |
| `ollama:qwen3:8b>openai:gpt-6.1-sol` | 1.00 | 0.98 (0.93–1.00) | 0.79 (0.70–0.83) | 1.00 | 0.88 (0.84–0.89) | 0.44 | 0.84 (0.78–0.88) | 1.00 | 3 of 3 | 0.0 | 0.033 (0.029–0.039) | 383 (182–753) | 0 of 3 |

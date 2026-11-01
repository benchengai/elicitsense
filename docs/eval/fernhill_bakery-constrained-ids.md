### fernhill_bakery: 3 runs per model

Mean across successful runs, range in brackets. Cost and latency are per full project run (every meeting extracted, then merged) and include failed runs. `a>b` extracts with a and merges with b.

Merge link ids: restricted to the ids in the prompt. Extraction outputs reused from the earlier runs in `runs/bench/fernhill_bakery/baseline`; only merge was called again.

| Model | Req. recall | Req. precision | Strict 1:1 precision | Quotes verified | Uncertainty agr. | Relations, exact kind | Relation precision | Status changes | Open conflicts right | Invalid links | Cost (USD) | Time (s) | Failed runs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `openai:gpt-6.1-sol` | 1.00 | 1.00 | 0.74 (0.72–0.75) | 1.00 | 1.00 | 0.86 | 0.88 | 1.00 | 3 of 3 | 0.0 | 0.085 (0.080–0.092) | 74 (69–83) | 0 of 3 |
| `openai:gpt-6.1-terra` | 1.00 | 0.99 (0.96–1.00) | 0.80 (0.78–0.81) | 1.00 | 1.00 | 0.67 (0.57–0.71) | 0.67 (0.57–0.71) | 1.00 | 0 of 3 | 0.0 | 0.039 (0.038–0.040) | 80 (79–82) | 0 of 3 |
| `openai:gpt-6-luna` | 1.00 | 1.00 | 0.80 (0.75–0.84) | 1.00 | 1.00 | 0.62 (0.57–0.71) | 0.82 (0.75–0.86) | 1.00 | 0 of 3 | 0.0 | 0.006 (0.005–0.006) | 75 (68–84) | 0 of 3 |
| `ollama:qwen3:8b` | 0.98 (0.95–1.00) | 0.97 (0.96–1.00) | 0.86 (0.81–0.91) | 1.00 | 0.95 | 0.81 (0.71–0.86) | 0.71 (0.67–0.75) | 0.00 | 2 of 3 | 11.0 | 0.000 | 391 (275–549) | 0 of 3 |
| `openai:gpt-6-luna>openai:gpt-6.1-sol` | 1.00 | 1.00 | 0.80 (0.75–0.84) | 1.00 | 1.00 | 0.76 (0.71–0.86) | 0.85 (0.83–0.86) | 1.00 | 3 of 3 | 0.0 | 0.035 (0.032–0.038) | 69 (66–75) | 0 of 3 |
| `ollama:qwen3:8b>openai:gpt-6.1-sol` | 0.98 (0.95–1.00) | 0.97 (0.96–1.00) | 0.86 (0.81–0.91) | 1.00 | 0.95 | 0.95 (0.86–1.00) | 0.84 (0.78–0.88) | 1.00 | 2 of 3 | 0.0 | 0.031 (0.026–0.037) | 295 (186–444) | 0 of 3 |

# ElicitSense

Turn requirements-elicitation meeting recordings into a reviewable requirements
register. Every requirement cites the exact words and timestamp it came from,
and is flagged "needs confirmation" when the stakeholder hesitated while
stating it.

Built from the systematic mapping study *Emotions in Software Engineering*
and the multimodal requirements-elicitation prototype MEmoRE (IEEE RE 2023).
See [docs/SPEC.md](docs/SPEC.md) for the product and technical spec and
[docs/portfolio-lineup.md](docs/portfolio-lineup.md) for the wider portfolio.

## Status

Milestones M1 (pipeline CLI), M2 (cross-meeting register) and M3 (evaluation
and model comparison) are done. Works today:

- scripted demo meetings rendered to audio with macOS `say` (`data/projects/`)
- local transcription with word timestamps (faster-whisper, nothing uploaded)
- uncertainty cues from hedges, filled pauses, long pauses and slow speech
- requirement extraction with Claude, GPT or a local open-weight model through
  Ollama (same prompt and schema), followed by deterministic quote verification,
  cue attachment and quality checks
- a project register across meetings: the model proposes links (same, refines,
  supersedes, conflicts, status change); statuses, supersession, reinstatement,
  open conflicts and history are applied by code
- two gold-labelled projects: `harbour_physio` (development set) and
  `fernhill_bakery` (held out), with scorers for cues, extraction and the register
- `bench`: runs several models several times on the same transcripts and
  reports quality, cost, latency and failures ([docs/eval](docs/eval/README.md))

Next: Q&A agent over the register with cited answers (M4), then a minimal web
UI (M5).

## Quick start

Requires macOS (for the synthetic demo audio), [uv](https://docs.astral.sh/uv/)
and an Anthropic or OpenAI API key, or [Ollama](https://ollama.com) for a local
model. Put API keys in a `.env` file at the repository root (git-ignored):

```
ANTHROPIC_API_KEY=...
# or
OPENAI_API_KEY=...
```

```bash
uv sync
uv run pytest
uv run elicitsense run data/projects/harbour_physio/m1_kickoff.txt
uv run elicitsense eval-cues runs/harbour_physio data/projects/harbour_physio/gold.json
uv run elicitsense eval-extract runs/harbour_physio data/projects/harbour_physio/gold.json
uv run elicitsense merge runs/harbour_physio -o runs/harbour_physio/register.json
uv run elicitsense eval-merge runs/harbour_physio/register.json data/projects/harbour_physio/gold.json
uv run elicitsense bench data/projects/harbour_physio -m openai:gpt-6.1-sol ollama:qwen3:8b --runs 3
```

`run` writes `runs/<project>/<meeting>/segments.json`, `cues.json` and
`requirements.json`; `merge` combines every meeting of a project (ordered by
meeting date) into one register. `--provider auto` (the default) uses whichever
API key is set, preferring Anthropic; `--provider openai --llm gpt-6.1-sol` or
`--provider ollama --llm qwen3:8b` picks explicitly. Add `--skip-extract` to
stop after transcription and cues, or `--setting internal` to run without
uncertainty cues. `bench` needs the transcripts first (`run --skip-extract` on
each meeting) and caches finished runs, so it resumes if interrupted. A model
spec `a>b` extracts with a and merges with b, and `--reuse-extraction` re-runs
only the merge step on an earlier bench's extraction outputs.

## Privacy and compliance

- Audio is transcribed locally; only transcript text is sent to the model.
- Cues are attached to requirements, never aggregated per person.
- `--setting internal` disables cues: the EU AI Act (Art. 5(1)(f)) prohibits
  AI emotion inference in workplace settings. The intended use is consented
  client elicitation sessions.
- The demo meetings are fictional and synthetic.

## Results so far

Full report with method, tables and limitations: [docs/eval](docs/eval/README.md).
Two fictional projects, three meetings each: `harbour_physio` (development
set, 19 requirements, 9 relations) and `fernhill_bakery` (held out, 21
requirements, 7 relations). Three runs per model; mean shown.

| | `gpt-6.1-sol` | `gpt-6.1-terra` | `gpt-6-luna` | `qwen3:8b` (local) |
|---|---|---|---|---|
| Requirement recall, dev / held out | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 0.98 |
| Quotes verified | 1.00 | 1.00 | 1.00 | 1.00 |
| Relations found with the right kind, dev / held out | 0.78 / 0.86 | 0.52 / 0.67 | 0.52 / 0.67 | 0.04 / 0.24 |
| Held-out runs that kept the unresolved conflict open | 3 of 3 | 0 of 3 | 0 of 3 | 0 of 3 |
| Cost per project run (USD) | 0.08–0.09 | 0.04–0.05 | 0.005–0.008 | local |

Uncertainty flags (rule-based, no LLM): precision 1.00 on both sets, recall
1.00 on the development set and 0.75 on the held-out set.

Follow-up experiment, same extraction outputs, merge step re-run:

- Restricting link ids in the merge schema to the ids in the prompt removed
  the local model's invalid ids (16.7 and 20 refused links per run before);
  API models were unaffected. Now the default.
- Routing the steps (`gpt-6-luna` extracts, `gpt-6.1-sol` merges) costs 53% to
  59% less than `gpt-6.1-sol` alone, kept the unresolved conflict in 3 of 3
  held-out runs, and found about one relation fewer per project.
- With the merge model fixed, who extracted still moved relation recall by up
  to 0.34, which requirement recall did not show.

What this shows: extracting grounded requirements is within reach of every
model tested, including an 8B model on a laptop; linking them across meetings
and keeping disagreements visible is where model choice matters, and a cheap
extractor in front of a strong merge model gets most of the way for half the
cost.

Read these numbers as a smoke test, not a benchmark. The audio is synthetic
with scripted hesitation, the projects are small (one relation moves recall
by 0.11 to 0.14), and one person wrote the prompts, scripts and gold labels.

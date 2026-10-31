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

Milestones M1 (pipeline CLI) and M2 (cross-meeting register) are done. Works today:

- scripted demo meetings rendered to audio with macOS `say` (`data/meetings/`)
- local transcription with word timestamps (faster-whisper, nothing uploaded)
- uncertainty cues from hedges, filled pauses, long pauses and slow speech
- requirement extraction with Claude or GPT (same prompt and schema),
  followed by deterministic quote verification, cue attachment and quality checks
- a project register across meetings: the model proposes links (same, refines,
  supersedes, conflicts, status change); statuses, supersession, reinstatement,
  open conflicts and history are applied by code
- gold labels for the three demo meetings (`data/gold/harbour_physio.json`)
  and scorers for cues, extraction and the register

Next: evaluation report page (M3), web UI (M4).

## Quick start

Requires macOS (for the synthetic demo audio), [uv](https://docs.astral.sh/uv/)
and an Anthropic or OpenAI API key for the extraction step. Put the key in a
`.env` file at the repository root (git-ignored):

```
ANTHROPIC_API_KEY=...
# or
OPENAI_API_KEY=...
```

```bash
uv sync
uv run pytest
uv run elicitsense run data/meetings/m1_kickoff.txt
uv run elicitsense eval-cues runs data/gold/harbour_physio.json
uv run elicitsense eval-extract runs data/gold/harbour_physio.json
uv run elicitsense merge runs -o runs/register.json
uv run elicitsense eval-merge runs/register.json data/gold/harbour_physio.json
```

`run` writes `runs/<meeting>/segments.json`, `cues.json` and
`requirements.json`; `merge` combines every meeting in `runs/` (ordered by
meeting date) into `runs/register.json`. `--provider auto` (the default) uses whichever key is
set, preferring Anthropic; `--provider openai --llm gpt-6.1-sol` picks
explicitly. Add `--skip-extract` to stop before the API call, or
`--setting internal` to run without uncertainty cues.

## Privacy and compliance

- Audio is transcribed locally; only transcript text is sent to the model.
- Cues are attached to requirements, never aggregated per person.
- `--setting internal` disables cues: the EU AI Act (Art. 5(1)(f)) prohibits
  AI emotion inference in workplace settings. The intended use is consented
  client elicitation sessions.
- The demo meetings are fictional and synthetic.

## Results so far

Three synthetic meetings, 55 utterances, 19 gold requirements, 9 gold
cross-meeting relations and 1 status change. LLM: gpt-6.1-sol.

| Measure | Result |
|---|---|
| Uncertainty flags vs gold (6 hesitant utterances) | precision 1.00, recall 1.00 |
| Requirement recall | 1.00 (19 of 19) |
| Requirement precision, splits counted as correct | 0.97 (strict one-to-one: 0.63) |
| Extracted items whose quotes verified | 30 of 30 |
| Type agreement / uncertainty agreement on matched items | 0.89 / 0.89 |
| Register relations found with the right kind (3 merge runs) | 7 of 9 every run (8 of 9 ignoring kind) |
| Register relation precision (3 merge runs) | 0.80 to 0.90 |
| Status changes / open conflicts after meeting 3 | 1 of 1 / 0 |

The model splits requirements more finely than the gold labels (10 splits,
such as "choose a practitioner" and "see their available times"), which is
why strict one-to-one precision is low. Of the two register relations not
found with the right kind, one is labelled "supersedes" where the gold says
"conflicts" (a login-only proposal that was reversed within the same
meeting), and one is a representation difference: the model kept the SMS
reminder as a restatement and added the email reminder as new, where the
gold has one combined reminder requirement superseding the old one.

Read these numbers as a smoke test, not a benchmark. The hesitation was
scripted and rendered by speech synthesis, there is one fictional project,
and the gold set was used while developing the prompts. Role-played human
recordings and a held-out project are the next tests.

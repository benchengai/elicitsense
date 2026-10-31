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

Milestone M1 (pipeline CLI). Works today:

- scripted demo meetings rendered to audio with macOS `say` (`data/meetings/`)
- local transcription with word timestamps (faster-whisper, nothing uploaded)
- uncertainty cues from hedges, filled pauses, long pauses and slow speech
- requirement extraction with Claude, followed by deterministic quote
  verification, cue attachment and quality checks
- gold labels for the three demo meetings (`data/gold/harbour_physio.json`)

Next: cross-meeting merge (M2), evaluation report (M3), web UI (M4).

## Quick start

Requires macOS (for the synthetic demo audio), [uv](https://docs.astral.sh/uv/)
and an Anthropic API key for the extraction step.

```bash
uv sync
uv run pytest
export ANTHROPIC_API_KEY=...        # only needed for extraction
uv run elicitsense run data/meetings/m1_kickoff.txt
uv run elicitsense eval-cues runs data/gold/harbour_physio.json
```

`run` writes `runs/<meeting>/segments.json`, `cues.json` and
`requirements.json`. Add `--skip-extract` to stop before the API call, or
`--setting internal` to run without uncertainty cues.

## Privacy and compliance

- Audio is transcribed locally; only transcript text is sent to the model.
- Cues are attached to requirements, never aggregated per person.
- `--setting internal` disables cues: the EU AI Act (Art. 5(1)(f)) prohibits
  AI emotion inference in workplace settings. The intended use is consented
  client elicitation sessions.
- The demo meetings are fictional and synthetic.

## Results so far

On the three synthetic meetings, the uncertainty flags match the gold labels
on all 6 hesitant utterances with no false alarms (55 utterances total). This
is an easy setting: the hesitation was scripted and rendered by speech
synthesis. Role-played human recordings are the next test.

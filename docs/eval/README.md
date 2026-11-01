# ElicitSense evaluation report

What this measures: how well each step of the pipeline does against
hand-labelled gold data, and how the choice of LLM changes quality, cost and
speed. Every number here comes from `elicitsense eval-*` and
`elicitsense bench` runs; the per-run files are in `runs/` (not committed) and
the tables below are generated from them.

## Setup

| | |
|---|---|
| Projects | `harbour_physio`: 3 meetings, 55 utterances, 19 gold requirements, 9 relations, 1 status change (development set: prompts were written against it). `fernhill_bakery`: 3 meetings, 40 utterances, 21 gold requirements, 7 relations, 1 status change, 1 conflict left open (held out: written before any model ran on it, prompts not changed after) |
| Audio | Scripted meetings rendered with macOS `say`, four to five voices, hesitations scripted as pauses, fillers and slower delivery |
| Transcription | faster-whisper `small.en`, int8 on CPU, word timestamps, run once per meeting and shared by every model |
| Uncertainty cues | Rule-based (hedges, filled pauses, pauses ≥ 0.7 s, speech slower than 0.8 × the speaker's median); a line is flagged when it shows two kinds |
| LLM steps | Extraction (one call per meeting) and merge (one call per meeting), both with strict JSON-schema output |
| Models | API: `gpt-6.1-sol`, `gpt-6.1-terra`, `gpt-6-luna`. Local: `qwen3:8b` through Ollama on an Apple M5 with 16 GB, reasoning mode off |
| Runs | 3 full project runs per model and project |
| Cost | Published standard per-token prices as of 2026-11-01 ([pricing.py](../../elicitsense/pricing.py)); local runs have no per-token cost |

How items are matched: extracted and gold requirements are paired by the
transcript lines their evidence cites. An extra item that cites lines of an
already-paired gold item is a *split* (finer granularity, counted as correct
for precision; strict precision counts it as wrong). An item that only records
a status change or mentions an existing requirement is a *mention*.
Relations are scored after mapping register ids to gold ids through that
pairing.

## Transcription and uncertainty cues (no LLM)

| | Development set | Held-out set |
|---|---|---|
| Hesitant utterances (gold) | 6 | 4 |
| Flag precision | 1.00 (6 of 6) | 1.00 (3 of 3) |
| Flag recall | 1.00 (6 of 6) | 0.75 (3 of 4) |

The held-out miss is f3:L008 ("Um... I still haven't decided"). Only the
filler was detected. Whisper's word timestamps put 0.64 s between "Um" and
"I", just under the 0.7 s pause threshold, and the slower delivery did not
register because the speaker had only four short lines in that meeting to
set a baseline. The thresholds were not changed after seeing this.

Transcription errors on the held-out set are the realistic kind: product and
company names ("Xero" heard as "zero"), domain words ("cutoff" as "QTOF",
"cafés" as "Hafez"), and numbers ("not two" as "not to"). Quotes are verified
against the transcript, not the script, so these errors do not cause
rejections; they show up in the extracted wording instead.

## LLM comparison

Generated with:

```bash
uv run elicitsense bench data/projects/<project> --runs 3 --free-ids \
  -o runs/bench/<project>/baseline --report docs/eval/<project>.md \
  -m openai:gpt-6.1-sol openai:gpt-6.1-terra openai:gpt-6-luna ollama:qwen3:8b
```

These are the M3 runs, before merge link ids were restricted (`--free-ids`
reproduces that). "Invalid links" counts links the validator refused because
they named an unknown id or linked a requirement to itself.

### Development set (`harbour_physio`)

Mean across successful runs, range in brackets. Cost and latency are per full project run (every meeting extracted, then merged) and include failed runs. `a>b` extracts with a and merges with b.

Merge link ids: free text.

| Model | Req. recall | Req. precision | Strict 1:1 precision | Quotes verified | Uncertainty agr. | Relations, exact kind | Relation precision | Status changes | Open conflicts right | Invalid links | Cost (USD) | Time (s) | Failed runs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `openai:gpt-6.1-sol` | 1.00 | 1.00 | 0.61 | 1.00 | 0.93 (0.89–0.95) | 0.78 | 0.81 (0.80–0.82) | 1.00 | 3 of 3 | 0.0 | 0.091 (0.087–0.096) | 83 (80–84) | 0 of 3 |
| `openai:gpt-6.1-terra` | 1.00 | 0.99 (0.97–1.00) | 0.62 (0.59–0.66) | 1.00 | 0.89 | 0.52 (0.44–0.56) | 0.96 (0.89–1.00) | 1.00 | 3 of 3 | 0.0 | 0.047 (0.043–0.049) | 97 (92–100) | 0 of 3 |
| `openai:gpt-6-luna` | 1.00 | 1.00 | 0.63 (0.61–0.66) | 1.00 | 0.89 | 0.52 (0.33–0.67) | 0.90 (0.80–1.00) | 1.00 | 1 of 3 | 0.0 | 0.007 (0.006–0.008) | 137 (106–181) | 0 of 3 |
| `ollama:qwen3:8b` | 1.00 | 0.98 (0.93–1.00) | 0.79 (0.70–0.83) | 1.00 | 0.88 (0.84–0.89) | 0.04 (0.00–0.11) | 0.42 (0.00–1.00) | 0.67 (0.00–1.00) | 3 of 3 | 16.7 (10.0–23.0) | 0.000 | 544 (250–1085) | 0 of 3 |

### Held-out set (`fernhill_bakery`)

Mean across successful runs, range in brackets. Cost and latency are per full project run (every meeting extracted, then merged) and include failed runs. `a>b` extracts with a and merges with b.

Merge link ids: free text.

| Model | Req. recall | Req. precision | Strict 1:1 precision | Quotes verified | Uncertainty agr. | Relations, exact kind | Relation precision | Status changes | Open conflicts right | Invalid links | Cost (USD) | Time (s) | Failed runs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `openai:gpt-6.1-sol` | 1.00 | 1.00 | 0.74 (0.72–0.75) | 1.00 | 1.00 | 0.86 | 0.88 | 1.00 | 3 of 3 | 0.0 | 0.083 (0.078–0.088) | 71 (65–76) | 0 of 3 |
| `openai:gpt-6.1-terra` | 1.00 | 0.99 (0.96–1.00) | 0.80 (0.78–0.81) | 1.00 | 1.00 | 0.67 (0.57–0.71) | 0.79 (0.67–0.86) | 1.00 | 0 of 3 | 0.0 | 0.038 (0.037–0.039) | 78 (77–79) | 0 of 3 |
| `openai:gpt-6-luna` | 1.00 | 1.00 | 0.80 (0.75–0.84) | 1.00 | 1.00 | 0.67 (0.57–0.86) | 0.87 (0.78–1.00) | 1.00 | 0 of 3 | 0.0 | 0.005 | 77 (76–80) | 0 of 3 |
| `ollama:qwen3:8b` | 0.98 (0.95–1.00) | 0.97 (0.96–1.00) | 0.86 (0.81–0.91) | 1.00 | 0.95 | 0.24 (0.14–0.29) | 0.41 (0.33–0.50) | 0.00 | 0 of 3 | 20.0 (19.0–22.0) | 0.000 | 371 (254–514) | 0 of 3 |

"Open conflicts right" counts runs whose register, after the last meeting,
has exactly the open conflicts the gold expects: none for the development set,
the credit-limit disagreement for the held-out set. Time is the sum of call
latencies for one project run, with calls made one after another.

## Findings

1. **Extraction recall does not separate the models.** All four models find
   0.98 to 1.00 of the gold requirements on both sets, including the 8B model
   running locally, and every kept quote verifies against the transcript.
   Smaller models split requirements less finely, which is why their strict
   one-to-one precision is higher. Recall hides real differences in what was
   extracted, though: see finding 10.
2. **Linking requirements across meetings does.** Relations found with the right
   kind: `gpt-6.1-sol` 0.78 (development) and 0.86 (held out), with almost no
   spread between runs; `gpt-6.1-terra` and `gpt-6-luna` 0.52 to 0.67 with a
   wider spread; `qwen3:8b` 0.04 and 0.24.
3. **Cheaper models lose an unresolved disagreement.** In the held-out project,
   accounts wants to block orders above a credit limit and dispatch wants to
   keep delivering; the last meeting leaves it undecided. `gpt-6.1-sol` kept
   that conflict open in all three runs. `gpt-6.1-terra` kept it in none,
   either not linking the two requirements or calling one a refinement of the
   other. `gpt-6-luna` kept it in one run, and that run also left a second,
   unexpected conflict open. For a requirements tool this is the
   costly kind of error, because the disagreement disappears without a trace.
4. **The local model fails at merge in a specific, contained way.** Most of
   its proposed links name ids that do not exist or put a register id where
   the new requirement's id belongs (10 to 23 such links per run). The
   validator drops them and records why, so the register is never corrupted,
   but few relations survive. It also missed the held-out status change
   (product ratings dropped) in all three runs. Restricting ids in the JSON
   schema is tested below (finding 8).
5. **Extraction is most of the bill.** With `gpt-6.1-sol`, extraction costs
   $0.052 to $0.053 per project run and merge $0.031 to $0.038. A full
   `gpt-6-luna` run costs $0.005 to $0.008. Given findings 1 and 2,
   `gpt-6-luna` for extraction and `gpt-6.1-sol` for merge should cost about
   $0.034 to $0.041 per project run, under half of an all-`gpt-6.1-sol` run.
   Measured below (finding 9).
6. **Some misses are representation differences.** On the held-out set every
   API model recorded the card-payment decision as a status change of the open
   question (to confirmed) plus a separate surcharge requirement, where the
   gold has one requirement refining the open question. The scorer counts
   that as a missed "refines". The development set has the same pattern
   (G14). The gold labels were not changed.
7. **Local inference is slow on a laptop.** 250 to 1085 seconds per project
   run on a 16 GB M5, against 71 to 137 seconds for the API models. The slow
   end was recorded while the machine was low on battery and swapping.

## Experiment: restricted ids and per-step routing

Two changes, following findings 4 and 5:

- **Restricted ids.** The merge schema now limits `new_id` to the ids of the
  newest meeting's requirements and `target_id` to ids in the register or the
  newest meeting (`schema_for` in [merge.py](../../elicitsense/merge.py)), so
  constrained decoding cannot produce an id that is not in the prompt. The
  prompt is unchanged.
- **Per-step routing.** `a>b` extracts with model a and merges with model b.

Every run here reuses the extraction outputs of the matching M3 run and only
calls the merge step again, so differences come from the merge step alone. No
prompt or gold label was changed. The held-out set had already been scored
once (above), so it is no longer blind for this comparison.

```bash
uv run elicitsense bench data/projects/<project> --runs 3 \
  -o runs/bench/<project>/constrained-ids --reuse-extraction runs/bench/<project>/baseline \
  -m openai:gpt-6.1-sol openai:gpt-6.1-terra openai:gpt-6-luna ollama:qwen3:8b \
     "openai:gpt-6-luna>openai:gpt-6.1-sol" "ollama:qwen3:8b>openai:gpt-6.1-sol"
```

Means over three runs, development set / held-out set. Rows without "free ids"
use restricted ids. Full tables:
[development](harbour_physio-constrained-ids.md),
[held out](fernhill_bakery-constrained-ids.md).

| Extract > merge | Relations, exact kind (dev / held out) | Relation precision | Status changes | Open conflicts right | Invalid links per run | Cost per project run (USD) |
|---|---|---|---|---|---|---|
| `gpt-6.1-sol`, free ids (M3) | 0.78 / 0.86 | 0.81 / 0.88 | 1.00 / 1.00 | 3/3 / 3/3 | 0.0 / 0.0 | 0.091 / 0.083 |
| `gpt-6.1-sol` | 0.78 / 0.86 | 0.85 / 0.88 | 1.00 / 1.00 | 3/3 / 3/3 | 0.0 / 0.0 | 0.093 / 0.085 |
| `gpt-6.1-terra`, free ids (M3) | 0.52 / 0.67 | 0.96 / 0.79 | 1.00 / 1.00 | 3/3 / 0/3 | 0.0 / 0.0 | 0.047 / 0.038 |
| `gpt-6.1-terra` | 0.52 / 0.67 | 0.93 / 0.67 | 1.00 / 1.00 | 3/3 / 0/3 | 0.0 / 0.0 | 0.049 / 0.039 |
| `gpt-6-luna`, free ids (M3) | 0.52 / 0.67 | 0.90 / 0.87 | 1.00 / 1.00 | 1/3 / 0/3 | 0.0 / 0.0 | 0.007 / 0.005 |
| `gpt-6-luna` | 0.56 / 0.62 | 0.84 / 0.82 | 1.00 / 1.00 | 1/3 / 0/3 | 0.0 / 0.0 | 0.007 / 0.006 |
| `qwen3:8b`, free ids (M3) | 0.04 / 0.24 | 0.42 / 0.41 | 0.67 / 0.00 | 3/3 / 0/3 | 16.7 / 20.0 | 0.000 / 0.000 |
| `qwen3:8b` | 0.04 / 0.81 | 0.44 / 0.71 | 0.00 / 0.00 | 3/3 / 2/3 | 3.3 / 11.0 | 0.000 / 0.000 |
| `gpt-6-luna` > `gpt-6.1-sol` | 0.67 / 0.76 | 0.87 / 0.85 | 1.00 / 1.00 | 3/3 / 3/3 | 0.0 / 0.0 | 0.044 / 0.035 |
| `qwen3:8b` > `gpt-6.1-sol` | 0.44 / 0.95 | 0.84 / 0.84 | 1.00 / 1.00 | 3/3 / 2/3 | 0.0 / 0.0 | 0.033 / 0.031 |

8. **Restricted ids remove the local model's invalid ids, but it is still not
   reliable at merge.** Every link it still gets refused is a requirement
   marked "same" as itself, which amounts to "new" (0 to 11 per run).
   Its relation recall rose on the held-out set (0.24 to 0.81) and stayed at
   0.04 on the development set, and it missed the status change in every run
   on both sets. The API models never produced invalid ids, and their scores
   moved only within run-to-run noise. Restricted ids are now the default.
9. **Routing extraction to a cheap model halves the cost and keeps the
   conflict.** `gpt-6-luna` > `gpt-6.1-sol` costs $0.044 and $0.035 per
   project run against $0.093 and $0.085 for `gpt-6.1-sol` alone (53% and 59%
   less). It kept the unresolved conflict in all three held-out runs, which
   `gpt-6-luna` alone did in none, and got every status change right. It
   finds about one relation fewer per project than `gpt-6.1-sol` alone (0.67
   and 0.76 against 0.78 and 0.86).
10. **Extraction differs more than recall shows.** With the merge model fixed
    at `gpt-6.1-sol`, changing only who extracted moves relation recall from
    0.78 to 0.67 (`gpt-6-luna`) and 0.44 (`qwen3:8b`) on the development set,
    and from 0.86 to 0.76 and 0.95 on the held-out set. On the development
    set, `qwen3:8b` recorded the login-only proposal, which the meeting
    reversed a few lines later, as confirmed instead of superseded, and left out
    that account holders can see past appointments, so the merge had nothing
    to link. On the held-out set it kept card payment and its surcharge in one
    requirement, which is the form the gold uses (finding 6). Requirement
    recall sees neither effect because it only checks which lines are cited.
    Scoring extraction properly needs a gold status for each requirement.

## Not covered yet

- Gold statuses per requirement, so extraction is scored on status as well as
  coverage (finding 10).
- A merge schema that also rules out linking a requirement to itself.
- `qwen3:8b` with reasoning mode on. A single-meeting trial gave the same
  requirements in 1.5 times the time; the full bench was stopped when the
  machine slept on low battery.
- Claude models: no Anthropic key was configured for this round. The bench
  supports them (`anthropic:claude-opus-5-5`).

## Limitations

- Synthetic audio from speech synthesis, with scripted hesitation. Real
  meetings have overlapping speech, accents and background noise.
- Two small fictional projects (40 gold requirements, 16 relations), so a
  single relation moves recall by 0.11 to 0.14. Differences of that size
  between models are within noise.
- One author wrote the prompts, the scripts and the gold labels. The held-out
  project limits overfitting to one project, not to one person's way of
  describing requirements.
- Matching is automatic (evidence-line overlap) and was spot-checked, not
  fully adjudicated by a second annotator.

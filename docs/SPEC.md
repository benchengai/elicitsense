# ElicitSense — product and technical spec

ElicitSense turns requirements-elicitation meeting recordings into a reviewable
requirements register. Every requirement links back to the exact words and
timestamp it came from, carries quality checks, and is flagged for follow-up
when the stakeholder sounded unsure while stating it.

It is the flagship of a five-app portfolio derived from the systematic mapping
study *Emotions in Software Engineering* (Cheng, Wang, Arora, Hoang, Liu) and
productises the multimodal requirements-elicitation prototype MEmoRE
(Cheng et al., IEEE RE 2023).

## 1. Why this exists

Generic meeting assistants already transcribe, summarise, draft user stories
and answer questions across meetings. What they do not do well:

| Gap | What ElicitSense does instead |
|---|---|
| Output is meeting notes or draft stories, not requirements | A typed register: functional, non-functional, constraint; acceptance criteria; assumptions; open questions |
| Generated items cannot be audited | Every item cites a verbatim quote and timestamp; items whose quote is not in the transcript are rejected |
| No view of how requirements change across meetings | Cross-meeting matching: same / refines / conflicts / new, with version history |
| Emotion analytics score people | Uncertainty cues are attached to requirements, never to people |
| No published accuracy | Ships with a gold-labelled evaluation set and an evaluation page |

### Research basis

- Requirements engineering is one of the least-studied phases for emotion in SE
  (7 of 57 studies), and communication-and-collaboration research has no RE
  studies at all, although stakeholder interaction peaks there.
- Every communication study in the map is observational; none evaluates a tool
  that supports communication as it happens.
- Decision-making-bias research is almost entirely post-hoc (6 of 7 studies mine
  artefacts after decisions were made); the study recommends bringing those
  signals to the point where requirement decisions are taken.
- Requirement changes, especially late ones, are a primary trigger of emotional
  responses (Madampe et al. 2020, 2022, 2023).
- Facial configurations are not reliable fingerprints of discrete emotions
  (Barrett et al. 2019), so ElicitSense reports *cues* ("long pause, hedging")
  rather than emotion labels ("angry").

## 2. Users and core loop

Primary user: a business analyst, product manager or consultant who runs
discovery workshops with clients.

1. Upload one or more recordings of meetings about the same project.
2. ElicitSense transcribes locally, extracts requirements, verifies evidence,
   attaches uncertainty cues, and merges them into the project register.
3. The analyst reviews: confirm, edit, reject, or mark for follow-up. Clicking
   any evidence plays that moment of the recording.
4. Ask questions of the register ("Who asked for SMS reminders and did it
   change?"); every answer cites evidence.
5. Export to Jira CSV or a Markdown requirements document.

## 3. Compliance and privacy (design constraints, not features)

- Transcription runs on the analyst's machine; audio is never uploaded.
- Only transcript text is sent to the LLM.
- Uncertainty cues are computed from text and timing (pauses, hedges, filled
  pauses, speech rate). Facial analysis is out of scope for the MVP and, if
  added, off by default.
- Cues are shown per requirement, never aggregated per person. There is no
  per-person score anywhere in the product.
- Cues are disabled by default for internal team meetings: the EU AI Act
  (Art. 5(1)(f)) prohibits AI emotion inference in workplace settings. The
  intended setting is consented client elicitation sessions.
- All recordings in the public demo are synthetic or role-played with consent.

## 4. Architecture

```
recording ──► transcribe (faster-whisper, local, word timestamps)
                 │
          speaker turns (MVP: provided turns file; later: diarization adapter)
                 │
                 ▼
          segments.json ──► cues (text hedges + timing) ──► cues.json
                 │
                 ▼
          extract (Claude or GPT, structured output) ──► candidates
                 │
          verify (quote must match its cited segment) ──► requirements.json
                 │
          merge across meetings (match + relation) ──► register (SQLite)
                 │
       ┌─────────┼──────────────┐
    web UI     Q&A agent      export
  (Next.js)  (tools + cites)  (Jira CSV / Markdown)
                 │
             MCP server (later)
```

### Data model (register)

```
Requirement
  id            REQ-001
  type          functional | non_functional | constraint
  statement     "Patients can book an appointment without creating an account."
  rationale     optional
  acceptance    list of acceptance criteria (may be empty → quality issue)
  stakeholder   speaker label who stated it
  status        proposed | confirmed | disputed | rejected | superseded
  evidence      [{meeting, segment_id, start, end, quote}]
  quality       [{kind: ambiguous_term | missing_acceptance | compound, detail}]
  uncertainty   {flag: bool, cues: [{kind, detail, segment_id}]}
  relations     [{kind: refines | conflicts | supersedes, target}]
  history       [{meeting, change}]
```

### Evidence verification

The LLM must return, for each requirement, the segment ids it relies on and a
verbatim quote. A requirement is kept only if its quote matches the text of a
cited segment (normalised fuzzy match). Unsupported items are reported, not
silently dropped, so the evaluation page can show the rejection rate.

### Uncertainty cues (MVP)

Per segment, from transcript text and word timings:

- hedging phrases ("I think", "maybe", "not sure", "probably", "I guess")
- filled pauses ("um", "uh")
- long silent gaps inside the utterance (≥ 0.7 s)
- speech rate well below the speaker's own median

A requirement is flagged when any evidence segment has two or more cue kinds.
The flag reads "needs confirmation", listing the cues.

## 5. Evaluation

The repository includes three scripted meetings about one fictional project,
with gold labels: the requirements each meeting introduces, their evidence
lines, which lines carry uncertainty, and how meeting 2 and 3 change meeting 1.

Metrics on the evaluation page:

- requirement extraction precision, recall, F1 (matched by evidence overlap,
  then manually spot-checked)
- evidence validity rate (share of extracted items whose quote verifies)
- uncertainty-flag precision and recall against gold
- cross-meeting relation accuracy (refines / conflicts / supersedes)

## 6. Milestones

| | Scope | Done when |
|---|---|---|
| M0 | Scripts, gold labels, synthetic audio | 3 meetings render to WAV with ground-truth turns |
| M1 | CLI: transcribe → cues → extract → verify | `requirements.json` for meeting 1 with verified evidence |
| M2 | Cross-meeting merge and register | conflicts between meeting 1 and 2 detected |
| M3 | Evaluation script and report | metrics computed against gold |
| M4 | Web UI: register, synced player, review actions | demo runs locally |
| M5 | Q&A with cited answers, export | answers cite segments; Jira CSV imports |
| M6 | Demo mode and deploy | static demo on Vercel, no API key needed |
| Later | Diarization adapter, role-played recordings, MCP server | |

Demo mode serves outputs produced by real pipeline runs on the public demo
meetings. It never serves hand-written outputs presented as model output.

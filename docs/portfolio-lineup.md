# Portfolio lineup: from a 57-study map to five products

Source: *Emotions in Software Engineering: A Systematic Mapping Study*.
Each app targets an empty or fragmented cell of the study's
emotion-category × SDLC-phase map.

| # | App | Map cell | One line |
|---|---|---|---|
| 1 | **ElicitSense** (flagship) | Communication × Requirements (0 studies); Tools × Requirements (2) | Meeting recordings → evidence-linked requirements register with uncertainty cues and cross-meeting change tracking |
| 2 | PR Tone Coach | Communication × Design/Implementation (0) | Pre-send code review comment checker: target (person/code/tool), pushback risk, rewrite |
| 3 | ReleasePulse | Decision bias × Requirements (1) | App reviews and tickets → emotion by release and feature → prioritisation evidence (can feed ElicitSense's register) |
| 4 | SentiBench | Tools × Cross-phase (10, fragmented) | Evaluation harness: lexicon vs SE-specific vs LLM sentiment classifiers on SE benchmarks |
| 5 | SprintWeather | Team health × Maintenance (0); intervention gap | Opt-in, self-reported, k-anonymous team pulse for retrospectives |

Build order, aimed at AI engineering roles: ElicitSense first and in depth
(evaluation, model comparison, Q&A agent), then SentiBench as an LLM
evaluation project (LLMs against lexicon and SE-specific sentiment tools on
published SE datasets, with cost and agreement analysis). Apps 2, 3 and 5
wait until those two are finished.

Shared rules for every demo:

- Sample-data mode that works with no API key, in under 30 seconds.
- "Research basis" and "Limitations" panels on every page.
- Claims say "grounded in", never "validated".
- No per-person emotion scores; no workplace emotion inference.

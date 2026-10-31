"""Extract requirements from one meeting transcript with an LLM, then verify them.

The model only proposes requirements and cites evidence. Everything that has
to be trustworthy is done deterministically afterwards: quote verification,
uncertainty cues, quality checks and ids. That keeps the provider swappable:
Claude (Anthropic) and GPT (OpenAI) share the same prompt, schema and checks.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from . import quality
from .llm import LLMError as ExtractionError
from .llm import complete_json
from .verify import quote_matches

SYSTEM = """You are a requirements analyst. You read the transcript of one requirements \
elicitation meeting and extract the software requirements that participants stated, \
proposed or agreed in this meeting.

Rules:
- One requirement per distinct need. Split compound statements.
- Write each statement as one plain-English sentence, keeping numbers, limits and \
conditions exactly as said.
- Include only what the meeting supports. List acceptance criteria only if they were \
stated or directly specified in the transcript; otherwise leave the list empty.
- Facts that limit the solution (an external system's capability, a legal or data rule) \
are constraints.
- evidence: cite every segment the requirement relies on. For each, copy a quote \
verbatim from that segment's text: exact words, at least four words, or the whole \
segment if it is shorter. Quotes are checked automatically against the transcript, and \
requirements whose quotes do not match are discarded.
- stakeholder: the speaker label of whoever asked for or stated the requirement. Use the \
analyst only when the analyst proposed it.
- status: "confirmed" when the client side explicitly agreed in this meeting, \
"open_question" when it was raised but not decided, "deferred" when it was explicitly \
postponed, "superseded" when it was proposed and then replaced by a different version \
later in this same meeting, otherwise "proposed".
- Keep superseded proposals as their own requirement, alongside the version that \
replaced them, so the change is recorded.
- type: "functional", "non_functional" (performance, usability, accessibility and other \
quality attributes) or "constraint".
- open_questions: questions raised in this meeting and left unresolved.
- Do not describe or judge anyone's emotions."""

STATUSES = ("proposed", "confirmed", "open_question", "deferred", "superseded")

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["requirements", "open_questions"],
    "properties": {
        "requirements": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["statement", "type", "stakeholder", "status", "rationale",
                             "acceptance_criteria", "evidence"],
                "properties": {
                    "statement": {"type": "string"},
                    "type": {"type": "string", "enum": ["functional", "non_functional", "constraint"]},
                    "stakeholder": {"type": "string"},
                    "status": {"type": "string", "enum": list(STATUSES)},
                    "rationale": {"type": "string"},
                    "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["segment_id", "quote"],
                            "properties": {
                                "segment_id": {"type": "string"},
                                "quote": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "open_questions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["question", "segment_ids"],
                "properties": {
                    "question": {"type": "string"},
                    "segment_ids": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}


class Evidence(BaseModel):
    segment_id: str
    quote: str


class Candidate(BaseModel):
    statement: str
    type: Literal["functional", "non_functional", "constraint"]
    stakeholder: str
    status: Literal["proposed", "confirmed", "open_question", "deferred", "superseded"]
    rationale: str
    acceptance_criteria: list[str]
    evidence: list[Evidence]


class OpenQuestion(BaseModel):
    question: str
    segment_ids: list[str]


class Extraction(BaseModel):
    requirements: list[Candidate]
    open_questions: list[OpenQuestion]


def _fmt_time(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def render_transcript(transcript: dict) -> str:
    m = transcript["meeting"]
    lines = [f"Meeting: {m.get('title', m['id'])} ({m.get('date', 'undated')})", ""]
    for seg in transcript["segments"]:
        lines.append(f"[{seg['id']} | {seg['speaker']} | {_fmt_time(seg['start'])}] {seg['text']}")
    return "\n".join(lines)


def call_model(transcript: dict, provider: str = "auto", model: str | None = None) -> tuple[Extraction, dict]:
    text, meta = complete_json(SYSTEM, render_transcript(transcript), SCHEMA, "requirements_extraction",
                               provider, model)
    return Extraction.model_validate_json(text), meta


def assemble(transcript: dict, extraction: Extraction, cues: dict | None) -> dict:
    meeting_id = transcript["meeting"]["id"]
    segs = {s["id"]: s for s in transcript["segments"]}
    speakers = {s["speaker"] for s in transcript["segments"]}
    cue_segs = (cues or {}).get("segments", {})

    requirements, rejected = [], []
    for cand in extraction.requirements:
        verified, failed = [], []
        for ev in cand.evidence:
            seg = segs.get(ev.segment_id)
            if seg and quote_matches(ev.quote, seg["text"]):
                verified.append({
                    "meeting": meeting_id, "segment_id": seg["id"], "start": seg["start"],
                    "end": seg["end"], "speaker": seg["speaker"], "quote": ev.quote,
                })
            else:
                failed.append({"segment_id": ev.segment_id, "quote": ev.quote,
                               "reason": "unknown segment" if not seg else "quote not found in segment"})
        if not verified:
            rejected.append({"statement": cand.statement, "failed_evidence": failed})
            continue

        uncertainty_cues = [
            {**c, "segment_id": ev["segment_id"]}
            for ev in verified
            if cue_segs.get(ev["segment_id"], {}).get("flag")
            for c in cue_segs[ev["segment_id"]]["cues"]
        ]
        requirements.append({
            "id": f"REQ-{meeting_id}-{len(requirements) + 1:03d}",
            "type": cand.type,
            "statement": cand.statement,
            "rationale": cand.rationale,
            "acceptance": cand.acceptance_criteria,
            "stakeholder": cand.stakeholder if cand.stakeholder in speakers else "UNKNOWN",
            "status": cand.status,
            "evidence": verified,
            "dropped_evidence": failed,
            "quality": quality.check(cand.statement, cand.type, cand.acceptance_criteria),
            "uncertainty": {
                "flag": bool(uncertainty_cues),
                "label": "needs confirmation" if uncertainty_cues else None,
                "cues": uncertainty_cues,
            },
        })

    return {
        "meeting": transcript["meeting"],
        "cues_enabled": cues is not None,
        "requirements": requirements,
        "rejected": rejected,
        "open_questions": [q.model_dump() for q in extraction.open_questions],
    }

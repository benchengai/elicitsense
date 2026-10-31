"""Uncertainty cues from transcript text and word timing.

These are cues, not emotion labels: a long pause or a hedge says the
statement may need confirming, not what the speaker felt. Cues are computed
per segment and later attached to requirements; nothing is aggregated per
person.
"""

from __future__ import annotations

import re
import statistics

HEDGES = [
    "i think", "i believe", "i guess", "i suppose", "maybe", "perhaps", "probably",
    "not sure", "i don't know", "don't really know", "we'd have to see", "kind of", "sort of",
]
# Whisper spells the same filler several ways ("uh" often comes out as "ah", "hmm" as "hum").
FILLED_PAUSES = {"um", "umm", "uh", "uhm", "ah", "er", "erm", "hmm", "hm", "hum", "mm"}

PAUSE_S = 0.7          # silent gap inside an utterance
SLOW_RATIO = 0.8       # speech rate below this share of the speaker's median
MIN_WORDS_FOR_RATE = 4
MIN_SEGMENTS_FOR_BASELINE = 3
MIN_KINDS_TO_FLAG = 2

_TOKEN_RE = re.compile(r"[^a-z']+")


def _norm_word(w: str) -> str:
    return _TOKEN_RE.sub("", w.lower().replace("’", "'"))


def _norm_text(text: str) -> str:
    return " " + " ".join(_norm_word(w) for w in text.split() if _norm_word(w)) + " "


def _rate(seg: dict) -> float | None:
    words = seg["words"]
    if len(words) < MIN_WORDS_FOR_RATE:
        return None
    span = words[-1]["end"] - words[0]["start"]
    return len(words) / span if span > 0 else None


def speaker_baselines(segments: list[dict]) -> dict[str, float]:
    rates: dict[str, list[float]] = {}
    for seg in segments:
        if (r := _rate(seg)) is not None:
            rates.setdefault(seg["speaker"], []).append(r)
    return {s: statistics.median(rs) for s, rs in rates.items() if len(rs) >= MIN_SEGMENTS_FOR_BASELINE}


def segment_cues(seg: dict, baseline: float | None) -> list[dict]:
    cues = []
    text = _norm_text(seg["text"])
    hedges = [h for h in HEDGES if f" {h} " in text]
    if hedges:
        cues.append({"kind": "hedging", "detail": ", ".join(f'"{h}"' for h in hedges)})

    fillers = [_norm_word(w["w"]) for w in seg["words"] if _norm_word(w["w"]) in FILLED_PAUSES]
    if fillers:
        cues.append({"kind": "filled_pause", "detail": ", ".join(f'"{f}"' for f in fillers)})

    words = seg["words"]
    gaps = [
        (round(b["start"] - a["end"], 2), b["w"])
        for a, b in zip(words, words[1:])
        if b["start"] - a["end"] >= PAUSE_S
    ]
    if gaps:
        cues.append({"kind": "long_pause", "detail": "; ".join(f'{g:.1f} s before "{w}"' for g, w in gaps)})

    rate = _rate(seg)
    if baseline and rate and rate < SLOW_RATIO * baseline:
        cues.append({"kind": "slow_speech", "detail": f"{rate:.1f} words/s vs speaker median {baseline:.1f}"})
    return cues


def compute_cues(transcript: dict) -> dict:
    segments = transcript["segments"]
    baselines = speaker_baselines(segments)
    out = {}
    for seg in segments:
        cues = segment_cues(seg, baselines.get(seg["speaker"]))
        kinds = sorted({c["kind"] for c in cues})
        out[seg["id"]] = {"flag": len(kinds) >= MIN_KINDS_TO_FLAG, "kinds": kinds, "cues": cues}
    return {
        "meeting": transcript["meeting"]["id"],
        "params": {
            "pause_s": PAUSE_S, "slow_ratio": SLOW_RATIO, "min_kinds_to_flag": MIN_KINDS_TO_FLAG,
        },
        "segments": out,
    }

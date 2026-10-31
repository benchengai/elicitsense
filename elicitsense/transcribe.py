"""Local transcription with word timestamps (faster-whisper).

Audio never leaves the machine. Speaker turns come from a turns file (ground
truth for synthetic meetings, or the output of a diarization step). Each turn
is transcribed on its own, which keeps speaker attribution exact and stops a
long silence or a misread turn from swallowing its neighbours. Without turns,
the whole file is transcribed and attributed to an unknown speaker.
"""

from __future__ import annotations

import json
from pathlib import Path

SAMPLE_RATE = 16_000
CLIP_PAD_S = 0.1
# Whisper tends to clean up disfluencies. Priming it with a disfluent prompt
# keeps "um", "uh" and "hmm" in the transcript, which the cue detector needs.
# On a long file the prompt can make Whisper skip its first window, so it is
# only used for per-turn clips, with an unprompted retry if a clip comes back empty.
DISFLUENT_PROMPT = "Um, so, uh... I think, hmm, maybe we could... I'm not sure."


def load_audio(audio: Path):
    """16 kHz mono PCM WAV is read directly; anything else goes through faster-whisper's decoder."""
    import wave

    import numpy as np
    from faster_whisper import decode_audio

    if audio.suffix.lower() == ".wav":
        with wave.open(str(audio), "rb") as w:
            if (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, SAMPLE_RATE):
                pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
                return pcm.astype(np.float32) / 32768.0
    return decode_audio(str(audio), sampling_rate=SAMPLE_RATE)


def clip_bounds(turn: dict, n_samples: int) -> tuple[int, int]:
    start = max(0, int((turn["start"] - CLIP_PAD_S) * SAMPLE_RATE))
    end = min(n_samples, int((turn["end"] + CLIP_PAD_S) * SAMPLE_RATE))
    return start, end


def _words(model, audio, offset: float, prompt: str | None) -> list[dict]:
    segments, _ = model.transcribe(
        audio,
        word_timestamps=True,
        initial_prompt=prompt,
        condition_on_previous_text=False,
    )
    words = []
    for seg in segments:
        for w in seg.words or []:
            if text := w.word.strip():
                words.append({
                    "w": text,
                    "start": round(offset + w.start, 3),
                    "end": round(offset + w.end, 3),
                    "p": round(w.probability, 3),
                })
    return words


def make_segment(index: int, speaker: str, line_id: str | None, words: list[dict]) -> dict:
    return {
        "id": f"S{index:03d}",
        "speaker": speaker,
        "source_line": line_id,
        "start": words[0]["start"],
        "end": words[-1]["end"],
        "text": " ".join(w["w"] for w in words),
        "words": words,
    }


def transcribe(audio_path: Path, turns_path: Path | None, meeting: dict, model_size: str = "small.en") -> dict:
    from faster_whisper import WhisperModel  # heavy import, keep it local

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    audio = load_audio(audio_path)
    segments, empty_turns = [], []

    if turns_path:
        for turn in json.loads(turns_path.read_text(encoding="utf-8"))["turns"]:
            a, b = clip_bounds(turn, len(audio))
            offset = a / SAMPLE_RATE
            words = _words(model, audio[a:b], offset, DISFLUENT_PROMPT) or _words(model, audio[a:b], offset, None)
            if not words:
                empty_turns.append(turn.get("line_id"))
                continue
            segments.append(make_segment(len(segments) + 1, turn["speaker"], turn.get("line_id"), words))
    else:
        if words := _words(model, audio, 0.0, None):
            segments.append(make_segment(1, "UNKNOWN", None, words))

    return {
        "meeting": {**meeting, "audio": str(audio_path)},
        "asr": {"model": model_size, "per_turn": bool(turns_path), "empty_turns": empty_turns},
        "segments": segments,
    }

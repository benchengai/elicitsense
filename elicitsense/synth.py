"""Render a scripted meeting to a 16 kHz mono WAV with macOS `say`.

This is a development utility for producing synthetic test meetings. It also
writes the ground-truth speaker turns, which stand in for diarization until a
diarization adapter exists.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

from .script import Script

SAMPLE_RATE = 16_000
# Distinct accents make the synthetic speakers easy to tell apart by ear.
DEFAULT_VOICES = {
    "ANALYST": "Samantha",
    "OWNER": "Karen",
    "FRONTDESK": "Moira",
    "DEVLEAD": "Daniel",
    "DISPATCH": "Rishi",
    "ACCOUNTS": "Tessa",
}
NORMAL_RATE = 185  # words per minute
SLOW_RATE = 140
PAUSE_MS = 700
TURN_GAP_S = 0.45


def _say_markup(text: str) -> str:
    # `say` embedded command for silence; "..." in scripts means a hesitation pause.
    return text.replace("...", f" [[slnc {PAUSE_MS}]] ")


def _render_line(text: str, voice: str, rate: int, out: Path) -> None:
    subprocess.run(
        [
            "say", "-v", voice, "-r", str(rate),
            "--file-format=WAVE", f"--data-format=LEI16@{SAMPLE_RATE}",
            "-o", str(out), _say_markup(text),
        ],
        check=True,
    )


def synthesize(script: Script, wav_path: Path, voices: dict[str, str] | None = None) -> list[dict]:
    if shutil.which("say") is None:
        raise RuntimeError("macOS `say` is required to synthesise meetings")
    voices = {**DEFAULT_VOICES, **(voices or {})}
    missing = [s for s in script.speakers if s not in voices]
    if missing:
        raise ValueError(f"no voice configured for speakers: {missing}")

    wav_path.parent.mkdir(parents=True, exist_ok=True)
    turns: list[dict] = []
    gap = b"\x00\x00" * int(TURN_GAP_S * SAMPLE_RATE)
    cursor = 0.0
    with tempfile.TemporaryDirectory() as tmp, wave.open(str(wav_path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        for line in script.lines:
            piece = Path(tmp) / f"{line.id}.wav"
            _render_line(line.text, voices[line.speaker], SLOW_RATE if line.slow else NORMAL_RATE, piece)
            with wave.open(str(piece), "rb") as w:
                if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, SAMPLE_RATE):
                    raise RuntimeError(f"unexpected audio format from `say` for {line.id}")
                frames = w.readframes(w.getnframes())
                duration = w.getnframes() / SAMPLE_RATE
            out.writeframes(frames)
            turns.append({
                "line_id": line.id,
                "speaker": line.speaker,
                "start": round(cursor, 3),
                "end": round(cursor + duration, 3),
                "script_text": line.text.replace("...", " ").replace("  ", " "),
            })
            out.writeframes(gap)
            cursor += duration + TURN_GAP_S
    return turns


def write_turns(turns: list[dict], path: Path) -> None:
    path.write_text(json.dumps({"turns": turns}, indent=2), encoding="utf-8")

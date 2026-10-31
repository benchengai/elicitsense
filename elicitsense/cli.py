"""Command-line entry point.

    elicitsense run data/meetings/m1_kickoff.txt         # synth → transcribe → cues → extract
    elicitsense eval-cues runs/ data/gold/harbour_physio.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import cues as cues_mod
from .script import parse_script

AUDIO_DIR = Path("data/audio")
RUNS_DIR = Path("runs")


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {path}")


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_synth(args) -> None:
    from .synth import synthesize, write_turns

    script = parse_script(args.script)
    wav = AUDIO_DIR / f"{script.id}.wav"
    turns = synthesize(script, wav)
    write_turns(turns, AUDIO_DIR / f"{script.id}.turns.json")
    print(f"wrote {wav} ({turns[-1]['end']:.0f} s, {len(turns)} turns)")


def cmd_transcribe(args) -> None:
    from .transcribe import transcribe

    meeting = {"id": args.meeting_id, "title": args.title or args.meeting_id, "date": args.date or ""}
    data = transcribe(Path(args.audio), Path(args.turns) if args.turns else None, meeting, args.model)
    _write(Path(args.out), data)


def cmd_cues(args) -> None:
    _write(Path(args.out), cues_mod.compute_cues(_read(Path(args.segments))))


def _extract(segments_path: Path, cues_path: Path | None, out: Path) -> None:
    import anthropic

    from .extract import ExtractionError, assemble, call_model

    transcript = _read(segments_path)
    try:
        extraction, meta = call_model(transcript)
    except ExtractionError as e:
        sys.exit(f"extraction failed: {e}")
    except anthropic.AuthenticationError:
        sys.exit("extraction failed: the Anthropic API key was rejected")
    except anthropic.RateLimitError as e:
        sys.exit(f"extraction failed: rate limited, retry after {e.response.headers.get('retry-after', '60')} s")
    except anthropic.APIStatusError as e:
        sys.exit(f"extraction failed: API error {e.status_code}: {e.message}")
    except anthropic.APIConnectionError:
        sys.exit("extraction failed: could not reach the Anthropic API")
    except TypeError as e:
        if "authentication" not in str(e):
            raise
        sys.exit("extraction failed: no Anthropic credentials. Set ANTHROPIC_API_KEY (see README).")
    result = assemble(transcript, extraction, _read(cues_path) if cues_path else None)
    result["llm"] = meta
    _write(out, result)
    print(f"{len(result['requirements'])} requirements kept, {len(result['rejected'])} rejected for unverifiable evidence")


def cmd_extract(args) -> None:
    _extract(Path(args.segments), Path(args.cues) if args.cues else None, Path(args.out))


def cmd_run(args) -> None:
    from .synth import synthesize, write_turns
    from .transcribe import transcribe

    script = parse_script(args.script)
    run_dir = RUNS_DIR / script.id
    wav, turns_path = AUDIO_DIR / f"{script.id}.wav", AUDIO_DIR / f"{script.id}.turns.json"
    if not wav.exists() or args.resynth:
        write_turns(synthesize(script, wav), turns_path)
        print(f"wrote {wav}")
    meeting = {"id": script.id, "title": script.title, "date": script.date}
    transcript = transcribe(wav, turns_path, meeting, args.model)
    _write(run_dir / "segments.json", transcript)

    cues_path = None
    if args.setting == "client":
        cues_path = run_dir / "cues.json"
        _write(cues_path, cues_mod.compute_cues(transcript))
    else:
        print("internal meeting: uncertainty cues disabled")

    if args.skip_extract:
        return
    _extract(run_dir / "segments.json", cues_path, run_dir / "requirements.json")


def cmd_eval_cues(args) -> None:
    gold = set(_read(Path(args.gold))["uncertain_lines"])
    tp = fp = fn = 0
    rows = []
    for cues_path in sorted(Path(args.runs).glob("*/cues.json")):
        cues = _read(cues_path)
        meeting = cues["meeting"]
        segments = _read(cues_path.with_name("segments.json"))["segments"]
        for seg in segments:
            key = f"{meeting}:{seg['source_line']}"
            flagged = cues["segments"][seg["id"]]["flag"]
            expected = key in gold
            tp += flagged and expected
            fp += flagged and not expected
            fn += expected and not flagged
            if flagged or expected:
                verdict = "TP" if flagged and expected else ("FP" if flagged else "FN")
                rows.append(f"  {verdict}  {key:<9} {', '.join(cues['segments'][seg['id']]['kinds']) or '-':<40} {seg['text'][:60]}")
    print("\n".join(rows))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    print(f"\nuncertainty flags: precision {precision:.2f}  recall {recall:.2f}  (tp={tp} fp={fp} fn={fn})")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="elicitsense")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("synth", help="render a scripted meeting to WAV with macOS say")
    s.add_argument("script")
    s.set_defaults(func=cmd_synth)

    s = sub.add_parser("transcribe", help="transcribe audio locally with word timestamps")
    s.add_argument("audio")
    s.add_argument("--turns", help="speaker turns JSON (from synth or diarization)")
    s.add_argument("--meeting-id", required=True)
    s.add_argument("--title")
    s.add_argument("--date")
    s.add_argument("--model", default="small.en")
    s.add_argument("-o", "--out", required=True)
    s.set_defaults(func=cmd_transcribe)

    s = sub.add_parser("cues", help="compute uncertainty cues per segment")
    s.add_argument("segments")
    s.add_argument("-o", "--out", required=True)
    s.set_defaults(func=cmd_cues)

    s = sub.add_parser("extract", help="extract and verify requirements with Claude")
    s.add_argument("segments")
    s.add_argument("--cues")
    s.add_argument("-o", "--out", required=True)
    s.set_defaults(func=cmd_extract)

    s = sub.add_parser("run", help="full pipeline for a scripted meeting")
    s.add_argument("script")
    s.add_argument("--setting", choices=["client", "internal"], default="client",
                   help="internal meetings run without uncertainty cues (EU AI Act Art. 5(1)(f))")
    s.add_argument("--model", default="small.en")
    s.add_argument("--resynth", action="store_true")
    s.add_argument("--skip-extract", action="store_true")
    s.set_defaults(func=cmd_run)

    s = sub.add_parser("eval-cues", help="score uncertainty flags against gold labels")
    s.add_argument("runs")
    s.add_argument("gold")
    s.set_defaults(func=cmd_eval_cues)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

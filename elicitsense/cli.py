"""Command-line entry point.

    elicitsense run data/meetings/m1_kickoff.txt         # synth → transcribe → cues → extract
    elicitsense eval-cues runs/ data/gold/harbour_physio.json
    elicitsense eval-extract runs/ data/gold/harbour_physio.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import cues as cues_mod
from .script import parse_script

AUDIO_DIR = Path("data/audio")
RUNS_DIR = Path("runs")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path) -> None:
    """Read KEY=VALUE lines into the environment without overriding variables already set."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key and not key.startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _api_error_message(e: Exception) -> str | None:
    import anthropic
    import openai

    if isinstance(e, (anthropic.AuthenticationError, openai.AuthenticationError)):
        return "the API key was rejected"
    if isinstance(e, (anthropic.RateLimitError, openai.RateLimitError)):
        return "rate limited, retry later"
    if isinstance(e, (anthropic.APIStatusError, openai.APIStatusError)):
        return f"API error {e.status_code}: {e.message}"
    if isinstance(e, (anthropic.APIConnectionError, openai.APIConnectionError)):
        return "could not reach the API"
    if isinstance(e, TypeError) and "authentication" in str(e):
        return "no Anthropic credentials. Set ANTHROPIC_API_KEY in .env, or use --provider openai."
    if isinstance(e, openai.OpenAIError) and "api_key" in str(e):
        return "no OpenAI credentials. Set OPENAI_API_KEY in .env."
    return None


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


def _extract(segments_path: Path, cues_path: Path | None, out: Path, provider: str, model: str | None) -> None:
    from .extract import ExtractionError, assemble, call_model

    transcript = _read(segments_path)
    try:
        extraction, meta = call_model(transcript, provider, model)
    except ExtractionError as e:
        sys.exit(f"extraction failed: {e}")
    except Exception as e:
        if (message := _api_error_message(e)) is None:
            raise
        sys.exit(f"extraction failed: {message}")
    result = assemble(transcript, extraction, _read(cues_path) if cues_path else None)
    result["llm"] = meta
    _write(out, result)
    print(f"{meta['provider']}/{meta['model']}: {len(result['requirements'])} requirements kept, "
          f"{len(result['rejected'])} rejected for unverifiable evidence")


def cmd_extract(args) -> None:
    _extract(Path(args.segments), Path(args.cues) if args.cues else None, Path(args.out), args.provider, args.llm)


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
    _extract(run_dir / "segments.json", cues_path, run_dir / "requirements.json", args.provider, args.llm)


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


def cmd_eval_extract(args) -> None:
    from .evaluate import score_meeting, summarise

    gold = _read(Path(args.gold))
    reports = []
    for req_path in sorted(Path(args.runs).glob("*/requirements.json")):
        result = _read(req_path)
        segments = _read(req_path.with_name("segments.json"))["segments"]
        report = score_meeting(result, segments, gold)
        reports.append(report)
        print(f"\n== {report['meeting']} ({result.get('llm', {}).get('model', '?')})")
        for pair in report["matched"]:
            marks = ("" if pair["type_ok"] else " [type]") + ("" if pair["uncertainty_ok"] else " [uncertainty]")
            print(f"  {pair['gold']} = {pair['pred']}{marks}  {pair['pred_statement'][:80]}")
        for sp in report["splits"]:
            print(f"  {sp['gold']} + {sp['pred']} (split)  {sp['pred_statement'][:80]}")
        for g in report["missed"]:
            print(f"  {g['id']} MISSED  {g['statement'][:80]}")
        for r in report["extra"]:
            print(f"  EXTRA {r['id']}  {r['statement'][:80]}")
    s = summarise(reports)
    print(f"\nrequirements: precision {s['precision']:.2f} (strict 1:1 {s['strict_precision']:.2f})  "
          f"recall {s['recall']:.2f}  F1 {s['f1']:.2f}  "
          f"(matched {s['matched']}, splits {s['splits']}, missed {s['missed']}, extra {s['extra']})")
    print(f"evidence verified: {s['evidence_validity']:.2f} of extracted items  |  "
          f"type agreement {s['type_agreement']:.2f}  |  uncertainty agreement {s['uncertainty_agreement']:.2f}")


def main(argv: list[str] | None = None) -> None:
    load_dotenv(Path(".env"))
    load_dotenv(PROJECT_ROOT / ".env")
    p = argparse.ArgumentParser(prog="elicitsense")
    sub = p.add_subparsers(dest="cmd", required=True)
    llm_flags = argparse.ArgumentParser(add_help=False)
    llm_flags.add_argument("--provider", choices=["auto", "anthropic", "openai"], default="auto",
                           help="LLM provider for extraction; auto uses whichever key is configured")
    llm_flags.add_argument("--llm", help="model id (defaults: claude-opus-5-5 / gpt-6.1-sol)")

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

    s = sub.add_parser("extract", parents=[llm_flags], help="extract and verify requirements with an LLM")
    s.add_argument("segments")
    s.add_argument("--cues")
    s.add_argument("-o", "--out", required=True)
    s.set_defaults(func=cmd_extract)

    s = sub.add_parser("run", parents=[llm_flags], help="full pipeline for a scripted meeting")
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

    s = sub.add_parser("eval-extract", help="score extracted requirements against gold labels")
    s.add_argument("runs")
    s.add_argument("gold")
    s.set_defaults(func=cmd_eval_extract)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

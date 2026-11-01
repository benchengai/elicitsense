"""Command-line entry point.

    elicitsense run data/projects/harbour_physio/m1_kickoff.txt   # synth → transcribe → cues → extract
    elicitsense eval-extract runs/harbour_physio data/projects/harbour_physio/gold.json
    elicitsense bench data/projects/harbour_physio -m openai:gpt-6.1-sol ollama:qwen3:8b
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


def _project(script_path: str) -> str:
    """Meetings live in data/projects/<project>/; the folder name is the project id."""
    return Path(script_path).resolve().parent.name


def cmd_synth(args) -> None:
    from .synth import synthesize, write_turns

    script = parse_script(args.script)
    audio = AUDIO_DIR / _project(args.script)
    wav = audio / f"{script.id}.wav"
    turns = synthesize(script, wav)
    write_turns(turns, audio / f"{script.id}.turns.json")
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
    project = _project(args.script)
    run_dir = RUNS_DIR / project / script.id
    audio = AUDIO_DIR / project
    wav, turns_path = audio / f"{script.id}.wav", audio / f"{script.id}.turns.json"
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
        for mn in report["mentions"]:
            print(f"  {mn['gold']} ~ {mn['pred']} (mention)  {mn['pred_statement'][:80]}")
        for g in report["missed"]:
            print(f"  {g['id']} MISSED  {g['statement'][:80]}")
        for r in report["extra"]:
            print(f"  EXTRA {r['id']}  {r['statement'][:80]}")
    s = summarise(reports)
    print(f"\nrequirements: precision {s['precision']:.2f} (strict 1:1 {s['strict_precision']:.2f})  "
          f"recall {s['recall']:.2f}  F1 {s['f1']:.2f}  "
          f"(matched {s['matched']}, splits {s['splits']}, mentions {s['mentions']}, "
          f"missed {s['missed']}, extra {s['extra']})")
    print(f"evidence verified: {s['evidence_validity']:.2f} of extracted items  |  "
          f"type agreement {s['type_agreement']:.2f}  |  uncertainty agreement {s['uncertainty_agreement']:.2f}")


def _meeting_dirs(runs: Path) -> list[Path]:
    dirs = [p.parent for p in runs.glob("*/requirements.json")]
    meta = {d: _read(d / "requirements.json")["meeting"] for d in dirs}
    return sorted(dirs, key=lambda d: (meta[d].get("date", ""), meta[d]["id"]))


def cmd_merge(args) -> None:
    from .llm import LLMError
    from .merge import apply_links, empty_register, finalise, link_meeting

    register = empty_register()
    for d in _meeting_dirs(Path(args.runs)):
        result, transcript = _read(d / "requirements.json"), _read(d / "segments.json")
        try:
            linking, meta = link_meeting(register, result, transcript, args.provider, args.llm)
        except LLMError as e:
            sys.exit(f"merge failed on {d.name}: {e}")
        except Exception as e:
            if (message := _api_error_message(e)) is None:
                raise
            sys.exit(f"merge failed on {d.name}: {message}")
        apply_links(register, result, linking)
        register["llm"].append({"meeting": result["meeting"]["id"], **meta})
    out = finalise(register)
    _write(Path(args.out), out)

    items = {i["id"]: i for i in out["requirements"]}
    print(f"\nactive requirements ({len(out['active'])}):")
    for rid in out["active"]:
        print(f"  {rid}  [{items[rid]['status']}]  {items[rid]['statement'][:80]}")
    print("\nrelations:")
    for r in out["relations"]:
        if r["kind"] != "same":
            extra = f" -> {r['new_status']}" if r.get("new_status") else ""
            print(f"  {r['from']} {r['kind']} {r['to']}{extra}  ({r['explanation'][:70]})")
    print(f"\nopen conflicts: {len(out['open_conflicts'])}  |  dropped links: {len(out['dropped_links'])}")


def cmd_eval_merge(args) -> None:
    from .evaluate import score_meeting, score_register

    gold = _read(Path(args.gold))
    register = _read(Path(args.register))
    runs = Path(args.register).parent
    reports = [score_meeting(_read(d / "requirements.json"), _read(d / "segments.json")["segments"], gold)
               for d in _meeting_dirs(runs)]
    s = score_register(register, reports, gold)
    for row in s["gold_relations"]:
        print(f"  {row['verdict']:<10} {row['from']} {row['kind']} {row['to']}"
              + (f"  (found as {row['found_kind']})" if row["found_kind"] not in (None, row["kind"]) else ""))
    for row in s["status_changes"]:
        print(f"  {'OK' if row['ok'] else 'WRONG':<10} {row['requirement']} status {row['status']} (register: {row['found']})")
    for row in s["spurious"]:
        print(f"  SPURIOUS   {row['from']} {row['kind']} {row['to']}  ({row['explanation'][:60]})")
    print(f"\nrelations: recall {s['recall']:.2f} exact kind, {s['recall_any']:.2f} any kind  |  "
          f"precision {s['precision']:.2f}  |  status changes {s['status_ok']}/{len(s['status_changes'])}  |  "
          f"open conflicts: {s['open_conflicts_found']}/{s['open_conflicts_expected']} expected found, "
          f"{s['open_conflicts_unexpected']} unexpected")


def _spec(provider: str, model: str | None) -> str:
    from .llm import DEFAULT_MODELS, resolve_provider

    provider = resolve_provider(provider)
    return f"{provider}:{model or DEFAULT_MODELS[provider]}"


def cmd_ask(args) -> None:
    from .qa import ask, load

    runs = Path(args.project_runs)
    project = load(runs, Path(args.register) if args.register else runs / "register.json", args.retrieval)
    try:
        r = ask(project, args.question, _spec(args.provider, args.llm))
    except Exception as e:
        if (message := _api_error_message(e)) is None:
            raise
        sys.exit(f"ask failed: {message}")
    label = "answer" if r["supported"] else ("not in the meetings" if not r["answerable"] else "UNSUPPORTED")
    print(f"\n[{label}] {r['answer']}\n")
    for c in r["citations"]:
        mark = "ok " if c["verified"] else "BAD"
        seg = project.segments.get(c["segment"])
        when = f"{seg['speaker']} {seg['start']:.0f}s" if seg else "?"
        print(f"  {mark} {c['segment']} ({when}): \"{c['quote']}\"")
    if r["requirement_ids"]:
        print(f"  requirements: {', '.join(r['requirement_ids'])}")
    u = r["usage"]
    cost = f"${u['cost_usd']:.4f}" if u["cost_usd"] is not None else "cost unknown"
    print(f"\n{r['model']}: {len(r['trace'])} tool calls, {u['calls']} model turns, {u['latency_s']:.0f}s, {cost}")


def cmd_bench(args) -> None:
    from .bench import bench, render_markdown

    project = Path(args.project)
    out = Path(args.out) if args.out else RUNS_DIR / "bench" / project.name
    print(f"bench {project.name}: {len(args.models)} models x {args.runs} runs -> {out}")
    try:
        results = bench(project, args.models, args.runs, RUNS_DIR, out, args.workers,
                        constrain_ids=not args.free_ids,
                        extraction_from=Path(args.reuse_extraction) if args.reuse_extraction else None)
    except Exception as e:
        if (message := _api_error_message(e)) is None:
            raise
        sys.exit(f"bench stopped: {message} (finished runs are kept; rerun to resume)")
    table = render_markdown(results)
    print("\n" + table)
    _write(out / "results.json", results)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(table, encoding="utf-8")
        print(f"wrote {args.report}")


def cmd_bench_qa(args) -> None:
    from .qa_bench import bench_qa, render_qa_markdown

    project = Path(args.project)
    runs = RUNS_DIR / project.name
    out = Path(args.out) if args.out else RUNS_DIR / "bench-qa" / project.name
    print(f"bench-qa {project.name}: {len(args.models)} models x {args.runs} runs -> {out}")
    try:
        results = bench_qa(project, runs, Path(args.register), args.models, args.runs, out,
                           args.retrieval, args.workers, strict=args.strict)
    except Exception as e:
        if (message := _api_error_message(e)) is None:
            raise
        sys.exit(f"bench-qa stopped: {message} (finished answers are kept; rerun to resume)")
    table = render_qa_markdown(results)
    print("\n" + table)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(table, encoding="utf-8")
        print(f"wrote {args.report}")


def main(argv: list[str] | None = None) -> None:
    load_dotenv(Path(".env"))
    load_dotenv(PROJECT_ROOT / ".env")
    p = argparse.ArgumentParser(prog="elicitsense")
    sub = p.add_subparsers(dest="cmd", required=True)
    llm_flags = argparse.ArgumentParser(add_help=False)
    llm_flags.add_argument("--provider", choices=["auto", "anthropic", "openai", "ollama"], default="auto",
                           help="LLM provider; auto uses whichever API key is configured, ollama runs locally")
    llm_flags.add_argument("--llm", help="model id (defaults: claude-opus-5-5 / gpt-6.1-sol / qwen3:8b)")

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

    s = sub.add_parser("merge", parents=[llm_flags], help="merge all meetings in a runs folder into one register")
    s.add_argument("runs")
    s.add_argument("-o", "--out", required=True)
    s.set_defaults(func=cmd_merge)

    s = sub.add_parser("eval-merge", help="score register relations and status changes against gold labels")
    s.add_argument("register")
    s.add_argument("gold")
    s.set_defaults(func=cmd_eval_merge)

    s = sub.add_parser("ask", parents=[llm_flags], help="ask a question about a project's requirements")
    s.add_argument("project_runs", help="runs folder of one project, e.g. runs/harbour_physio")
    s.add_argument("question")
    s.add_argument("--register", help="register JSON (default <project_runs>/register.json)")
    s.add_argument("--retrieval", choices=["bm25", "dense", "hybrid"], default="hybrid")
    s.set_defaults(func=cmd_ask)

    s = sub.add_parser("bench", help="compare models on extraction and merge for one project")
    s.add_argument("project", help="project folder, e.g. data/projects/harbour_physio")
    s.add_argument("-m", "--models", nargs="+", required=True,
                   help="provider:model specs, e.g. openai:gpt-6.1-sol ollama:qwen3:8b; "
                        "extract>merge routes the steps, e.g. openai:gpt-6-luna>openai:gpt-6.1-sol")
    s.add_argument("--runs", type=int, default=3, help="full project runs per model")
    s.add_argument("--workers", type=int, default=3, help="parallel API runs (local models run one at a time)")
    s.add_argument("-o", "--out", help="output folder (default runs/bench/<project>)")
    s.add_argument("--report", help="also write the markdown results table to this file")
    s.add_argument("--free-ids", action="store_true",
                   help="do not restrict merge link ids to the ids in the prompt (the M3 baseline)")
    s.add_argument("--reuse-extraction", metavar="BENCH_DIR",
                   help="reuse run k's extraction outputs from an earlier bench folder; only merge is called")
    s.set_defaults(func=cmd_bench)

    s = sub.add_parser("bench-qa", help="score the Q&A agent on a project's gold questions")
    s.add_argument("project", help="project folder with questions.json, e.g. data/projects/harbour_physio")
    s.add_argument("--register", required=True, help="register JSON the agent answers from")
    s.add_argument("-m", "--models", nargs="+", required=True, help="provider:model specs")
    s.add_argument("--runs", type=int, default=3)
    s.add_argument("--retrieval", choices=["bm25", "dense", "hybrid"], default="hybrid")
    s.add_argument("--workers", type=int, default=3)
    s.add_argument("-o", "--out", help="output folder (default runs/bench-qa/<project>)")
    s.add_argument("--report", help="also write the markdown results table to this file")
    s.add_argument("--strict", action="store_true",
                   help="do not parse final answers written as text instead of a submit_answer call")
    s.set_defaults(func=cmd_bench_qa)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

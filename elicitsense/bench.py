"""Compare LLMs on the extraction and merge steps of one project.

Transcripts and cues are computed once per project (`elicitsense run
--skip-extract`) and shared by every model, so differences come from the LLM
alone. Each model runs the whole project several times: extract every meeting,
then merge them into a register. Every run is scored against the gold labels
and the results are reported as mean and range across runs.

A spec can route the two steps to different models ("openai:gpt-6-luna>
openai:gpt-6.1-sol" extracts with the first and merges with the second). With
`extraction_from`, run k reuses the extraction outputs of run k in an earlier
bench folder and only the merge step is called again, so a merge change is
compared on identical inputs.

Finished runs are cached on disk, so an interrupted bench resumes where it
stopped. A run that fails (invalid or truncated output) is recorded and
counted, not retried.
"""

from __future__ import annotations

import json
import statistics
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pydantic import ValidationError

from .evaluate import score_meeting, score_register, summarise
from .extract import assemble, call_model
from .llm import LLMError, parse_model_spec
from .merge import apply_links, empty_register, finalise, link_meeting
from .script import parse_script


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_project(project_dir: Path, runs_root: Path) -> dict:
    meetings = []
    for script_path in sorted(project_dir.glob("*.txt")):
        script = parse_script(script_path)
        run_dir = runs_root / project_dir.name / script.id
        if not (run_dir / "segments.json").exists():
            raise FileNotFoundError(f"no transcript for {script.id}: run `elicitsense run {script_path} --skip-extract`")
        cues = run_dir / "cues.json"
        meetings.append({"id": script.id, "date": script.date,
                         "transcript": _read(run_dir / "segments.json"),
                         "cues": _read(cues) if cues.exists() else None})
    meetings.sort(key=lambda m: (m["date"], m["id"]))
    return {"name": project_dir.name, "gold": _read(project_dir / "gold.json"), "meetings": meetings}


def slug(spec: str) -> str:
    return spec.replace(":", "_").replace("/", "_").replace("+", "_").replace(">", "__")


def parse_route(spec: str) -> tuple[str, str]:
    """'a>b' extracts with a and merges with b; a plain spec uses one model for both."""
    extract_spec, _, merge_spec = spec.partition(">")
    return extract_spec, merge_spec or extract_spec


def run_once(project: dict, spec: str, out: Path, constrain_ids: bool = True,
             extraction_source: Path | None = None) -> dict:
    """One full pass over the project. Writes requirements, register and call log to `out`."""
    if (out / "run.json").exists():
        return _read(out / "run.json")
    extract_spec, merge_spec = parse_route(spec)
    calls, results = [], []
    step = meeting = None
    try:
        if extraction_source:
            reused = _read(extraction_source / "run.json")
            if not reused["ok"] or parse_route(reused["spec"])[0] != extract_spec:
                raise FileNotFoundError(f"{extraction_source} has no usable {extract_spec} extraction")
            calls += [c for c in reused["calls"] if c["step"] == "extract"]
        provider, model = parse_model_spec(extract_spec)
        for m in project["meetings"]:
            step, meeting = "extract", m["id"]
            if extraction_source:
                result = _read(extraction_source / meeting / "requirements.json")
            else:
                extraction, meta = call_model(m["transcript"], provider, model)
                calls.append({"step": step, "meeting": meeting, **meta})
                result = assemble(m["transcript"], extraction, m["cues"])
                result["llm"] = meta
            _write(out / meeting / "requirements.json", result)
            results.append(result)
        provider, model = parse_model_spec(merge_spec)
        register = empty_register()
        for m, result in zip(project["meetings"], results):
            step, meeting = "merge", m["id"]
            linking, meta = link_meeting(register, result, m["transcript"], provider, model, constrain_ids)
            calls.append({"step": step, "meeting": meeting, **meta})
            apply_links(register, result, linking)
            register["llm"].append({"meeting": meeting, **meta})
        _write(out / "register.json", finalise(register))
        run = {"spec": spec, "ok": True, "constrain_ids": constrain_ids,
               "extraction_from": str(extraction_source) if extraction_source else None, "calls": calls}
    except (LLMError, ValidationError, json.JSONDecodeError) as e:
        run = {"spec": spec, "ok": False, "constrain_ids": constrain_ids, "calls": calls,
               "error": {"step": step, "meeting": meeting, "message": str(e)[:500]}}
    _write(out / "run.json", run)
    return run


# Links the validator refused; "model returned no link" is a consequence, not counted.
INVALID_LINK_REASONS = {"unknown new requirement", "unknown or self target", "status_change without new_status"}


def score_run(project: dict, run: dict, out: Path) -> dict:
    calls = run["calls"]
    row = {
        "ok": run["ok"],
        "error": run.get("error"),
        "calls": len(calls),
        "input_tokens": sum(c["input_tokens"] for c in calls),
        "output_tokens": sum(c["output_tokens"] for c in calls),
        "latency_s": sum(c["latency_s"] for c in calls),
        "cost_usd": None if any(c["cost_usd"] is None for c in calls) else sum(c["cost_usd"] for c in calls),
    }
    if not run["ok"]:
        return row
    gold = project["gold"]
    reports = [score_meeting(_read(out / m["id"] / "requirements.json"), m["transcript"]["segments"], gold)
               for m in project["meetings"]]
    s = summarise(reports)
    register = _read(out / "register.json")
    r = score_register(register, reports, gold)
    row.update({
        "req_recall": s["recall"],
        "req_precision": s["precision"],
        "req_strict_precision": s["strict_precision"],
        "evidence_verified": s["evidence_validity"],
        "type_agreement": s["type_agreement"],
        "uncertainty_agreement": s["uncertainty_agreement"],
        "status_agreement": s.get("status_agreement"),
        "special_status_recall": s.get("special_status_recall"),
        "rel_recall": r["recall"],
        "rel_recall_any": r["recall_any"],
        "rel_precision": r["precision"],
        "status_ok": r["status_ok"] / len(r["status_changes"]) if r["status_changes"] else None,
        "open_conflicts_found": r["open_conflicts_found"],
        "open_conflicts_expected": r["open_conflicts_expected"],
        "open_conflicts_unexpected": r["open_conflicts_unexpected"],
        "invalid_links": sum(d["reason"] in INVALID_LINK_REASONS for d in register["dropped_links"]),
        "relations": [{k: g[k] for k in ("from", "kind", "to", "verdict", "found_kind")} for g in r["gold_relations"]],
    })
    return row


def bench(project_dir: Path, specs: list[str], runs: int, runs_root: Path, out_root: Path,
          api_workers: int = 3, constrain_ids: bool = True, extraction_from: Path | None = None) -> dict:
    project = load_project(project_dir, runs_root)
    jobs = [(spec, k) for spec in specs for k in range(1, runs + 1)]

    def source(spec: str, k: int) -> Path | None:
        return extraction_from / slug(parse_route(spec)[0]) / f"run{k}" if extraction_from else None

    def calls_local_model(spec: str) -> bool:
        extract_spec, merge_spec = parse_route(spec)
        return merge_spec.startswith("ollama:") or (extract_spec.startswith("ollama:") and not extraction_from)

    def job(spec_k):
        spec, k = spec_k
        out = out_root / slug(spec) / f"run{k}"
        run = run_once(project, spec, out, constrain_ids, source(spec, k))
        status = "ok" if run["ok"] else f"FAILED at {run['error']['step']} {run['error']['meeting']}"
        print(f"  {spec} run {k}: {status}", flush=True)
        return spec_k, score_run(project, run, out)

    # API calls run in parallel; a local model gets one request at a time.
    local = [j for j in jobs if calls_local_model(j[0])]
    remote = [j for j in jobs if not calls_local_model(j[0])]
    with ThreadPoolExecutor(api_workers) as api, ThreadPoolExecutor(1) as gpu:
        futures = [api.submit(job, j) for j in remote] + [gpu.submit(job, j) for j in local]
        scored = dict(f.result() for f in futures)

    results = {"project": project["name"], "runs_per_model": runs, "constrain_ids": constrain_ids,
               "extraction_from": str(extraction_from) if extraction_from else None, "models": {}}
    for spec in specs:
        rows = [scored[(spec, k)] for k in range(1, runs + 1)]
        results["models"][spec] = {"runs": rows, "summary": aggregate(rows)}
    _write(out_root / "results.json", results)
    return results


METRICS = ("req_recall", "req_precision", "req_strict_precision", "evidence_verified", "type_agreement",
           "uncertainty_agreement", "status_agreement", "special_status_recall", "rel_recall", "rel_recall_any", "rel_precision", "status_ok",
           "open_conflicts_found", "open_conflicts_unexpected", "invalid_links", "cost_usd", "latency_s",
           "input_tokens", "output_tokens")


def aggregate(rows: list[dict]) -> dict:
    ok = [r for r in rows if r["ok"]]
    summary = {"runs": len(rows), "failed": len(rows) - len(ok)}
    for key in METRICS:
        values = [r[key] for r in (ok if key not in ("cost_usd", "latency_s") else rows) if r.get(key) is not None]
        if values:
            summary[key] = {"mean": statistics.fmean(values), "min": min(values), "max": max(values)}
    return summary


def _cell(summary: dict, key: str, fmt: str = "{:.2f}") -> str:
    if key not in summary:
        return "–"
    v = summary[key]
    if fmt.format(v["min"]) == fmt.format(v["max"]):
        return fmt.format(v["mean"])
    return f"{fmt.format(v['mean'])} ({fmt.format(v['min'])}–{fmt.format(v['max'])})"


def render_markdown(results: dict) -> str:
    models = results["models"]
    lines = [
        f"### {results['project']}: {results['runs_per_model']} runs per model",
        "",
        "Mean across successful runs, range in brackets. Cost and latency are per full project run "
        "(every meeting extracted, then merged) and include failed runs. `a>b` extracts with a and merges with b.",
        "",
        f"Merge link ids: {'restricted to the ids in the prompt' if results.get('constrain_ids', True) else 'free text'}."
        + (" Extraction outputs reused from the earlier runs in "
           f"`{results['extraction_from']}`; only merge was called again." if results.get("extraction_from") else ""),
        "",
        "| Model | Req. recall | Req. precision | Strict 1:1 precision | Quotes verified | Uncertainty agr. "
        "| Relations, exact kind | Relation precision | Status changes | Open conflicts right | Invalid links "
        "| Cost (USD) | Time (s) | Failed runs |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for spec, m in models.items():
        s = m["summary"]
        expected = m["runs"][0].get("open_conflicts_expected", 0) if m["runs"] else 0
        open_ok = [r for r in m["runs"] if r["ok"]
                   and r["open_conflicts_found"] == expected and r["open_conflicts_unexpected"] == 0]
        ok_runs = s["runs"] - s["failed"]
        lines.append(
            f"| `{spec}` | {_cell(s, 'req_recall')} | {_cell(s, 'req_precision')} | {_cell(s, 'req_strict_precision')} "
            f"| {_cell(s, 'evidence_verified')} | {_cell(s, 'uncertainty_agreement')} "
            f"| {_cell(s, 'rel_recall')} | {_cell(s, 'rel_precision')} | {_cell(s, 'status_ok')} "
            f"| {len(open_ok)} of {ok_runs} | {_cell(s, 'invalid_links', '{:.1f}')} | {_cell(s, 'cost_usd', '{:.3f}')} | {_cell(s, 'latency_s', '{:.0f}')} "
            f"| {s['failed']} of {s['runs']} |")
    failures = [(spec, r["error"]) for spec, m in models.items() for r in m["runs"] if not r["ok"]]
    if failures:
        lines += ["", "Failed runs:", ""]
        lines += [f"- `{spec}` at {e['step']} {e['meeting']}: {e['message'][:160]}" for spec, e in failures]
    return "\n".join(lines) + "\n"

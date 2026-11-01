"""Benchmark the Q&A agent on a project's gold questions.

Every model answers every question several times against the same register,
transcripts and search index. Answers are cached per question, so an
interrupted bench resumes. Retrieval is also scored on its own: how many gold
evidence lines the raw question retrieves in the top k, per retrieval mode.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .bench import _cell, _read, _write, slug
from .evaluate import score_answer, summarise_answers
from .index import MODES, Embedder, Index, build_docs, load_project_corpus
from .llm import LLMError
from .qa import Project, ask, finish

QA_METRICS = ("correct", "answerable_correct", "abstained_correctly", "false_abstentions", "facts_found",
              "supported", "citations_verified", "evidence_recall", "retrieval_recall", "tool_calls",
              "cost_usd", "latency_s", "failed_questions", "recovered", "no_submit")


def retrieval_recall(project_runs: Path, register: dict, transcripts: list[dict], questions: list[dict],
                     k: int) -> dict:
    """Share of gold evidence lines covered by the top-k hits for each answerable question."""
    docs = build_docs(register, transcripts)
    line = {f"{t['meeting']['id']}:{s['id']}": f"{t['meeting']['id']}:{s['source_line']}"
            for t in transcripts for s in t["segments"]}
    out = {}
    for mode in MODES:
        index = Index(docs, mode, Embedder(project_runs / "embeddings.json") if mode != "bm25" else None)
        scores = []
        for q in (q for q in questions if q["answerable"]):
            covered = {line[c] for d in index.search(q["question"], "all", k) for c in d["covers"] if c in line}
            scores.append(len(covered & set(q["evidence"])) / len(q["evidence"]))
        out[mode] = sum(scores) / len(scores)
    return out


def _run(project: Project, questions: list[dict], spec: str, out: Path, strict: bool = False) -> dict:
    rows, usage = [], {"cost_usd": 0.0, "latency_s": 0.0, "tool_calls": 0, "failed_questions": 0}
    for q in questions:
        path = out / f"{q['id']}.json"
        if path.exists():
            record = _read(path)
        else:
            try:
                record = ask(project, q["question"], spec)
            except LLMError as e:
                record = {"error": str(e)[:300]}
            _write(path, record)
        if "error" in record:
            usage["failed_questions"] += 1
            rows.append({"id": q["id"], "gold_answerable": q["answerable"], "said_answerable": False,
                         "citations": 0, "citations_verified": 0, "correct": False, "facts_found": 0.0,
                         "supported": False, "evidence_recall": 0.0, "retrieval_recall": 0.0, "error": record["error"]})
            continue
        if record.get("no_submit") and not strict:
            # Re-check the stored final text; older caches kept it in "answer".
            record = {**record, **finish(project, {"submitted": None,
                                                   "final_text": record.get("final_text", record["answer"])})}
        elif strict and record.get("recovered_from_text"):
            text = record.get("final_text", "")
            record = {**record, "answer": text, "answerable": bool(text), "citations": [], "requirement_ids": [],
                      "supported": False, "no_submit": True, "recovered_from_text": False}
        rows.append({**score_answer(record, q), "recovered": bool(record.get("recovered_from_text")),
                     "no_submit": bool(record.get("no_submit"))})
        u = record["usage"]
        usage["cost_usd"] = None if usage["cost_usd"] is None or u["cost_usd"] is None else usage["cost_usd"] + u["cost_usd"]
        usage["latency_s"] += u["latency_s"]
        usage["tool_calls"] += len(record["trace"])
    summary = summarise_answers(rows)
    usage["recovered"] = sum(r.get("recovered", False) for r in rows)
    usage["no_submit"] = sum(r.get("no_submit", False) for r in rows)
    return {"ok": True, "questions": rows, **summary, **usage,
            "tool_calls": usage["tool_calls"] / len(questions)}


def bench_qa(project_dir: Path, project_runs: Path, register_path: Path, specs: list[str], runs: int,
             out_root: Path, retrieval: str = "hybrid", api_workers: int = 3, k: int = 5,
             strict: bool = False) -> dict:
    questions = _read(project_dir / "questions.json")["questions"]
    register, transcripts = load_project_corpus(project_runs, register_path)
    embedder = Embedder(project_runs / "embeddings.json") if retrieval != "bm25" else None
    project = Project(register, transcripts, Index(build_docs(register, transcripts), retrieval, embedder))

    def job(spec_k):
        spec, k_run = spec_k
        result = _run(project, questions, spec, out_root / slug(spec) / f"run{k_run}", strict)
        print(f"  {spec} run {k_run}: {result['correct']:.2f} correct", flush=True)
        return spec_k, result

    jobs = [(spec, n) for spec in specs for n in range(1, runs + 1)]
    local = [j for j in jobs if j[0].startswith("ollama:")]
    remote = [j for j in jobs if not j[0].startswith("ollama:")]
    with ThreadPoolExecutor(api_workers) as api, ThreadPoolExecutor(1) as gpu:
        futures = [api.submit(job, j) for j in remote] + [gpu.submit(job, j) for j in local]
        scored = dict(f.result() for f in futures)

    results = {
        "project": project_dir.name, "register": str(register_path), "retrieval": retrieval, "strict": strict,
        "questions": len(questions), "runs_per_model": runs,
        "retrieval_recall_at_k": {"k": k, **retrieval_recall(project_runs, register, transcripts, questions, k)},
        "models": {},
    }
    for spec in specs:
        rows = [scored[(spec, n)] for n in range(1, runs + 1)]
        summary = {"runs": len(rows), "failed": 0}
        for key in QA_METRICS:
            values = [r[key] for r in rows if r.get(key) is not None]
            if values:
                summary[key] = {"mean": sum(values) / len(values), "min": min(values), "max": max(values)}
        results["models"][spec] = {"runs": rows, "summary": summary}
    _write(out_root / "results.json", results)
    return results


def render_qa_markdown(results: dict) -> str:
    n = results["questions"]
    r = results["retrieval_recall_at_k"]
    lines = [
        f"### {results['project']}: {n} questions, {results['runs_per_model']} runs per model",
        "",
        f"Agent retrieval: {results['retrieval']}. Mean across runs, range in brackets. Cost and time are for "
        "the whole question set. "
        + ("Strict scoring: a final answer written as text instead of a submit_answer call counts as "
           "unsubmitted (column: such answers per run)." if results.get("strict") else
           "A final answer written as text instead of a submit_answer call is parsed and checked like a call "
           "(column: such answers per run)."),
        "",
        "| Model | Correct | Answerable correct | Abstained correctly | Facts found | Answers with a verified citation "
        "| Citations verified | Evidence recall | Retrieval recall | Tool calls per question | Final call written as text "
        "| Cost (USD) | Time (s) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for spec, m in results["models"].items():
        s = m["summary"]
        lines.append(
            f"| `{spec}` | {_cell(s, 'correct')} | {_cell(s, 'answerable_correct')} | {_cell(s, 'abstained_correctly')} "
            f"| {_cell(s, 'facts_found')} | {_cell(s, 'supported')} | {_cell(s, 'citations_verified')} "
            f"| {_cell(s, 'evidence_recall')} | {_cell(s, 'retrieval_recall')} | {_cell(s, 'tool_calls', '{:.1f}')} "
            f"| {_cell(s, 'recovered', '{:.1f}') if not results.get('strict') else _cell(s, 'no_submit', '{:.1f}')} "
            f"| {_cell(s, 'cost_usd', '{:.3f}')} | {_cell(s, 'latency_s', '{:.0f}')} |")
    lines += ["", f"Retrieval alone, gold evidence lines in the top {r['k']} hits for the raw question: "
              + ", ".join(f"{mode} {r[mode]:.2f}" for mode in MODES) + "."]
    failures = [(spec, q) for spec, m in results["models"].items() for run in m["runs"]
                for q in run["questions"] if "error" in q]
    if failures:
        lines += ["", "Failed questions:", ""] + [f"- `{spec}` {q['id']}: {q['error'][:160]}" for spec, q in failures]
    return "\n".join(lines) + "\n"

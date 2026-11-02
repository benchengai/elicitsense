"""Export pipeline outputs for the static web demo.

Everything the demo shows comes from real runs: the register from a merge run,
transcripts from local transcription, answers from a recorded Q&A bench run,
and the evaluation tables from bench results. Nothing is written by hand.
Audio is converted to AAC with macOS `afconvert` so the demo can play it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

from .index import load_project_corpus
from .script import parse_script

REQ_FIELDS = ("id", "type", "statement", "acceptance", "stakeholder", "status", "meeting", "evidence",
              "quality", "uncertainty", "history", "merged_into", "merged_from", "superseded_by")


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _audio(wav: Path, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("afconvert") is None:
        raise RuntimeError("macOS afconvert is needed to convert demo audio")
    subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", "48000", str(wav), str(out)], check=True)


def _summary(model: dict, keys: tuple[str, ...]) -> dict:
    s = model["summary"]
    return {k: s[k] for k in keys if k in s}


def export_project(project_dir: Path, runs_root: Path, audio_root: Path, register_path: Path,
                   qa_dir: Path, qa_spec: str, out: Path) -> dict:
    name = project_dir.name
    gold = _read(project_dir / "gold.json")
    register, transcripts = load_project_corpus(runs_root / name, register_path)
    scripts = {parse_script(p).id: parse_script(p) for p in sorted(project_dir.glob("*.txt"))}

    meetings = []
    for t in transcripts:
        m = t["meeting"]
        segs = t["segments"]
        _audio(audio_root / name / f"{m['id']}.wav", out / "audio" / f"{m['id']}.m4a")
        meetings.append({"id": m["id"], "title": m.get("title", ""), "date": m.get("date", ""),
                         "audio": f"audio/{m['id']}.m4a", "duration": round(segs[-1]["end"], 1) if segs else 0,
                         "speakers": sorted({s["speaker"] for s in segs}),
                         "segments": [{"id": s["id"], "line": s["source_line"], "speaker": s["speaker"],
                                       "start": round(s["start"], 2), "end": round(s["end"], 2), "text": s["text"]}
                                      for s in segs]})
        assert m["id"] in scripts

    requirements = [{k: r.get(k) for k in REQ_FIELDS} for r in register["requirements"]]
    _write(out / "register.json", {
        "requirements": requirements, "relations": register["relations"],
        "open_conflicts": register["open_conflicts"], "active": register["active"],
        "llm": [{k: c.get(k) for k in ("meeting", "provider", "model", "input_tokens", "output_tokens",
                                       "cost_usd", "latency_s")} for c in register.get("llm", [])],
    })
    _write(out / "meetings.json", meetings)

    questions = _read(project_dir / "questions.json")["questions"]
    slug = qa_spec.replace(":", "_")
    answers = []
    for q in questions:
        rec = _read(qa_dir / slug / "run1" / f"{q['id']}.json")
        answers.append({
            "id": q["id"], "question": q["question"], "gold_answerable": q["answerable"],
            "answer": rec["answer"], "answerable": rec["answerable"], "supported": rec["supported"],
            "citations": [{k: c.get(k) for k in ("segment", "quote", "verified", "line")} for c in rec["citations"]],
            "requirement_ids": rec["requirement_ids"], "tools": [t["tool"] for t in rec["trace"]],
            "model": rec["model"], "cost_usd": rec["usage"]["cost_usd"], "latency_s": rec["usage"]["latency_s"],
        })
    _write(out / "qa.json", {"spec": qa_spec, "run": "run1", "answers": answers})

    meta = {"id": name, "title": gold["project"], "heldout": "held-out" in gold.get("notes", "").lower(),
            "meetings": [{k: m[k] for k in ("id", "title", "date", "duration")} for m in meetings],
            "register_source": str(register_path), "exported": date.today().isoformat(),
            "counts": {"requirements": len(requirements), "active": len(register["active"]),
                       "relations": len([r for r in register["relations"] if r["kind"] not in ("same",)]),
                       "open_conflicts": len(register["open_conflicts"])}}
    _write(out / "meta.json", meta)
    return meta


def export_eval(runs_root: Path, projects: list[str], out: Path) -> None:
    """Compact evaluation tables for the demo's evaluation page."""
    merge_keys = ("req_recall", "req_precision", "evidence_verified", "rel_recall", "rel_precision",
                  "status_ok", "cost_usd", "latency_s", "invalid_links")
    qa_keys = ("correct", "abstained_correctly", "supported", "citations_verified", "evidence_recall",
               "tool_calls", "cost_usd", "latency_s")
    data = {"projects": {}}
    for p in projects:
        entry = {}
        for variant in ("baseline", "constrained-ids"):
            res = _read(runs_root / "bench" / p / variant / "results.json")
            entry[variant] = {spec: {**_summary(m, merge_keys),
                                     "open_ok": sum(r["ok"] and r.get("open_conflicts_found") == r.get("open_conflicts_expected")
                                                    and r.get("open_conflicts_unexpected") == 0 for r in m["runs"]),
                                     "runs": len(m["runs"])}
                              for spec, m in res["models"].items()}
        qa = _read(runs_root / "bench-qa" / p / "api" / "results.json")
        entry["qa"] = {spec: _summary(m, qa_keys) for spec, m in qa["models"].items()}
        entry["qa_questions"] = qa["questions"]
        entry["retrieval_at_5"] = qa["retrieval_recall_at_k"]
        local = runs_root / "bench-qa" / p / "local" / "results.json"
        if local.exists():
            entry["qa_local"] = {spec: _summary(m, qa_keys) for spec, m in _read(local)["models"].items()}
        data["projects"][p] = entry
    _write(out / "eval.json", data)

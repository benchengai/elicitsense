from pathlib import Path

import pytest

from elicitsense import quality
from elicitsense.cues import compute_cues
from elicitsense.extract import Candidate, Evidence, Extraction, assemble
from elicitsense.script import parse_script
from elicitsense.transcribe import clip_bounds, make_segment
from elicitsense.verify import quote_matches

ROOT = Path(__file__).resolve().parents[1]


def _words(text: str, start: float = 0.0, step: float = 0.3, pauses: dict[int, float] | None = None):
    words, t = [], start
    for i, w in enumerate(text.split()):
        t += (pauses or {}).get(i, 0.0)
        words.append({"w": w, "start": round(t, 3), "end": round(t + step - 0.05, 3), "p": 1.0})
        t += step
    return words


def test_parse_scripts():
    for path in sorted((ROOT / "data/projects").glob("*/*.txt")):
        script = parse_script(path)
        assert script.lines, path
        assert all(line.id.startswith("L") for line in script.lines)
    m1 = parse_script(ROOT / "data/projects/harbour_physio/m1_kickoff.txt")
    assert m1.id == "m1"
    l012 = next(line for line in m1.lines if line.id == "L012")
    assert l012.slow and l012.text.startswith("Um...")


def test_clip_bounds_pad_and_clamp():
    assert clip_bounds({"start": 0.0, "end": 1.0}, 100_000) == (0, 17_600)
    assert clip_bounds({"start": 2.0, "end": 9.0}, 100_000) == (30_400, 100_000)


def test_make_segment():
    seg = make_segment(7, "OWNER", "L002", _words("general kenobi", 1.6))
    assert seg["id"] == "S007"
    assert seg["text"] == "general kenobi"
    assert seg["source_line"] == "L002"
    assert seg["start"] == 1.6


def test_verify_quotes():
    seg = "Patients should be able to book an appointment online without creating an account."
    assert quote_matches("book an appointment online without creating an account", seg)
    assert quote_matches("Book an appointment online, without creating an account!", seg)
    assert not quote_matches("patients must pay a deposit", seg)


def test_cues_flag_needs_two_kinds():
    confident = "Patients should get an SMS reminder the day before their appointment."
    hesitant = "Um... I think maybe a deposit? I'm not sure."
    transcript = {
        "meeting": {"id": "t"},
        "segments": [
            {"id": "S001", "speaker": "OWNER", "text": confident, "words": _words(confident)},
            {"id": "S002", "speaker": "OWNER", "text": "I think we need logins.", "words": _words("I think we need logins.")},
            {"id": "S003", "speaker": "OWNER", "text": hesitant, "words": _words(hesitant, pauses={1: 0.9})},
        ],
    }
    out = compute_cues(transcript)["segments"]
    assert not out["S001"]["flag"]
    assert out["S002"]["kinds"] == ["hedging"] and not out["S002"]["flag"]
    assert out["S003"]["flag"]
    assert {"hedging", "filled_pause", "long_pause"} <= set(out["S003"]["kinds"])


def test_quality_flags_ambiguous_terms_without_targets():
    issues = quality.check("Booking is fast and easy to use on phones.", "non_functional", [])
    kinds = [i["kind"] for i in issues]
    assert kinds.count("ambiguous_term") >= 2
    assert not [i for i in quality.check("Times load in under 2 seconds and fast.", "non_functional", ["x"])
                if i["kind"] == "ambiguous_term"]


def test_assemble_rejects_unverifiable_and_attaches_cues():
    transcript = {
        "meeting": {"id": "m1"},
        "segments": [
            {"id": "S001", "speaker": "OWNER", "start": 0.0, "end": 2.0,
             "text": "Patients should get an SMS reminder the day before."},
            {"id": "S002", "speaker": "OWNER", "start": 3.0, "end": 6.0,
             "text": "Um... I think maybe a deposit? I'm not sure."},
        ],
    }
    cues = {"segments": {
        "S001": {"flag": False, "kinds": [], "cues": []},
        "S002": {"flag": True, "kinds": ["filled_pause", "hedging"],
                 "cues": [{"kind": "hedging", "detail": '"i think"'}, {"kind": "filled_pause", "detail": '"um"'}]},
    }}
    extraction = Extraction(
        requirements=[
            Candidate(statement="Patients get an SMS reminder the day before.", type="functional",
                      stakeholder="OWNER", status="proposed", rationale="", acceptance_criteria=[],
                      evidence=[Evidence(segment_id="S001", quote="get an SMS reminder the day before")]),
            Candidate(statement="Patients may pay a deposit online.", type="functional",
                      stakeholder="OWNER", status="open_question", rationale="", acceptance_criteria=[],
                      evidence=[Evidence(segment_id="S002", quote="maybe a deposit")]),
            Candidate(statement="Patients pay in full upfront.", type="functional",
                      stakeholder="OWNER", status="proposed", rationale="", acceptance_criteria=[],
                      evidence=[Evidence(segment_id="S002", quote="patients pay in full upfront")]),
        ],
        open_questions=[],
    )
    result = assemble(transcript, extraction, cues)
    assert [r["id"] for r in result["requirements"]] == ["REQ-m1-001", "REQ-m1-002"]
    assert not result["requirements"][0]["uncertainty"]["flag"]
    assert result["requirements"][1]["uncertainty"]["label"] == "needs confirmation"
    assert len(result["rejected"]) == 1


def test_score_meeting_pairs_by_evidence_lines():
    from elicitsense.evaluate import score_meeting, summarise

    segments = [{"id": f"S00{i}", "source_line": f"L00{i}"} for i in range(1, 6)]
    gold = {"requirements": [
        {"id": "G1", "meeting": "m1", "type": "functional", "statement": "a", "evidence": ["m1:L001"], "uncertain": False},
        {"id": "G2", "meeting": "m1", "type": "constraint", "statement": "b", "evidence": ["m1:L002", "m1:L003"], "uncertain": True},
        {"id": "G3", "meeting": "m1", "type": "functional", "statement": "c", "evidence": ["m1:L004"], "uncertain": False},
        {"id": "G9", "meeting": "m2", "type": "functional", "statement": "other meeting", "evidence": ["m2:L001"], "uncertain": False},
    ]}
    req = lambda rid, t, segs, flag: {"id": rid, "type": t, "statement": rid, "uncertainty": {"flag": flag},
                                      "evidence": [{"segment_id": s} for s in segs]}
    result = {"meeting": {"id": "m1"}, "rejected": [{"statement": "x"}], "requirements": [
        req("R1", "functional", ["S001"], False),
        req("R2", "functional", ["S003"], True),
        req("R3", "functional", ["S003"], False),
        req("R4", "functional", ["S005"], False),
    ]}
    report = score_meeting(result, segments, gold)
    assert [(m["gold"], m["pred"]) for m in report["matched"]] == [("G1", "R1"), ("G2", "R2")]
    assert [(sp["gold"], sp["pred"]) for sp in report["splits"]] == [("G2", "R3")]
    assert [g["id"] for g in report["missed"]] == ["G3"]
    assert [r["id"] for r in report["extra"]] == ["R4"]
    s = summarise([report])
    assert s["precision"] == 0.75 and s["strict_precision"] == 0.5
    assert round(s["recall"], 2) == 0.67
    assert s["evidence_validity"] == 0.8
    assert s["type_agreement"] == 0.5 and s["uncertainty_agreement"] == 1.0


def test_load_dotenv_does_not_override(tmp_path, monkeypatch):
    from elicitsense.cli import load_dotenv

    env = tmp_path / ".env"
    env.write_text("# comment\nELICIT_A=from_file\nELICIT_B='quoted'\n")
    monkeypatch.setenv("ELICIT_A", "already_set")
    monkeypatch.delenv("ELICIT_B", raising=False)
    load_dotenv(env)
    import os
    assert os.environ["ELICIT_A"] == "already_set"
    assert os.environ["ELICIT_B"] == "quoted"


def test_resolve_provider(monkeypatch):
    from elicitsense.llm import resolve_provider

    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    assert resolve_provider("auto") == "anthropic"
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    assert resolve_provider("auto") == "openai"
    assert resolve_provider("anthropic") == "anthropic"


def test_assemble_without_cues_never_flags():
    transcript = {"meeting": {"id": "m1"}, "segments": [
        {"id": "S001", "speaker": "OWNER", "start": 0.0, "end": 2.0, "text": "Um I think maybe a deposit."}]}
    extraction = Extraction(requirements=[
        Candidate(statement="Deposit online.", type="functional", stakeholder="OWNER", status="proposed",
                  rationale="", acceptance_criteria=[], evidence=[Evidence(segment_id="S001", quote="maybe a deposit")])],
        open_questions=[])
    result = assemble(transcript, extraction, None)
    assert result["cues_enabled"] is False
    assert not result["requirements"][0]["uncertainty"]["flag"]


def _result(meeting, reqs):
    return {"meeting": {"id": meeting}, "requirements": [
        {"id": rid, "type": "functional", "statement": rid, "status": status,
         "evidence": [{"segment_id": "S001", "speaker": "OWNER", "quote": rid}],
         "uncertainty": {"flag": False}}
        for rid, status in reqs
    ]}


def test_apply_links_tracks_supersession_conflicts_and_status():
    from elicitsense.merge import Link, Linking, apply_links, empty_register, finalise

    L = lambda n, rel, t="", st="": Link(new_id=n, relation=rel, target_id=t, new_status=st, explanation="x")
    reg = empty_register()
    apply_links(reg, _result("m1", [("R1", "proposed"), ("R2", "proposed")]),
                Linking(links=[L("R1", "new"), L("R2", "new")]))
    apply_links(reg, _result("m2", [("N1", "superseded"), ("N2", "confirmed"), ("N3", "proposed"), ("N5", "proposed")]),
                Linking(links=[L("N1", "conflicts", "R1"), L("N2", "supersedes", "N1"), L("N2", "refines", "R1"),
                               L("N3", "conflicts", "R2"), L("N5", "new"), L("N5", "refines", "NOPE")]))
    mid = finalise(reg)
    assert [(c["from"], c["to"]) for c in mid["open_conflicts"]] == [("N3", "R2")]
    assert reg["items"]["N1"]["superseded_by"] == "N2"
    assert [d["reason"] for d in mid["dropped_links"]] == ["unknown or self target"]

    apply_links(reg, _result("m3", [("M1", "confirmed"), ("M2", "deferred")]),
                Linking(links=[L("M1", "supersedes", "R2"), L("M2", "status_change", "N5", "deferred")]))
    out = finalise(reg)
    assert out["open_conflicts"] == []
    assert reg["items"]["N5"]["status"] == "deferred"
    assert reg["items"]["M2"]["merged_into"] == "N5"
    assert out["active"] == ["R1", "N2", "N3", "N5", "M1"]


def test_score_register_maps_splits_and_flags_spurious():
    from elicitsense.evaluate import score_register

    reports = [{"matched": [{"pred": "R1", "gold": "G1"}, {"pred": "N2", "gold": "G2"}, {"pred": "N3", "gold": "G3"}],
                "splits": [{"pred": "N2b", "gold": "G2"}]}]
    register = {
        "relations": [
            {"from": "N2b", "kind": "refines", "to": "R1", "explanation": ""},
            {"from": "N2", "kind": "refines", "to": "N2b", "explanation": ""},
            {"from": "N3", "kind": "refines", "to": "R1", "explanation": ""},
            {"from": "N3", "kind": "same", "to": "R1", "explanation": ""},
        ],
        "requirements": [{"id": "N3", "status": "deferred"}],
        "open_conflicts": [],
    }
    gold = {"relations": [{"from": "G2", "kind": "refines", "to": "G1"}, {"from": "G3", "kind": "supersedes", "to": "G1"}],
            "status_changes": [{"requirement": "G3", "status": "deferred"}]}
    s = score_register(register, reports, gold)
    assert [r["verdict"] for r in s["gold_relations"]] == ["FOUND", "WRONG-KIND"]
    assert s["spurious"] == [] and s["precision"] == 1.0
    assert s["status_ok"] == 1


def test_confirmed_restatement_reinstates_superseded_item():
    from elicitsense.merge import Link, Linking, apply_links, empty_register

    L = lambda n, rel, t="": Link(new_id=n, relation=rel, target_id=t, new_status="", explanation="x")
    reg = empty_register()
    apply_links(reg, _result("m1", [("R1", "confirmed")]), Linking(links=[L("R1", "new")]))
    apply_links(reg, _result("m2", [("N1", "superseded"), ("N2", "confirmed")]),
                Linking(links=[L("N1", "supersedes", "R1"), L("N2", "same", "R1")]))
    assert reg["items"]["R1"]["status"] == "confirmed"
    assert reg["items"]["R1"]["superseded_by"] is None
    assert any(h["change"] == "reinstated by N2" for h in reg["items"]["R1"]["history"])


def test_mentions_and_expected_open_conflicts_are_scored():
    from elicitsense.evaluate import score_meeting, score_register

    segments = [{"id": "S001", "source_line": "L001"}, {"id": "S002", "source_line": "L002"}]
    gold = {
        "requirements": [{"id": "G1", "meeting": "m2", "type": "functional", "uncertain": False,
                          "statement": "a", "evidence": ["m2:L001"]}],
        "mentions": [{"requirement": "G0", "meeting": "m2", "evidence": ["m2:L002"]}],
        "relations": [],
        "open_conflicts_after": [{"from": "G1", "to": "G0"}],
    }
    pred = lambda rid, seg: {"id": rid, "statement": rid, "type": "functional",
                             "uncertainty": {"flag": False}, "evidence": [{"segment_id": seg}]}
    result = {"meeting": {"id": "m2"}, "requirements": [pred("N1", "S001"), pred("N2", "S002")]}
    report = score_meeting(result, segments, gold)
    assert [m["gold"] for m in report["mentions"]] == ["G0"] and report["extra"] == []

    reports = [report, {"matched": [{"pred": "R0", "gold": "G0"}], "splits": []}]
    register = {"relations": [], "requirements": [],
                "open_conflicts": [{"from": "N1", "to": "R0"}, {"from": "N2", "to": "N1"}]}
    s = score_register(register, reports, gold)
    assert s["open_conflicts_found"] == 1 and s["open_conflicts_unexpected"] == 1


def test_model_spec_and_cost():
    from elicitsense.llm import parse_model_spec
    from elicitsense.pricing import cost_usd

    assert parse_model_spec("ollama:qwen3:8b+think") == ("ollama", "qwen3:8b+think")
    assert parse_model_spec("openai:gpt-6.1-sol") == ("openai", "gpt-6.1-sol")
    with pytest.raises(ValueError):
        parse_model_spec("gpt-6.1-sol")
    # 1M uncached input at $2, 1M cached at $0.10, 1M output at $10 (dated snapshot id)
    assert cost_usd("openai", "gpt-6.1-sol-2026-09-01", 2_000_000, 1_000_000, 1_000_000) == pytest.approx(12.10)
    assert cost_usd("ollama", "qwen3:8b", 5000, 0, 5000) == 0.0
    assert cost_usd("openai", "unlisted-model", 1, 0, 1) is None


def test_bench_aggregate_counts_failures_and_keeps_their_cost():
    from elicitsense.bench import aggregate, render_markdown

    ok = {"ok": True, "req_recall": 1.0, "cost_usd": 0.02, "latency_s": 10.0,
          "open_conflicts_found": 0, "open_conflicts_expected": 0, "open_conflicts_unexpected": 0}
    rows = [ok, {**ok, "req_recall": 0.5, "cost_usd": 0.04},
            {"ok": False, "cost_usd": 0.01, "latency_s": 4.0,
             "error": {"step": "merge", "meeting": "m2", "message": "bad json"}}]
    s = aggregate(rows)
    assert s["failed"] == 1 and s["req_recall"]["mean"] == 0.75
    assert s["cost_usd"]["max"] == 0.04 and s["cost_usd"]["min"] == 0.01
    table = render_markdown({"project": "p", "runs_per_model": 3, "models": {"x:y": {"runs": rows, "summary": s}}})
    assert "1 of 3" in table and "2 of 2" in table and "merge m2" in table


def test_merge_schema_restricts_ids_to_the_prompt():
    from elicitsense.merge import SCHEMA, empty_register, schema_for

    reg = empty_register()
    reg["items"] = {"REQ-m1-001": {}, "REQ-m1-002": {}}
    fields = schema_for(reg, {"requirements": [{"id": "REQ-m2-001"}]})["properties"]["links"]["items"]["properties"]
    assert fields["new_id"]["enum"] == ["REQ-m2-001"]
    assert fields["target_id"]["enum"] == ["", "REQ-m1-001", "REQ-m1-002", "REQ-m2-001"]
    assert "enum" not in SCHEMA["properties"]["links"]["items"]["properties"]["new_id"]
    assert schema_for(reg, {"requirements": []}) is SCHEMA


def test_bench_route_specs():
    from elicitsense.bench import parse_route, slug

    assert parse_route("openai:gpt-6-luna>openai:gpt-6.1-sol") == ("openai:gpt-6-luna", "openai:gpt-6.1-sol")
    assert parse_route("ollama:qwen3:8b") == ("ollama:qwen3:8b", "ollama:qwen3:8b")
    assert slug("ollama:qwen3:8b>openai:gpt-6.1-sol") == "ollama_qwen3_8b__openai_gpt-6.1-sol"


def _qa_project():
    from elicitsense.index import Index, build_docs
    from elicitsense.qa import Project

    seg = lambda i, line, text: {"id": i, "source_line": line, "speaker": "OWNER", "start": 1.0, "end": 2.0,
                                 "text": text, "words": []}
    transcripts = [{"meeting": {"id": "m1", "date": "2026-03-02"},
                    "segments": [seg("S001", "L001", "We want an SMS reminder the day before."),
                                 seg("S002", "L002", "Patient data has to stay in Australia.")]}]
    register = {"requirements": [{"id": "REQ-m1-001", "meeting": "m1", "type": "functional", "status": "confirmed",
                                  "stakeholder": "OWNER", "statement": "Patients get an SMS reminder.",
                                  "evidence": [{"meeting": "m1", "segment_id": "S001", "speaker": "OWNER",
                                                "quote": "an SMS reminder the day before"}], "history": []}],
                "relations": [], "open_conflicts": []}
    return Project(register, transcripts, Index(build_docs(register, transcripts), "bm25"))


def test_qa_tools_track_seen_segments_and_check_citations():
    project = _qa_project()
    seen = set()
    hits = project.run_tool("search", {"query": "where is data stored Australia", "scope": "transcript", "k": 1}, seen)
    assert hits["results"][0]["segment"] == "m1:S002" and seen == {"m1:S002"}
    project.run_tool("get_requirement", {"id": "REQ-m1-001"}, seen)
    assert seen == {"m1:S001", "m1:S002"}
    checked = project.check({"answer": "In Australia.", "answerable": True, "requirement_ids": ["REQ-m1-001", "REQ-x"],
                             "citations": [{"segment": "m1:S002", "quote": "has to stay in Australia"},
                                           {"segment": "m1:S001", "quote": "data stays in Europe"}]})
    assert [c["verified"] for c in checked["citations"]] == [True, False]
    assert checked["supported"] and checked["unknown_requirement_ids"] == ["REQ-x"]


def test_score_answer_facts_abstention_and_evidence():
    from elicitsense.evaluate import score_answer, summarise_answers

    q = {"id": "q1", "answerable": True, "facts": [["$20", "twenty dollar"], ["24 hours", "twenty four hours"]],
         "evidence": ["m2:L007", "m2:L009"]}
    rec = {"answer": "New patients pay a twenty-dollar deposit, refunded if they cancel 24 hours ahead.",
           "answerable": True, "supported": True, "seen_lines": ["m2:L007", "m2:L009"],
           "citations": [{"verified": True, "line": "m2:L007"}, {"verified": False, "line": "m2:L009"}]}
    row = score_answer(rec, q)
    assert row["correct"] and row["evidence_recall"] == 0.5 and row["retrieval_recall"] == 1.0
    no = score_answer({"answer": "Not discussed.", "answerable": False, "citations": [], "seen_lines": []},
                      {"id": "q2", "answerable": False, "facts": [], "evidence": []})
    assert no["correct"]
    s = summarise_answers([row, no])
    assert s["correct"] == 1.0 and s["citations_verified"] == 0.5 and s["false_abstentions"] == 0


def test_recover_submit_written_as_text():
    from elicitsense.qa import finish, recover_submit

    text = 'submit_answer {"answer": "Not discussed.", "answerable": false, "citations": [], "requirement_ids": []} </tool_call>'
    assert recover_submit(text)["answerable"] is False
    assert recover_submit("The deposit is $20.") is None
    rec = finish(_qa_project(), {"submitted": None, "final_text": text})
    assert rec["recovered_from_text"] and not rec["answerable"] and not rec["no_submit"]


def test_status_agreement_uses_coarse_statuses():
    from elicitsense.evaluate import coarse_status, summarise

    assert coarse_status("confirmed") == coarse_status("proposed") == "agreed"
    pairs = [{"type_ok": True, "uncertainty_ok": True, "gold_status": "agreed", "status_ok": True},
             {"type_ok": True, "uncertainty_ok": True, "gold_status": "superseded", "status_ok": False}]
    s = summarise([{"matched": pairs, "splits": [], "missed": [], "extra": [], "kept": 2, "rejected": 0}])
    assert s["status_agreement"] == 0.5 and s["special_status_recall"] == 0.0

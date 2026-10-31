from pathlib import Path

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
    for path in sorted((ROOT / "data/meetings").glob("*.txt")):
        script = parse_script(path)
        assert script.lines, path
        assert all(line.id.startswith("L") for line in script.lines)
    m1 = parse_script(ROOT / "data/meetings/m1_kickoff.txt")
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
    from elicitsense.extract import resolve_provider

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

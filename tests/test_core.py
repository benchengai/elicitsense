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

"""Merge per-meeting requirements into one project register.

Meetings are processed in order. For each meeting the LLM proposes links from
its new requirements to the register so far (or to each other, for changes
made within the meeting). The links are validated and applied
deterministically: statuses, supersession, open conflicts and history are
all computed here, not by the model.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .extract import render_transcript
from .llm import complete_json

INACTIVE = {"superseded", "rejected", "merged"}

SYSTEM = """You maintain a requirements register across a series of requirements \
elicitation meetings for one project. You are given the current register (requirements \
from earlier meetings, with ids and statuses), the requirements extracted from the \
newest meeting, and that meeting's transcript. Link every new requirement to the register.

Relations, always from a new requirement to a target:
- "same": restates the target without changing it.
- "refines": adds detail, a number, a condition or a narrower scope to the target \
without contradicting it.
- "supersedes": replaces the target, which no longer applies.
- "conflicts": contradicts the target, and the meeting did not settle which one holds.
- "status_change": the new item only records a decision about the target (for example \
that it is postponed, confirmed or dropped). Set new_status.
- "new": not related to any target. Leave target_id empty.

Rules:
- Every new requirement needs at least one link. It may have several, for example \
superseding one item while refining another.
- A target can be a register item or another item from the newest meeting, for changes \
made within the meeting.
- Link only items about the same need. Do not link an item to itself.
- new_status is empty unless the relation is "status_change".
- If the newest meeting settles an open conflict listed below the register, link the \
requirement that settles it with "supersedes" to whichever side no longer holds.
- explanation: one short sentence saying what changed."""

RELATIONS = ("same", "refines", "supersedes", "conflicts", "status_change", "new")
NEW_STATUSES = ("", "proposed", "confirmed", "open_question", "deferred", "rejected")

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["links"],
    "properties": {
        "links": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["new_id", "relation", "target_id", "new_status", "explanation"],
                "properties": {
                    "new_id": {"type": "string"},
                    "relation": {"type": "string", "enum": list(RELATIONS)},
                    "target_id": {"type": "string"},
                    "new_status": {"type": "string", "enum": list(NEW_STATUSES)},
                    "explanation": {"type": "string"},
                },
            },
        },
    },
}


class Link(BaseModel):
    new_id: str
    relation: Literal["same", "refines", "supersedes", "conflicts", "status_change", "new"]
    target_id: str
    new_status: Literal["", "proposed", "confirmed", "open_question", "deferred", "rejected"]
    explanation: str


class Linking(BaseModel):
    links: list[Link]


def empty_register() -> dict:
    return {"meetings": [], "items": {}, "relations": [], "dropped_links": [], "llm": []}


def render_prompt(register: dict, result: dict, transcript: dict) -> str:
    lines = ["Current register:"]
    items = register["items"]
    if not items:
        lines.append("(empty: this is the first meeting)")
    for item in items.values():
        lines.append(f"[{item['id']} | {item['type']} | {item['status']} | {item['meeting']}] {item['statement']}")
    if conflicts := open_conflicts(register):
        lines += ["", "Open conflicts:"]
        lines += [f"{c['from']} conflicts with {c['to']}: {c['explanation']}" for c in conflicts]
    m = result["meeting"]
    lines += ["", f"Requirements extracted from the newest meeting ({m['id']}: {m.get('title', '')}, {m.get('date', '')}):"]
    for r in result["requirements"]:
        lines.append(f"[{r['id']} | {r['type']} | {r['status']}] {r['statement']}")
        for ev in r["evidence"]:
            lines.append(f'    {ev["speaker"]}: "{ev["quote"]}"')
    lines += ["", "Transcript of the newest meeting:", render_transcript(transcript)]
    return "\n".join(lines)


def link_meeting(register: dict, result: dict, transcript: dict,
                 provider: str = "auto", model: str | None = None) -> tuple[Linking, dict]:
    text, meta = complete_json(SYSTEM, render_prompt(register, result, transcript), SCHEMA,
                               "register_links", provider, model)
    return Linking.model_validate_json(text), meta


def _history(item: dict, meeting: str, change: str, **extra) -> None:
    item["history"].append({"meeting": meeting, "change": change, **extra})


def _reinstate(item: dict, meeting: str, by: str) -> None:
    """A superseded requirement that is confirmed again applies once more."""
    if item["status"] == "superseded":
        item["superseded_by"] = None
        _history(item, meeting, f"reinstated by {by}")


def apply_links(register: dict, result: dict, linking: Linking) -> dict:
    meeting = result["meeting"]["id"]
    items = register["items"]
    register["meetings"].append(meeting)

    new_ids = []
    for r in result["requirements"]:
        items[r["id"]] = {**r, "meeting": meeting, "history": [], "merged_from": [],
                          "merged_into": None, "superseded_by": None}
        _history(items[r["id"]], meeting, f"raised as {r['status']}")
        new_ids.append(r["id"])

    linked = set()
    for link in linking.links:
        record = {"from": link.new_id, "kind": link.relation, "to": link.target_id,
                  "meeting": meeting, "explanation": link.explanation}
        if link.new_id not in new_ids:
            register["dropped_links"].append({**record, "reason": "unknown new requirement"})
            continue
        linked.add(link.new_id)
        if link.relation == "new":
            continue
        if link.target_id not in items or link.target_id == link.new_id:
            register["dropped_links"].append({**record, "reason": "unknown or self target"})
            continue
        if link.relation == "status_change" and not link.new_status:
            register["dropped_links"].append({**record, "reason": "status_change without new_status"})
            continue

        new, target = items[link.new_id], items[link.target_id]
        if link.relation == "same":
            target["evidence"] = target["evidence"] + new["evidence"]
            target["merged_from"].append(new["id"])
            if new["status"] == "confirmed":
                _reinstate(target, meeting, new["id"])
                target["status"] = "confirmed"
            new["status"], new["merged_into"] = "merged", target["id"]
            _history(target, meeting, f"restated as {new['id']}")
        elif link.relation == "status_change":
            if link.new_status != "rejected":
                _reinstate(target, meeting, new["id"])
            target["status"] = link.new_status
            new["status"], new["merged_into"] = "merged", target["id"]
            _history(target, meeting, f"status changed to {link.new_status}",
                     evidence=new["evidence"], note=link.explanation)
            record["new_status"] = link.new_status
        elif link.relation == "supersedes":
            target["status"], target["superseded_by"] = "superseded", new["id"]
            _history(target, meeting, f"superseded by {new['id']}", note=link.explanation)
        elif link.relation == "refines":
            _history(target, meeting, f"refined by {new['id']}", note=link.explanation)
        elif link.relation == "conflicts":
            _history(target, meeting, f"conflicts with {new['id']}", note=link.explanation)
        register["relations"].append(record)

    for rid in new_ids:
        if rid not in linked:
            register["dropped_links"].append({"from": rid, "kind": "new", "to": "", "meeting": meeting,
                                              "reason": "model returned no link; treated as new"})
    return register


def open_conflicts(register: dict) -> list[dict]:
    items = register["items"]
    return [r for r in register["relations"]
            if r["kind"] == "conflicts"
            and items[r["from"]]["status"] not in INACTIVE
            and items[r["to"]]["status"] not in INACTIVE]


def finalise(register: dict) -> dict:
    items = list(register["items"].values())
    return {
        "meetings": register["meetings"],
        "active": [i["id"] for i in items if i["status"] not in INACTIVE],
        "open_conflicts": open_conflicts(register),
        "requirements": items,
        "relations": register["relations"],
        "dropped_links": register["dropped_links"],
        "llm": register["llm"],
    }

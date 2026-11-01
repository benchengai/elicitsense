"""Score extracted requirements against gold labels.

Extracted and gold requirements are paired by the transcript lines their
evidence cites (one-to-one, largest overlap first). An unpaired extracted item
whose evidence overlaps an already-paired gold item is counted as a *split*
(finer granularity than the gold label, e.g. "choose a practitioner" and "see
their times" for one gold item), not as an invented requirement. An unpaired
item whose evidence is a line the gold marks as a status change or a mention of
an existing requirement ("let's leave the waitlist out") is counted as a
*mention* of that requirement. This is an automatic first pass; the paired
statements are printed for spot-checking.
"""

from __future__ import annotations


def _pairs(preds: dict[str, set[str]], golds: dict[str, set[str]]) -> list[tuple[str, str]]:
    candidates = []
    for gid, g_lines in golds.items():
        for pid, p_lines in preds.items():
            if overlap := len(g_lines & p_lines):
                candidates.append((overlap, overlap / len(g_lines | p_lines), gid, pid))
    candidates.sort(key=lambda c: (-c[0], -c[1], c[2], c[3]))
    used_g, used_p, pairs = set(), set(), []
    for _, _, gid, pid in candidates:
        if gid not in used_g and pid not in used_p:
            used_g.add(gid)
            used_p.add(pid)
            pairs.append((gid, pid))
    return sorted(pairs)


def score_meeting(result: dict, segments: list[dict], gold: dict) -> dict:
    meeting = result["meeting"]["id"]
    seg_line = {s["id"]: f"{meeting}:{s['source_line']}" for s in segments}
    golds = {g["id"]: g for g in gold["requirements"] if g["meeting"] == meeting}
    preds = {r["id"]: r for r in result["requirements"]}

    pred_lines = {pid: {seg_line[e["segment_id"]] for e in r["evidence"]} for pid, r in preds.items()}
    gold_lines = {gid: set(g["evidence"]) for gid, g in golds.items()}
    pairs = _pairs(pred_lines, gold_lines)
    matched = [{
        "gold": gid,
        "pred": pid,
        "pred_statement": preds[pid]["statement"],
        "gold_statement": golds[gid]["statement"],
        "type_ok": preds[pid]["type"] == golds[gid]["type"],
        "uncertainty_ok": preds[pid]["uncertainty"]["flag"] == golds[gid]["uncertain"],
    } for gid, pid in pairs]
    matched_g = {m["gold"] for m in matched}
    matched_p = {m["pred"] for m in matched}
    mention_lines = {line: m["requirement"]
                     for m in gold.get("status_changes", []) + gold.get("mentions", [])
                     if m["meeting"] == meeting for line in m["evidence"]}
    splits, mentions, extra = [], [], []
    for pid, r in preds.items():
        if pid in matched_p:
            continue
        parent = next((gid for gid in sorted(matched_g) if gold_lines[gid] & pred_lines[pid]), None)
        mentioned = next((mention_lines[line] for line in sorted(pred_lines[pid]) if line in mention_lines), None)
        if parent:
            splits.append({"gold": parent, "pred": pid, "pred_statement": r["statement"]})
        elif mentioned:
            mentions.append({"gold": mentioned, "pred": pid, "pred_statement": r["statement"]})
        else:
            extra.append(r)
    return {
        "meeting": meeting,
        "matched": matched,
        "splits": splits,
        "mentions": mentions,
        "missed": [g for gid, g in golds.items() if gid not in matched_g],
        "extra": extra,
        "kept": len(preds),
        "rejected": len(result.get("rejected", [])),
    }


def summarise(reports: list[dict]) -> dict:
    matched = sum(len(r["matched"]) for r in reports)
    splits = sum(len(r["splits"]) for r in reports)
    mentions = sum(len(r.get("mentions", [])) for r in reports)
    missed = sum(len(r["missed"]) for r in reports)
    extra = sum(len(r["extra"]) for r in reports)
    kept = sum(r["kept"] for r in reports)
    rejected = sum(r["rejected"] for r in reports)
    # Splits and mentions are grounded in a gold requirement, so they count as correct extractions.
    precision = (matched + splits + mentions) / kept if kept else 0.0
    recall = matched / (matched + missed) if matched + missed else 0.0
    pairs = [m for r in reports for m in r["matched"]]
    return {
        "matched": matched, "splits": splits, "mentions": mentions, "missed": missed, "extra": extra,
        "precision": precision,
        "strict_precision": matched / kept if kept else 0.0,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "evidence_validity": kept / (kept + rejected) if kept + rejected else 0.0,
        "type_agreement": sum(m["type_ok"] for m in pairs) / len(pairs) if pairs else 0.0,
        "uncertainty_agreement": sum(m["uncertainty_ok"] for m in pairs) / len(pairs) if pairs else 0.0,
    }


SCORED_KINDS = {"refines", "supersedes", "conflicts"}


def score_register(register: dict, reports: list[dict], gold: dict) -> dict:
    """Score cross-meeting relations, status changes and the conflicts left open,
    mapping register ids to gold ids through the per-meeting pairing (splits and
    mentions map to their gold item)."""
    to_gold = {}
    for r in reports:
        to_gold.update({m["pred"]: m["gold"] for m in r["matched"]})
        to_gold.update({sp["pred"]: sp["gold"] for sp in r["splits"] + r.get("mentions", [])})

    predicted = [r for r in register["relations"] if r["kind"] in SCORED_KINDS]
    gold_pairs = {(g["from"], g["to"]) for g in gold["relations"]}

    rows = []
    for g in gold["relations"]:
        kinds = {p["kind"] for p in predicted
                 if to_gold.get(p["from"]) == g["from"] and to_gold.get(p["to"]) == g["to"]}
        found = g["kind"] if g["kind"] in kinds else (sorted(kinds)[0] if kinds else None)
        verdict = "FOUND" if found == g["kind"] else ("WRONG-KIND" if found else "MISSED")
        rows.append({**g, "found_kind": found, "verdict": verdict})

    spurious, correct = [], 0
    for p in predicted:
        a, b = to_gold.get(p["from"]), to_gold.get(p["to"])
        if a and a == b:
            continue  # link between splits of one gold item
        if (a, b) in gold_pairs or (b, a) in gold_pairs:
            correct += 1
        else:
            spurious.append(p)

    items = {i["id"]: i for i in register["requirements"]}
    status_rows = []
    for sc in gold.get("status_changes", []):
        found = sorted({i["status"] for rid, i in items.items() if to_gold.get(rid) == sc["requirement"]})
        status_rows.append({**sc, "found": found, "ok": sc["status"] in found})

    expected_open = [(c["from"], c["to"]) for c in gold.get("open_conflicts_after", [])]
    predicted_open = {frozenset((to_gold.get(c["from"]), to_gold.get(c["to"])))
                      for c in register["open_conflicts"]}
    open_found = sum(frozenset(pair) in predicted_open for pair in expected_open)

    scored = correct + len(spurious)
    return {
        "gold_relations": rows,
        "spurious": spurious,
        "recall": sum(r["verdict"] == "FOUND" for r in rows) / len(rows) if rows else 0.0,
        "recall_any": sum(r["verdict"] != "MISSED" for r in rows) / len(rows) if rows else 0.0,
        "precision": correct / scored if scored else 0.0,
        "status_changes": status_rows,
        "status_ok": sum(r["ok"] for r in status_rows),
        "open_conflicts_expected": len(expected_open),
        "open_conflicts_found": open_found,
        "open_conflicts_unexpected": len(register["open_conflicts"]) - open_found,
    }

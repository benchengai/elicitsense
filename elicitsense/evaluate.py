"""Score extracted requirements against gold labels.

Extracted and gold requirements are paired by the transcript lines their
evidence cites (one-to-one, largest overlap first). An unpaired extracted item
whose evidence overlaps an already-paired gold item is counted as a *split*
(finer granularity than the gold label, e.g. "choose a practitioner" and "see
their times" for one gold item), not as an invented requirement. This is an
automatic first pass; the paired statements are printed for spot-checking.
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
    splits, extra = [], []
    for pid, r in preds.items():
        if pid in matched_p:
            continue
        parent = next((gid for gid in sorted(matched_g) if gold_lines[gid] & pred_lines[pid]), None)
        if parent:
            splits.append({"gold": parent, "pred": pid, "pred_statement": r["statement"]})
        else:
            extra.append(r)
    return {
        "meeting": meeting,
        "matched": matched,
        "splits": splits,
        "missed": [g for gid, g in golds.items() if gid not in matched_g],
        "extra": extra,
        "kept": len(preds),
        "rejected": len(result.get("rejected", [])),
    }


def summarise(reports: list[dict]) -> dict:
    matched = sum(len(r["matched"]) for r in reports)
    splits = sum(len(r["splits"]) for r in reports)
    missed = sum(len(r["missed"]) for r in reports)
    extra = sum(len(r["extra"]) for r in reports)
    kept = sum(r["kept"] for r in reports)
    rejected = sum(r["rejected"] for r in reports)
    # Splits are grounded in a gold requirement, so they count as correct extractions.
    precision = (matched + splits) / kept if kept else 0.0
    recall = matched / (matched + missed) if matched + missed else 0.0
    pairs = [m for r in reports for m in r["matched"]]
    return {
        "matched": matched, "splits": splits, "missed": missed, "extra": extra,
        "precision": precision,
        "strict_precision": matched / kept if kept else 0.0,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "evidence_validity": kept / (kept + rejected) if kept + rejected else 0.0,
        "type_agreement": sum(m["type_ok"] for m in pairs) / len(pairs) if pairs else 0.0,
        "uncertainty_agreement": sum(m["uncertainty_ok"] for m in pairs) / len(pairs) if pairs else 0.0,
    }

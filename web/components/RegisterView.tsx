"use client";

import { useEffect, useMemo, useState } from "react";
import { clock, CUE_LABEL, isActive, QUALITY_LABEL, RELATION_TONE, statusBadge, TYPE_LABEL } from "@/lib/format";
import { download, toJiraCsv, toMarkdown, type Review, type Reviews } from "@/lib/export";
import type { Meeting, Register, Requirement } from "@/lib/types";

type Props = {
  title: string;
  project: string;
  register: Register;
  meetings: Meeting[];
  reviews: Reviews;
  setReview: (id: string, review: Review) => void;
  play: (meeting: string, time: number, segment: string) => void;
  focus: { id: string; nonce: number } | null;
};

type Filter = "active" | "confirm" | "open" | "all";

const VERB_OUT: Record<string, string> = {
  refines: "refines",
  supersedes: "supersedes",
  conflicts: "conflicts with",
  status_change: "changes status of",
};
const VERB_IN: Record<string, string> = {
  refines: "refined by",
  supersedes: "superseded by",
  conflicts: "conflicts with",
  status_change: "status changed by",
};

export default function RegisterView({ title, project, register, meetings, reviews, setReview, play, focus }: Props) {
  const [filter, setFilter] = useState<Filter>("active");
  const [type, setType] = useState("any");
  const [query, setQuery] = useState("");
  const byId = useMemo(() => new Map(register.requirements.map((r) => [r.id, r])), [register]);

  const [lastFocus, setLastFocus] = useState(focus);
  if (focus !== lastFocus) {
    setLastFocus(focus);
    const target = focus && byId.get(focus.id);
    if (target && !isActive(target)) setFilter("all");
    setType("any");
    setQuery("");
  }

  useEffect(() => {
    if (!focus) return;
    const t = setTimeout(() => {
      const el = document.getElementById(focus.id);
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
      el?.classList.add("flash");
      setTimeout(() => el?.classList.remove("flash"), 1600);
    }, 60);
    return () => clearTimeout(t);
  }, [focus, byId]);

  const shown = register.requirements.filter((r) => {
    if (filter === "active" && !isActive(r)) return false;
    if (filter === "confirm" && !(isActive(r) && r.uncertainty.flag)) return false;
    if (filter === "open" && r.status !== "open_question") return false;
    if (type !== "any" && r.type !== type) return false;
    if (query && !`${r.id} ${r.statement} ${r.stakeholder}`.toLowerCase().includes(query.toLowerCase())) return false;
    return true;
  });

  const active = register.requirements.filter(isActive);
  const counts = {
    active: active.length,
    confirm: active.filter((r) => r.uncertainty.flag).length,
    open: register.requirements.filter((r) => r.status === "open_question").length,
    all: register.requirements.length,
  };

  return (
    <div className="stack">
      {register.open_conflicts.map((c) => (
        <div key={`${c.from}-${c.to}`} className="notice danger">
          <strong>Open conflict, not settled in a later meeting.</strong>{" "}
          <a href={`#${c.from}`}>{c.from}</a> {byId.get(c.from)?.statement}{" "}
          <span className="badge danger">conflicts with</span> <a href={`#${c.to}`}>{c.to}</a>{" "}
          {byId.get(c.to)?.statement} <span className="muted">({c.explanation})</span>
        </div>
      ))}

      <div className="row toolbar">
        {(["active", "confirm", "open", "all"] as Filter[]).map((f) => (
          <button key={f} className="btn small" aria-pressed={filter === f} onClick={() => setFilter(f)}>
            {{ active: "Active", confirm: "Needs confirmation", open: "Open questions", all: "All, with history" }[f]}{" "}
            <span className="faint">{counts[f]}</span>
          </button>
        ))}
        <select value={type} onChange={(e) => setType(e.target.value)} aria-label="Requirement type">
          <option value="any">Any type</option>
          {Object.entries(TYPE_LABEL).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <input type="search" placeholder="Filter by words or id" value={query} onChange={(e) => setQuery(e.target.value)} />
        <span className="spacer" />
        <span className="faint small">Export</span>
        <button className="btn small" onClick={() => download(`${project}-requirements.md`, toMarkdown(title, register.requirements, meetings, reviews), "text/markdown")}>
          Markdown
        </button>
        <button className="btn small" onClick={() => download(`${project}-jira.csv`, toJiraCsv(register.requirements, meetings, reviews), "text/csv")}>
          Jira CSV
        </button>
      </div>

      {shown.length === 0 && <p className="muted">No requirements match.</p>}
      {shown.map((r) => (
        <RequirementCard
          key={r.id}
          r={r}
          register={register}
          byId={byId}
          meetings={meetings}
          review={reviews[r.id] ?? {}}
          setReview={(rv) => setReview(r.id, rv)}
          play={play}
        />
      ))}
    </div>
  );
}

function RequirementCard({
  r,
  register,
  byId,
  meetings,
  review,
  setReview,
  play,
}: {
  r: Requirement;
  register: Register;
  byId: Map<string, Requirement>;
  meetings: Meeting[];
  review: Review;
  setReview: (r: Review) => void;
  play: Props["play"];
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(review.statement ?? r.statement);
  const status = statusBadge(r);
  const relations = register.relations.filter((x) => x.kind !== "same" && (x.from === r.id || x.to === r.id));
  const date = (id: string) => meetings.find((m) => m.id === id)?.date ?? "";
  const decide = (d: Review["decision"]) => setReview({ ...review, decision: review.decision === d ? undefined : d });

  return (
    <article id={r.id} className={`card req ${isActive(r) ? "" : "inactive"} ${review.decision === "rejected" ? "rejected" : ""}`}>
      <div className="row req-head">
        <span className="mono req-id">{r.id}</span>
        <span className="badge outline">{TYPE_LABEL[r.type]}</span>
        <span className={`badge ${status.tone}`}>{status.label}</span>
        {r.uncertainty.flag && (
          <span className="badge warn" title="The stakeholder hesitated while stating this. Confirm it with them.">
            needs confirmation
          </span>
        )}
        <span className="faint small">
          {r.stakeholder} · raised in {r.meeting} ({date(r.meeting)})
        </span>
      </div>

      {editing ? (
        <div className="stack">
          <textarea rows={2} value={draft} onChange={(e) => setDraft(e.target.value)} />
          <div className="row">
            <button className="btn small primary" onClick={() => { setReview({ ...review, statement: draft }); setEditing(false); }}>
              Save wording
            </button>
            <button className="btn small" onClick={() => { setDraft(r.statement); setReview({ ...review, statement: undefined }); setEditing(false); }}>
              Revert to extracted
            </button>
          </div>
        </div>
      ) : (
        <p className="req-statement">
          {review.statement ?? r.statement}
          {review.statement && <span className="badge outline" style={{ marginLeft: 8 }}>edited</span>}
        </p>
      )}

      {r.uncertainty.flag && (
        <p className="small cues">
          Cues: {r.uncertainty.cues.map((c) => `${CUE_LABEL[c.kind] ?? c.kind} (${c.detail})`).join("; ")}
        </p>
      )}
      {r.quality.length > 0 && (
        <div className="row">
          {r.quality.map((q, i) => (
            <span key={i} className="badge outline" title={q.detail}>
              {QUALITY_LABEL[q.kind] ?? q.kind}
              {q.kind !== "missing_acceptance" && `: ${q.detail}`}
            </span>
          ))}
        </div>
      )}
      {r.acceptance.length > 0 && (
        <ul className="small acceptance">
          {r.acceptance.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
      )}

      <div className="evidence">
        {r.evidence.map((e, i) => (
          <button key={i} className="quote" onClick={() => play(e.meeting, e.start, e.segment_id)} title="Play this moment">
            <span className="meta">
              ▶ {e.meeting} {clock(e.start)} {e.speaker}
            </span>
            “{e.quote}”
          </button>
        ))}
      </div>

      {relations.length > 0 && (
        <ul className="relations small">
          {relations.map((x, i) => {
            const outgoing = x.from === r.id;
            const other = outgoing ? x.to : x.from;
            return (
              <li key={i}>
                <span className={`badge ${RELATION_TONE[x.kind] ?? ""}`}>{(outgoing ? VERB_OUT : VERB_IN)[x.kind] ?? x.kind}</span>{" "}
                <a href={`#${other}`} className="mono">{other}</a>{" "}
                <span className="muted">{byId.get(other)?.statement}</span>{" "}
                <span className="faint">({x.meeting}: {x.explanation})</span>
              </li>
            );
          })}
        </ul>
      )}

      {r.history.length > 1 && (
        <details className="small history">
          <summary>History ({r.history.length})</summary>
          <ol>
            {r.history.map((h, i) => (
              <li key={i}>
                <span className="mono">{h.meeting}</span> {h.change}
                {h.note && <span className="muted"> · {h.note}</span>}
              </li>
            ))}
          </ol>
        </details>
      )}

      <div className="row review">
        <span className="faint small">Review</span>
        <button className="btn small" aria-pressed={review.decision === "accepted"} onClick={() => decide("accepted")}>Accept</button>
        <button className="btn small" aria-pressed={review.decision === "follow_up"} onClick={() => decide("follow_up")}>Follow up</button>
        <button className="btn small" aria-pressed={review.decision === "rejected"} onClick={() => decide("rejected")}>Reject</button>
        <button className="btn small" onClick={() => setEditing((v) => !v)}>Edit wording</button>
      </div>
    </article>
  );
}

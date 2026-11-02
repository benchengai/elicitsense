"use client";

import { RELATION_TONE } from "@/lib/format";
import type { Meeting, Register } from "@/lib/types";

const VERB: Record<string, string> = {
  refines: "refines",
  supersedes: "supersedes",
  conflicts: "conflicts with",
  status_change: "changes the status of",
};

// What each meeting changed: new requirements and the links the merge step recorded.
export default function ChangesView({ register, meetings }: { register: Register; meetings: Meeting[] }) {
  const byId = new Map(register.requirements.map((r) => [r.id, r]));
  return (
    <div className="stack">
      <p className="muted small">
        For each meeting, the model proposed how its requirements relate to the register so far. Statuses,
        supersession and open conflicts were then applied by code, not by the model. Restatements are counted but not
        listed.
      </p>
      {meetings.map((m) => {
        const raised = register.requirements.filter((r) => r.meeting === m.id);
        const links = register.relations.filter((x) => x.meeting === m.id && x.kind !== "same");
        const same = register.relations.filter((x) => x.meeting === m.id && x.kind === "same").length;
        return (
          <section key={m.id} className="card">
            <h3>
              {m.id} · {m.title} <span className="faint small">{m.date}</span>
            </h3>
            <p className="small muted">
              {raised.length} items extracted · {links.length} links to earlier or same-meeting requirements · {same}{" "}
              restatements
            </p>
            {links.length === 0 ? (
              <p className="small faint">No changes to earlier requirements.</p>
            ) : (
              <ul className="changes">
                {links.map((x, i) => (
                  <li key={i}>
                    <div className="row">
                      <a href={`#${x.from}`} className="mono small">{x.from}</a>
                      <span className={`badge ${RELATION_TONE[x.kind] ?? ""}`}>
                        {VERB[x.kind] ?? x.kind}
                        {x.new_status ? ` → ${x.new_status.replace("_", " ")}` : ""}
                      </span>
                      <a href={`#${x.to}`} className="mono small">{x.to}</a>
                    </div>
                    <div className="small">
                      <span>{byId.get(x.from)?.statement}</span>
                      <span className="faint"> ← vs → </span>
                      <span className="muted">{byId.get(x.to)?.statement}</span>
                    </div>
                    <div className="small faint">{x.explanation}</div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </div>
  );
}

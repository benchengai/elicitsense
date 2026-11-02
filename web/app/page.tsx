import Link from "next/link";
import { evaluation, projects } from "@/lib/data";
import type { ModelRow, Stat } from "@/lib/types";

const mean = (row: ModelRow | undefined, key: string) => (row?.[key] as Stat | undefined)?.mean;
const pct = (v: number | undefined) => (v == null ? "–" : v.toFixed(2));

const STEPS = [
  ["Record", "Client elicitation meetings, with consent"],
  ["Transcribe", "Locally with faster-whisper; audio never leaves the machine"],
  ["Cues", "Hedges, fillers, pauses, slow speech, per utterance"],
  ["Extract", "LLM with a strict JSON schema; quotes are checked against the transcript"],
  ["Merge", "Model proposes links across meetings; code applies statuses and conflicts"],
  ["Ask", "Tool-using agent; every cited quote is checked"],
];

export default function Home() {
  const list = projects();
  const ev = evaluation().projects;
  const held = ev["fernhill_bakery"];
  const dev = ev["harbour_physio"];
  const sol = "openai:gpt-6.1-sol";
  const route = "openai:gpt-6-luna>openai:gpt-6.1-sol";
  const routeCost = mean(held?.["constrained-ids"][route], "cost_usd");
  const solCost = mean(held?.["constrained-ids"][sol], "cost_usd");

  return (
    <div className="wrap">
      <section className="hero">
        <h1>Meeting recordings in, a requirements register out.</h1>
        <p className="lead">
          ElicitSense turns requirements-elicitation meetings into a register an analyst can review: every requirement
          cites the exact words and moment it came from, hesitant statements are flagged for confirmation, changes are
          tracked across meetings, and questions are answered with checked citations.
        </p>
        <div className="row">
          <Link className="btn primary" href="/p/fernhill_bakery/">Open the held-out demo</Link>
          <Link className="btn" href="/p/harbour_physio/">Development demo</Link>
          <Link className="btn" href="/evaluation/">Evaluation</Link>
        </div>
      </section>

      <section className="steps">
        {STEPS.map(([name, text], i) => (
          <div key={name} className="step">
            <span className="step-n">{i + 1}</span>
            <strong>{name}</strong>
            <span className="small muted">{text}</span>
          </div>
        ))}
      </section>

      <section className="grid-2" style={{ marginTop: 24 }}>
        {list.map((p) => (
          <Link key={p.id} href={`/p/${p.id}/`} className="card project-card">
            <div className="row">
              <span className={`badge ${p.heldout ? "warn" : "accent"}`}>{p.heldout ? "held out" : "development"}</span>
              <span className="badge outline">synthetic</span>
            </div>
            <h2 style={{ marginTop: 8 }}>{p.title}</h2>
            <p className="muted small">
              {p.meetings.map((m) => m.title).join(" → ")}
            </p>
            <p className="small">
              {p.counts.active} active requirements · {p.counts.relations} recorded changes ·{" "}
              {p.counts.open_conflicts ? `${p.counts.open_conflicts} open conflict` : "no open conflicts"}
            </p>
          </Link>
        ))}
      </section>

      <section style={{ marginTop: 32 }}>
        <h2>What the evaluation found</h2>
        <p className="muted small">
          From real benchmark runs, three per model, on the development and held-out projects. Small synthetic data: read
          these as a smoke test, not a benchmark. <Link href="/evaluation/">Full tables</Link>.
        </p>
        <div className="grid-3">
          <div className="card stat">
            <span className="stat-n">{pct(mean(dev?.baseline[sol], "rel_recall"))} / {pct(mean(held?.baseline[sol], "rel_recall"))}</span>
            <span className="small">cross-meeting changes found with the right kind by <code>gpt-6.1-sol</code> (dev / held out)</span>
          </div>
          <div className="card stat">
            <span className="stat-n">
              {routeCost && solCost ? `${Math.round((1 - routeCost / solCost) * 100)}% cheaper` : "–"}
            </span>
            <span className="small">routing extraction to <code>gpt-6-luna</code> and merge to <code>gpt-6.1-sol</code>; the unresolved conflict was kept in every held-out run</span>
          </div>
          <div className="card stat">
            <span className="stat-n">{pct(mean(held?.qa["openai:gpt-6-luna"], "correct"))}</span>
            <span className="small">held-out questions answered correctly by the cheapest model, at about $0.001 per question, every answer with a verified citation</span>
          </div>
        </div>
      </section>

      <section className="grid-2" style={{ marginTop: 32 }}>
        <div className="card">
          <h3>Grounded in research</h3>
          <p className="small">
            Built from the systematic mapping study <em>Emotions in Software Engineering</em> (57 studies) and the
            multimodal elicitation prototype MEmoRE (IEEE RE 2023). Requirements engineering is among the least-studied
            phases for emotion research, and no study in the map evaluates a tool that supports stakeholder
            communication as it happens.
          </p>
          <Link href="/method/" className="small">Research basis, privacy and limitations →</Link>
        </div>
        <div className="card">
          <h3>Cues, not emotion labels</h3>
          <p className="small">
            ElicitSense reports observable cues (hedging, fillers, pauses, slow speech) on a requirement, never an
            emotion and never a score for a person. Cues are off for internal team meetings, because the EU AI Act
            prohibits AI emotion inference in the workplace.
          </p>
        </div>
      </section>
    </div>
  );
}

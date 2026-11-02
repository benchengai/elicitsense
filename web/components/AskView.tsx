"use client";

import { useMemo, useState } from "react";
import { BM25 } from "@/lib/bm25";
import { clock, usd } from "@/lib/format";
import type { Answer, Meeting, QA, Register } from "@/lib/types";

type Hit = { kind: "segment"; meeting: string; id: string; speaker: string; start: number; text: string };

type Props = {
  qa: QA;
  register: Register;
  meetings: Meeting[];
  play: (meeting: string, time: number, segment: string) => void;
};

export default function AskView({ qa, meetings, play }: Props) {
  const [query, setQuery] = useState("");
  const segments = useMemo(
    () => meetings.flatMap((m) => m.segments.map((s): Hit => ({ kind: "segment", meeting: m.id, id: s.id, speaker: s.speaker, start: s.start, text: s.text }))),
    [meetings],
  );
  const index = useMemo(() => new BM25(segments, (h) => `${h.speaker} ${h.text}`), [segments]);
  const hits = query.trim() ? index.search(query, 6) : [];
  const seg = (ref: string) => {
    const [mid, sid] = ref.split(":");
    const s = meetings.find((m) => m.id === mid)?.segments.find((x) => x.id === sid);
    return s ? { mid, s } : null;
  };

  return (
    <div className="stack">
      <div className="card">
        <h3>Search the meetings</h3>
        <p className="small muted">
          Keyword search (BM25) over every transcript, running in your browser. The full agent below also uses dense
          embeddings and tools, which need an API key, so in this demo its answers are recorded.
        </p>
        <input
          type="search"
          style={{ width: "100%" }}
          placeholder="e.g. deposit refund, credit limit, Xero"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {hits.length > 0 && (
          <div className="evidence" style={{ marginTop: 10 }}>
            {hits.map(({ item: h }) => (
              <button key={`${h.meeting}:${h.id}`} className="quote" onClick={() => play(h.meeting, h.start, h.id)}>
                <span className="meta">
                  ▶ {h.meeting} {clock(h.start)} {h.speaker}
                </span>
                {h.text}
              </button>
            ))}
          </div>
        )}
        {query.trim() && hits.length === 0 && <p className="small faint" style={{ marginTop: 8 }}>No matching words.</p>}
      </div>

      <div className="notice">
        <strong>Recorded answers.</strong> Each answer below is the output of one real run of the Q&A agent (
        <code>{qa.spec}</code>, run 1 of the benchmark) on the evaluation questions, including the ones it should
        decline. Quote checks were done by code after the run. To ask your own questions, run{" "}
        <code>elicitsense ask runs/&lt;project&gt; &quot;…&quot;</code> locally.
      </div>

      {qa.answers.map((a) => (
        <AnswerCard key={a.id} a={a} seg={seg} play={play} />
      ))}
    </div>
  );
}

function AnswerCard({
  a,
  seg,
  play,
}: {
  a: Answer;
  seg: (ref: string) => { mid: string; s: Meeting["segments"][number] } | null;
  play: Props["play"];
}) {
  const verdict = !a.answerable
    ? { label: "not in the meetings", tone: "" }
    : a.supported
      ? { label: "answered, citations verified", tone: "ok" }
      : { label: "unsupported", tone: "danger" };
  return (
    <details className="card answer" open={false}>
      <summary>
        <span className="answer-q">{a.question}</span>{" "}
        <span className={`badge ${verdict.tone}`}>{verdict.label}</span>
        {!a.gold_answerable && <span className="badge outline">never discussed</span>}
      </summary>
      <p style={{ marginTop: 10 }}>{a.answer}</p>
      {a.citations.length > 0 && (
        <div className="evidence">
          {a.citations.map((c, i) => {
            const hit = seg(c.segment);
            return (
              <button
                key={i}
                className={`quote ${c.verified ? "" : "bad"}`}
                onClick={() => hit && play(hit.mid, hit.s.start, hit.s.id)}
                title={c.verified ? "Quote verified against the transcript. Play it." : "Quote not found in the cited segment"}
              >
                <span className="meta">
                  {c.verified ? "✓" : "✗"} {c.segment} {hit ? `${clock(hit.s.start)} ${hit.s.speaker}` : ""}
                </span>
                “{c.quote}”
              </button>
            );
          })}
        </div>
      )}
      <p className="small faint" style={{ marginTop: 8, marginBottom: 0 }}>
        {a.requirement_ids.length > 0 && (
          <>
            Requirements:{" "}
            {a.requirement_ids.map((id, i) => (
              <span key={id}>
                {i > 0 && ", "}
                <a href={`#${id}`} className="mono">{id}</a>
              </span>
            ))}
            {" · "}
          </>
        )}
        Tools: {a.tools.join(", ") || "none"} · {a.model} · {usd(a.cost_usd)} · {a.latency_s.toFixed(1)} s
      </p>
    </details>
  );
}

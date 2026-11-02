import type { Metadata } from "next";
import { CostScatter, GroupedBars, type Bar, type Point } from "@/components/Charts";
import { evaluation } from "@/lib/data";
import type { ModelRow, Stat } from "@/lib/types";

export const metadata: Metadata = { title: "Evaluation · ElicitSense" };

const NAMES: Record<string, string> = {
  "openai:gpt-6.1-sol": "gpt-6.1-sol",
  "openai:gpt-6.1-terra": "gpt-6.1-terra",
  "openai:gpt-6-luna": "gpt-6-luna",
  "ollama:qwen3:8b": "qwen3:8b (local)",
  "openai:gpt-6-luna>openai:gpt-6.1-sol": "luna extracts > sol merges",
  "ollama:qwen3:8b>openai:gpt-6.1-sol": "qwen extracts > sol merges",
};

const st = (row: ModelRow | undefined, key: string) => row?.[key] as Stat | undefined;
const triple = (s: Stat | undefined): [number, number, number] | undefined => (s ? [s.mean, s.min, s.max] : undefined);
const f = (s: Stat | undefined, digits = 2) => {
  if (!s) return "–";
  const m = s.mean.toFixed(digits);
  return s.min.toFixed(digits) === s.max.toFixed(digits) ? m : `${m} (${s.min.toFixed(digits)}–${s.max.toFixed(digits)})`;
};
const money = (s: Stat | undefined) => (s ? (s.mean === 0 ? "local" : `$${s.mean.toFixed(3)}`) : "–");

export default function Evaluation() {
  const ev = evaluation().projects;
  const dev = ev["harbour_physio"];
  const held = ev["fernhill_bakery"];
  const specs = Object.keys(NAMES);

  const bars: Bar[] = specs.map((spec) => ({
    label: NAMES[spec],
    dev: triple(st(dev["constrained-ids"][spec], "rel_recall")),
    held: triple(st(held["constrained-ids"][spec], "rel_recall")),
  }));
  const points: Point[] = specs
    .filter((spec) => !spec.startsWith("ollama:qwen3:8b") || spec.includes(">"))
    .map((spec) => {
      const row = held["constrained-ids"][spec];
      return {
        label: NAMES[spec],
        x: st(row, "cost_usd")!.mean,
        y: st(row, "rel_recall")!.mean,
        note: `$${st(row, "cost_usd")!.mean.toFixed(3)} per project run, relations ${st(row, "rel_recall")!.mean.toFixed(2)}, open conflict kept in ${row.open_ok} of ${row.runs} runs`,
      };
    });

  return (
    <div className="wrap">
      <div className="page-head">
        <h1>Evaluation</h1>
        <p className="muted">
          Every number comes from <code>elicitsense bench</code> and <code>bench-qa</code> runs: each model runs each
          project three times on identical transcripts. Development set: Harbour Physio (prompts were written against it).
          Held-out set: Fernhill Bakery (written before any model ran on it). Small synthetic projects; one relation
          moves recall by 0.11 to 0.14, so treat differences of that size as noise.
        </p>
      </div>

      <div className="stack">
        <GroupedBars rows={bars} title="Cross-meeting changes found with the right kind" unit="recall" />
        <p className="small muted">
          Extraction is not where models differ (every API model finds all gold requirements and every quote verifies).
          Linking requirements across meetings is. Only runs that merge with <code>gpt-6.1-sol</code>, on its own or
          after <code>gpt-6-luna</code> extracted, kept the held-out project&rsquo;s unresolved disagreement open in every
          run. The local model&rsquo;s held-out bar is not a stable result: on the development set it found almost none.
        </p>

        <CostScatter
          points={points}
          title="Held-out project: cost against changes found"
          xLabel="cost per project run (USD, log scale)"
          yLabel="relations found"
        />
        <p className="small muted">
          Routing the cheap model to extraction and the strong one to merging costs about half as much and keeps the
          unresolved conflict. The local model runs at no per-token cost but is left off this chart (it has no position on
          a log scale); see the table.
        </p>

        <section className="card">
          <h2>Extraction and merge</h2>
          <p className="small muted">Merge link ids restricted to the ids in the prompt. Mean over 3 runs (range).</p>
          {[
            ["Development set", dev],
            ["Held-out set", held],
          ].map(([name, data]) => (
            <div key={name as string} className="table-scroll" style={{ marginTop: 12 }}>
              <h3>{name as string}</h3>
              <table>
                <thead>
                  <tr>
                    <th>Extract &gt; merge</th>
                    <th className="num">Req. recall</th>
                    <th className="num">Quotes verified</th>
                    <th className="num">Relations, right kind</th>
                    <th className="num">Relation precision</th>
                    <th className="num">Status changes</th>
                    <th className="num">Open conflicts right</th>
                    <th className="num">Cost / run</th>
                    <th className="num">Time / run (s)</th>
                  </tr>
                </thead>
                <tbody>
                  {specs.map((spec) => {
                    const row = (data as typeof dev)["constrained-ids"][spec];
                    if (!row) return null;
                    return (
                      <tr key={spec}>
                        <td>{NAMES[spec]}</td>
                        <td className="num">{f(st(row, "req_recall"))}</td>
                        <td className="num">{f(st(row, "evidence_verified"))}</td>
                        <td className="num">{f(st(row, "rel_recall"))}</td>
                        <td className="num">{f(st(row, "rel_precision"))}</td>
                        <td className="num">{f(st(row, "status_ok"))}</td>
                        <td className="num">{row.open_ok as number} of {row.runs as number}</td>
                        <td className="num">{money(st(row, "cost_usd"))}</td>
                        <td className="num">{f(st(row, "latency_s"), 0)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ))}
        </section>

        <section className="card">
          <h2>Q&amp;A agent</h2>
          <p className="small muted">
            {dev.qa_questions} development and {held.qa_questions} held-out questions, including two per project the
            meetings never discussed. Correct means every gold fact stated, or declining an unanswerable question.
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Model</th>
                  <th className="num">Correct (dev / held out)</th>
                  <th className="num">Declined unanswerable</th>
                  <th className="num">Answers with a verified citation</th>
                  <th className="num">Quotes verified</th>
                  <th className="num">Tool calls / question</th>
                  <th className="num">Cost / question</th>
                </tr>
              </thead>
              <tbody>
                {Object.keys(held.qa).map((spec) => (
                  <tr key={spec}>
                    <td>{NAMES[spec] ?? spec}</td>
                    <td className="num">{f(st(dev.qa[spec], "correct"))} / {f(st(held.qa[spec], "correct"))}</td>
                    <td className="num">{f(st(held.qa[spec], "abstained_correctly"))}</td>
                    <td className="num">{f(st(held.qa[spec], "supported"))}</td>
                    <td className="num">{f(st(held.qa[spec], "citations_verified"))}</td>
                    <td className="num">{f(st(held.qa[spec], "tool_calls"), 1)}</td>
                    <td className="num">${((st(held.qa[spec], "cost_usd")?.mean ?? 0) / held.qa_questions).toFixed(4)}</td>
                  </tr>
                ))}
                {held.qa_local &&
                  Object.keys(held.qa_local).map((spec) => (
                    <tr key={spec}>
                      <td>{NAMES[spec] ?? spec}, 1 run, final call parsed from text</td>
                      <td className="num">{f(st(dev.qa_local?.[spec], "correct"))} / {f(st(held.qa_local?.[spec], "correct"))}</td>
                      <td className="num">{f(st(held.qa_local?.[spec], "abstained_correctly"))}</td>
                      <td className="num">{f(st(held.qa_local?.[spec], "supported"))}</td>
                      <td className="num">{f(st(held.qa_local?.[spec], "citations_verified"))}</td>
                      <td className="num">{f(st(held.qa_local?.[spec], "tool_calls"), 1)}</td>
                      <td className="num">local</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          <p className="small muted" style={{ marginTop: 10 }}>
            Retrieval alone, gold lines in the top 5 for the raw question (dev / held out): BM25{" "}
            {dev.retrieval_at_5.bm25.toFixed(2)} / {held.retrieval_at_5.bm25.toFixed(2)}, dense{" "}
            {dev.retrieval_at_5.dense.toFixed(2)} / {held.retrieval_at_5.dense.toFixed(2)}, hybrid{" "}
            {dev.retrieval_at_5.hybrid.toFixed(2)} / {held.retrieval_at_5.hybrid.toFixed(2)}.
          </p>
        </section>

        <section className="card">
          <h2>Known gaps the evaluation found</h2>
          <ul className="small">
            <li>A question with a false premise (&ldquo;why did they decide…&rdquo; when nothing was decided) was corrected in every answer, but most runs flagged it &ldquo;not answerable&rdquo;. The answer schema needs a &ldquo;premise corrected&rdquo; outcome.</li>
            <li>Extraction recall hides status errors: the same merge model finds fewer changes when a smaller model extracted, because a reversed proposal was recorded as confirmed.</li>
            <li>The local 8B model often wrote its final tool call as text instead of making it.</li>
            <li>Q&amp;A facts are matched by keywords, which undercounts paraphrases.</li>
          </ul>
        </section>
      </div>
    </div>
  );
}

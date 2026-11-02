import type { Metadata } from "next";

export const metadata: Metadata = { title: "Method and limits · ElicitSense" };

export default function Method() {
  return (
    <div className="wrap prose">
      <div className="page-head">
        <h1>Method, research basis and limitations</h1>
      </div>

      <section className="card">
        <h2>Research basis</h2>
        <ul>
          <li>
            In the mapping study <em>Emotions in Software Engineering</em> (Cheng, Wang, Arora, Hoang, Liu; 57 studies,
            classified by emotion category and SDLC phase), requirements engineering is one of the least-studied phases
            (7 of 57 studies). Communication-and-collaboration research has no requirements-engineering studies at all,
            although stakeholder interaction peaks there.
          </li>
          <li>Every communication study in the map is observational; none evaluates a tool that supports communication as it happens.</li>
          <li>
            Decision-making-bias research is almost entirely post hoc (6 of 7 studies mine artefacts after decisions were
            made). ElicitSense brings the signal to the moment requirement decisions are taken.
          </li>
          <li>Requirement changes, especially late ones, are a main trigger of emotional responses (Madampe et al.).</li>
          <li>
            Facial configurations are not reliable fingerprints of discrete emotions (Barrett et al. 2019), so ElicitSense
            reports cues such as &ldquo;long pause, hedging&rdquo; rather than labels such as &ldquo;angry&rdquo;.
          </li>
          <li>It productises MEmoRE, a multimodal requirements-elicitation prototype (Cheng et al., IEEE RE 2023).</li>
        </ul>
      </section>

      <section className="card">
        <h2>How outputs are kept honest</h2>
        <ul>
          <li>The model proposes; code decides. Extraction and linking use strict JSON schemas, and statuses, supersession, conflicts and history are applied deterministically.</li>
          <li>Every requirement and every Q&amp;A answer cites verbatim quotes. A quote that does not match its transcript segment is rejected and reported, not shown as evidence.</li>
          <li>Q&amp;A answers marked answerable without a verified citation are shown as unsupported. Questions the meetings never covered should be declined, and are scored.</li>
          <li>Merge link ids are restricted to the ids in the prompt, so constrained decoding cannot invent one.</li>
        </ul>
      </section>

      <section className="card">
        <h2>Privacy and compliance</h2>
        <ul>
          <li>Audio is transcribed on the analyst&rsquo;s machine; only transcript text is sent to the model.</li>
          <li>Cues are attached to requirements, never aggregated per person. There is no per-person score anywhere.</li>
          <li>
            Cues are off for internal team meetings (<code>--setting internal</code>): the EU AI Act, Art. 5(1)(f),
            prohibits AI systems that infer emotions of people in the workplace. The intended setting is consented client
            elicitation sessions.
          </li>
          <li>The demo meetings are fictional and synthetic.</li>
        </ul>
      </section>

      <section className="card">
        <h2>Evaluation design</h2>
        <ul>
          <li>Two gold-labelled projects: <code>harbour_physio</code> is the development set (prompts were written against it); <code>fernhill_bakery</code> was written before any model ran on it and its results did not change the prompts.</li>
          <li>Each model runs each project three times on identical transcripts; tables report the mean and range, cost from published prices and latency.</li>
          <li>Q&amp;A is scored on gold questions: required facts, declining never-discussed questions, citation validity and coverage of the gold evidence lines.</li>
        </ul>
      </section>

      <section className="card">
        <h2>Limitations</h2>
        <ul>
          <li>Synthetic audio from speech synthesis, with scripted hesitation. Real meetings have overlapping speech, accents and noise.</li>
          <li>Two small fictional projects (40 gold requirements, 16 relations): one relation moves recall by 0.11 to 0.14, so differences of that size are noise.</li>
          <li>One person wrote the prompts, scripts and gold labels. The held-out project limits overfitting to one project, not to one way of describing requirements.</li>
          <li>Matching is automatic (evidence-line overlap) and was spot-checked, not adjudicated by a second annotator. Q&amp;A facts are matched by keywords, which undercounts paraphrases.</li>
          <li>Speaker turns come from the synthesis script; a diarization step for real recordings is not built yet.</li>
        </ul>
      </section>
    </div>
  );
}

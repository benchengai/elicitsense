export type Segment = { id: string; line: string; speaker: string; start: number; end: number; text: string };

export type Meeting = {
  id: string;
  title: string;
  date: string;
  audio: string;
  duration: number;
  speakers: string[];
  segments: Segment[];
};

export type Evidence = { meeting: string; segment_id: string; start: number; end: number; speaker: string; quote: string };

export type HistoryEntry = { meeting: string; change: string; note?: string; evidence?: Evidence[] };

export type Requirement = {
  id: string;
  type: "functional" | "non_functional" | "constraint";
  statement: string;
  acceptance: string[];
  stakeholder: string;
  status: string;
  meeting: string;
  evidence: Evidence[];
  quality: { kind: string; detail: string }[];
  uncertainty: { flag: boolean; label: string; cues: { kind: string; detail: string; segment_id: string }[] };
  history: HistoryEntry[];
  merged_into: string | null;
  merged_from: string[];
  superseded_by: string | null;
};

export type Relation = { from: string; kind: string; to: string; meeting: string; explanation: string; new_status?: string };

export type Register = {
  requirements: Requirement[];
  relations: Relation[];
  open_conflicts: Relation[];
  active: string[];
  llm: { meeting: string; model: string; cost_usd: number | null; latency_s: number }[];
};

export type Citation = { segment: string; quote: string; verified: boolean; line: string | null };

export type Answer = {
  id: string;
  question: string;
  gold_answerable: boolean;
  answer: string;
  answerable: boolean;
  supported: boolean;
  citations: Citation[];
  requirement_ids: string[];
  tools: string[];
  model: string;
  cost_usd: number | null;
  latency_s: number;
};

export type QA = { spec: string; run: string; answers: Answer[] };

export type ProjectMeta = {
  id: string;
  title: string;
  heldout: boolean;
  meetings: { id: string; title: string; date: string; duration: number }[];
  exported: string;
  counts: { requirements: number; active: number; relations: number; open_conflicts: number };
};

export type Stat = { mean: number; min: number; max: number };
export type ModelRow = Record<string, Stat | number | undefined>;
export type EvalData = {
  projects: Record<
    string,
    {
      baseline: Record<string, ModelRow>;
      "constrained-ids": Record<string, ModelRow>;
      qa: Record<string, ModelRow>;
      qa_local?: Record<string, ModelRow>;
      qa_questions: number;
      retrieval_at_5: { k: number; bm25: number; dense: number; hybrid: number };
    }
  >;
};

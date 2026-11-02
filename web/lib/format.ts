import type { Requirement } from "./types";

export const clock = (s: number) => {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
};

export const INACTIVE = new Set(["superseded", "rejected", "merged"]);
export const isActive = (r: Requirement) => !INACTIVE.has(r.status);

export const TYPE_LABEL: Record<string, string> = {
  functional: "Functional",
  non_functional: "Non-functional",
  constraint: "Constraint",
};

export function statusBadge(r: Requirement): { label: string; tone: string } {
  switch (r.status) {
    case "confirmed":
      return { label: "confirmed", tone: "ok" };
    case "proposed":
      return { label: "proposed", tone: "accent" };
    case "open_question":
      return { label: "open question", tone: "warn" };
    case "deferred":
      return { label: "deferred", tone: "" };
    case "rejected":
      return { label: "rejected", tone: "danger" };
    case "superseded":
      return { label: r.superseded_by ? `superseded by ${r.superseded_by}` : "superseded", tone: "outline" };
    case "merged":
      return { label: r.merged_into ? `restates ${r.merged_into}` : "merged", tone: "outline" };
    default:
      return { label: r.status, tone: "" };
  }
}

export const RELATION_TONE: Record<string, string> = {
  refines: "accent",
  supersedes: "warn",
  conflicts: "danger",
  status_change: "",
  same: "outline",
};

export const CUE_LABEL: Record<string, string> = {
  hedging: "hedging",
  filled_pause: "filled pause",
  long_pause: "long pause",
  slow_speech: "slow speech",
};

export const QUALITY_LABEL: Record<string, string> = {
  ambiguous_term: "ambiguous term",
  missing_acceptance: "no acceptance criteria",
  compound: "compound statement",
};

export const usd = (v: number | null | undefined, digits = 4) => (v == null ? "–" : `$${v.toFixed(digits)}`);

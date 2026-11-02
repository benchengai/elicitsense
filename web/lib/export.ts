import { clock, isActive, TYPE_LABEL } from "./format";
import type { Meeting, Requirement } from "./types";

export type Review = { decision?: "accepted" | "rejected" | "follow_up"; statement?: string; note?: string };
export type Reviews = Record<string, Review>;

const statementOf = (r: Requirement, reviews: Reviews) => reviews[r.id]?.statement?.trim() || r.statement;

function evidenceLines(r: Requirement, meetings: Meeting[]) {
  const date = (id: string) => meetings.find((m) => m.id === id)?.date ?? "";
  return r.evidence.map((e) => `${e.speaker}, ${e.meeting} ${date(e.meeting)} at ${clock(e.start)}: "${e.quote}"`);
}

function exported(requirements: Requirement[], reviews: Reviews) {
  return requirements.filter((r) => isActive(r) && reviews[r.id]?.decision !== "rejected");
}

export function toMarkdown(title: string, requirements: Requirement[], meetings: Meeting[], reviews: Reviews) {
  const lines = [`# ${title}: requirements`, "", `Meetings: ${meetings.map((m) => `${m.id} ${m.date} ${m.title}`).join("; ")}.`, ""];
  for (const type of ["functional", "non_functional", "constraint"]) {
    const items = exported(requirements, reviews).filter((r) => r.type === type);
    if (!items.length) continue;
    lines.push(`## ${TYPE_LABEL[type]}`, "");
    for (const r of items) {
      const review = reviews[r.id]?.decision;
      const flags = [r.status.replace("_", " "), review === "follow_up" ? "follow up" : review === "accepted" ? "reviewed" : "", r.uncertainty.flag ? "needs confirmation" : ""].filter(Boolean);
      lines.push(`### ${r.id}: ${statementOf(r, reviews)}`, "", `Stakeholder: ${r.stakeholder}. Status: ${flags.join(", ")}.`, "");
      if (r.acceptance.length) lines.push("Acceptance criteria:", ...r.acceptance.map((a) => `- ${a}`), "");
      lines.push("Evidence:", ...evidenceLines(r, meetings).map((l) => `- ${l}`), "");
      if (reviews[r.id]?.note) lines.push(`Reviewer note: ${reviews[r.id]?.note}`, "");
    }
  }
  return lines.join("\n");
}

const csvCell = (v: string) => `"${v.replace(/"/g, '""')}"`;

export function toJiraCsv(requirements: Requirement[], meetings: Meeting[], reviews: Reviews) {
  const header = ["Summary", "Description", "Issue Type", "Labels", "Labels", "Labels"];
  const rows = exported(requirements, reviews).map((r) => {
    const statement = statementOf(r, reviews);
    const description = [
      statement,
      r.acceptance.length ? `Acceptance criteria:\n${r.acceptance.map((a) => `* ${a}`).join("\n")}` : "Acceptance criteria: none discussed yet.",
      `Evidence:\n${evidenceLines(r, meetings).map((l) => `* ${l}`).join("\n")}`,
      r.uncertainty.flag ? `Needs confirmation: ${r.uncertainty.cues.map((c) => c.kind.replace("_", " ")).join(", ")}.` : "",
      `Source: ElicitSense ${r.id}, stakeholder ${r.stakeholder}.`,
    ].filter(Boolean).join("\n\n");
    const summary = statement.length > 250 ? `${statement.slice(0, 247)}...` : statement;
    return [summary, description, r.type === "functional" ? "Story" : "Task", "elicitsense", r.type, r.status];
  });
  return [header, ...rows].map((row) => row.map(csvCell).join(",")).join("\n");
}

export function download(filename: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

import { readFileSync } from "node:fs";
import path from "node:path";
import type { EvalData, Meeting, ProjectMeta, QA, Register } from "./types";

// Read at build time only; the exported site ships these as static payloads.
const root = path.join(process.cwd(), "public", "demo");
const read = <T,>(...parts: string[]): T => JSON.parse(readFileSync(path.join(root, ...parts), "utf8")) as T;

export const projects = (): ProjectMeta[] => read<ProjectMeta[]>("projects.json");

export function project(id: string) {
  return {
    meta: read<ProjectMeta>(id, "meta.json"),
    register: read<Register>(id, "register.json"),
    meetings: read<Meeting[]>(id, "meetings.json"),
    qa: read<QA>(id, "qa.json"),
  };
}

export const evaluation = (): EvalData => read<EvalData>("eval.json");

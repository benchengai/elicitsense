import type { Metadata } from "next";
import ProjectView from "@/components/ProjectView";
import { project, projects } from "@/lib/data";

export const dynamicParams = false;

export function generateStaticParams() {
  return projects().map((p) => ({ project: p.id }));
}

export async function generateMetadata({ params }: PageProps<"/p/[project]">): Promise<Metadata> {
  const { project: id } = await params;
  return { title: `${project(id).meta.title} · ElicitSense` };
}

export default async function ProjectPage({ params }: PageProps<"/p/[project]">) {
  const { project: id } = await params;
  const { meta, register, meetings, qa } = project(id);
  const llm = register.llm[0]?.model;
  return (
    <div className="wrap">
      <div className="page-head">
        <h1>{meta.title}</h1>
        <p className="muted">
          {meta.meetings.length} fictional elicitation meetings, {meta.meetings[0].date} to{" "}
          {meta.meetings[meta.meetings.length - 1].date}. {meta.counts.active} active requirements out of{" "}
          {meta.counts.requirements} extracted, {meta.counts.relations} recorded changes,{" "}
          {meta.counts.open_conflicts === 0 ? "no open conflicts" : `${meta.counts.open_conflicts} open conflict`}.
        </p>
        <div className="row">
          <span className={`badge ${meta.heldout ? "warn" : "accent"}`}>
            {meta.heldout ? "held-out project: written before any model ran on it" : "development project: prompts were written against it"}
          </span>
          <span className="badge outline">synthetic audio</span>
          {llm && <span className="badge outline">extract + merge: {llm}</span>}
          <span className="badge outline">click any quote to hear it</span>
        </div>
      </div>
      <ProjectView meta={meta} register={register} meetings={meetings} qa={qa} />
    </div>
  );
}

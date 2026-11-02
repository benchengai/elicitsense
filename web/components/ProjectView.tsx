"use client";

import { useCallback, useMemo, useState, useSyncExternalStore } from "react";
import AskView from "./AskView";
import ChangesView from "./ChangesView";
import Player, { type Seek } from "./Player";
import RegisterView from "./RegisterView";
import type { Review, Reviews } from "@/lib/export";
import type { Meeting, ProjectMeta, QA, Register } from "@/lib/types";

type Tab = "register" | "changes" | "ask";

const CHANGE = "elicitsense-review-change";
const subscribe = (notify: () => void) => {
  window.addEventListener("storage", notify);
  window.addEventListener(CHANGE, notify);
  return () => {
    window.removeEventListener("storage", notify);
    window.removeEventListener(CHANGE, notify);
  };
};
const readStored = (key: string) => {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
};
const writeStored = (key: string, value: Reviews) => {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {}
  window.dispatchEvent(new Event(CHANGE));
};

type Props = { meta: ProjectMeta; register: Register; meetings: Meeting[]; qa: QA };

export default function ProjectView({ meta, register, meetings, qa }: Props) {
  const [tab, setTab] = useState<Tab>("register");
  const [seek, setSeek] = useState<Seek | null>(null);
  const [focus, setFocus] = useState<{ id: string; nonce: number } | null>(null);
  const key = `elicitsense-review-${meta.id}`;

  // Review decisions are a per-viewer convenience: kept in this browser only.
  const raw = useSyncExternalStore(subscribe, () => readStored(key), () => null);
  const reviews = useMemo<Reviews>(() => {
    try {
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  }, [raw]);
  const setReviews = useCallback((next: Reviews) => writeStored(key, next), [key]);
  const setReview = useCallback(
    (id: string, review: Review) => setReviews({ ...reviews, [id]: review }),
    [reviews, setReviews],
  );

  const play = useCallback((meeting: string, time: number, segment: string) => {
    setSeek({ meeting, time, segment, nonce: Date.now() });
  }, []);

  const reviewed = Object.values(reviews).filter((r) => r.decision || r.statement).length;

  return (
    <div className="project-grid">
      <section
        className="project-main"
        onClickCapture={(e) => {
          // Requirement links work from every tab: jump to the card in the register.
          const a = (e.target as HTMLElement).closest("a");
          const href = a?.getAttribute("href") ?? "";
          if (href.startsWith("#REQ-")) {
            e.preventDefault();
            setTab("register");
            setFocus({ id: href.slice(1), nonce: Date.now() });
          }
        }}
      >
        <div className="tabs" role="tablist">
          {(
            [
              ["register", "Register"],
              ["changes", "Changes by meeting"],
              ["ask", "Ask"],
            ] as [Tab, string][]
          ).map(([id, label]) => (
            <button key={id} role="tab" className="tab" aria-selected={tab === id} onClick={() => setTab(id)}>
              {label}
            </button>
          ))}
          <span className="spacer" />
          {reviewed > 0 && (
            <span className="faint small tab-note">
              {reviewed} reviewed in this browser ·{" "}
              <button
                className="linklike"
                onClick={() => {
                  setReviews({});
                }}
              >
                clear
              </button>
            </span>
          )}
        </div>
        {tab === "register" && (
          <RegisterView
            title={meta.title}
            project={meta.id}
            register={register}
            meetings={meetings}
            reviews={reviews}
            setReview={setReview}
            play={play}
            focus={focus}
          />
        )}
        {tab === "changes" && <ChangesView register={register} meetings={meetings} />}
        {tab === "ask" && <AskView qa={qa} register={register} meetings={meetings} play={play} />}
      </section>
      <aside className="project-aside">
        <Player project={meta.id} meetings={meetings} seek={seek} onPick={play} />
      </aside>
    </div>
  );
}

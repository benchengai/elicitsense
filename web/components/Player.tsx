"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { clock } from "@/lib/format";
import type { Meeting } from "@/lib/types";

export type Seek = { meeting: string; time: number; segment?: string; nonce: number };

type Props = {
  project: string;
  meetings: Meeting[];
  seek: Seek | null;
  onPick: (meeting: string, time: number, segment: string) => void;
};

// Audio player and transcript for one meeting at a time. A seek request (from clicking
// evidence anywhere on the page) switches meeting if needed, jumps to the segment and plays.
export default function Player({ project, meetings, seek, onPick }: Props) {
  const audio = useRef<HTMLAudioElement>(null);
  const list = useRef<HTMLOListElement>(null);
  const [meetingId, setMeetingId] = useState(meetings[0]?.id);
  const [time, setTime] = useState(0);
  const [focus, setFocus] = useState<string | undefined>();
  const [open, setOpen] = useState(true);
  const [lastSeek, setLastSeek] = useState<Seek | null>(null);
  const applied = useRef(0);
  if (seek !== lastSeek) {
    setLastSeek(seek);
    if (seek) {
      setFocus(seek.segment);
      setOpen(true);
      setMeetingId(seek.meeting);
    }
  }
  const meeting = meetings.find((m) => m.id === meetingId) ?? meetings[0];

  const current = useMemo(
    () => meeting.segments.find((s) => time >= s.start - 0.05 && time < s.end + 0.4)?.id,
    [meeting, time],
  );

  // Play a seek request once its meeting's audio is loaded (now, or on loadedmetadata).
  const apply = () => {
    const el = audio.current;
    if (!el || !seek || applied.current === seek.nonce || seek.meeting !== meeting.id || el.readyState < 1) return;
    applied.current = seek.nonce;
    el.currentTime = seek.time;
    el.play().catch(() => {});
  };

  useEffect(apply);

  useEffect(() => {
    const id = focus ?? current;
    if (!id || !list.current) return;
    list.current.querySelector(`[data-seg="${id}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [focus, current]);

  return (
    <div className="card player">
      <div className="row" role="tablist" aria-label="Meetings">
        {meetings.map((m) => (
          <button
            key={m.id}
            className="btn small"
            aria-pressed={m.id === meeting.id}
            onClick={() => {
              setMeetingId(m.id);
              setFocus(undefined);
              setTime(0);
            }}
          >
            {m.id} · {m.date.slice(5)}
          </button>
        ))}
      </div>
      <div className="player-title">
        <strong>{meeting.title}</strong>
        <span className="faint small"> {meeting.date} · {clock(meeting.duration)}</span>
      </div>
      <audio
        key={meeting.id}
        ref={audio}
        src={`/demo/${project}/${meetings.find((m) => m.id === meeting.id)!.audio}`}
        controls
        preload="metadata"
        onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
        onLoadedMetadata={apply}
      />
      <button className="btn small transcript-toggle" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        {open ? "Hide transcript" : "Show transcript"}
      </button>
      {open && (
        <ol className="transcript" ref={list}>
          {meeting.segments.map((s) => (
            <li
              key={s.id}
              data-seg={s.id}
              className={[s.id === current ? "playing" : "", s.id === focus ? "focus" : ""].join(" ")}
            >
              <button onClick={() => onPick(meeting.id, s.start, s.id)} title="Play from here">
                <span className="seg-meta">
                  <span className="mono">{clock(s.start)}</span> {s.speaker}
                </span>
                <span>{s.text}</span>
              </button>
            </li>
          ))}
        </ol>
      )}
      <p className="faint small" style={{ marginTop: 8, marginBottom: 0 }}>
        Synthetic audio (macOS speech synthesis), transcribed locally with faster-whisper. Transcription errors are
        kept as they are.
      </p>
    </div>
  );
}

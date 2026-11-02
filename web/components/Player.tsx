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
  const src = `${process.env.NEXT_PUBLIC_BASE_PATH}/demo/${project}/${meeting.audio}`;

  // Load the whole file as a blob so seeking works on any static host, including
  // servers without HTTP range requests. Each meeting is well under 1 MB.
  const [blob, setBlob] = useState<{ src: string; url: string } | null>(null);
  useEffect(() => {
    let url = "";
    let cancelled = false;
    fetch(src)
      .then((r) => r.blob())
      .then((b) => {
        if (cancelled) return;
        url = URL.createObjectURL(b);
        setBlob({ src, url });
      })
      .catch(() => !cancelled && setBlob({ src, url: src }));
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [src]);
  const audioUrl = blob?.src === src ? blob.url : undefined;

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
    const box = list.current;
    const el = box?.querySelector<HTMLElement>(`[data-seg="${id}"]`);
    if (!box || !el) return;
    // Scroll only the transcript, never the page the reader is on.
    if (el.offsetTop < box.scrollTop || el.offsetTop + el.offsetHeight > box.scrollTop + box.clientHeight) {
      box.scrollTo({ top: el.offsetTop - box.clientHeight / 3, behavior: "smooth" });
    }
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
        key={audioUrl ?? meeting.id}
        ref={audio}
        src={audioUrl}
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

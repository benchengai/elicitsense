"use client";

import { useState } from "react";

export type Bar = { label: string; dev?: [number, number, number]; held?: [number, number, number] }; // mean, min, max
export type Point = { label: string; x: number; y: number; note: string };

const SERIES = [
  { key: "dev", name: "Development set", cls: "s1" },
  { key: "held", name: "Held-out set", cls: "s2" },
] as const;

function Tooltip({ tip }: { tip: { x: number; y: number; text: string } | null }) {
  if (!tip) return null;
  return (
    <div className="viz-tip" style={{ left: tip.x, top: tip.y }} role="status">
      {tip.text}
    </div>
  );
}

// Horizontal grouped bars, two series, mean with a min–max whisker across runs.
export function GroupedBars({ rows, title, unit }: { rows: Bar[]; title: string; unit: string }) {
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  const W = 640, labelW = 190, right = 24, top = 8, bar = 12, gap = 2, band = 40;
  const H = top + rows.length * band + 26;
  const plotW = W - labelW - right;
  const x = (v: number) => labelW + v * plotW;
  return (
    <figure className="viz-root" onMouseLeave={() => setTip(null)}>
      <figcaption>
        <strong>{title}</strong>
        <span className="viz-legend">
          {SERIES.map((s) => (
            <span key={s.key}>
              <i className={`swatch ${s.cls}`} /> {s.name}
            </span>
          ))}
          <span className="faint">line: range over 3 runs</span>
        </span>
      </figcaption>
      <div className="viz-scroll">
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={title}>
          {[0, 0.25, 0.5, 0.75, 1].map((t) => (
            <g key={t}>
              <line x1={x(t)} x2={x(t)} y1={top} y2={H - 22} className="grid" />
              <text x={x(t)} y={H - 6} className="tick" textAnchor="middle">{t.toFixed(2)}</text>
            </g>
          ))}
          {rows.map((r, i) => {
            const y0 = top + i * band + (band - 2 * bar - gap) / 2;
            return (
              <g key={r.label}>
                <text x={labelW - 10} y={y0 + bar + 4} className="row-label" textAnchor="end">{r.label}</text>
                {SERIES.map((s, j) => {
                  const v = r[s.key];
                  if (!v) return null;
                  const y = y0 + j * (bar + gap);
                  const w = Math.max(0, x(v[0]) - x(0));
                  const radius = Math.min(4, w / 2);
                  const path = `M${x(0)},${y} h${Math.max(0, w - radius)} a${radius},${radius} 0 0 1 ${radius},${radius} v${bar - 2 * radius} a${radius},${radius} 0 0 1 ${-radius},${radius} h${-Math.max(0, w - radius)} z`;
                  const text = `${r.label} · ${s.name}: ${v[0].toFixed(2)} ${unit}${v[1] !== v[2] ? ` (runs ${v[1].toFixed(2)}–${v[2].toFixed(2)})` : ""}`;
                  return (
                    <g key={s.key}>
                      <path d={path} className={`mark ${s.cls}`} />
                      {v[1] !== v[2] && <line x1={x(v[1])} x2={x(v[2])} y1={y + bar / 2} y2={y + bar / 2} className="whisker" />}
                      <rect
                        x={labelW}
                        y={y - 1}
                        width={plotW}
                        height={bar + 2}
                        className="hit"
                        onMouseMove={(e) => {
                          const box = (e.currentTarget.ownerSVGElement?.parentElement as HTMLElement).getBoundingClientRect();
                          setTip({ x: e.clientX - box.left + 12, y: e.clientY - box.top - 30, text });
                        }}
                      />
                    </g>
                  );
                })}
              </g>
            );
          })}
        </svg>
        <Tooltip tip={tip} />
      </div>
    </figure>
  );
}

// Cost against quality, one series, direct labels; x is logarithmic.
export function CostScatter({ points, title, xLabel, yLabel }: { points: Point[]; title: string; xLabel: string; yLabel: string }) {
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  const W = 640, H = 300, left = 52, right = 150, top = 14, bottom = 40;
  const xs = points.map((p) => Math.log10(p.x));
  const lo = Math.floor(Math.min(...xs)), hi = Math.ceil(Math.max(...xs));
  const x = (v: number) => left + ((Math.log10(v) - lo) / (hi - lo || 1)) * (W - left - right);
  const y = (v: number) => top + (1 - v) * (H - top - bottom);
  const ticks = Array.from({ length: hi - lo + 1 }, (_, i) => 10 ** (lo + i));
  return (
    <figure className="viz-root" onMouseLeave={() => setTip(null)}>
      <figcaption>
        <strong>{title}</strong>
      </figcaption>
      <div className="viz-scroll">
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={title}>
          {[0, 0.25, 0.5, 0.75, 1].map((t) => (
            <g key={t}>
              <line x1={left} x2={W - right} y1={y(t)} y2={y(t)} className="grid" />
              <text x={left - 8} y={y(t) + 4} className="tick" textAnchor="end">{t.toFixed(2)}</text>
            </g>
          ))}
          {ticks.map((t) => (
            <text key={t} x={x(t)} y={H - bottom + 18} className="tick" textAnchor="middle">${t >= 0.01 ? t.toFixed(2) : t.toFixed(3)}</text>
          ))}
          <text x={(left + W - right) / 2} y={H - 4} className="axis-label" textAnchor="middle">{xLabel}</text>
          <text x={14} y={(top + H - bottom) / 2} className="axis-label" textAnchor="middle" transform={`rotate(-90 14 ${(top + H - bottom) / 2})`}>{yLabel}</text>
          {points.map((p) => (
            <g key={p.label}>
              <circle cx={x(p.x)} cy={y(p.y)} r={5} className="mark s1 ring" />
              <text x={x(p.x) + 9} y={y(p.y) + 4} className="point-label">{p.label}</text>
              <circle
                cx={x(p.x)}
                cy={y(p.y)}
                r={14}
                className="hit"
                onMouseMove={(e) => {
                  const box = (e.currentTarget.ownerSVGElement?.parentElement as HTMLElement).getBoundingClientRect();
                  setTip({ x: e.clientX - box.left + 12, y: e.clientY - box.top - 30, text: `${p.label}: ${p.note}` });
                }}
              />
            </g>
          ))}
        </svg>
        <Tooltip tip={tip} />
      </div>
    </figure>
  );
}

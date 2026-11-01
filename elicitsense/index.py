"""Search over one project's register and transcripts.

Two kinds of document: requirements (statement, status, history and evidence
quotes) and transcript segments from every meeting. Retrieval is BM25, dense
(OpenAI embeddings, cached on disk), or a hybrid of both by reciprocal rank
fusion. A requirement hit also covers the segments its evidence cites, which
is how retrieval recall is measured against gold evidence lines.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
from collections import Counter
from pathlib import Path

EMBEDDING_MODEL = "text-embedding-3-small"
RRF_K = 60
MODES = ("bm25", "dense", "hybrid")

_TOKEN = re.compile(r"[a-z0-9$%]+(?:'[a-z]+)?")
STOPWORDS = set("""a an and are as at be but by can could did do does for from had has have he her his
how i if in into is it its me my no not of on or our she so that the their them then there these
they this to us was we were what when where which who why will with would you your""".split())


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower().replace("’", "'")) if t not in STOPWORDS]


def _clock(seconds: float) -> str:
    return f"{int(seconds // 60):02d}:{seconds % 60:04.1f}"


def build_docs(register: dict, transcripts: list[dict]) -> list[dict]:
    docs = []
    for t in transcripts:
        m = t["meeting"]
        for s in t["segments"]:
            docs.append({
                "id": f"{m['id']}:{s['id']}", "kind": "segment", "meeting": m["id"], "date": m.get("date", ""),
                "speaker": s["speaker"], "time": _clock(s["start"]), "line": s["source_line"],
                "text": s["text"], "covers": [f"{m['id']}:{s['id']}"],
            })
    for r in register["requirements"]:
        history = "; ".join(h["change"] for h in r.get("history", []))
        quotes = " ".join(e["quote"] for e in r["evidence"])
        docs.append({
            "id": r["id"], "kind": "requirement", "meeting": r["meeting"], "status": r["status"],
            "type": r["type"], "stakeholder": r["stakeholder"], "statement": r["statement"],
            "text": f"{r['statement']} ({r['type']}, {r['status']}, {r['stakeholder']}). {history}. {quotes}",
            "covers": [f"{e.get('meeting', r['meeting'])}:{e['segment_id']}" for e in r["evidence"]],
        })
    return docs


class BM25:
    def __init__(self, texts: list[str], k1: float = 1.5, b: float = 0.75):
        self.docs = [Counter(tokens(t)) for t in texts]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.lengths) / len(self.lengths) if self.lengths else 0.0
        df = Counter(term for d in self.docs for term in d)
        n = len(self.docs)
        self.idf = {term: math.log(1 + (n - f + 0.5) / (f + 0.5)) for term, f in df.items()}
        self.k1, self.b = k1, b

    def scores(self, query: str) -> list[float]:
        q = tokens(query)
        out = []
        for d, length in zip(self.docs, self.lengths):
            s = 0.0
            for term in q:
                if f := d.get(term):
                    s += self.idf[term] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * length / self.avg))
            out.append(s)
        return out


class Embedder:
    """OpenAI embeddings with a JSON cache keyed by text hash, so a corpus is embedded once."""

    def __init__(self, cache_path: Path, model: str = EMBEDDING_MODEL):
        self.path, self.model = cache_path, model
        self.cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
        self.tokens_used = 0
        self._lock = threading.Lock()  # the Q&A bench shares one index across threads

    def _key(self, text: str) -> str:
        return hashlib.sha1(f"{self.model}\n{text}".encode()).hexdigest()

    def embed(self, texts: list[str]) -> list[list[float]]:
        with self._lock:
            missing = list(dict.fromkeys(t for t in texts if self._key(t) not in self.cache))
            if missing:
                import openai

                response = openai.OpenAI().embeddings.create(model=self.model, input=missing)
                self.tokens_used += response.usage.total_tokens
                for text, item in zip(missing, response.data):
                    self.cache[self._key(text)] = item.embedding
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_suffix(f".{os.getpid()}.tmp")
                tmp.write_text(json.dumps(self.cache))
                os.replace(tmp, self.path)
            return [self.cache[self._key(t)] for t in texts]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) or 1.0)


class Index:
    def __init__(self, docs: list[dict], mode: str = "hybrid", embedder: Embedder | None = None):
        if mode not in MODES:
            raise ValueError(f"retrieval mode must be one of {MODES}")
        if mode != "bm25" and embedder is None:
            raise ValueError(f"{mode} retrieval needs an embedder")
        self.docs, self.mode, self.embedder = docs, mode, embedder
        self.bm25 = BM25([d["text"] for d in docs])
        self.vectors = embedder.embed([d["text"] for d in docs]) if mode != "bm25" else None

    def _ranked(self, scores: list[float], allowed: list[int]) -> list[int]:
        return sorted((i for i in allowed if scores[i] > 0 or self.mode != "bm25"), key=lambda i: -scores[i])

    def search(self, query: str, scope: str = "all", k: int = 5) -> list[dict]:
        allowed = [i for i, d in enumerate(self.docs)
                   if scope == "all" or (scope == "requirements") == (d["kind"] == "requirement")]
        rankings = []
        if self.mode in ("bm25", "hybrid"):
            rankings.append([i for i in self._ranked(self.bm25.scores(query), allowed)])
        if self.mode in ("dense", "hybrid"):
            q = self.embedder.embed([query])[0]
            dense = [_cosine(q, v) for v in self.vectors]
            rankings.append(sorted(allowed, key=lambda i: -dense[i]))
        fused = Counter()
        for ranking in rankings:
            for rank, i in enumerate(ranking):
                fused[i] += 1 / (RRF_K + rank + 1)
        return [self.docs[i] for i, _ in fused.most_common(k)]


def load_project_corpus(project_runs: Path, register_path: Path) -> tuple[dict, list[dict]]:
    """Register plus every meeting transcript under runs/<project>/, oldest meeting first."""
    register = json.loads(register_path.read_text(encoding="utf-8"))
    transcripts = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(project_runs.glob("*/segments.json"))]
    transcripts.sort(key=lambda t: (t["meeting"].get("date", ""), t["meeting"]["id"]))
    return register, transcripts

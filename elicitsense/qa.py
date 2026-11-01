"""Answer questions about a project's requirements with a tool-using agent.

The model searches the register and the meeting transcripts through tools,
then submits an answer with citations. Citations are checked like extraction
evidence: each quote must match the transcript segment it cites. An answer
with no verified citation is marked unsupported rather than shown as fact.

The tool loop runs natively on each provider's function-calling API (OpenAI
Responses, Anthropic Messages, Ollama chat); the tools, prompt and checks are
shared.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from pathlib import Path

from .index import Embedder, Index, build_docs, load_project_corpus
from .llm import LLMError, OLLAMA_CONTEXT, parse_model_spec
from .pricing import cost_usd
from .verify import quote_matches

MAX_STEPS = 10

SYSTEM = """You answer questions about one software project's requirements, using the \
project's requirements register and the transcripts of its requirements elicitation \
meetings. Look things up with the tools before answering; do not answer from memory.

- Base every statement on what was said in the meetings. Cite the transcript segments \
that support the answer, each with a quote copied verbatim from that segment: exact \
words, at least four, or the whole segment if it is shorter. Quotes are checked \
automatically and unverifiable ones are discarded.
- When a requirement changed across meetings, say what it was, what it became, and in \
which meeting. Mention open conflicts and open questions when they bear on the answer.
- If the meetings do not answer the question, set answerable to false and say what is \
missing. Do not guess or fill gaps with common practice.
- Register entries are summaries written by a model; when they disagree with the \
transcript, the transcript wins.
- Describe what people asked for and decided, not how they felt.
- Finish by calling submit_answer, once."""

STATUSES = ["any", "proposed", "confirmed", "open_question", "deferred", "superseded", "rejected", "merged"]

TOOLS = [
    {
        "name": "search",
        "description": "Search the register and the meeting transcripts. Returns the best matches: "
                       "requirements (id, statement, status) and transcript segments (id like m2:S007, "
                       "speaker, time, text).",
        "schema": {
            "type": "object", "additionalProperties": False, "required": ["query", "scope", "k"],
            "properties": {
                "query": {"type": "string", "description": "words to search for"},
                "scope": {"type": "string", "enum": ["all", "requirements", "transcript"]},
                "k": {"type": "integer", "description": "number of results, 1 to 10"},
            },
        },
    },
    {
        "name": "get_requirement",
        "description": "Full record of one requirement: statement, status, stakeholder, evidence quotes "
                       "with segment ids, whether it needs confirmation (the stakeholder hesitated), "
                       "relations to other requirements, and change history.",
        "schema": {
            "type": "object", "additionalProperties": False, "required": ["id"],
            "properties": {"id": {"type": "string", "description": "requirement id, e.g. REQ-m1-003"}},
        },
    },
    {
        "name": "list_requirements",
        "description": "List requirements, optionally filtered by status and by the meeting that raised them.",
        "schema": {
            "type": "object", "additionalProperties": False, "required": ["status", "meeting"],
            "properties": {
                "status": {"type": "string", "enum": STATUSES},
                "meeting": {"type": "string", "description": "meeting id such as m2, or 'any'"},
            },
        },
    },
    {
        "name": "open_conflicts",
        "description": "Conflicts between requirements that no later meeting has settled.",
        "schema": {"type": "object", "additionalProperties": False, "required": [], "properties": {}},
    },
    {
        "name": "submit_answer",
        "description": "Submit the final answer with its supporting citations. Call this once, last.",
        "schema": {
            "type": "object", "additionalProperties": False,
            "required": ["answer", "answerable", "citations", "requirement_ids"],
            "properties": {
                "answer": {"type": "string", "description": "a short, direct answer in plain English"},
                "answerable": {"type": "boolean",
                               "description": "false if the meetings do not contain the answer"},
                "citations": {
                    "type": "array",
                    "items": {
                        "type": "object", "additionalProperties": False, "required": ["segment", "quote"],
                        "properties": {
                            "segment": {"type": "string", "description": "segment id, e.g. m2:S007"},
                            "quote": {"type": "string", "description": "verbatim words from that segment"},
                        },
                    },
                },
                "requirement_ids": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
]


class Project:
    """The register, transcripts and search index the tools read from."""

    def __init__(self, register: dict, transcripts: list[dict], index: Index):
        self.register, self.transcripts, self.index = register, transcripts, index
        self.items = {r["id"]: r for r in register["requirements"]}
        self.segments = {f"{t['meeting']['id']}:{s['id']}": {**s, "meeting": t["meeting"]["id"]}
                         for t in transcripts for s in t["segments"]}

    def meetings_line(self) -> str:
        return "; ".join(f"{t['meeting']['id']} {t['meeting'].get('date', '')} {t['meeting'].get('title', '')}"
                         for t in self.transcripts)

    def _evidence(self, r: dict) -> list[dict]:
        return [{"segment": f"{e.get('meeting', r['meeting'])}:{e['segment_id']}", "speaker": e["speaker"],
                 "quote": e["quote"]} for e in r["evidence"]]

    def run_tool(self, name: str, args: dict, seen: set[str]) -> dict:
        if name == "search":
            if not str(args.get("query", "")).strip():
                return {"error": "empty query; use list_requirements to browse everything"}
            k = max(1, min(int(args.get("k", 5)), 10))
            hits = self.index.search(args.get("query", ""), args.get("scope", "all"), k)
            out = []
            for d in hits:
                seen.update(d["covers"])
                if d["kind"] == "segment":
                    out.append({"segment": d["id"], "speaker": d["speaker"], "time": d["time"], "text": d["text"]})
                else:
                    out.append({"requirement": d["id"], "status": d["status"], "statement": d["statement"],
                                "evidence": d["covers"]})
            return {"results": out}
        if name == "get_requirement":
            r = self.items.get(args.get("id", ""))
            if r is None:
                return {"error": f"no requirement {args.get('id')!r}"}
            evidence = self._evidence(r)
            seen.update(e["segment"] for e in evidence)
            relations = [x for x in self.register["relations"] if r["id"] in (x["from"], x["to"])]
            return {
                "id": r["id"], "statement": r["statement"], "type": r["type"], "status": r["status"],
                "stakeholder": r["stakeholder"], "raised_in": r["meeting"], "evidence": evidence,
                "needs_confirmation": r.get("uncertainty", {}).get("flag", False),
                "uncertainty_cues": [c["kind"] for c in r.get("uncertainty", {}).get("cues", [])],
                "superseded_by": r.get("superseded_by"), "merged_into": r.get("merged_into"),
                "relations": [{k: x[k] for k in ("from", "kind", "to", "meeting", "explanation")} for x in relations],
                "history": r.get("history", []),
            }
        if name == "list_requirements":
            status, meeting = args.get("status", "any"), args.get("meeting", "any")
            return {"requirements": [
                {"id": r["id"], "status": r["status"], "type": r["type"], "raised_in": r["meeting"],
                 "statement": r["statement"], "needs_confirmation": r.get("uncertainty", {}).get("flag", False)}
                for r in self.items.values()
                if status in ("any", r["status"]) and meeting in ("any", r["meeting"])]}
        if name == "open_conflicts":
            return {"open_conflicts": [{"between": [c["from"], c["to"]], "raised_in": c["meeting"],
                                        "explanation": c["explanation"]} for c in self.register["open_conflicts"]]}
        return {"error": f"unknown tool {name!r}"}

    def check(self, submitted: dict) -> dict:
        citations = []
        for c in submitted.get("citations", []):
            seg = self.segments.get(c.get("segment", ""))
            ok = bool(seg) and quote_matches(c.get("quote", ""), seg["text"])
            citations.append({**c, "verified": ok,
                              "line": f"{seg['meeting']}:{seg['source_line']}" if seg else None})
        ids = submitted.get("requirement_ids", [])
        answerable = bool(submitted.get("answerable"))
        return {
            "answer": submitted.get("answer", ""),
            "answerable": answerable,
            "citations": citations,
            "requirement_ids": [i for i in ids if i in self.items],
            "unknown_requirement_ids": [i for i in ids if i not in self.items],
            "supported": answerable and any(c["verified"] for c in citations),
        }


def load(project_runs: Path, register_path: Path, retrieval: str = "hybrid") -> Project:
    register, transcripts = load_project_corpus(project_runs, register_path)
    embedder = Embedder(project_runs / "embeddings.json") if retrieval != "bm25" else None
    return Project(register, transcripts, Index(build_docs(register, transcripts), retrieval, embedder))


# --- provider adapters: one tool-calling turn each -------------------------------------------

class _OpenAIChat:
    def __init__(self, model: str, system: str):
        import openai

        self.client, self.model = openai.OpenAI(), model
        self.tools = [{"type": "function", "name": t["name"], "description": t["description"],
                       "parameters": t["schema"], "strict": True} for t in TOOLS]
        self.input: list = [{"role": "system", "content": system}]

    def user(self, text: str) -> None:
        self.input.append({"role": "user", "content": text})

    def turn(self):
        r = self.client.responses.create(model=self.model, input=self.input, tools=self.tools)
        if r.status == "incomplete":
            raise LLMError(f"response incomplete: {r.incomplete_details}")
        self.input += r.output
        calls = [(c.call_id, c.name, json.loads(c.arguments)) for c in r.output if c.type == "function_call"]
        u = r.usage
        return calls, r.output_text, r.model, (u.input_tokens, u.input_tokens_details.cached_tokens or 0,
                                               u.output_tokens)

    def results(self, outputs: list[tuple[str, str, str]]) -> None:
        self.input += [{"type": "function_call_output", "call_id": cid, "output": out} for cid, _, out in outputs]


class _AnthropicChat:
    def __init__(self, model: str, system: str):
        import anthropic

        self.client, self.model, self.system = anthropic.Anthropic(), model, system
        self.tools = [{"name": t["name"], "description": t["description"], "input_schema": t["schema"],
                       "strict": True} for t in TOOLS]
        self.messages: list = []

    def user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

    def turn(self):
        r = self.client.messages.create(model=self.model, max_tokens=16000, system=self.system,
                                        tools=self.tools, messages=self.messages)
        if r.stop_reason == "refusal":
            raise LLMError("model declined the request")
        if r.stop_reason == "max_tokens":
            raise LLMError("output hit max_tokens")
        self.messages.append({"role": "assistant", "content": r.content})
        calls = [(b.id, b.name, b.input) for b in r.content if b.type == "tool_use"]
        text = "".join(b.text for b in r.content if b.type == "text")
        u = r.usage
        cached = u.cache_read_input_tokens or 0
        return calls, text, r.model, (u.input_tokens + cached + (u.cache_creation_input_tokens or 0), cached,
                                      u.output_tokens)

    def results(self, outputs: list[tuple[str, str, str]]) -> None:
        self.messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": cid, "content": out} for cid, _, out in outputs]})


class _OllamaChat:
    def __init__(self, model: str, system: str):
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.url = f"{host if host.startswith('http') else 'http://' + host}/api/chat"
        self.model = model
        self.tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                        "parameters": t["schema"]}} for t in TOOLS]
        self.messages: list = [{"role": "system", "content": system}]

    def user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

    def turn(self):
        body = {"model": self.model, "messages": self.messages, "tools": self.tools, "stream": False,
                "think": False, "options": {"num_ctx": OLLAMA_CONTEXT}}
        request = urllib.request.Request(self.url, data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=1800) as r:
                data = json.loads(r.read())
        except (urllib.error.URLError, TimeoutError) as e:
            raise LLMError(f"Ollama request failed: {e}") from e
        message = data["message"]
        self.messages.append(message)
        calls = []
        for n, c in enumerate(message.get("tool_calls") or []):
            args = c["function"].get("arguments") or {}
            calls.append((str(n), c["function"]["name"], json.loads(args) if isinstance(args, str) else args))
        return calls, message.get("content", ""), self.model, (data.get("prompt_eval_count", 0), 0,
                                                               data.get("eval_count", 0))

    def results(self, outputs: list[tuple[str, str, str]]) -> None:
        self.messages += [{"role": "tool", "tool_name": name, "content": out} for _, name, out in outputs]


ADAPTERS = {"openai": _OpenAIChat, "anthropic": _AnthropicChat, "ollama": _OllamaChat}


def recover_submit(text: str) -> dict | None:
    """Small local models sometimes write the final tool call as text ('submit_answer {...}')
    instead of emitting it as a call. Parse that form; anything else stays unsubmitted."""
    at = text.find("submit_answer")
    start = text.find("{", at) if at >= 0 else -1
    if start < 0:
        return None
    try:
        args, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return None
    return args if isinstance(args, dict) and "answer" in args else None


def finish(project: Project, record: dict) -> dict:
    """Checked answer fields for a finished run, recovering a final call written as text."""
    if record.get("submitted") is not None:
        return {**project.check(record["submitted"]), "no_submit": False, "recovered_from_text": False}
    if (args := recover_submit(record.get("final_text", ""))) is not None:
        return {**project.check(args), "no_submit": False, "recovered_from_text": True}
    text = record.get("final_text", "")
    return {"answer": text, "answerable": bool(text), "citations": [], "requirement_ids": [],
            "unknown_requirement_ids": [], "supported": False, "no_submit": True, "recovered_from_text": False}


def ask(project: Project, question: str, spec: str) -> dict:
    """Run the agent on one question. Returns the checked answer plus a trace of tool calls,
    the transcript segments the tools showed the model, and usage."""
    provider, model = parse_model_spec(spec)
    chat = ADAPTERS[provider](model, SYSTEM)
    chat.user(f"Meetings: {project.meetings_line()}.\n\nQuestion: {question}")
    seen: set[str] = set()
    trace, usage = [], {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "calls": 0}
    submitted, nudged, final_text, model_id = None, False, "", model
    started = time.perf_counter()
    for _ in range(MAX_STEPS):
        calls, text, model_id, (inp, cached, out) = chat.turn()
        usage["calls"] += 1
        usage["input_tokens"] += inp
        usage["cached_input_tokens"] += cached
        usage["output_tokens"] += out
        final_text = text or final_text
        if answer := next((args for _, name, args in calls if name == "submit_answer"), None):
            submitted = answer
            break
        if not calls:
            if nudged:
                break
            chat.user("Call submit_answer with your answer and citations.")
            nudged = True
            continue
        outputs = []
        for cid, name, args in calls:
            result = project.run_tool(name, args, seen)
            trace.append({"tool": name, "args": args})
            outputs.append((cid, name, json.dumps(result, ensure_ascii=False)))
        chat.results(outputs)
    usage["latency_s"] = round(time.perf_counter() - started, 2)
    usage["cost_usd"] = cost_usd(provider, model_id, usage["input_tokens"], usage["cached_input_tokens"],
                                 usage["output_tokens"])
    record = finish(project, {"submitted": submitted, "final_text": final_text})
    seen_lines = sorted({f"{project.segments[s]['meeting']}:{project.segments[s]['source_line']}"
                         for s in seen if s in project.segments})
    return {"question": question, "spec": spec, "model": model_id, **record, "submitted": submitted,
            "final_text": final_text, "trace": trace, "seen_lines": seen_lines, "usage": usage}

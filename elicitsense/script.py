"""Parse scripted meetings used for demos and evaluation.

Format, one utterance per line:

    # id: m1
    # title: Kickoff
    L001 ANALYST: Text of the utterance.
    L012 OWNER: {slow} Um... I think... maybe a deposit?

"..." marks a pause and {slow} marks a slower delivery; both are rendering
hints for speech synthesis and are not part of the spoken words.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

LINE_RE = re.compile(r"^(?P<id>L\d{3})\s+(?P<speaker>[A-Z_]+):\s*(?P<body>.+)$")
META_RE = re.compile(r"^#\s*(?P<key>[a-z_]+):\s*(?P<value>.+)$")


@dataclass
class ScriptLine:
    id: str
    speaker: str
    text: str
    slow: bool = False


@dataclass
class Script:
    id: str
    title: str
    date: str
    lines: list[ScriptLine] = field(default_factory=list)

    @property
    def speakers(self) -> list[str]:
        return sorted({line.speaker for line in self.lines})


def parse_script(path: str | Path) -> Script:
    meta: dict[str, str] = {}
    lines: list[ScriptLine] = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        if m := META_RE.match(raw):
            meta[m["key"]] = m["value"].strip()
            continue
        if raw.startswith("#"):
            continue
        m = LINE_RE.match(raw)
        if not m:
            raise ValueError(f"{path}: cannot parse line: {raw!r}")
        body = m["body"].strip()
        slow = body.startswith("{slow}")
        if slow:
            body = body[len("{slow}"):].strip()
        lines.append(ScriptLine(id=m["id"], speaker=m["speaker"], text=body, slow=slow))
    if "id" not in meta:
        raise ValueError(f"{path}: missing '# id:' header")
    return Script(
        id=meta["id"],
        title=meta.get("title", meta["id"]),
        date=meta.get("date", ""),
        lines=lines,
    )

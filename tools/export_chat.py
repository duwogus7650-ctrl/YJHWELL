"""Export a Claude Code session transcript (.jsonl) to a small, git-friendly,
TEXT-ONLY markdown chat log. Strips images/base64 and tool-result payloads so a
213 MB screenshot-laden transcript collapses to a readable few-hundred-KB log
that any device can read to recover conversation context.

Usage:
    python tools/export_chat.py <transcript.jsonl> <out.md>
"""
from __future__ import annotations

import json
import sys


def _text_blocks(content):
    """Yield ('text'|'tool'|'toolresult', str) from a message content field."""
    if isinstance(content, str):
        if content.strip():
            yield ("text", content)
        return
    if not isinstance(content, list):
        return
    for b in content:
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        if t == "text" and b.get("text", "").strip():
            yield ("text", b["text"])
        elif t == "tool_use":
            name = b.get("name", "?")
            yield ("tool", f"[tool call: {name}]")
        elif t == "tool_result":
            # collapse — never embed tool output (can be huge / images)
            yield ("toolresult", "[tool result]")
        elif t == "image":
            yield ("toolresult", "[image omitted]")


def main():
    src, out = sys.argv[1], sys.argv[2]
    n_msgs = 0
    with open(src, encoding="utf-8") as f, open(out, "w", encoding="utf-8") as w:
        w.write("# Chat log (text-only export)\n\n")
        w.write("Images and tool-result payloads are stripped. Full raw "
                "transcript (with screenshots) is kept as a local desktop "
                "backup, not in git.\n\n---\n\n")
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            msg = ev.get("message")
            if not isinstance(msg, dict):
                continue
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue
            texts = [s for kind, s in _text_blocks(msg.get("content"))
                     if kind == "text"]
            if not texts:
                continue                     # pure tool-call/result turn: skip
            body = "\n\n".join(texts).strip()
            if not body:
                continue
            w.write(f"## {role.upper()}\n\n{body}\n\n---\n\n")
            n_msgs += 1
    print(f"wrote {out}: {n_msgs} text turns")


if __name__ == "__main__":
    main()

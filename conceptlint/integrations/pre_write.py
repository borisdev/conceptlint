"""A `PreToolUse` hook: stop the agent BEFORE it writes a new domain model.

Reporting a duplicate after it is written is the consolation prize. The failure Boris actually
experiences is an agent creating a class without having asked whether to reuse one, extend one,
compose two, or split an existing one with a `kind` discriminator.

A linter reports. A hook can interrupt. This is the interrupt.

    Claude runs Write/Edit
        -> hook reads the pending content
        -> does it declare a NEW Pydantic model?
        -> is there already a model that means this?
            yes  -> BLOCK with the existing one named
            no   -> ASK the four questions, once, and let the human decide

## Two rules it lives by

**Silent unless a new model appears.** It fires on a tiny fraction of writes. A hook that comments
on every edit is one that gets removed within a day, and then the useful interrupt is gone too.

**Fail open, always.** Any error, any timeout, any unparseable input -> allow. A semantic convenience
must never be able to stop work. The cost of being wrong here is a missed prompt; the cost of a hard
failure is a blocked session.

## Install

    {"hooks": {"PreToolUse": [{"matcher": "Write|Edit",
      "hooks": [{"type": "command",
                 "command": "python3 -m conceptlint.integrations.pre_write"}]}]}}

Claude Code passes the tool call on stdin as JSON and reads the decision from stdout.
"""
from __future__ import annotations

import ast
import json
import pathlib
import sys

MODEL_BASES = {"BaseModel", "RootModel"}


def _new_models(content: str) -> list[tuple[str, tuple[str, ...]]]:
    """Pydantic models declared in the pending content, with their fields."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []                       # mid-edit source is not this hook's business
    out = []
    local = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
        bases |= {b.attr for b in node.bases if isinstance(b, ast.Attribute)}
        if not (bases & MODEL_BASES or bases & local):
            continue
        local.add(node.name)
        fields = tuple(t.id for s in node.body if isinstance(s, ast.AnnAssign)
                       for t in [s.target] if isinstance(t, ast.Name) and not t.id.isupper())
        out.append((node.name, fields))
    return out


def _existing(repo: pathlib.Path):
    from conceptlint.models import ModelRecord, discover_models, _overlap  # noqa: PLC0415
    return discover_models(repo), _overlap


def review(content: str, repo: pathlib.Path, path: str = "") -> str | None:
    """The message to show, or None to stay out of the way."""
    proposed = _new_models(content)
    if not proposed:
        return None

    try:
        models, overlap = _existing(repo)
    except Exception:                   # noqa: BLE001 — fail open, see the module docstring
        return None

    # A name that already exists ANYWHERE is being edited, not invented. The first version
    # excluded models from the file being written, which inverted the test: editing `Finding` in
    # models.py made `Finding` look new and fired on every edit to an existing model. That is the
    # noise that gets a hook uninstalled inside a day.
    known = {m.name for m in models}
    lines: list[str] = []

    for name, fields in proposed:
        if name in known:
            continue                    # editing an existing model
        collisions = [
            m for m in models
            if m.name != name
            and (set(_words(name)) & set(_words(m.name)))
            and overlap(set(fields), set(m.fields)) >= 0.6
        ]
        if collisions:
            m = collisions[0]
            lines.append(
                f"⛔ `{name}` looks like `{m.name}`, which already exists at {m.file}:{m.line}\n"
                f"   {m.docstring.splitlines()[0] if m.docstring else '(no docstring)'}\n"
                f"   Reuse it, or say what distinction `{name}` carries that it does not.")
        else:
            lines.append(
                f"❓ `{name}` is a NEW domain model. Before writing it, answer one of:\n"
                f"   1. reuse    — does an existing model already mean this?\n"
                f"   2. extend   — should it subclass one, so the relationship is declared?\n"
                f"   3. compose  — is it two existing models together, rather than a new kind?\n"
                f"   4. split    — should an existing model gain a `kind` discriminator instead?\n"
                f"   If none fit, say why in one line and proceed.")
    return "\n\n".join(lines) if lines else None


def _words(name: str) -> set[str]:
    from conceptlint.models import words  # noqa: PLC0415
    return words(name)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:                   # noqa: BLE001
        return 0

    tool = payload.get("tool_name") or payload.get("tool") or ""
    if tool not in {"Write", "Edit", "MultiEdit"}:
        return 0

    inp = payload.get("tool_input") or {}
    content = inp.get("content") or inp.get("new_string") or ""
    path = inp.get("file_path") or ""
    repo = pathlib.Path(payload.get("cwd") or ".")

    try:
        message = review(content, repo, path=pathlib.Path(path).name if path else "")
    except Exception:                   # noqa: BLE001 — a convenience must never block work
        return 0

    if not message:
        return 0

    # `ask` hands the decision to the human rather than deciding for them. The hook's job is to
    # make the question unavoidable, not to be right about the answer.
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": message,
        }
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

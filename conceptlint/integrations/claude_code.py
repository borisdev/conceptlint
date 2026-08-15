"""Claude Code integration: install the agent rule.

The rule is HAND-WRITTEN and short. The previous one was GENERATED from a package that has since
been retired — which is how it went stale, and then wrong, and then deleted. A rule about language
is not a derived artifact; the vocabulary is answered live by `conceptlint`, and the rule only
carries the part no tool can check.
"""
from __future__ import annotations

import pathlib

RULE_SOURCE = pathlib.Path(__file__).with_name("agent_rule.md")
RULE_PATH = pathlib.Path.home() / ".claude" / "rules" / "domain-language.md"


def install(path: pathlib.Path = RULE_PATH) -> pathlib.Path:
    """Write the rule. Claude Code reads ~/.claude/rules/ at the START of a session."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(RULE_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def uninstall(path: pathlib.Path = RULE_PATH) -> bool:
    if path.exists():
        path.unlink()
        return True
    return False


def status(path: pathlib.Path = RULE_PATH) -> str:
    return f"installed at {path}" if path.exists() else "not installed"

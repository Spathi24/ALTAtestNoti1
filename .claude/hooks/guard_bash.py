"""PreToolUse guard for Bash commands in the ALTA repo.

Blocks the mechanically-enforceable CLAUDE.md hard rules so they stop relying
on prose. Exit code 2 = block the tool call; stderr is shown to Claude.

Wired from .claude/settings.json (PreToolUse, matcher "Bash").
Windows-friendly: pure stdlib, no shell tricks.

Matching note: banned patterns are searched only in the EXECUTABLE part of the
command -- heredoc bodies and quoted strings are stripped first, so a commit
message that merely MENTIONS "git add -A" is not blocked (real incident,
2026-07-03: the guard blocked the commit that introduced the guard). This is a
guardrail against habitual mistakes, not an adversarial sandbox: a command
deliberately smuggled through `bash -c "..."` quoting would bypass it, which
is acceptable for this threat model.
"""
import json
import re
import sys


def executable_part(cmd: str) -> str:
    """Strip heredoc bodies and quoted-string contents from a shell command,
    leaving only the parts the shell would parse as commands/arguments."""
    # Heredoc bodies: <<EOF / <<'EOF' / <<-"EOF" ... up to the terminator line.
    cmd = re.sub(
        r"<<-?\s*(['\"]?)(\w+)\1.*?^\2\s*$",
        "<<HEREDOC",
        cmd,
        flags=re.S | re.M,
    )
    # Quoted string contents (single first: no escapes inside '...').
    cmd = re.sub(r"'[^']*'", "''", cmd)
    cmd = re.sub(r'"(?:\\.|[^"\\])*"', '""', cmd)
    return cmd


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # never break the session on a malformed payload
    raw = (payload.get("tool_input") or {}).get("command", "") or ""
    cmd = executable_part(raw)
    # Rules apply per shell segment so `.*` never leaks across `&&`/`;`/pipes
    # (e.g. `git add foo.py && cat .env.example` must not trip rule 7).
    segments = re.split(r"&&|\|\||;|\||\n", cmd)

    rules = [
        (r"git\s+worktree\s+add",
         "BLOCKED (CLAUDE.md rule 1): never create worktrees. Work on main "
         "in the real repo directory."),
        (r"git\s+add\s+(-A\b|--all\b|\.(\s|$))",
         "BLOCKED (CLAUDE.md rule 3): stage specific files only -- "
         "`git add <file> <file>`, never -A / --all / `.`"),
        (r"git\s+add\s+.*(\.env\b|\.sqlite\b|\.pyc\b)",
         "BLOCKED (CLAUDE.md rule 7): never stage .env / *.sqlite / *.pyc."),
        (r"git\s+push\s+.*(-f\b|--force\b)",
         "BLOCKED: no force-push to origin/main. Ask the user."),
    ]
    for seg in segments:
        for pattern, msg in rules:
            if re.search(pattern, seg):
                print(msg, file=sys.stderr)
                return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

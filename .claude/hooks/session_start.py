"""SessionStart hook: inject the ALTA preflight anchor into context.

stdout from a SessionStart hook is added to Claude's context at session start.
Keep it short — it is a pointer, not a copy of the rules.
"""
import subprocess


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except Exception:
        return "(git unavailable)"


branch = _git("rev-parse", "--abbrev-ref", "HEAD")
top = _git("rev-parse", "--show-toplevel")

print(
    f"[ALTA preflight] repo={top} branch={branch}\n"
    "Before ANY edit: run the `alta-preflight` skill (read CLAUDE.md -> "
    "PROJECT_STATE.md -> HANDOFF.md -> top CHANGELOG entry; suite + ruff "
    "green; quote the active slice's Definition of Done verbatim).\n"
    "Standing anchors: build freeze is ON; one slice per session; at any "
    "limitation, park it in HANDOFF and STOP; after every change ask "
    "'did this save someone time, or did I just make the code more complete?'"
)
if branch != "main":
    print(f"WARNING: not on main (on '{branch}'). CLAUDE.md rule 1.")
if ".claude/worktrees" in top.replace("\\", "/"):
    print("WARNING: you are inside a worktree. cd back to the real repo NOW.")

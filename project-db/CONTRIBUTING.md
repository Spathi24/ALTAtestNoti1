# Contributing & Development Process — ALTA / `project_db`

This is the **how we work** doc. CLAUDE.md has the hard rules; STRATEGY.md has
the mission; HANDOFF.md has the engineering state. This file is the mechanics:
the toolchain, the quality gates, and the conventions that keep ~40k lines
consistent without anyone policing them by hand.

The guiding principle: **consistency is enforced by tools, not willpower.** A
rule that isn't in `ruff`, `mypy`, pre-commit, or CI will drift. So every
convention below is (or is becoming) machine-checked.

---

## 0. One-time setup

```bash
cd project-db
py -3.13 -m pip install -e ".[dev]"        # editable install + tooling
cd ..                                       # repo root (where the hooks live)
py -3.13 -m pip install pre-commit
py -3.13 -m pre_commit install              # installs the git hook
git config blame.ignoreRevsFile .git-blame-ignore-revs
```

## 1. The everyday loop

```bash
cd project-db
py -3.13 -m pytest tests/ -q          # the suite MUST stay green (CLAUDE.md #3)
py -3.13 -m ruff check .              # lint
py -3.13 -m ruff format .            # auto-format
py -3.13 -m mypy                      # type check (lenient today)
```

Pre-commit runs the fast subset (format + lint + hygiene) automatically on
`git commit`. The full suite runs in CI. Commit specific files, never `-A`
(the egg-info trap). Push to `origin/main` after each meaningful change.

## 2. Quality gates (what blocks what)

| Gate | Where | Blocking? |
|------|-------|-----------|
| 958-test suite | CI (`test` job, py3.11 + py3.13) | **Yes** |
| ruff lint | pre-commit + CI (`quality`) | informational → **ratcheting to yes** |
| ruff format | pre-commit + CI | informational → **ratcheting to yes** |
| mypy | CI (`quality`) | informational (lenient baseline) |

CI lives in `.github/workflows/ci.yml`. The `quality` job's lint/format steps
are `continue-on-error: true` **only until the codebase-wide sweep lands**
(§3); flip them to blocking the moment the tree is green.

## 3. Linting: the ratchet

Config is in `pyproject.toml` `[tool.ruff.lint]`. We deliberately started with a
set we can hold green today: `E, F, W, I, UP, C4, RUF` (line-length is owned by
the formatter, not the linter).

**How to tighten** — one rule-family per PR, never a big-bang:

1. Add a family to `select` (e.g. `B` flake8-bugbear, then `SIM`, `PTH`,
   `PERF`, `ASYNC`).
2. `ruff check --statistics` to see the volume.
3. Auto-fix what's safe (`ruff check --fix`), hand-fix the rest, or — if a rule
   has legitimate exceptions — add a **scoped** `per-file-ignores` entry with a
   comment saying why (e.g. `B008` is FastAPI's `Depends()`/`Query()` idiom and
   stays ignored for `web/` routes).
4. Run the suite, commit, push. The ratchet only turns one way: the lint
   surface can shrink, never grow.

## 4. Formatting

`ruff format` (Black-compatible, 100 cols). Activating it across an existing
codebase reflows nearly every file, so it lands as **one tagged, behavior-free
commit** whose SHA goes in `.git-blame-ignore-revs` — that keeps `git blame`
pointing at the real author of each line. After that, the formatter just keeps
new code in line; no more bulk reflows.

## 5. Type checking: the ratchet

mypy config is in `pyproject.toml` `[tool.mypy]`, lenient today (the codebase is
largely untyped). Adoption order (type the high-traffic chokepoints first, where
types pay off most):

1. `db/models/` and `identity/` — imported everywhere; typing them lets callers
   be checked too.
2. `ai/views.py::report_project_financials` and the other report chokepoints.
3. New code: every new function gets annotations (encouraged now, enforced
   later via a stricter `[[tool.mypy.overrides]]` block per typed module).

Tighten by adding a per-module override that turns on `disallow_untyped_defs`
once a module is clean — same one-way ratchet as linting.

## 6. Code conventions (the consistency rules)

These encode patterns already load-bearing in the codebase (see HANDOFF §1–§3).
Most are or will be tool-checked; the rest are review conventions.

- **Chokepoints are sacred.** Money flows through
  `ai/views.py::report_project_financials`; identity through
  `resolve_or_create`; derived values through a service module
  (`ai/views.py` / `web/ui_views.py`), never a template or route. Don't add a
  second path — call the chokepoint.
- **LLM extracts; deterministic code computes.** No arithmetic, sums, or
  classification-by-rule inside a prompt. The LLM returns evidence-backed facts;
  Python does the math. (Trust invariant.)
- **Advisor, never actor.** AI suggestions land in `Proposal` as PENDING; a
  human accepts. External write first, local mirror second, status flip last.
- **Validate-don't-crash at boundaries.** Unknown enum values coerce to a
  catch-all + warn; bad LLM items go to `batch.errors`; never let a malformed
  source record take down a sync.
- **ASCII in CLI/script `print()`** (cp1252 console). `force_utf8_output()`
  covers entry points, but prefer `->`, `OK:`, `FAIL:` over arrows/box-drawing.
- **Imports:** standard lib → third-party → first-party (`project_db`),
  enforced by ruff `I`. **Naming:** `snake_case` functions/vars, `PascalCase`
  classes, `_leading_underscore` for module-private helpers.
- **Errors:** raise with context (`raise X from err` inside `except` — ruff
  `B904` once `B` is enabled); don't swallow exceptions silently.

## 7. Tests

- `tests/conftest.py` stubs env BEFORE app import; any code path that could hit
  `.complete()` must use `MockLLMProvider`. Web tests use `StaticPool` +
  `check_same_thread=False`; call `session.expire_all()` after a route commits.
- Add a test with every feature; update the test when you change an API surface.
- LLM-app specific: prefer **deterministic, mock-driven** end-to-end tests
  (note → signals → proposals). The eval-harness for prompt-quality regression
  (a small gold set + scorer) is tracked in INTENTIONS §8 — that's the
  LLM-output-quality gate, complementary to these correctness tests.

## 8. Commits & PRs

- Specific files staged (never `-A`). Imperative subject, concern-grouped body.
- Co-author trailer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
  (use the model actually running).
- Keep the suite green before pushing. A red `main` is a stop-the-line event.

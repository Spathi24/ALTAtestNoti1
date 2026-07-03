"""Cross-document financial reconciliation via the OpenAI API (cheap + reusable).

WHY THIS EXISTS
---------------
The per-document extractor (``fill-ledger-llm``) reads one file at a time, so it
structurally cannot see relationships ACROSS a project's documents:
  * the SAME estimate counted twice (a Google Doc + its PDF export; a signed
    contract + the estimate it references)
  * a lump "SOW / Contract Price" that RESTATES itemized quotes already counted
  * a vendor bill addressed TO Alta wrongly booked as Alta REVENUE (sign error)
  * superseding versions of one estimate counted as two

This tool reads ALL of a project's documents TOGETHER and reports those faults.
It is ADVISORY and READ-ONLY: it never touches the database. It writes a JSON +
Markdown report you (a human) approve before anything changes.

It is deliberately a standalone OpenAI script, not a Claude-agent deployment:
gpt-4o-mini chews through every project for a few cents, and you can re-run it
whenever the ledger changes.

PIPELINE
--------
    py -3.13 scripts/export_financial_bundles.py --out .reconcile_bundles
    py -3.13 scripts/reconcile_financials_llm.py  --bundles-dir .reconcile_bundles

For a large project the per-doc payload is split across several calls (each still
sees a one-line index of EVERY doc, so cross-doc awareness is preserved), then a
final consolidation call dedupes the candidate flags. A second adversarial
"verify" call per project tries to refute each flag before it counts.

Corrected revenue/cost are summed DETERMINISTICALLY in Python from each flag's
explicit revenue_delta / cost_delta -- the model never does the arithmetic.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import project_db.config  # noqa: F401  (triggers selective .env load)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

COMPANY = "Alta Construction Group"

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = f"""You are a forensic construction-accounting reconciler for "{COMPANY}"
(also "Group Alta" / "Groupe Construction Alta", RBQ 5867-9390-01, 7557 Gouin Est, Montreal).

You receive ONE project's financial documents -- each with the line-item rows an
automated single-document extractor produced. A single-doc extractor CANNOT see
relationships ACROSS documents, so it double-counts and mis-sides. Read ALL the
documents TOGETHER and find ONLY genuine cross-document errors. Be skeptical;
demand verbatim evidence; do NOT invent problems.

ACCOUNTING RULES
- REVENUE = what Alta's CLIENT pays Alta. A document is revenue ONLY if Alta is the
  SELLER/CONTRACTOR issuing it to a homeowner/client (an Alta estimate/quote/SOW
  addressed to a person like "Richard Geller", "Tania Bagdassarian", "Murielle Zagury").
- COST = what Alta pays a SUPPLIER/SUBCONTRACTOR. If a document is BILLED TO / SOLD TO /
  "submitted to" Alta or its staff (Erik Linseisen, Lorenzo Collard, ...) by an outside
  vendor (window maker, plumber, electrician, glass shop, appliance store, environmental
  consultant), it is a COST even if its doc_type says "quote"/"estimate"/"proposal".
  Look at the BILL TO / SOLD TO / "submitted by" / issuer lines in the text.
- A worksheet that lists several OUTSIDE vendors in a "Company"/"Supplier" column (each
  with that vendor's own phone) is Alta's COST build-up, not client revenue.
- STATUS RULE (read carefully): each revenue row carries a status. CONTRACTED (INCLUDED in
  revenue) = status accepted, actual, unknown, or empty. EXCLUDED (pipeline) = status
  "proposed" or "superseded". "unknown" simply means the system has not labelled the stage
  -- it is CONTRACTED, INCLUDE it. NEVER flag or exclude a document merely because its
  status is "unknown". Do not emit a flag whose only basis is the status value.
- SIDE RULE: every row already has a "side" (revenue or cost). A supplier bill already
  booked on the COST side is CORRECT -- do NOT "reclassify it to cost" again (that
  double-counts the cost). Only raise a side_misclassification when a row's CURRENT side
  CONTRADICTS the issuer / BILL-TO evidence (e.g. a vendor-billed doc currently sided as
  revenue, or Alta's own estimate sided as cost).
- CLEAN PROJECTS ARE COMMON: many bundles are a SINGLE genuine Alta-issued client
  quote/estimate (Alta is the issuer/seller to a named homeowner) with no errors at all.
  If nothing is duplicated, restated, or mis-sided, return an EMPTY flags array. Do not
  manufacture a flag to seem thorough.
- Sales taxes (GST/TPS, QST/TVQ, PST/HST) are pass-through, never revenue or cost.

TWO HIGH-VALUE PATTERNS people miss (general, not project-specific):
- OPPOSITE-SIDE NEAR-DUPLICATE: if two documents share the same/near-identical title,
  overview text, or itemized line descriptions+amounts but sit on OPPOSITE sides (one
  booked as revenue, the other as cost) -- e.g. a Google Doc estimate and its PDF export,
  or one estimate scanned twice -- that is almost always the SAME estimate counted twice
  and mis-sided. It is Alta's own value-of-work, so keep ONE copy on REVENUE and remove
  the phantom COST entirely (cost_delta = -(that cost), revenue_delta = 0).
- PER-ROW DISTINCT VENDORS = COST SHEET: do NOT trust the existing "side" label -- that is
  exactly what you are auditing. A genuine Alta CLIENT quote names a CLIENT (a homeowner /
  person) and reads as Alta's own priced scope. By contrast, if a document names NO client
  and instead organizes its line items BY VENDOR -- i.e. the source has a "Company" /
  "Fournisseur" / "Supplier" column listing several DIFFERENT outside firms (often each with
  its own phone in a "Contact" column), e.g. one row per appliance dealer / container company
  / HVAC firm / plumber / locksmith -- then the whole document is Alta's procurement / COST
  build-up sheet (amounts Alta PAYS), even if every row is currently sided as revenue. That
  vendor-column structure is DECISIVE. Move the whole total revenue->cost (revenue_delta
  = -(total), cost_delta = +(total)).

ERROR TYPES
1. duplicate -- the same economic document counted twice (Google Doc + PDF export;
   a contract + the estimate it references at the same total; the same estimate on
   opposite sides per the OPPOSITE-SIDE NEAR-DUPLICATE pattern above).
2. rollup_restatement -- a lump "SOW"/"Statement of Work"/"Contract Price" (often Div 99)
   restating scope already itemized in a quote/estimate for the same estimate # or scope.
3. superseding_version -- two estimates of the SAME scope at different totals; count only
   the latest/accepted one (note: a proposed version is already excluded, so its
   correcting deltas are usually 0).
4. side_misclassification -- a vendor doc billed TO Alta booked as revenue (or vice-versa);
   or the SAME estimate booked once as revenue and once as cost.
5. tax_contamination -- a tax amount that leaked into a revenue/cost row.

For EACH error emit a flag. CRITICAL -- give two explicit signed CAD deltas, the program
sums them (you do NOT compute corrected totals):
  revenue_delta = change to CONTRACTED REVENUE if the fix is applied (negative removes an overstatement)
  cost_delta    = change to TOTAL COST if the fix is applied (negative removes a phantom cost)
Examples: a supplier worksheet wrongly booked as $X revenue -> revenue_delta -X, cost_delta +X.
A duplicate that created a phantom $Y cost -> revenue_delta 0, cost_delta -Y.
A lump SOW restating an itemized quote (drop the lump) -> revenue_delta -Z, cost_delta 0.
If a flag is awareness-only (no correction), set both deltas to 0.
Quote VERBATIM evidence (the BILL TO line, the estimate #, the matching totals).
Apply the RULES generally; do not hard-code project-specific facts. If a project is clean,
return an empty flags array."""


def recon_user_prompt(project: str, naive_rev: float, naive_cost: float, doc_blocks: str, doc_index: str) -> str:
    return (
        f"PROJECT: {project}\n"
        f"NAIVE_CONTRACTED_REVENUE (current system): {naive_rev:.2f}\n"
        f"NAIVE_TOTAL_COST (current system): {naive_cost:.2f}\n\n"
        f"INDEX OF EVERY DOCUMENT IN THIS PROJECT (name | type | revenue | cost | statuses):\n{doc_index}\n\n"
        f"DOCUMENTS (full detail for the ones in THIS batch):\n{doc_blocks}\n\n"
        "Return the structured reconciliation for this project. Echo the naive figures."
    )


def consolidate_user_prompt(project: str, naive_rev: float, naive_cost: float, doc_index: str, candidates: str) -> str:
    return (
        f"PROJECT: {project}\n"
        f"NAIVE_CONTRACTED_REVENUE: {naive_rev:.2f}\nNAIVE_TOTAL_COST: {naive_cost:.2f}\n\n"
        f"FULL DOCUMENT INDEX:\n{doc_index}\n\n"
        f"CANDIDATE FLAGS produced by per-batch passes (may overlap or duplicate):\n{candidates}\n\n"
        "Consolidate: merge duplicates, drop anything unsupported, keep each distinct real error ONCE. "
        "Return the final structured reconciliation."
    )


def verify_user_prompt(project: str, doc_index: str, doc_blocks: str, flags_json: str) -> str:
    return (
        "You are a careful second-opinion verifier. For each flag, check it against the source text. "
        "Mark 'confirmed' when the evidence clearly supports it; 'uncertain' when you cannot tell from the "
        "text; and 'refuted' ONLY when you find a CONCRETE CONTRADICTION in the source (e.g. the BILL-TO "
        "party is actually the client not Alta, or the two docs are demonstrably different scopes). Do NOT "
        "refute merely because you are unsure -- use 'uncertain' for that. Matching estimate-# or identical "
        "line items across docs is strong evidence of a duplicate/restatement. Check that the fix does not "
        "erase legitimate separate work, and that the dollar deltas match the rows.\n\n"
        f"PROJECT: {project}\n\nDOCUMENT INDEX:\n{doc_index}\n\nDOCUMENT DETAIL:\n{doc_blocks}\n\n"
        f"FLAGS TO VERIFY:\n{flags_json}\n\n"
        "For each flag return: flag_id, verdict (confirmed/refuted/uncertain), and the revenue_delta and "
        "cost_delta YOU believe are correct (0 if refuted), plus brief reasoning citing the source text."
    )


# ---------------------------------------------------------------------------
# JSON schemas (OpenAI strict structured outputs)
# ---------------------------------------------------------------------------

_FLAG_PROPS = {
    "flag_id": {"type": "string", "description": "short unique id within the project, e.g. f1"},
    "flag_type": {
        "type": "string",
        "enum": ["duplicate", "rollup_restatement", "superseding_version", "side_misclassification", "tax_contamination", "other"],
    },
    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
    "documents": {"type": "array", "items": {"type": "string"}},
    "revenue_delta": {"type": "number", "description": "signed CAD change to contracted revenue if applied"},
    "cost_delta": {"type": "number", "description": "signed CAD change to total cost if applied"},
    "current_treatment": {"type": "string"},
    "recommended_treatment": {"type": "string"},
    "evidence": {"type": "string", "description": "verbatim quotes/figures from the documents"},
    "reasoning": {"type": "string"},
}

RECON_SCHEMA = {
    "name": "project_reconciliation",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["project", "confidence", "summary", "flags"],
        "properties": {
            "project": {"type": "string"},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "summary": {"type": "string"},
            "flags": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(_FLAG_PROPS.keys()),
                    "properties": _FLAG_PROPS,
                },
            },
        },
    },
}

VERDICT_SCHEMA = {
    "name": "flag_verdicts",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["verdicts"],
        "properties": {
            "verdicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["flag_id", "verdict", "revenue_delta", "cost_delta", "reasoning"],
                    "properties": {
                        "flag_id": {"type": "string"},
                        "verdict": {"type": "string", "enum": ["confirmed", "refuted", "uncertain"]},
                        "revenue_delta": {"type": "number"},
                        "cost_delta": {"type": "number"},
                        "reasoning": {"type": "string"},
                    },
                },
            }
        },
    },
}


# ---------------------------------------------------------------------------
# Rendering bundle docs into compact text for the model
# ---------------------------------------------------------------------------

def _doc_index_line(doc: dict) -> str:
    statuses = ",".join(doc.get("revenue_statuses") or []) or "-"
    roll = " [ROLLUP]" if doc.get("is_summary_rollup") else ""
    return (
        f"- {doc['document']!r} | {doc.get('doc_type')} | rev={doc.get('revenue_total', 0):.2f} "
        f"| cost={doc.get('cost_total', 0):.2f} | status={statuses}{roll}"
    )


def _doc_block(doc: dict, snippet_chars: int) -> str:
    rows = doc.get("rows") or []
    row_lines = []
    for r in rows[:40]:
        row_lines.append(
            f"    {r.get('side'):7} {r.get('status')!s:9} div{r.get('division_code')!s:>5} "
            f"{r.get('amount_type', ''):10} {float(r.get('amount') or 0):>12,.2f}  {(r.get('description') or '')[:70]}"
        )
    if len(rows) > 40:
        row_lines.append(f"    ... (+{len(rows) - 40} more rows)")
    snippet = (doc.get("text_excerpt") or "")[:snippet_chars]
    return (
        f"### {doc['document']!r}  (type={doc.get('doc_type')}, "
        f"rev={doc.get('revenue_total', 0):.2f}, cost={doc.get('cost_total', 0):.2f}, "
        f"statuses={doc.get('revenue_statuses')})\n"
        f"  ROWS:\n" + ("\n".join(row_lines) if row_lines else "    (none)") + "\n"
        f"  SOURCE TEXT (first {snippet_chars} chars):\n{snippet}\n"
    )


def _chunk_docs(docs: list[dict], snippet_chars: int, budget_chars: int) -> list[list[dict]]:
    """Greedily group docs so each batch's rendered detail fits the char budget.
    A single oversized doc still goes alone in its own batch."""
    chunks: list[list[dict]] = []
    cur: list[dict] = []
    cur_len = 0
    for d in docs:
        blen = len(_doc_block(d, snippet_chars))
        if cur and cur_len + blen > budget_chars:
            chunks.append(cur)
            cur, cur_len = [], 0
        cur.append(d)
        cur_len += blen
    if cur:
        chunks.append(cur)
    return chunks


# ---------------------------------------------------------------------------
# OpenAI plumbing
# ---------------------------------------------------------------------------

class _LLM:
    def __init__(self, model: str, timeout: float = 120.0) -> None:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise SystemExit("FAIL: OPENAI_API_KEY is not set (needed for reconciliation).")
        from openai import OpenAI

        self.model = model
        self._client = OpenAI(api_key=key, timeout=timeout)
        self.calls = 0

    def structured(self, system: str, user: str, schema: dict) -> dict:
        self.calls += 1
        last_exc: Exception | None = None
        for attempt in range(6):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    temperature=0,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    response_format={"type": "json_schema", "json_schema": schema},
                )
                msg = resp.choices[0].message
                if getattr(msg, "refusal", None):
                    raise RuntimeError(f"model refused: {msg.refusal}")
                return json.loads(msg.content)
            except Exception as exc:
                last_exc = exc
                s = str(exc)
                if "rate_limit" in s or "429" in s or "Rate limit" in s:
                    m = re.search(r"try again in ([\d.]+)s", s)
                    wait = float(m.group(1)) + 0.5 if m else min(2 ** attempt, 30)
                    time.sleep(wait)
                    continue
                raise
        raise RuntimeError(f"exhausted retries: {last_exc}")


# ---------------------------------------------------------------------------
# Per-project reconciliation
# ---------------------------------------------------------------------------

def reconcile_project(llm: _LLM, bundle: dict, *, snippet_chars: int, budget_chars: int, verify: bool) -> dict:
    project = bundle["project"]
    naive_rev = float(bundle.get("naive_contracted_revenue") or 0)
    naive_cost = float(bundle.get("naive_total_cost") or 0)
    docs = bundle.get("docs") or []
    doc_index = "\n".join(_doc_index_line(d) for d in docs)

    chunks = _chunk_docs(docs, snippet_chars, budget_chars)
    if len(chunks) <= 1:
        blocks = "\n".join(_doc_block(d, snippet_chars) for d in docs)
        recon = llm.structured(
            SYSTEM_PROMPT, recon_user_prompt(project, naive_rev, naive_cost, blocks, doc_index), RECON_SCHEMA
        )
        flags = recon.get("flags") or []
        confidence = recon.get("confidence", "medium")
        summary = recon.get("summary", "")
    else:
        # Split: each batch sees the full index but only its own docs' detail.
        candidate_flags: list[dict] = []
        for i, chunk in enumerate(chunks):
            blocks = "\n".join(_doc_block(d, snippet_chars) for d in chunk)
            part = llm.structured(
                SYSTEM_PROMPT, recon_user_prompt(project, naive_rev, naive_cost, blocks, doc_index), RECON_SCHEMA
            )
            for f in part.get("flags") or []:
                f["flag_id"] = f"b{i}_{f.get('flag_id', 'f')}"
                candidate_flags.append(f)
        # Consolidate candidates with full cross-doc index.
        merged = llm.structured(
            SYSTEM_PROMPT,
            consolidate_user_prompt(project, naive_rev, naive_cost, doc_index, json.dumps(candidate_flags, indent=2)),
            RECON_SCHEMA,
        )
        flags = merged.get("flags") or []
        confidence = merged.get("confidence", "medium")
        summary = merged.get("summary", "")

    # Adversarial verify pass (one call reviews all flags for the project).
    verdict_map: dict[str, dict] = {}
    if verify and flags:
        blocks = "\n".join(_doc_block(d, snippet_chars) for d in docs)[: budget_chars + 20_000]
        vres = llm.structured(
            SYSTEM_PROMPT,
            verify_user_prompt(project, doc_index, blocks, json.dumps(flags, indent=2)),
            VERDICT_SCHEMA,
        )
        for v in vres.get("verdicts") or []:
            verdict_map[v["flag_id"]] = v

    # Attach verdicts; deterministically sum deltas for every flag the finder raised
    # EXCEPT those a verifier explicitly refuted (a concrete contradiction). The human
    # still reviews each line; this is a "proposed corrected" picture, not an auto-write.
    rev_adj = cost_adj = 0.0
    out_flags = []
    for f in flags:
        v = verdict_map.get(f["flag_id"])
        verdict = (v or {}).get("verdict", "unverified" if verify else "not_verified")
        r_delta = float((v or {}).get("revenue_delta", f.get("revenue_delta", 0)) if v else f.get("revenue_delta", 0))
        c_delta = float((v or {}).get("cost_delta", f.get("cost_delta", 0)) if v else f.get("cost_delta", 0))
        applied = verdict != "refuted"
        if applied:
            rev_adj += r_delta
            cost_adj += c_delta
        out_flags.append(
            {
                **f,
                "verdict": verdict,
                "applied": applied,
                "verified_revenue_delta": r_delta,
                "verified_cost_delta": c_delta,
                "verifier_reasoning": (v or {}).get("reasoning", ""),
            }
        )

    return {
        "project": project,
        "confidence": confidence,
        "summary": summary,
        "naive_contracted_revenue": round(naive_rev, 2),
        "naive_total_cost": round(naive_cost, 2),
        "corrected_contracted_revenue": round(naive_rev + rev_adj, 2),
        "corrected_total_cost": round(naive_cost + cost_adj, 2),
        "n_calls_batches": len(chunks),
        "flags": out_flags,
    }


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def render_markdown(reports: list[dict]) -> str:
    lines = ["# Cross-Document Financial Reconciliation (advisory)\n"]
    lines.append(
        "_Read-only. Proposed corrections from reading each project's documents together. "
        "Nothing was written to the database._\n"
    )
    tot_naive_rev = sum(r["naive_contracted_revenue"] for r in reports)
    tot_corr_rev = sum(r["corrected_contracted_revenue"] for r in reports)
    tot_naive_cost = sum(r["naive_total_cost"] for r in reports)
    tot_corr_cost = sum(r["corrected_total_cost"] for r in reports)
    n_app = sum(1 for r in reports for f in r["flags"] if f.get("applied"))
    lines.append(
        f"**Portfolio (proposed):** contracted revenue {tot_naive_rev:,.2f} -> **{tot_corr_rev:,.2f}** "
        f"(Δ {tot_corr_rev - tot_naive_rev:,.2f}); cost {tot_naive_cost:,.2f} -> "
        f"**{tot_corr_cost:,.2f}** (Δ {tot_corr_cost - tot_naive_cost:,.2f}); "
        f"{n_app} proposed correction(s) across {len(reports)} projects. Each needs your approval.\n"
    )
    lines.append("| Project | Naive rev | Corrected rev | Naive cost | Corrected cost | Applied flags |")
    lines.append("|---|--:|--:|--:|--:|--:|")
    for r in sorted(reports, key=lambda x: x["naive_contracted_revenue"], reverse=True):
        nc = sum(1 for f in r["flags"] if f.get("applied"))
        lines.append(
            f"| {r['project']} | {r['naive_contracted_revenue']:,.2f} | {r['corrected_contracted_revenue']:,.2f} "
            f"| {r['naive_total_cost']:,.2f} | {r['corrected_total_cost']:,.2f} | {nc} |"
        )
    lines.append("")

    for r in sorted(reports, key=lambda x: x["naive_contracted_revenue"], reverse=True):
        flags = r["flags"]
        if not flags:
            continue
        n_ref = sum(1 for f in flags if f["verdict"] == "refuted")
        lines.append(f"\n## {r['project']}  (confidence: {r['confidence']})")
        lines.append(
            f"Revenue {r['naive_contracted_revenue']:,.2f} -> **{r['corrected_contracted_revenue']:,.2f}**, "
            f"cost {r['naive_total_cost']:,.2f} -> **{r['corrected_total_cost']:,.2f}**."
        )
        # Show CONFIRMED/UNCERTAIN first, then a clearly-labelled "found but dismissed"
        # block -- nothing is hidden, so you can overrule the model's verifier.
        for f in flags:
            if f["verdict"] == "refuted":
                continue
            mark = {"confirmed": "OK", "uncertain": "??", "unverified": "--"}.get(f["verdict"], "--")
            lines.append(
                f"\n- **[{mark} {f['verdict']}] {f['flag_type']} / {f['severity']}** "
                f"(rev Δ {f['verified_revenue_delta']:,.2f}, cost Δ {f['verified_cost_delta']:,.2f})"
            )
            lines.append(f"  - Docs: {', '.join(repr(d) for d in f.get('documents', []))}")
            lines.append(f"  - Now: {f.get('current_treatment', '')}")
            lines.append(f"  - Fix: {f.get('recommended_treatment', '')}")
            lines.append(f"  - Evidence: {f.get('evidence', '')[:400]}")
        if n_ref:
            lines.append(
                f"\n  _Found but DISMISSED on review ({n_ref}) -- double-check these yourself; "
                "the auto-verifier can be wrong:_"
            )
            for f in flags:
                if f["verdict"] != "refuted":
                    continue
                lines.append(
                    f"  - ~~{f['flag_type']}~~ {', '.join(repr(d) for d in f.get('documents', []))}: "
                    f"proposed rev Δ {f.get('revenue_delta', 0):,.2f}, cost Δ {f.get('cost_delta', 0):,.2f} "
                    f"-- {f.get('recommended_treatment', '')[:160]} (verifier: {f.get('verifier_reasoning','')[:160]})"
                )
    # Needs-your-eyes queue
    uncertain = [(r, f) for r in reports for f in r["flags"] if f["verdict"] == "uncertain"]
    if uncertain:
        lines.append("\n## Needs your eyes (uncertain)")
        for r, f in uncertain:
            lines.append(f"- **{r['project']}**: {f.get('recommended_treatment', '')} ({f.get('reasoning','')[:200]})")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bundles-dir", default=".reconcile_bundles", help="dir of *.json bundles from export_financial_bundles.py")
    ap.add_argument("--out", default=None, help="output basename (default <bundles-dir>/_reconciliation)")
    # gpt-4.1 is the right tier here: gpt-4o-mini invents false errors and gpt-4o misses
    # the subtler cross-doc patterns (vendor-worksheet-as-revenue). Override with --model.
    ap.add_argument("--model", default=os.environ.get("OPENAI_RECONCILE_MODEL", "gpt-4.1"))
    ap.add_argument("--snippet-chars", type=int, default=2800, help="source-text chars per doc sent to the model")
    ap.add_argument("--budget-chars", type=int, default=45_000, help="max rendered detail per call before splitting")
    ap.add_argument("--project", default=None, help="only this project (substring match on file/name)")
    ap.add_argument("--no-verify", action="store_true", help="skip the adversarial verify pass")
    args = ap.parse_args()

    bdir = Path(args.bundles_dir)
    if not bdir.is_dir():
        print(f"FAIL: {bdir} not found. Run export_financial_bundles.py first.", file=sys.stderr)
        return 2
    files = sorted(p for p in bdir.glob("*.json") if not p.name.startswith("_"))
    if args.project:
        needle = args.project.lower()
        files = [p for p in files if needle in p.name.lower()]
    if not files:
        print("FAIL: no bundle files matched.", file=sys.stderr)
        return 2

    llm = _LLM(args.model)
    reports = []
    print(f"Reconciling {len(files)} project(s) with {args.model} (verify={'off' if args.no_verify else 'on'})...\n")
    for p in files:
        bundle = json.loads(p.read_text(encoding="utf-8"))
        try:
            rep = reconcile_project(
                llm, bundle, snippet_chars=args.snippet_chars, budget_chars=args.budget_chars, verify=not args.no_verify
            )
        except Exception as exc:  # keep going; one bad project should not sink the run
            print(f"  FAIL {bundle.get('project', p.name)}: {exc}", file=sys.stderr)
            continue
        reports.append(rep)
        nconf = sum(1 for f in rep["flags"] if f["verdict"] == "confirmed")
        print(
            f"  {rep['project'][:34]:34} rev {rep['naive_contracted_revenue']:>12,.2f} -> "
            f"{rep['corrected_contracted_revenue']:>12,.2f}  cost {rep['naive_total_cost']:>11,.2f} -> "
            f"{rep['corrected_total_cost']:>11,.2f}  [{nconf} confirmed, {len(rep['flags'])} flags]"
        )

    out_base = Path(args.out) if args.out else bdir / "_reconciliation"
    out_base.parent.mkdir(parents=True, exist_ok=True)
    (out_base.with_suffix(".json")).write_text(json.dumps(reports, indent=2, default=str), encoding="utf-8")
    (out_base.with_suffix(".md")).write_text(render_markdown(reports), encoding="utf-8")

    tot_d_rev = sum(r["corrected_contracted_revenue"] - r["naive_contracted_revenue"] for r in reports)
    tot_d_cost = sum(r["corrected_total_cost"] - r["naive_total_cost"] for r in reports)
    print(
        f"\nDone in {llm.calls} OpenAI call(s). Portfolio revenue change {tot_d_rev:,.2f}, "
        f"cost change {tot_d_cost:,.2f}."
    )
    print(f"Report: {out_base.with_suffix('.md')}")
    print(f"JSON:   {out_base.with_suffix('.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

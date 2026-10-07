"""Render a PR comment from an evidence pack. Template only — no generated prose."""
from __future__ import annotations

ICONS = {"PASS": "✅", "WARN": "⚠️", "BLOCK": "🛑"}


def render_comment(pack: dict) -> str:
    verdict = pack["verdict"]
    lines = [
        f"## {ICONS.get(verdict, '')} ArcadeAttest verdict: **{verdict}**",
        "",
        f"Decision `{pack['decision_id']}` v{pack['record_version']} · repo `{pack.get('repo') or 'n/a'}` · mode `{pack['mode']}`"
        + ("" if pack["enforced"] else " (advisory — not enforced)"),
        "",
        "| Predicate | Severity | Status | Measured | Threshold |",
        "|---|---|---|---|---|",
    ]
    for result in pack["predicates"]:
        threshold = ", ".join(f"{k}={v}" for k, v in result["threshold"].items())
        lines.append(
            f"| `{result['type']}` | {result['severity']} | {result['status']} | {result['measured']} | {threshold} |"
        )
    criteria = pack.get("criteria") or []
    if criteria:
        scoring = pack.get("scoring") or {}
        overall = pack.get("overall_score")
        profile = scoring.get("profile") or {}
        profile_text = f" · profile `{profile.get('id', 'balanced')}` ({scoring.get('config_source', 'default')})" if profile else ""
        lines += [
            "",
            f"**Criterion scores** ({scoring.get('version', 'scoring@1')}, 0.0–1.0 step 0.1) · "
            f"overall (weighted): **{overall if overall is not None else 'n/a'}**{profile_text} · "
            f"scored {scoring.get('scored_count', 0)}/{len(criteria)} in parallel over one bundle",
            "",
            "| # | Criterion | Weight | Score | Status | Measured |",
            "|---|---|---|---|---|---|",
        ]
        for index, criterion in enumerate(criteria, start=1):
            score = criterion["score"] if criterion["score"] is not None else "—"
            measured = ", ".join(
                f"{k}={v}" for k, v in (criterion.get("measured") or {}).items() if v is not None
            ) or "—"
            lines.append(
                f"| {index} | `{criterion['id']}` | {criterion.get('weight', 1.0)} | {score} | {criterion['status']} | {measured} |"
            )
        not_run = scoring.get("not_run") or []
        if not_run:
            lines += ["", "Not run (evidence missing, never scored 0): " + ", ".join(f"`{c}`" for c in not_run)]
    triggered = [r for r in pack["predicates"] if r["status"] == "triggered"]
    if triggered:
        lines += ["", "**Evidence**"]
        for result in triggered:
            for item in result["evidence"][:10]:
                lines.append(f"- `{result['type']}`: `{item}`")
    warnings = (pack.get("coverage") or {}).get("warnings") or []
    if warnings:
        lines += ["", "**Coverage warnings**"] + [f"- {warning}" for warning in warnings]
    lines += [
        "",
        f"Evidence pack `{pack['id']}` · evidence_hash `{pack['hashes']['evidence_hash'][:16]}…` · "
        f"decision_record_hash `{pack['hashes']['decision_record_hash'][:16]}…`",
        "Rendered from the evidence pack JSON by template. Verdict produced by the deterministic engine; no LLM participated.",
    ]
    return "\n".join(lines) + "\n"

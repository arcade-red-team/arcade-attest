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

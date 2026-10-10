// Render a PR comment from an evidence pack. Template only — no generated prose.
const ICONS = { PASS: "✅", WARN: "⚠️", BLOCK: "🛑" };

export function renderComment(pack) {
  const lines = [
    `## ${ICONS[pack.verdict] ?? ""} ArcadeAttest verdict: **${pack.verdict}**`,
    "",
    `Decision \`${pack.decision_id}\` v${pack.record_version} · repo \`${pack.repo ?? "n/a"}\` · mode \`${pack.mode}\`${pack.enforced ? "" : " (advisory — not enforced)"}`,
    "",
    "| Predicate | Severity | Status | Measured | Threshold |",
    "|---|---|---|---|---|",
  ];
  for (const r of pack.predicates) {
    const threshold = Object.entries(r.threshold).map(([k, v]) => `${k}=${v}`).join(", ");
    lines.push(`| \`${r.type}\` | ${r.severity} | ${r.status} | ${r.measured} | ${threshold} |`);
  }
  const criteria = pack.criteria ?? [];
  if (criteria.length) {
    const scoring = pack.scoring ?? {};
    const profile = scoring.profile ?? {};
    const profileText = profile.id ? ` · profile \`${profile.id}\` (${scoring.config_source ?? "default"})` : "";
    lines.push(
      "",
      `**Criterion scores** (${scoring.version ?? "scoring@1"}, 0.0–1.0 step 0.1) · overall (weighted): **${pack.overall_score ?? "n/a"}**${profileText} · scored ${scoring.scored_count ?? 0}/${criteria.length} in parallel over one bundle`,
      "",
      "| # | Criterion | Weight | Score | Status | Measured |",
      "|---|---|---|---|---|---|",
    );
    criteria.forEach((c, i) => {
      const measured = Object.entries(c.measured ?? {}).filter(([, v]) => v !== null).map(([k, v]) => `${k}=${v}`).join(", ") || "—";
      lines.push(`| ${i + 1} | \`${c.id}\` | ${c.weight ?? 1} | ${c.score ?? "—"} | ${c.status} | ${measured} |`);
    });
    if (scoring.not_run?.length) {
      lines.push("", `Not run (evidence missing, never scored 0): ${scoring.not_run.map((c) => `\`${c}\``).join(", ")}`);
    }
  }
  const triggered = pack.predicates.filter((r) => r.status === "triggered");
  if (triggered.length) {
    lines.push("", "**Evidence**");
    for (const r of triggered) {
      for (const item of r.evidence.slice(0, 10)) lines.push(`- \`${r.type}\`: \`${JSON.stringify(item)}\``);
    }
  }
  const warnings = pack.coverage?.warnings ?? [];
  if (warnings.length) lines.push("", "**Coverage warnings**", ...warnings.map((w) => `- ${w}`));
  lines.push(
    "",
    `Evidence pack \`${pack.id}\` · evidence_hash \`${pack.hashes.evidence_hash.slice(0, 16)}…\` · decision_record_hash \`${pack.hashes.decision_record_hash.slice(0, 16)}…\``,
    "Rendered from the evidence pack JSON by template. Verdict produced by the deterministic engine; no LLM participated.",
  );
  return `${lines.join("\n")}\n`;
}

// Decision engine — Cloudflare Workers port of src/arcade_attest/engine.py.
//
// Pure and deterministic: same record + same data + same evaluated_at gives
// the same verdict and the same JS-canonical evidence_hash on every run.
// SHA-256 is async (Web Crypto), so evaluate() is async; nothing else does
// I/O. Semantic parity with Python (verdict, predicates, criterion scores,
// overall) is pinned by test/golden.json.
import {
  SCORING_VERSION, buildBundle, overallScore, resolveWeights, scoreAll, validateScoringConfig,
} from "./scoring.js";

export const VERDICT_CODES = { PASS: 0, WARN: 1, BLOCK: 2 };
const SUPPORTED_PREDICATES = ["no_new_smells", "max_responsibility_shifts", "component_entity_cap"];
const SEVERITIES = ["fail", "warn"];

export const HONEST_GAPS = [
  "No edge-level diff yet: deny_dependency predicates are not evaluated in this MVP.",
  "Parser blind spots exist (for example files that declare no entities): a component can look empty and a verdict can be a false PASS. Coverage is reported in every evidence pack.",
  "Predicate thresholds are starting guesses; they need per-repo history to calibrate.",
  "An on-chain attestation proves the integrity and timestamp of a verdict, not that the verdict is objectively correct.",
  "Criterion scores (scoring@1) are advisory: 0.5 on a trend criterion means 'no measured change', and a criterion without evidence is reported not_run instead of being scored.",
  "The Cloudflare surface evaluates changelog data produced by arcade-agent elsewhere (CI, local, GitHub Action); it does not parse source trees on the edge, because arcade-agent's native dependencies do not run in Workers isolates.",
];

export function canonicalJson(payload) {
  if (payload === null || typeof payload !== "object") return JSON.stringify(payload) ?? "null";
  if (Array.isArray(payload)) return `[${payload.map(canonicalJson).join(",")}]`;
  const keys = Object.keys(payload).sort();
  return `{${keys.map((k) => `${JSON.stringify(k)}:${canonicalJson(payload[k])}`).join(",")}}`;
}

export async function sha256Hex(payload) {
  const bytes = typeof payload === "string" ? new TextEncoder().encode(payload) : new TextEncoder().encode(canonicalJson(payload));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// Port of adapter.normalize_changelog: arcade-agent changelog -> engine input.
export function normalizeChangelog(changelog = {}) {
  const cl = changelog?.changelog ?? changelog ?? {};
  const smells = cl.smells ?? {};
  const summary = cl.summary ?? {};
  let sizes;
  let componentSizesKnown = false;
  if (Array.isArray(cl.components) && cl.components.length && typeof cl.components[0] === "object" && "entities" in cl.components[0]) {
    sizes = cl.components.map((c) => ({ name: String(c.name ?? c.id ?? "component"), entities: Number(c.entities ?? 0) }));
    componentSizesKnown = true;
  } else {
    const names = new Set();
    for (const key of ["added", "removed", "renamed", "split", "merged", "rewritten", "stable"]) {
      for (const item of cl.components?.[key] ?? []) {
        if (item && typeof item === "object") names.add(String(item.name ?? item.to ?? item.id ?? "component"));
        else if (item) names.add(String(item));
      }
    }
    sizes = [...names].sort().map((name) => ({ name, entities: 0 }));
  }
  return {
    smells_new: smells.new ?? cl.smells_new ?? [],
    responsibility_shifts: cl.responsibility_shifts ?? [],
    components: sizes,
    summary,
    metrics: cl.metrics ?? {},
    coverage: {
      languages_a: cl.languages?.a ?? cl.coverage?.languages_a ?? [],
      languages_b: cl.languages?.b ?? cl.coverage?.languages_b ?? [],
      entities_a: summary.entities_a ?? cl.coverage?.entities_a ?? null,
      entities_b: summary.entities_b ?? cl.coverage?.entities_b ?? null,
      component_sizes_known: cl.coverage?.component_sizes_known ?? componentSizesKnown,
      warnings: cl.coverage?.warnings ?? [],
    },
    refs: cl.refs ?? {},
    changes: cl.changes ?? null,
    architecture_summary: cl.architecture_summary ?? null,
  };
}

// If the caller already sends normalized engine data, pass it through with
// the same defaults the Python adapter would produce.
export function normalizeData(body = {}) {
  if (body.data && typeof body.data === "object") {
    const data = body.data;
    return {
      smells_new: data.smells_new ?? [],
      responsibility_shifts: data.responsibility_shifts ?? [],
      components: data.components ?? [],
      summary: data.summary ?? {},
      metrics: data.metrics ?? {},
      coverage: data.coverage ?? {},
      refs: data.refs ?? {},
      changes: data.changes ?? null,
      architecture_summary: data.architecture_summary ?? null,
    };
  }
  return normalizeChangelog(body.changelog ?? {});
}

export function validateRecord(record) {
  if (!record || typeof record !== "object" || Array.isArray(record)) throw new Error("Decision Record must be a JSON object");
  if (!record.id) throw new Error("Decision Record requires an 'id'");
  const predicates = record.predicates;
  if (!Array.isArray(predicates) || !predicates.length) throw new Error("Decision Record requires a non-empty 'predicates' list");
  for (const pred of predicates) {
    if (!SUPPORTED_PREDICATES.includes(pred.type)) {
      throw new Error(`Unsupported predicate type: ${JSON.stringify(pred.type)} (supported: ${SUPPORTED_PREDICATES.join(", ")})`);
    }
    if (!SEVERITIES.includes(pred.severity ?? "fail")) throw new Error(`Predicate ${pred.type}: severity must be one of ${SEVERITIES.join(", ")}`);
    if (["max_responsibility_shifts", "component_entity_cap"].includes(pred.type)) {
      const limit = pred.params?.max;
      if (typeof limit !== "number" || limit < 0) throw new Error(`Predicate ${pred.type}: params.max must be a non-negative number`);
    }
  }
  validateScoringConfig(record.scoring);
}

const smellKind = (s) => String(s.smell_type ?? s.type ?? s.kind ?? "unknown");

function evaluatePredicate(pred, data) {
  const params = pred.params ?? {};
  const severity = pred.severity ?? "fail";
  if (pred.type === "no_new_smells") {
    const kinds = params.kinds;
    const items = (data.smells_new ?? []).filter((s) => !kinds || kinds.includes(smellKind(s)));
    return {
      type: pred.type, severity, status: items.length > 0 ? "triggered" : "pass",
      measured: items.length, threshold: { kinds: kinds ?? "any", allowed: 0 },
      evidence: items.map((s) => ({ kind: smellKind(s), components: s.affected_components ?? s.components ?? [] })),
    };
  }
  if (pred.type === "max_responsibility_shifts") {
    const shifts = data.responsibility_shifts ?? [];
    return {
      type: pred.type, severity, status: shifts.length > params.max ? "triggered" : "pass",
      measured: shifts.length, threshold: { max: params.max }, evidence: shifts,
    };
  }
  const components = data.components ?? [];
  const scoped = components.filter((c) => !params.component || c.name === params.component);
  const offenders = scoped.filter((c) => Number(c.entities ?? 0) > params.max);
  return {
    type: pred.type, severity, status: offenders.length ? "triggered" : "pass",
    measured: scoped.reduce((max, c) => Math.max(max, Number(c.entities ?? 0)), 0),
    threshold: { max: params.max, component: params.component ?? "any" },
    evidence: offenders.map((c) => ({ component: c.name, entities: Number(c.entities ?? 0) })),
  };
}

export async function evaluate(record, data, { evaluatedAt, expiresAt = null } = {}) {
  validateRecord(record);
  const results = record.predicates.map((pred) => evaluatePredicate(pred, data));
  let verdict = "PASS";
  for (const r of results) {
    if (r.status !== "triggered") continue;
    const candidate = r.severity === "fail" ? "BLOCK" : "WARN";
    if (VERDICT_CODES[candidate] > VERDICT_CODES[verdict]) verdict = candidate;
  }
  const components = data.components ?? [];
  const largest = components.reduce((best, c) => (!best || (c.entities ?? 0) > (best.entities ?? 0) ? c : best), null);
  const coverage = { ...(data.coverage ?? {}) };
  const warnings = [...(coverage.warnings ?? [])];
  if (coverage.entities_b === 0) warnings.push("Head analysis produced 0 entities: possible parser blind spot, verdict may be a false PASS.");
  if (coverage.component_sizes_known === false) warnings.push("Component entity counts are unknown (changelog-only input): component_entity_cap cannot trigger on this input.");
  const mode = record.mode ?? "advisory";
  const bundle = buildBundle(data);
  const resolved = resolveWeights(record);
  const criteria = scoreAll(bundle, resolved.weights);
  const scored = criteria.filter((c) => c.status === "scored");
  const scoredPositive = scored.filter((c) => resolved.weights[c.id] > 0);
  const scoredWeight = scoredPositive.reduce((sum, c) => sum + resolved.weights[c.id], 0);
  const effectiveWeights = scoredWeight > 0
    ? Object.fromEntries(scoredPositive.map((c) => [c.id, Math.round((resolved.weights[c.id] / scoredWeight) * 10000) / 10000]))
    : {};
  const pack = {
    schema: "arcade-attest/evidence@1",
    decision_id: record.id,
    record_version: record.version ?? 1,
    repo: record.repo ?? null,
    mode,
    enforced: mode === "blocking",
    refs: data.refs ?? {},
    evaluated_at: evaluatedAt,
    expires_at: expiresAt,
    verdict,
    verdict_code: VERDICT_CODES[verdict],
    predicates: results,
    measured: {
      smells_new: (data.smells_new ?? []).length,
      responsibility_shifts: (data.responsibility_shifts ?? []).length,
      largest_component: largest ? { name: largest.name, entities: Number(largest.entities ?? 0) } : null,
    },
    summary: data.summary ?? {},
    architecture_summary: bundle.architecture_summary.derived,
    criteria,
    overall_score: overallScore(criteria, resolved.weights),
    scoring: {
      version: SCORING_VERSION,
      scale: "0.0-1.0 step 0.1",
      parallel_scorers: criteria.length,
      scored_count: scored.length,
      not_run: criteria.filter((c) => c.status !== "scored").map((c) => c.id),
      scoring_input_hash: await sha256Hex(bundle),
      changes_source: bundle.changes.source,
      profile: resolved.profile,
      config_source: resolved.source,
      suggestion_rule: resolved.suggestion_rule,
      weights: resolved.weights,
      normalized_weights: resolved.normalized_weights,
      effective_weights: effectiveWeights,
      llm_in_scoring: false,
    },
    coverage: { ...coverage, warnings },
    engine: {
      name: "arcade-attest",
      version: "0.1.0",
      analyzer: "arcade-agent changelog_architecture (PKG recovery)",
      runtime: "cloudflare-workers",
      llm_in_verdict: false,
    },
    honest_gaps: HONEST_GAPS,
    hashes: { decision_record_hash: await sha256Hex(record) },
  };
  pack.hashes.evidence_hash = await sha256Hex(pack);
  pack.id = `att_${pack.hashes.evidence_hash.slice(0, 16)}`;
  return pack;
}

const EAS_SCHEMA = "string repo,bytes32 baseCommit,bytes32 headCommit,bytes32 decisionRecordHash,uint8 verdict,int32 smellsDelta,uint32 responsibilityShifts,bytes32 evidenceHash,uint64 evaluatedAt,uint64 expiresAt";

function bytes32(value = "") {
  const digest = String(value ?? "").replace(/^0x/, "");
  return `0x${digest.padEnd(64, "0").slice(0, 64)}`;
}

export function buildAttestationPayload(pack, { baseCommit = "", headCommit = "" } = {}) {
  const summary = pack.summary ?? {};
  return {
    schema: EAS_SCHEMA,
    network: "base-sepolia",
    data: {
      repo: pack.repo ?? "",
      baseCommit: bytes32(baseCommit),
      headCommit: bytes32(headCommit),
      decisionRecordHash: bytes32(pack.hashes.decision_record_hash),
      verdict: pack.verdict_code,
      smellsDelta: Number(summary.smells_new ?? pack.measured.smells_new) - Number(summary.smells_resolved ?? 0),
      responsibilityShifts: pack.measured.responsibility_shifts,
      evidenceHash: bytes32(pack.hashes.evidence_hash),
      evaluatedAt: pack.evaluated_at,
      expiresAt: pack.expires_at ?? null,
    },
    status: "not_submitted",
    note: "Payload builder only; EAS submission is D3-D4 scope.",
  };
}

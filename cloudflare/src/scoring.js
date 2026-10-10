// Ten-criterion PR scoring (scoring@1) — Cloudflare Workers port.
//
// Semantic parity with src/arcade_attest/scoring.py is enforced by
// test/golden.json (generated from the Python engine). Same rule as Python:
// missing evidence -> status "not_run", score null, never a fabricated 0.
// Scores are advisory; the predicate verdict never moves with weights.

export const SCORING_VERSION = "scoring@1";

export const CRITERION_IDS = [
  "smell_regression",
  "responsibility_stability",
  "god_component_risk",
  "component_balance",
  "modularity_trend",
  "cohesion_trend",
  "coupling_control",
  "recovery_confidence_trend",
  "change_containment",
  "evidence_confidence",
];

const SEVERITY_WEIGHT = { low: 1, medium: 2, high: 3, critical: 4 };

const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);
const clamp01 = (v) => Math.max(0, Math.min(1, v));
export const quantize = (raw) => Math.floor(clamp01(raw) * 10 + 0.5) / 10;
const round4 = (v) => Math.round(v * 10000) / 10000;

function result(id, formula, measured, evidence, raw) {
  if (raw === null || raw === undefined) {
    return { id, score: null, status: "not_run", measured, evidence, formula };
  }
  return { id, score: quantize(raw), status: "scored", measured, evidence, formula };
}

export function buildBundle(data = {}) {
  const summary = data.summary ?? {};
  const metrics = data.metrics ?? {};
  const components = Array.isArray(data.components) ? data.components : [];
  const total = components.reduce((sum, c) => sum + (Number.isInteger(c?.entities) ? c.entities : 0), 0);
  const largest = components.reduce((best, c) => (!best || (c?.entities ?? 0) > (best.entities ?? 0) ? c : best), null);
  const suppliedChanges = data.changes && typeof data.changes === "object" ? data.changes : null;
  const changes = {
    source: suppliedChanges ? "supplied" : "derived_from_summary",
    entities_added: suppliedChanges?.entities_added ?? summary.entities_added ?? null,
    entities_deleted: suppliedChanges?.entities_deleted ?? summary.entities_deleted ?? null,
    files_changed: suppliedChanges?.files_changed ?? null,
    lines_added: suppliedChanges?.lines_added ?? null,
    lines_deleted: suppliedChanges?.lines_deleted ?? null,
  };
  if (suppliedChanges && "raw" in suppliedChanges) changes.raw = suppliedChanges.raw;
  return {
    changes,
    architecture_summary: {
      source: data.architecture_summary != null ? "supplied" : "derived",
      derived: {
        components_b: summary.components_b ?? components.length,
        entities_a: summary.entities_a ?? null,
        entities_b: summary.entities_b ?? null,
        total_component_entities: total,
        largest_component: largest ? { name: largest.name, entities: largest.entities } : null,
        metrics_b: Object.fromEntries(Object.entries(metrics).map(([k, v]) => [k, v?.b ?? null])),
        languages_b: data.coverage?.languages_b ?? [],
      },
      supplied: data.architecture_summary ?? null,
    },
    changelog: {
      smells_new: data.smells_new ?? [],
      responsibility_shifts: data.responsibility_shifts ?? [],
      components,
      summary,
      metrics,
      coverage: data.coverage ?? {},
    },
  };
}

function componentShares(bundle) {
  const { changelog } = bundle;
  if (changelog.coverage.component_sizes_known === false) return null;
  const components = changelog.components.filter((c) => c && typeof c === "object");
  const total = components.reduce((sum, c) => sum + (c.entities ?? 0), 0);
  if (!components.length || total <= 0) return null;
  return { components, total };
}

function metricDelta(bundle, name) {
  const metric = bundle.changelog.metrics?.[name];
  return metric && typeof metric === "object" ? num(metric.delta) : null;
}

const SCORERS = {
  smell_regression(bundle) {
    const evidence = [];
    let weighted = 0;
    for (const smell of bundle.changelog.smells_new) {
      if (!smell || typeof smell !== "object") continue;
      const weight = SEVERITY_WEIGHT[String(smell.severity ?? "").toLowerCase()] ?? 1;
      weighted += weight;
      evidence.push({
        kind: smell.smell_type ?? smell.type ?? smell.kind ?? "unknown",
        severity: smell.severity ?? null,
        weight,
        components: smell.affected_components ?? smell.components ?? [],
      });
    }
    return result("smell_regression", "scoring@1:smell_regression:raw=clamp(1-0.2*weighted_smells)",
      { new_smells: evidence.length, weighted_smells: weighted }, evidence, 1 - 0.2 * weighted);
  },

  responsibility_stability(bundle) {
    const { changelog } = bundle;
    const shifts = changelog.responsibility_shifts;
    const entitiesB = num(changelog.summary.entities_b) ?? num(changelog.coverage.entities_b);
    const formula = "scoring@1:responsibility_stability:raw=clamp(1-5*(shifts/max(1,entities_b)))";
    if (entitiesB === null) {
      return result("responsibility_stability", formula,
        { responsibility_shifts: shifts.length, entities_b: null },
        [{ reason: "entities_b missing: shift rate cannot be computed" }], null);
    }
    const shiftRate = shifts.length / Math.max(1, entitiesB);
    return result("responsibility_stability", formula,
      { responsibility_shifts: shifts.length, entities_b: entitiesB, shift_rate: round4(shiftRate) },
      shifts.slice(0, 10), 1 - 5 * shiftRate);
  },

  god_component_risk(bundle) {
    const formula = "scoring@1:god_component_risk:raw=clamp(1-largest_share)";
    const shares = componentShares(bundle);
    if (!shares) return result("god_component_risk", formula, {}, [{ reason: "component sizes unknown or empty" }], null);
    const largest = shares.components.reduce((a, b) => ((b.entities ?? 0) > (a.entities ?? 0) ? b : a));
    const share = (largest.entities ?? 0) / shares.total;
    return result("god_component_risk", formula,
      { largest_component: largest.name, largest_entities: largest.entities, largest_share: round4(share) },
      [{ component: largest.name, entities: largest.entities }], 1 - share);
  },

  component_balance(bundle) {
    const formula = "scoring@1:component_balance:raw=clamp(1-(HHI-1/n)/(1-1/n))";
    const shares = componentShares(bundle);
    if (!shares) return result("component_balance", formula, {}, [{ reason: "component sizes unknown or empty" }], null);
    const n = shares.components.length;
    if (n < 2) {
      return result("component_balance", formula, { components: n },
        [{ reason: "fewer than 2 components: balance is undefined" }], null);
    }
    const hhi = shares.components.reduce((sum, c) => sum + ((c.entities ?? 0) / shares.total) ** 2, 0);
    return result("component_balance", formula, { components: n, hhi: round4(hhi) },
      shares.components.map((c) => ({ component: c.name, entities: c.entities })),
      1 - (hhi - 1 / n) / (1 - 1 / n));
  },

  modularity_trend(bundle) {
    const formula = "scoring@1:modularity_trend:raw=clamp(0.5+clamp(TurboMQ.delta,-0.5,0.5))";
    const delta = metricDelta(bundle, "TurboMQ");
    if (delta === null) {
      return result("modularity_trend", formula, { metric: "TurboMQ", delta: null },
        [{ reason: "metric TurboMQ missing from changelog" }], null);
    }
    const m = bundle.changelog.metrics.TurboMQ;
    return result("modularity_trend", formula, { metric: "TurboMQ", a: m.a ?? null, b: m.b ?? null, delta },
      [{ metric: "TurboMQ", a: m.a ?? null, b: m.b ?? null, delta }],
      0.5 + Math.max(-0.5, Math.min(0.5, delta)));
  },

  cohesion_trend(bundle) {
    return trend("cohesion_trend", "IntraConnectivity", 2.5, bundle);
  },

  coupling_control(bundle) {
    const formula = "scoring@1:coupling_control:raw=clamp(0.5-2.5*InterConnectivity.delta-1.0*TwoWayPairRatio.delta)";
    const inter = metricDelta(bundle, "InterConnectivity");
    if (inter === null) {
      return result("coupling_control", formula, { metric: "InterConnectivity", delta: null },
        [{ reason: "metric InterConnectivity missing from changelog" }], null);
    }
    const twoway = metricDelta(bundle, "TwoWayPairRatio") ?? 0;
    return result("coupling_control", formula, { inter_delta: inter, twoway_delta: twoway },
      [{ metric: "InterConnectivity", delta: inter }, { metric: "TwoWayPairRatio", delta: twoway }],
      0.5 - 2.5 * inter - twoway);
  },

  recovery_confidence_trend(bundle) {
    return trend("recovery_confidence_trend", "RCI", 2.5, bundle);
  },

  change_containment(bundle) {
    const formula = "scoring@1:change_containment:raw=clamp(1-0.5*((added+deleted)/max(1,entities_a)))";
    const added = num(bundle.changes.entities_added);
    const deleted = num(bundle.changes.entities_deleted);
    const entitiesA = num(bundle.changelog.summary.entities_a);
    if (added === null || deleted === null || entitiesA === null) {
      return result("change_containment", formula,
        { entities_added: added, entities_deleted: deleted, entities_a: entitiesA },
        [{ reason: "entities_added/entities_deleted/entities_a missing: churn cannot be computed" }], null);
    }
    const churn = (added + deleted) / Math.max(1, entitiesA);
    return result("change_containment", formula,
      { entities_added: added, entities_deleted: deleted, entities_a: entitiesA, churn_rate: round4(churn) },
      [{ entities_added: added, entities_deleted: deleted, entities_a: entitiesA }], 1 - 0.5 * churn);
  },

  evidence_confidence(bundle) {
    const formula = "scoring@1:evidence_confidence:raw=clamp(1-penalties)";
    const coverage = bundle.changelog.coverage;
    const entitiesB = num(coverage.entities_b) ?? num(bundle.changelog.summary.entities_b);
    if (entitiesB === null) {
      return result("evidence_confidence", formula, { entities_b: null },
        [{ reason: "coverage entities_b missing: measurement confidence cannot be scored" }], null);
    }
    const penalties = [];
    let raw = 1;
    if (entitiesB === 0) { raw = 0; penalties.push({ penalty: "entities_b_zero", value: -1 }); }
    if (coverage.component_sizes_known === false) { raw -= 0.3; penalties.push({ penalty: "component_sizes_unknown", value: -0.3 }); }
    const warnings = coverage.warnings ?? [];
    if (warnings.length) {
      const deduction = Math.min(0.3, 0.1 * warnings.length);
      raw -= deduction;
      penalties.push({ penalty: "coverage_warnings", count: warnings.length, value: -deduction });
    }
    if (!coverage.languages_b?.length) { raw -= 0.2; penalties.push({ penalty: "languages_b_empty", value: -0.2 }); }
    return result("evidence_confidence", formula, { entities_b: entitiesB, warnings: warnings.length }, penalties, raw);
  },
};

function trend(id, metric, factor, bundle) {
  const formula = `scoring@1:${id}:raw=clamp(0.5+${factor}*${metric}.delta)`;
  const delta = metricDelta(bundle, metric);
  if (delta === null) {
    return result(id, formula, { metric, delta: null }, [{ reason: `metric ${metric} missing from changelog` }], null);
  }
  const m = bundle.changelog.metrics[metric];
  return result(id, formula, { metric, a: m.a ?? null, b: m.b ?? null, delta },
    [{ metric, a: m.a ?? null, b: m.b ?? null, delta }], 0.5 + factor * delta);
}

export function scoreAll(bundle, weights = {}) {
  return CRITERION_IDS.map((id) => {
    const scored = SCORERS[id](structuredClone(bundle));
    const weight = Number(weights[id] ?? 1);
    scored.weight = weight;
    scored.weighted_score = scored.score === null ? null : Math.round(scored.score * weight * 10000) / 10000;
    return scored;
  });
}

export function overallScore(criteria, weights = {}) {
  let sum = 0;
  let totalWeight = 0;
  for (const criterion of criteria) {
    if (criterion.status !== "scored" || criterion.score === null) continue;
    const weight = Number(weights[criterion.id] ?? criterion.weight ?? 1);
    if (weight <= 0) continue;
    sum += criterion.score * weight;
    totalWeight += weight;
  }
  return totalWeight > 0 ? quantize(sum / totalWeight) : null;
}

// --- Admin weight profiles (template/appetite skills) ----------------------
// Mirrors SCORING_PROFILES in the Python engine and skills/scoring/*.json.

function weightsWith(overrides) {
  return Object.fromEntries(CRITERION_IDS.map((id) => [id, overrides[id] ?? 1]));
}

export const SCORING_PROFILES = [
  {
    id: "balanced", name: "Balanced (default)", appetite: "balanced",
    description: "Every criterion counts equally. Default when an admin configures nothing.",
    apply_when: { signals: ["no special signal", "first rollout", "baseline reporting"] },
    weights: weightsWith({}),
  },
  {
    id: "strict_gate", name: "Strict Gate", appetite: "risk_averse",
    description: "Blocking/architecture-board gates: smells, god components, coupling and evidence confidence dominate.",
    apply_when: { mode: ["blocking"], signals: ["architecture board", "regulated", "high risk"] },
    weights: weightsWith({ smell_regression: 3, responsibility_stability: 2, god_component_risk: 3, component_balance: 1.5, modularity_trend: 1.5, coupling_control: 2.5, change_containment: 1.5, evidence_confidence: 2 }),
  },
  {
    id: "ship_fast", name: "Ship Fast", appetite: "speed",
    description: "Small-team/startup flow: containment and responsibility stability dominate; trend criteria still report but weigh less.",
    apply_when: { signals: ["ship-fast", "startup", "mvp", "small team"] },
    weights: weightsWith({ smell_regression: 1.5, responsibility_stability: 2, component_balance: 0.5, cohesion_trend: 0.5, coupling_control: 1, recovery_confidence_trend: 0.5, change_containment: 3, evidence_confidence: 1.5 }),
  },
  {
    id: "refactor_friendly", name: "Refactor Friendly", appetite: "refactor_tolerant",
    description: "Migrations and refactors: modularity/cohesion/RCI/balance dominate; shifts and churn are expected, so they weigh less.",
    apply_when: { signals: ["refactor", "migration", "modernization"] },
    weights: weightsWith({ smell_regression: 1.5, responsibility_stability: 0.5, god_component_risk: 2, component_balance: 2, modularity_trend: 3, cohesion_trend: 2.5, coupling_control: 2, recovery_confidence_trend: 2.5, change_containment: 0.5, evidence_confidence: 1.5 }),
  },
  {
    id: "ai_agent_code_gate", name: "AI Agent Code Gate", appetite: "agent_risk_averse",
    description: "Code produced by AI agents: smells, god components, coupling, containment and evidence confidence dominate.",
    apply_when: { signals: ["ai-agent", "agent-code", "ai-generated"] },
    weights: weightsWith({ smell_regression: 3, responsibility_stability: 2, god_component_risk: 3, component_balance: 1.5, modularity_trend: 1.5, coupling_control: 3, change_containment: 2.5, evidence_confidence: 2.5 }),
  },
  {
    id: "oss_maintainer", name: "OSS Maintainer Triage", appetite: "maintainer_triage",
    description: "High-volume PR triage: evidence confidence, smells, stability and containment decide what needs a human first.",
    apply_when: { signals: ["oss", "maintainer", "review-triage", "high-volume pr"] },
    weights: weightsWith({ smell_regression: 2.5, responsibility_stability: 2, god_component_risk: 1.5, cohesion_trend: 0.75, recovery_confidence_trend: 0.75, change_containment: 2.5, evidence_confidence: 3 }),
  },
];

const PROFILE_BY_ID = Object.fromEntries(SCORING_PROFILES.map((p) => [p.id, p]));

export function listProfiles() {
  return structuredClone(SCORING_PROFILES);
}

export function validateScoringConfig(config) {
  if (config == null) return;
  if (typeof config !== "object" || Array.isArray(config)) throw new Error("Decision Record 'scoring' must be a JSON object");
  for (const key of Object.keys(config)) {
    if (!["profile", "weights", "context"].includes(key)) throw new Error(`Decision Record 'scoring' has unsupported keys: ${key}`);
  }
  if (config.profile != null && config.profile !== "auto" && !PROFILE_BY_ID[config.profile]) {
    throw new Error(`Unsupported scoring profile: ${JSON.stringify(config.profile)} (supported: ${Object.keys(PROFILE_BY_ID).join(", ")}, auto)`);
  }
  if (config.weights != null) {
    const entries = Object.entries(config.weights);
    if (!entries.length) throw new Error("Decision Record 'scoring.weights' must be a non-empty JSON object");
    for (const [id, value] of entries) {
      if (!CRITERION_IDS.includes(id)) throw new Error(`Unknown criterion in scoring.weights: ${id}`);
      if (typeof value !== "number" || value < 0) throw new Error(`scoring.weights.${id} must be a non-negative number`);
    }
    if (entries.every(([, v]) => v === 0)) throw new Error("scoring.weights must not set every criterion weight to 0");
  }
  if (config.context != null) {
    if (typeof config.context !== "object" || Array.isArray(config.context)) throw new Error("Decision Record 'scoring.context' must be a JSON object");
    const tags = config.context.tags;
    if (tags != null && (!Array.isArray(tags) || tags.some((t) => typeof t !== "string"))) {
      throw new Error("Decision Record 'scoring.context.tags' must be a list of strings");
    }
  }
}

export function suggestProfile(context = {}, mode = null) {
  const signals = new Set([...(context.tags ?? []).map((t) => String(t).toLowerCase()),
    String(context.purpose ?? "").toLowerCase(), String(context.change_kind ?? "").toLowerCase()]);
  const has = (...names) => names.some((n) => signals.has(n));
  if (has("ai-agent", "agent-code", "ai-generated")) return ["ai_agent_code_gate", "signal:ai-agent-code"];
  if (has("refactor", "migration", "modernization")) return ["refactor_friendly", "signal:refactor-or-migration"];
  if (has("oss", "maintainer", "review-triage", "high-volume pr")) return ["oss_maintainer", "signal:oss-maintainer-triage"];
  if (has("ship-fast", "startup", "mvp", "small team")) return ["ship_fast", "signal:ship-fast"];
  if (mode === "blocking" || has("regulated", "architecture board", "high risk")) return ["strict_gate", "signal:blocking-or-high-risk"];
  return ["balanced", "default:balanced"];
}

export function resolveWeights(record) {
  const config = record.scoring ?? {};
  validateScoringConfig(config);
  let suggestionRule = null;
  let profileId = config.profile;
  let source;
  if (profileId === "auto") {
    [profileId, suggestionRule] = suggestProfile(config.context ?? {}, record.mode ?? null);
    source = "auto_suggested";
  } else if (profileId) {
    source = "preset";
  } else {
    profileId = "balanced";
    source = "default";
  }
  const profile = PROFILE_BY_ID[profileId];
  const resolved = { ...profile.weights };
  for (const [id, value] of Object.entries(config.weights ?? {})) resolved[id] = Number(value);
  if (config.weights && Object.keys(config.weights).length) source += "+custom_weights";
  const total = Object.values(resolved).reduce((a, b) => a + b, 0);
  if (total <= 0) throw new Error("Resolved scoring weights sum to 0: at least one criterion needs a positive weight");
  return {
    profile: { id: profile.id, name: profile.name, appetite: profile.appetite, skill: `skills/scoring/${profile.id}.json` },
    source,
    suggestion_rule: suggestionRule,
    weights: resolved,
    normalized_weights: Object.fromEntries(Object.entries(resolved).map(([k, v]) => [k, round4(v / total)])),
  };
}

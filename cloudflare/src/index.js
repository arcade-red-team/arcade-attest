// ArcadeAttest Decision API — Cloudflare Workers surface.
//
// Mirrors the FastAPI contract (src/arcade_attest/api.py) where the edge can:
//   GET  /health
//   GET  /v1/scoring/profiles
//   POST /v1/decisions:evaluate          {decision_record, changelog|data, evaluated_at?}
//   GET  /v1/decisions/{id}
//   GET  /v1/decisions/{id}/comment
//   GET  /v1/decisions/{id}/attestation-payload
//   GET  /v1/repos/{owner}/{repo}/latest-verdict
//
// The Worker evaluates changelog data (produced by arcade-agent in CI/local/
// GitHub Action); it does not parse source trees, because arcade-agent's
// native dependencies do not run in Workers isolates. Evidence packs persist
// in the DECISIONS KV binding when configured; without it, packs live in an
// in-memory map for the lifetime of the isolate (local dev/tests only).
import { buildAttestationPayload, evaluate, normalizeData } from "./engine.js";
import { renderComment } from "./render.js";
import { listProfiles } from "./scoring.js";

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" };

function json(body, status = 200) {
  return new Response(JSON.stringify(body, null, 2), { status, headers: JSON_HEADERS });
}

function notFound(what) {
  return json({ detail: `${what} not found` }, 404);
}

export function createStore(env = {}) {
  const memory = new Map();
  const kv = env.DECISIONS ?? null;
  return {
    async write(pack) {
      if (kv) {
        await kv.put(`decision:${pack.id}`, JSON.stringify(pack));
        if (pack.repo) await kv.put(`latest:${pack.repo}`, pack.id);
      } else {
        memory.set(pack.id, pack);
        if (pack.repo) memory.set(`latest:${pack.repo}`, pack.id);
      }
    },
    async read(id) {
      if (kv) {
        const raw = await kv.get(`decision:${id}`);
        return raw ? JSON.parse(raw) : null;
      }
      return memory.get(id) ?? null;
    },
    async latestForRepo(repo) {
      const id = kv ? await kv.get(`latest:${repo}`) : memory.get(`latest:${repo}`);
      return id ? this.read(id) : null;
    },
  };
}

function authorized(request, env) {
  // Optional admin token: set with `wrangler secret put API_TOKEN`.
  // Unset means open (local/demo); production should set it. PLACEHOLDER.
  if (!env.API_TOKEN) return true;
  return request.headers.get("authorization") === `Bearer ${env.API_TOKEN}`;
}

export async function handleRequest(request, env = {}, store = createStore(env)) {
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/$/, "") || "/";

  if (request.method === "GET" && path === "/health") {
    return json({ ok: true, service: "arcade-attest", runtime: "cloudflare-workers", llm_in_verdict: false });
  }
  if (request.method === "GET" && path === "/v1/scoring/profiles") {
    return json({ version: "scoring@1", default: "balanced", profiles: listProfiles() });
  }

  if (request.method === "POST" && path === "/v1/decisions:evaluate") {
    if (!authorized(request, env)) return json({ detail: "unauthorized" }, 401);
    let body;
    try {
      body = await request.json();
    } catch {
      return json({ detail: "request body must be JSON" }, 422);
    }
    if (body.base_path || body.head_path) {
      return json({
        detail: "The Cloudflare surface evaluates changelog data, not source trees. Run arcade-agent (CI/local/GitHub Action) and POST {decision_record, changelog} or {decision_record, data}.",
      }, 422);
    }
    const record = { ...(body.decision_record ?? {}) };
    if (body.repo && !record.repo) record.repo = body.repo;
    try {
      const data = normalizeData(body);
      const evaluatedAt = body.evaluated_at ?? new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
      const expiresAt = new Date(new Date(evaluatedAt).getTime() + 24 * 3600 * 1000).toISOString().replace(/\.\d{3}Z$/, "Z");
      const pack = await evaluate(record, data, { evaluatedAt, expiresAt });
      await store.write(pack);
      return json(pack);
    } catch (error) {
      return json({ detail: String(error?.message ?? error) }, 422);
    }
  }

  const decisionMatch = path.match(/^\/v1\/decisions\/([^/]+)(\/comment|\/attestation-payload)?$/);
  if (request.method === "GET" && decisionMatch) {
    const pack = await store.read(decisionMatch[1]);
    if (!pack) return notFound("decision");
    if (decisionMatch[2] === "/comment") {
      return new Response(renderComment(pack), { headers: { "content-type": "text/markdown; charset=utf-8" } });
    }
    if (decisionMatch[2] === "/attestation-payload") return json(buildAttestationPayload(pack));
    return json(pack);
  }

  const latestMatch = path.match(/^\/v1\/repos\/([^/]+)\/([^/]+)\/latest-verdict$/);
  if (request.method === "GET" && latestMatch) {
    const pack = await store.latestForRepo(`${latestMatch[1]}/${latestMatch[2]}`);
    return pack ? json(pack) : notFound("no verdict stored for this repo");
  }

  return notFound("route");
}

export default {
  async fetch(request, env) {
    return handleRequest(request, env, createStore(env));
  },
};

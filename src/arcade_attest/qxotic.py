"""Qxotic Jinfer integration: local-LLM explanation drafts for evidence packs.

Qxotic (https://github.com/qxoticai/qxotic) provides Jinfer, a local LLM
inference engine for the JVM. Jinfer serves an OpenAI-compatible HTTP API
on loopback (`jinfer server`), so ArcadeAttest can ask a fully local model
to draft a human-readable explanation of an evidence pack.

Doctrine boundary (non-negotiable): the model drafts prose only. It never
sees a vote, never recomputes a score, and its output is appended to the
PR comment *after* the deterministic verdict. Every evidence pack keeps
`llm_in_verdict: false`; the explanation is labelled a draft in the text
itself so a rendered comment can never be mistaken for the gate.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

QXOTIC_REPO = "https://github.com/qxoticai/qxotic"
JINFER_VERSION = "0.3.1"
DEFAULT_MODEL = "LiquidAI/LFM2.5-350M-GGUF:Q8_0"
DEFAULT_BASE_URL = "http://127.0.0.1:54154"

SYSTEM_PROMPT = (
    "You explain ArcadeAttest evidence packs to pull-request reviewers. "
    "You are a drafting assistant only: the PASS/WARN/BLOCK verdict and all "
    "scores were computed by a deterministic engine and are final. Never "
    "question, restate, or change the verdict. Use only the numbers given "
    "in the pack summary. Be concise: at most 5 short sentences."
)


class QxoticError(RuntimeError):
    """Raised when the local Jinfer endpoint cannot produce an explanation."""


def build_explanation_prompt(pack: dict) -> str:
    """Build the (deterministic) prompt text for a pack.

    Only measured facts are handed to the model: verdict, measured values,
    predicate outcomes, criterion scores, and coverage warnings. The model
    is asked to explain, never to decide.
    """
    measured = pack.get("measured") or {}
    lines = [
        "Explain this ArcadeAttest verdict to a reviewer.",
        f"Decision: {pack.get('decision_id')} on repo {pack.get('repo')}",
        f"Verdict (final, deterministic): {pack.get('verdict')}",
        f"Overall advisory score: {pack.get('overall_score')}",
        (
            "Measured: "
            f"new smells={measured.get('smells_new')}, "
            f"responsibility shifts={measured.get('responsibility_shifts')}, "
            f"largest component={measured.get('largest_component')}"
        ),
        "Predicates:",
    ]
    for pred in pack.get("predicates") or []:
        lines.append(
            f"- {pred.get('type')}: status={pred.get('status')} "
            f"severity={pred.get('severity')} measured={pred.get('measured')}"
        )
    scored = [
        f"{c.get('id')}={c.get('score')}"
        for c in pack.get("criteria") or []
        if c.get("status") == "scored"
    ]
    if scored:
        lines.append("Criterion scores: " + ", ".join(scored))
    not_run = (pack.get("scoring") or {}).get("not_run") or []
    if not_run:
        lines.append("Criteria not run (missing evidence): " + ", ".join(not_run))
    warnings = (pack.get("coverage") or {}).get("warnings") or []
    for warning in warnings:
        lines.append(f"Coverage warning: {warning}")
    lines.append(
        "Write the explanation now. State the verdict once, explain which "
        "measurements drove it, and mention the warnings if any."
    )
    return "\n".join(lines)


def _resolve_model(base_url: str, model: str, *, opener=urllib.request.urlopen) -> str:
    """Resolve the model id the Jinfer server actually serves.

    Jinfer answers 404 when the request names a model it does not serve,
    and the served id depends on how the model was loaded (hub reference
    vs local file). Ask `/v1/models` first: keep the requested model when
    it is served, otherwise fall back to the single served model.
    """
    request = urllib.request.Request(base_url.rstrip("/") + "/v1/models", method="GET")
    try:
        with opener(request, timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))
        ids = [entry.get("id") for entry in body.get("data") or [] if entry.get("id")]
    except Exception:
        return model
    if model in ids:
        return model
    return ids[0] if len(ids) == 1 else model


def explain_pack(
    pack: dict,
    *,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    timeout: float = 120.0,
    max_tokens: int = 220,
    opener=urllib.request.urlopen,
) -> str:
    """Ask the local Jinfer (Qxotic) server to draft an explanation.

    Talks to Jinfer's OpenAI-compatible `/v1/chat/completions` endpoint
    with temperature 0 and a fixed seed so the draft is reproducible for a
    given pack. Any transport or shape problem raises `QxoticError`; the
    caller decides whether that is fatal (it must never change a verdict).
    """
    model = _resolve_model(base_url, model, opener=opener)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_explanation_prompt(pack)},
        ],
        "temperature": 0,
        "seed": 42,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with opener(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise QxoticError(f"Jinfer endpoint unreachable at {base_url}: {exc}") from exc
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise QxoticError(f"Unexpected Jinfer response shape: {body!r:.200}") from exc
    text = (content or "").strip()
    if not text:
        raise QxoticError("Jinfer returned an empty explanation")
    return text


def render_explanation_section(pack: dict, explanation: str, *, model: str = DEFAULT_MODEL) -> str:
    """Render the explanation as a clearly-labelled PR comment section."""
    return (
        "\n\n---\n\n"
        "### Local AI explanation (draft)\n\n"
        f"Drafted locally by Qxotic Jinfer {JINFER_VERSION} "
        f"(`{model}`, [qxoticai/qxotic]({QXOTIC_REPO})) from the evidence "
        "pack above. This text explains the pack for reviewers; it did not "
        "compute or influence the verdict "
        f"(**{pack.get('verdict')}**, `llm_in_verdict: false`).\n\n"
        f"{explanation.strip()}\n"
    )

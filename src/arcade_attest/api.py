"""HTTP API (FastAPI). Mirrors SPEC: POST /v1/decisions:evaluate, GET /v1/decisions/{id}.

Install with: pip install "arcade-attest[api]". Evidence packs persist as JSON
files under ./data/decisions/ (local MVP store).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from . import __version__, store
from .adapter import analyze_pair
from .anchor import build_attestation_payload
from .engine import evaluate
from .scoring import list_profiles

STORE = store.STORE_DIR

app = FastAPI(title="ArcadeAttest Decision API", version=__version__)


class EvaluateRequest(BaseModel):
    repo: str | None = None
    base_path: str
    head_path: str
    language: str = "python"
    decision_record: dict


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@app.get("/health")
def health():
    return {"ok": True, "service": "arcade-attest", "version": __version__, "llm_in_verdict": False}


@app.get("/v1/scoring/profiles")
def scoring_profiles():
    """Admin weight templates (appetite skills) for configuring scoring.

    An admin or agent picks one profile id (or ``auto`` plus context signals)
    and puts it in the Decision Record as ``scoring.profile``; the evaluate
    endpoint resolves, validates and reports the effective weights.
    """
    return {"version": "scoring@1", "default": "balanced", "profiles": list_profiles()}


@app.post("/v1/decisions:evaluate")
def evaluate_decision(request: EvaluateRequest):
    record = dict(request.decision_record)
    if request.repo and not record.get("repo"):
        record["repo"] = request.repo
    try:
        data = analyze_pair(request.base_path, request.head_path, language=request.language)
        evaluated_at = _now()
        expires = (datetime.now(timezone.utc) + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
        pack = evaluate(record, data, evaluated_at=evaluated_at, expires_at=expires)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    store.write_pack(pack)
    return pack


@app.get("/v1/decisions/{decision_uid}")
def get_decision(decision_uid: str):
    pack = store.read_pack(decision_uid)
    if pack is None:
        raise HTTPException(status_code=404, detail="decision not found")
    return pack


@app.get("/v1/decisions/{decision_uid}/attestation-payload")
def get_payload(decision_uid: str):
    pack = get_decision(decision_uid)
    return build_attestation_payload(pack)


@app.get("/v1/repos/{owner}/{repo}/latest-verdict")
def latest_verdict(owner: str, repo: str):
    pack = store.latest_for_repo(f"{owner}/{repo}")
    if pack is None:
        raise HTTPException(status_code=404, detail="no verdict stored for this repo")
    return pack

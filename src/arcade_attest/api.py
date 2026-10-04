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

from .adapter import analyze_pair
from .anchor import build_attestation_payload
from .engine import evaluate

STORE = Path("data/decisions")

app = FastAPI(title="ArcadeAttest Decision API", version="0.1.0")


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
    return {"ok": True, "service": "arcade-attest", "llm_in_verdict": False}


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
    STORE.mkdir(parents=True, exist_ok=True)
    (STORE / f"{pack['id']}.json").write_text(json.dumps(pack, indent=2), encoding="utf-8")
    return pack


@app.get("/v1/decisions/{decision_uid}")
def get_decision(decision_uid: str):
    path = STORE / f"{decision_uid}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="decision not found")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/v1/decisions/{decision_uid}/attestation-payload")
def get_payload(decision_uid: str):
    pack = get_decision(decision_uid)
    return build_attestation_payload(pack)


@app.get("/v1/repos/{owner}/{repo}/latest-verdict")
def latest_verdict(owner: str, repo: str):
    wanted = f"{owner}/{repo}"
    candidates = []
    if STORE.exists():
        for path in STORE.glob("att_*.json"):
            try:
                pack = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if pack.get("repo") == wanted:
                candidates.append(pack)
    if not candidates:
        raise HTTPException(status_code=404, detail="no verdict stored for this repo")
    return max(candidates, key=lambda pack: pack.get("evaluated_at", ""))

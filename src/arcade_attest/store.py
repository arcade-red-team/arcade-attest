"""Local evidence store: one JSON file per pack under data/decisions (MVP).

This is the only module that touches the filesystem for packs; the engine
stays pure. A networked store can replace this adapter later.
"""
from __future__ import annotations

import json
from pathlib import Path

STORE_DIR = Path("data/decisions")


def _dir(store_dir: str | Path | None) -> Path:
    directory = Path(store_dir) if store_dir else STORE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def write_pack(pack: dict, store_dir: str | Path | None = None) -> Path:
    path = _dir(store_dir) / f"{pack['id']}.json"
    path.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    return path


def read_pack(uid: str, store_dir: str | Path | None = None) -> dict | None:
    path = _dir(store_dir) / f"{uid}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_packs(store_dir: str | Path | None = None) -> list[dict]:
    packs = []
    for path in _dir(store_dir).glob("att_*.json"):
        try:
            packs.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return packs


def latest_for_repo(repo: str, store_dir: str | Path | None = None) -> dict | None:
    candidates = [pack for pack in list_packs(store_dir) if pack.get("repo") == repo]
    if not candidates:
        return None
    return max(candidates, key=lambda pack: pack.get("evaluated_at", ""))

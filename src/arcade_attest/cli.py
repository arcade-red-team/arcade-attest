"""CLI: arcade-attest evaluate | from-changelog | payload | serve"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .adapter import analyze_pair, normalize_changelog
from .anchor import build_attestation_payload
from .engine import evaluate


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _expiry(evaluated_at: str, hours: int = 24) -> str:
    start = datetime.strptime(evaluated_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (start + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _emit(pack: dict, out: str | None) -> None:
    text = json.dumps(pack, indent=2, ensure_ascii=False)
    if out:
        Path(out).write_text(text + "\n", encoding="utf-8")
        print(f"evidence pack -> {out}")
    print(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="arcade-attest", description="ArcadeAttest Decision API (deterministic architecture verdicts)")
    sub = parser.add_subparsers(dest="command", required=True)

    ev = sub.add_parser("evaluate", help="Analyze base vs head directories with arcade-agent, then evaluate")
    ev.add_argument("--base", required=True)
    ev.add_argument("--head", required=True)
    ev.add_argument("--record", required=True, help="Decision Record JSON file")
    ev.add_argument("--language", default="python")
    ev.add_argument("--out")

    fc = sub.add_parser("from-changelog", help="Evaluate an existing changelog_architecture JSON output")
    fc.add_argument("--changelog", required=True)
    fc.add_argument("--record", required=True)
    fc.add_argument("--out")

    pl = sub.add_parser("payload", help="Build the EAS attestation payload for an evidence pack")
    pl.add_argument("--pack", required=True)
    pl.add_argument("--base-commit", default="")
    pl.add_argument("--head-commit", default="")

    sv = sub.add_parser("serve", help="Run the HTTP API (requires the 'api' extra)")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8787)

    args = parser.parse_args(argv)
    if args.command == "serve":
        import uvicorn

        uvicorn.run("arcade_attest.api:app", host=args.host, port=args.port)
        return 0
    if args.command == "payload":
        pack = _load_json(args.pack)
        print(json.dumps(build_attestation_payload(pack, base_commit=args.base_commit, head_commit=args.head_commit), indent=2))
        return 0

    record = _load_json(args.record)
    if args.command == "evaluate":
        data = analyze_pair(args.base, args.head, language=args.language)
    else:
        raw = _load_json(args.changelog)
        data = normalize_changelog(raw.get("changelog", raw))
    evaluated_at = _now()
    pack = evaluate(record, data, evaluated_at=evaluated_at, expires_at=_expiry(evaluated_at))
    _emit(pack, args.out)
    return 0 if pack["verdict"] != "BLOCK" else 2


if __name__ == "__main__":
    sys.exit(main())

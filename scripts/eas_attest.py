#!/usr/bin/env python3
"""D3: register the ArcadeAttest EAS schema and attest evidence packs on Base Sepolia.

Dry-run by default: prints the payload, target contracts and the exact next
steps. Nothing is signed or sent without --submit, and --submit reads the key
from the EAS_PRIVATE_KEY environment variable of the person running this
script. Agents never hold keys; the owner runs this with their own wallet.

Canonical Base Sepolia predeploys (override via env if they ever change):
  SchemaRegistry 0x4200000000000000000000000000000000000020
  EAS            0x4200000000000000000000000000000000000021
Default RPC: https://sepolia.base.org (BASE_SEPOLIA_RPC overrides).

Usage:
  python scripts/eas_attest.py --pack data/demo-evidence.json            # dry-run
  EAS_PRIVATE_KEY=0x... python scripts/eas_attest.py --pack pack.json --register-schema --submit
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from arcade_attest.anchor import EAS_SCHEMA, build_attestation_payload  # noqa: E402

ZERO_ADDRESS = "0x" + "0" * 40
ZERO_BYTES32 = "0x" + "0" * 64
SCHEMA_REGISTRY = os.environ.get("EAS_SCHEMA_REGISTRY", "0x4200000000000000000000000000000000000020")
EAS_CONTRACT = os.environ.get("EAS_CONTRACT", "0x4200000000000000000000000000000000000021")
RPC = os.environ.get("BASE_SEPOLIA_RPC", "https://sepolia.base.org")

REGISTRY_ABI = [
    {"inputs": [{"name": "schema", "type": "string"}, {"name": "resolver", "type": "address"}, {"name": "revocable", "type": "bool"}],
     "name": "register", "outputs": [{"name": "", "type": "bytes32"}], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "uid", "type": "bytes32"}],
     "name": "getSchema", "outputs": [{"components": [{"name": "uid", "type": "bytes32"}, {"name": "resolver", "type": "address"}, {"name": "revocable", "type": "bool"}, {"name": "schema", "type": "string"}], "name": "", "type": "tuple"}],
     "stateMutability": "view", "type": "function"},
]
EAS_ABI = [
    {"inputs": [{"components": [{"name": "schema", "type": "bytes32"}, {"components": [{"name": "recipient", "type": "address"}, {"name": "expirationTime", "type": "uint64"}, {"name": "revocable", "type": "bool"}, {"name": "refUID", "type": "bytes32"}, {"name": "data", "type": "bytes"}, {"name": "value", "type": "uint256"}], "name": "data", "type": "tuple"}], "name": "request", "type": "tuple"}],
     "name": "attest", "outputs": [{"name": "", "type": "bytes32"}], "stateMutability": "payable", "type": "function"},
]

FIELD_TYPES = ["string", "bytes32", "bytes32", "bytes32", "uint8", "int32", "uint32", "bytes32", "uint64", "uint64"]


def _unix(iso: str | None) -> int:
    if not iso:
        return 0
    return int(datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp())


def encode_attestation_data(payload: dict) -> bytes:
    from eth_abi import encode

    data = payload["data"]
    values = [
        data["repo"],
        bytes.fromhex(data["baseCommit"].removeprefix("0x")),
        bytes.fromhex(data["headCommit"].removeprefix("0x")),
        bytes.fromhex(data["decisionRecordHash"].removeprefix("0x")),
        int(data["verdict"]),
        int(data["smellsDelta"]),
        int(data["responsibilityShifts"]),
        bytes.fromhex(data["evidenceHash"].removeprefix("0x")),
        _unix(data["evaluatedAt"]),
        _unix(data["expiresAt"]),
    ]
    return encode(FIELD_TYPES, values)


def main() -> int:
    parser = argparse.ArgumentParser(description="ArcadeAttest EAS anchoring (Base Sepolia)")
    parser.add_argument("--pack", required=True)
    parser.add_argument("--schema-uid", help="Existing schema UID; skip registration")
    parser.add_argument("--register-schema", action="store_true")
    parser.add_argument("--base-commit", default="")
    parser.add_argument("--head-commit", default="")
    parser.add_argument("--submit", action="store_true", help="Actually send transactions (needs EAS_PRIVATE_KEY)")
    args = parser.parse_args()

    pack = json.loads(Path(args.pack).read_text(encoding="utf-8"))
    payload = build_attestation_payload(pack, base_commit=args.base_commit, head_commit=args.head_commit)
    print(json.dumps({"mode": "submit" if args.submit else "dry-run", "rpc": RPC,
                      "schema_registry": SCHEMA_REGISTRY, "eas": EAS_CONTRACT,
                      "schema": EAS_SCHEMA, "payload": payload}, indent=2))
    if not args.submit:
        print("\nDry-run only. To anchor for real, the wallet owner runs:")
        print("  EAS_PRIVATE_KEY=0x... python scripts/eas_attest.py --pack <pack.json> --register-schema --submit")
        print("Then record the returned schema UID + attestation UID in the pack and on issue #1.")
        return 0

    key = os.environ.get("EAS_PRIVATE_KEY")
    if not key:
        print("EAS_PRIVATE_KEY is not set; refusing to submit.", file=sys.stderr)
        return 1
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(RPC))
    account = w3.eth.account.from_key(key)
    registry = w3.eth.contract(address=Web3.to_checksum_address(SCHEMA_REGISTRY), abi=REGISTRY_ABI)
    eas = w3.eth.contract(address=Web3.to_checksum_address(EAS_CONTRACT), abi=EAS_ABI)

    schema_uid = args.schema_uid
    if args.register_schema or not schema_uid:
        tx = registry.functions.register(EAS_SCHEMA, ZERO_ADDRESS, True).build_transaction(
            {"from": account.address, "nonce": w3.eth.get_transaction_count(account.address)})
        receipt = w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(account.sign_transaction(tx).raw_transaction))
        for log in receipt.logs:
            if log.address.lower() == SCHEMA_REGISTRY.lower() and len(log.topics) > 1:
                schema_uid = log.topics[1].hex()
                break
        if not schema_uid:
            print("Could not read schema UID from receipt logs.", file=sys.stderr)
            return 1
        schema_uid = "0x" + schema_uid.removeprefix("0x")
        print(f"schema registered: {schema_uid} (tx {receipt.transactionHash.hex()})")
    record = registry.functions.getSchema(bytes.fromhex(schema_uid.removeprefix("0x"))).call()
    assert record[3] == EAS_SCHEMA, "on-chain schema string mismatch"

    encoded = encode_attestation_data(payload)
    request = (bytes.fromhex(schema_uid.removeprefix("0x")),
               (ZERO_ADDRESS, 0, True, bytes.fromhex(ZERO_BYTES32.removeprefix("0x")), encoded, 0))
    tx = eas.functions.attest(request).build_transaction(
        {"from": account.address, "nonce": w3.eth.get_transaction_count(account.address), "value": 0})
    receipt = w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(account.sign_transaction(tx).raw_transaction))
    print(json.dumps({"schema_uid": schema_uid, "attestation_tx": receipt.transactionHash.hex(),
                      "verify": f"https://base-sepolia.easscan.org/schema/view/{schema_uid}"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""ArcadeAttest Decision API.

Deterministic architecture verdicts (PASS / WARN / BLOCK) over arcade-agent
changelog output. No LLM ever participates in a verdict; LLMs may only help
draft Decision Records for humans to approve.
"""

__version__ = "0.2.0"

VERDICT_CODES = {"PASS": 0, "WARN": 1, "BLOCK": 2}

HONEST_GAPS = [
    "No edge-level diff yet: deny_dependency predicates are not evaluated in this MVP.",
    "Parser blind spots exist (for example files that declare no entities): a component can look empty and a verdict can be a false PASS. Coverage is reported in every evidence pack.",
    "Predicate thresholds are starting guesses; they need per-repo history to calibrate.",
    "An on-chain attestation proves the integrity and timestamp of a verdict, not that the verdict is objectively correct.",
    "Criterion scores (scoring@1) are advisory: 0.5 on a trend criterion means 'no measured change', and a criterion without evidence is reported not_run instead of being scored.",
]

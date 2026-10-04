"""Adapter: run arcade-agent on two source trees and normalize the changelog.

arcade-agent is a pre-existing, separately published project (MIT,
github.com/tuannx/arcade-agent, PyPI `arcade-agent`). ArcadeAttest consumes
its `changelog_architecture` output; it does not modify it.
"""
from __future__ import annotations

from typing import Any


def to_plain(value: Any) -> Any:
    """Best-effort conversion of arcade-agent objects into plain JSON data."""
    if isinstance(value, dict):
        return {str(k): to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "model_dump"):
        return to_plain(value.model_dump())
    if hasattr(value, "__dict__"):
        return {k: to_plain(v) for k, v in vars(value).items() if not k.startswith("_")}
    return str(value)


def _component_sizes(arch: Any) -> list[dict]:
    components = getattr(arch, "components", None) or []
    sizes = []
    for index, component in enumerate(components):
        name = getattr(component, "name", None) or getattr(component, "id", None) or f"component-{index}"
        entities = getattr(component, "entities", None)
        if entities is None:
            count = getattr(component, "entity_count", 0) or 0
        else:
            try:
                count = len(entities)
            except TypeError:
                count = int(entities)
        sizes.append({"name": str(name), "entities": int(count)})
    return sizes


def normalize_changelog(changelog: Any, *, components=None, refs=None, languages_b=None) -> dict:
    """Map a changelog_architecture result into the engine's input shape."""
    cl = to_plain(changelog) or {}
    smells = cl.get("smells") or {}
    summary = cl.get("summary") or {}
    sizes = components
    if sizes is None:
        # Fallback when per-component entity counts are unavailable: expose the
        # component names from the changelog with unknown (0) sizes and say so.
        names = set()
        for key in ("added", "removed", "renamed", "split", "merged", "rewritten", "stable"):
            for item in (cl.get("components") or {}).get(key) or []:
                if isinstance(item, dict):
                    names.add(str(item.get("name") or item.get("to") or item.get("id") or "component"))
                elif item:
                    names.add(str(item))
        sizes = [{"name": name, "entities": 0} for name in sorted(names)]
    coverage = {
        "languages_a": (cl.get("languages") or {}).get("a") or [],
        "languages_b": (cl.get("languages") or {}).get("b") or languages_b or [],
        "entities_a": summary.get("entities_a"),
        "entities_b": summary.get("entities_b"),
        "warnings": [],
    }
    return {
        "smells_new": smells.get("new") or [],
        "responsibility_shifts": cl.get("responsibility_shifts") or [],
        "components": sizes,
        "summary": summary,
        "metrics": cl.get("metrics") or {},
        "coverage": coverage,
        "refs": refs or cl.get("refs") or {},
    }


def analyze_pair(base_path: str, head_path: str, *, language: str = "python", algorithm: str = "pkg") -> dict:
    """Analyze base vs head directories with arcade-agent and normalize."""
    from arcade_agent.source.ingest import ingest
    from arcade_agent.tools.parse import parse
    from arcade_agent.tools.recover import recover
    from arcade_agent.tools.detect_smells import detect_smells
    from arcade_agent.tools.compute_metrics import compute_metrics
    from arcade_agent.tools.changelog_architecture import changelog_architecture

    def analyze(path: str):
        repo = ingest(path, language=language)
        graph = parse(repo.path, language=language)
        arch = recover(graph, algorithm=algorithm)
        smells = detect_smells(arch, graph)
        metrics = compute_metrics(arch, graph)
        return graph, arch, smells, metrics

    graph_a, arch_a, smells_a, metrics_a = analyze(base_path)
    graph_b, arch_b, smells_b, metrics_b = analyze(head_path)
    changelog = changelog_architecture(
        arch_a, graph_a, arch_b, graph_b,
        smells_a=smells_a, smells_b=smells_b,
        metrics_a=metrics_a, metrics_b=metrics_b,
        ref_a=base_path, ref_b=head_path,
    )
    return normalize_changelog(
        changelog,
        components=_component_sizes(arch_b),
        refs={"a": base_path, "b": head_path},
    )

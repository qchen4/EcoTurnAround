"""T1 — skeleton sanity tests.

Verify the package and all placeholder modules import cleanly and the
expected project layout exists.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

ECOTURN_MODULES = [
    "ecoturn",
    "ecoturn.schemas",
    "ecoturn.parser",
    "ecoturn.scenario_generator",
    "ecoturn.simulator",
    "ecoturn.baseline",
    "ecoturn.optimizer",
    "ecoturn.metrics",
    "ecoturn.verifier",
    "ecoturn.refinement",
    "ecoturn.memory",
]


@pytest.mark.parametrize("module_name", ECOTURN_MODULES)
def test_modules_import_cleanly(module_name: str) -> None:
    assert importlib.import_module(module_name) is not None


def test_package_version() -> None:
    import ecoturn

    assert isinstance(ecoturn.__version__, str)


def test_expected_layout_exists() -> None:
    expected = [
        "app.py",
        "requirements.txt",
        "README.md",
        "docs/PROJECT_SPEC.md",
        "docs/ARCHITECTURE.md",
        "docs/SCHEMA.md",
        "data/presets",
        "data/reflection_log.jsonl",
        "ecoturn",
        "tests",
    ]
    missing = [rel for rel in expected if not (ROOT / rel).exists()]
    assert not missing, f"missing project paths: {missing}"

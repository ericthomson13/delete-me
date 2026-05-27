"""Unit tests for the audit-adapter-health followup script's YAML bumper.

We import the script as a module by path (it lives outside the package
tree). The bumper writes to the broker YAMLs in registry/brokers/ via an
absolute path computed in the script, so we monkeypatch BROKERS_DIR to a
tmp directory per test.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "audit_adapter_health_followup.py"


@pytest.fixture
def mod(tmp_path, monkeypatch):
    """Load the followup script as a module and point BROKERS_DIR at tmp_path."""
    spec = importlib.util.spec_from_file_location("audit_adapter_health_followup", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["audit_adapter_health_followup"] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "BROKERS_DIR", tmp_path)
    return module


def _yaml(text: str, tmp_path: Path, name: str = "spokeo.yaml") -> Path:
    p = tmp_path / name
    p.write_text(text)
    return p


def test_bump_creates_block_when_absent(mod, tmp_path):
    text = (
        "id: spokeo\n"
        "name: Spokeo\n"
        "audit_sources:\n"
        "  - spokeo_search\n"
        "statutes:\n"
        "  - ccpa\n"
    )
    _yaml(text, tmp_path)
    changed = mod.bump_last_pass("spokeo", "spokeo_search", "2026-05-27")
    assert changed is True
    result = (tmp_path / "spokeo.yaml").read_text()
    assert "audit_sources_last_pass:\n  spokeo_search: 2026-05-27\n" in result
    # The block must be inserted right after audit_sources (preserving order).
    assert result.index("audit_sources_last_pass") > result.index("audit_sources:")
    assert result.index("audit_sources_last_pass") < result.index("statutes:")


def test_bump_replaces_existing_date(mod, tmp_path):
    text = (
        "id: spokeo\n"
        "audit_sources:\n"
        "  - spokeo_search\n"
        "audit_sources_last_pass:\n"
        "  spokeo_search: 2026-01-01\n"
        "statutes:\n"
        "  - ccpa\n"
    )
    _yaml(text, tmp_path)
    changed = mod.bump_last_pass("spokeo", "spokeo_search", "2026-05-27")
    assert changed is True
    result = (tmp_path / "spokeo.yaml").read_text()
    assert "spokeo_search: 2026-05-27" in result
    assert "2026-01-01" not in result


def test_bump_adds_source_to_existing_block(mod, tmp_path):
    text = (
        "id: example\n"
        "audit_sources:\n"
        "  - example_search\n"
        "  - example_secondary\n"
        "audit_sources_last_pass:\n"
        "  example_search: 2026-01-01\n"
        "statutes:\n"
        "  - ccpa\n"
    )
    _yaml(text, tmp_path, name="example.yaml")
    changed = mod.bump_last_pass("example", "example_secondary", "2026-05-27")
    assert changed is True
    result = (tmp_path / "example.yaml").read_text()
    assert "example_search: 2026-01-01" in result  # untouched
    assert "example_secondary: 2026-05-27" in result


def test_bump_is_noop_when_date_already_today(mod, tmp_path):
    text = (
        "id: spokeo\n"
        "audit_sources:\n"
        "  - spokeo_search\n"
        "audit_sources_last_pass:\n"
        "  spokeo_search: 2026-05-27\n"
        "statutes:\n"
        "  - ccpa\n"
    )
    _yaml(text, tmp_path)
    changed = mod.bump_last_pass("spokeo", "spokeo_search", "2026-05-27")
    assert changed is False


def test_bump_refuses_when_no_audit_sources_block(mod, tmp_path, capsys):
    text = (
        "id: spokeo\n"
        "name: Spokeo\n"
        "statutes:\n"
        "  - ccpa\n"
    )
    _yaml(text, tmp_path)
    changed = mod.bump_last_pass("spokeo", "spokeo_search", "2026-05-27")
    assert changed is False
    assert "refusing to invent" in capsys.readouterr().err


def test_bump_returns_false_for_missing_broker_file(mod, tmp_path, capsys):
    changed = mod.bump_last_pass("does-not-exist", "x_search", "2026-05-27")
    assert changed is False
    assert "broker YAML not found" in capsys.readouterr().err


def test_bump_preserves_comments_and_unrelated_keys(mod, tmp_path):
    text = (
        "id: spokeo\n"
        "name: Spokeo\n"
        "# this is a comment that must survive\n"
        "audit_sources:\n"
        "  - spokeo_search  # inline comment\n"
        "statutes:\n"
        "  - ccpa\n"
    )
    _yaml(text, tmp_path)
    mod.bump_last_pass("spokeo", "spokeo_search", "2026-05-27")
    result = (tmp_path / "spokeo.yaml").read_text()
    assert "# this is a comment that must survive" in result
    assert "# inline comment" in result

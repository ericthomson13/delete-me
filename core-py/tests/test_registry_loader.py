"""Registry loader tests — exercise the schema and Pydantic models."""

from __future__ import annotations

import textwrap
from pathlib import Path

import jsonschema
import pytest
import yaml
from delete_me.registry import load_brokers, load_statutes
from delete_me.registry.loader import cross_check, validate_broker_file


def test_all_shipped_brokers_validate():
    brokers = load_brokers()
    assert len(brokers) >= 10, "Phase 0 ships at least 10 brokers"
    ids = {b.id for b in brokers}
    assert {"spokeo", "whitepages", "acxiom"}.issubset(ids)


def test_brokers_cross_check_statutes():
    brokers = load_brokers()
    statutes = load_statutes()
    errors = cross_check(brokers, statutes)
    assert errors == [], f"Cross-check errors: {errors}"


def test_broker_id_matches_filename(tmp_path: Path):
    bad = tmp_path / "wrongname.yaml"
    bad.write_text(
        textwrap.dedent(
            """
            id: spokeo
            name: Test
            opt_out: { methods: [email], email: a@b.com }
            accepts_authorized_agent: true
            required_pii: [full_name]
            statutes: [ccpa_1798_105]
            last_verified: 2026-05-18
            maintainer: "@ericthomson13"
            """
        ).strip()
    )
    with pytest.raises(ValueError, match="filename stem"):
        validate_broker_file(bad)


def test_schema_rejects_missing_required(tmp_path: Path):
    bad = tmp_path / "broken.yaml"
    bad.write_text("id: broken\nname: Broken\n")  # no opt_out, statutes, etc.
    with pytest.raises(jsonschema.ValidationError):
        validate_broker_file(bad)


def test_schema_rejects_unknown_opt_out_method(tmp_path: Path):
    bad = tmp_path / "broken2.yaml"
    bad.write_text(
        textwrap.dedent(
            """
            id: broken2
            name: Broken Two
            opt_out: { methods: [carrier_pigeon] }
            accepts_authorized_agent: false
            required_pii: [full_name]
            statutes: [ccpa_1798_105]
            last_verified: 2026-05-18
            maintainer: "@ericthomson13"
            """
        ).strip()
    )
    with pytest.raises(jsonschema.ValidationError):
        validate_broker_file(bad)


def test_statutes_load_with_known_keys():
    statutes = load_statutes()
    assert "ccpa_1798_105" in statutes
    assert "gdpr_article_17" in statutes
    s = statutes["ccpa_1798_105"]
    assert "1798.105" in s.citation


def test_brokers_yaml_is_parseable(tmp_path: Path):
    """Catch any YAML syntax errors at the source-file layer."""
    from delete_me.paths import brokers_dir

    for path in brokers_dir().glob("*.yaml"):
        with path.open() as f:
            yaml.safe_load(f)


def test_audit_sources_last_pass_validates_when_keys_match(tmp_path: Path):
    """audit_sources_last_pass keys must each appear in audit_sources."""
    good = tmp_path / "spokeo.yaml"
    good.write_text(
        textwrap.dedent(
            """
            id: spokeo
            name: Test
            opt_out: { methods: [email], email: a@b.com }
            accepts_authorized_agent: true
            required_pii: [full_name]
            audit_sources: [spokeo_search]
            audit_sources_last_pass:
              spokeo_search: 2026-05-27
            statutes: [ccpa_1798_105]
            last_verified: 2026-05-18
            maintainer: "@ericthomson13"
            """
        ).strip()
    )
    broker = validate_broker_file(good)
    statutes = load_statutes()
    errors = cross_check([broker], statutes)
    assert errors == []


def test_cross_check_rejects_orphan_last_pass_key(tmp_path: Path):
    """An audit_sources_last_pass key that isn't in audit_sources is a config bug."""
    bad = tmp_path / "spokeo.yaml"
    bad.write_text(
        textwrap.dedent(
            """
            id: spokeo
            name: Test
            opt_out: { methods: [email], email: a@b.com }
            accepts_authorized_agent: true
            required_pii: [full_name]
            audit_sources: [spokeo_search]
            audit_sources_last_pass:
              spokeo_search: 2026-05-27
              ghost_source: 2026-05-27
            statutes: [ccpa_1798_105]
            last_verified: 2026-05-18
            maintainer: "@ericthomson13"
            """
        ).strip()
    )
    broker = validate_broker_file(bad)
    errors = cross_check([broker], load_statutes())
    assert any("ghost_source" in e for e in errors)

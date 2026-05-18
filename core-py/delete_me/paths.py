"""Resolve repo-relative paths to the registry and legal directories.

Works whether the package is run from a source checkout (most common in
Phase 0) or installed as a wheel (later phases will switch to package data).
"""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    """Return the repo root by walking up from this file."""
    return Path(__file__).resolve().parents[2]


def registry_dir() -> Path:
    return repo_root() / "registry"


def brokers_dir() -> Path:
    return registry_dir() / "brokers"


def schemas_dir() -> Path:
    return registry_dir() / "schemas"


def legal_dir() -> Path:
    return repo_root() / "legal"


def templates_dir() -> Path:
    return Path(__file__).resolve().parent / "letters" / "templates"

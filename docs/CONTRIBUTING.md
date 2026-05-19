# Contributing

Welcome. There are two kinds of contributions to `delete-me` and they have
very different shapes.

## 1. Adding or updating a broker entry (the easy path)

This is the highest-leverage thing you can do. Adding a broker is one YAML
file, validated by CI. See [`ADDING_A_BROKER.md`](ADDING_A_BROKER.md).

You do **not** need to write code, run tests, or understand Python to do
this.

## 2. Code contributions

### Local setup

```sh
git clone https://github.com/ericthomson13/delete-me
cd delete-me
uv sync --extra dev
bash scripts/install-hooks.sh   # installs the pre-push hook
```

The pre-push hook runs `pytest`, `ruff`, and `delete-me validate-registry`
before allowing a push. **Don't bypass it with `--no-verify` unless a
maintainer asks you to.** Tests do not run in GitHub Actions to keep the
CI footprint small, so the hook is the gate.

### Running tests manually

```sh
uv run pytest                       # unit tests
uv run ruff check                   # lint
uv run delete-me validate-registry  # broker YAMLs against schema
```

### Code style

- Python 3.12, typed throughout. `mypy` is configured but not enforced
  in CI; treat type errors as bugs.
- `ruff` config in `pyproject.toml`. Run before committing.
- 100-column line length.
- Prefer functions to classes unless state is meaningful.
- Don't add a comment unless the *why* is non-obvious.

### Pull requests

- One topic per PR.
- Update the relevant doc in `docs/architecture/` if your change affects
  the plan, phases, risks, or research narrative.
- If you add a broker, update `last_verified` to today's date and put
  your `@github-handle` in the `maintainer` field.

## What `delete-me` will not accept

- **Automated form-submission scrapers.** See
  [`architecture/RESEARCH.md`](architecture/RESEARCH.md). If you have a
  better approach than every prior project that tried, open a discussion
  first.
- **CAPTCHA-solving integrations** (CapSolver, 2Captcha, etc.).
- **Telemetry that includes PII**, ad pixels, third-party trackers.
- **Specific attorney or law firm endorsements** in
  `legal/attorney_referral_sources.md`.

## Code of conduct

See [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Contributor Covenant 2.1.

## License

By contributing you agree your contribution is licensed under AGPL-3.0-or-later.

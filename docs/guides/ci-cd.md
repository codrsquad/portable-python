---
type: Reference
title: CI/CD
description: The GitHub Actions workflows — tests on every push/PR across the Python matrix, and trusted PyPI publishing on version tags.
tags: [ci, cd, github-actions, release, reference]
timestamp: 2026-06-23T00:00:00Z
---

# CI/CD

Two GitHub Actions workflows live in `.github/workflows/`. Both drive [tox](/guides/local-development.md) through `uv` / `tox-uv`.

## Tests (`tests.yml`)

Runs on every push to `main` and every pull request targeting `main`, with `cancel-in-progress` concurrency so superseded runs are cancelled.

| Job | What it does |
|-----|--------------|
| `test` | Matrix over Python `3.10`–`3.14` on `ubuntu-latest` (`fail-fast: false`). Runs `uvx --with tox-uv tox -e py`, then uploads coverage to Coveralls as a **parallel** build, flagged per version. |
| `coveralls-finish` | After all `test` jobs finish, signals Coveralls that the parallel build is complete. |
| `linters` | On Python `3.14`, runs `uvx --with tox-uv tox -e style` (ruff check + format diff). |

## Release (`release.yml`)

Triggers on pushing a tag matching `v[0-9]*`. The single `publish` job (Python `3.14`, GitHub environment `release`):

1. `uvx --with tox-uv tox -e py,style` — full test + lint gate.
2. `uv build` — build the sdist + wheel.
3. `pypa/gh-action-pypi-publish` — publish to PyPI via **trusted publishing** (OIDC, `id-token: write` — no API token is stored).

See [bump python support](/guides/bump-python-support.md) for keeping the test matrix in sync with supported versions.

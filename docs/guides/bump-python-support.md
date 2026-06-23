---
type: Playbook
title: Bump Python Support
description: Update the supported CPython versions across project metadata, the CI matrix, and the minimum version floor.
tags: [playbook, versions, cpython, maintenance]
timestamp: 2026-06-23T00:00:00Z
---

# Bump Python Support

portable-python deliberately tracks only the recent, non-EOL CPython versions (see [overview](/overview.md)). To move the supported window:

## Steps

1. **Project metadata** — update the classifiers and `requires-python` in `pyproject.toml`.
2. **CI matrix** — update the Python versions in `.github/workflows/tests.yml` (see [CI/CD](/guides/ci-cd.md)).
3. **Minimum version** — bump `CPythonFamily.min_version` (in `versions.py`) if the floor moved; it gates which versions [`list`](/cli/list.md) and [`build`](/cli/build.md) accept. See [`PPG`](/architecture/ppg.md).
4. **Verify** — run the full matrix with `tox` (see [local development](/guides/local-development.md)).

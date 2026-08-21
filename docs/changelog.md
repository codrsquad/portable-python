---
type: Changelog
title: Changelog
description: High-level release highlights for portable-python, newest first.
tags: [changelog, releases]
timestamp: 2026-06-23T00:00:00Z
---

## Unreleased

- Bumped SQLite to 3.53.4 and gettext-tiny to 0.3.3; re-checked every other component against upstream (all already current, or deliberately held back — see the `version` property comments).

## v2.0.2

- Corrected `readline` static linking

## v2.0.1

- Bumped the bundled components (OpenSSL, SQLite, Tcl/Tk, …) to current versions.
- Refreshed dependencies and modernized CI (now on uv / tox-uv, with updated GitHub Actions).
- Added an OKF documentation bundle under `docs/` (the old top-level docs folded into it).

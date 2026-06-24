---
type: Playbook
title: Release Process
description: >-
  How to cut a release for this repo — refresh the changelog highlights, then tag a new
  version from a clean main.
tags: [playbook, release, versioning, changelog]
timestamp: 2026-06-23T00:00:00Z
---

# Release Process

Releasing is opinionated and per-repo; this is portable-python's convention. A release is cut by
pushing a version tag from `main` — that's what triggers the build + PyPI publish (see
[CI/CD](/guides/ci-cd.md)).

## 1. Refresh the changelog

Review what changed since the last release:

```bash
git diff <last-tag>..main        # e.g. git diff v2.0.0..main
```

Summarize the **highlights** in [`changelog.md`](/changelog.md) — short and high-level. It should
give a reader a rough idea of the main changes since the last release, not a blow-by-blow; skip the
details.

- If the changelog is **already up to date** with `main`, go to step 2.
- If it's **not**, update it first — recommend landing that as its own PR before releasing.

## 2. Tag the release

Only once `main` is ready: the changelog is up to date, and you're on a **clean checkout of
`main`**.

Choose the bump — **ask the user; default to patch** — following semver from the last tag:

| Bump | When | Example |
|------|------|---------|
| patch | fixes, component bumps, docs | `v2.0.0 → v2.0.1` |
| minor | backward-compatible features | `v2.0.0 → v2.1.0` |
| major | breaking changes | `v2.0.0 → v3.0.0` |

Then **confirm the exact version with the user, and show these two commands before running them:**

```bash
git tag v2.0.1
git push origin v2.0.1
```

The tag push is what kicks off the release — there's nothing else to run.

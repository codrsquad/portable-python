---
type: Playbook
title: Bump Component Versions
description: >-
  How to update the pinned upstream versions of the external C libraries (ModuleBuilder
  subclasses) statically linked into CPython.
tags: [playbook, modules, versions, maintenance]
timestamp: 2026-06-23T00:00:00Z
---

# Bump Component Versions

Each [external module](/modules/index.md) pins a default upstream version — the `cfg_version("…")`
in its `version` property. This playbook keeps those current without breaking the build.

## Steps

1. **List the components** — the `ModuleBuilder` subclasses under `src/portable_python/external/`
   (openssl, zlib, xz, sqlite, … plus sub-modules like ncurses/tcl/tk and the toolchain). The
   [external modules reference](/modules/external-modules.md) is the catalog.
2. **Check upstream** for each. Its `version` property carries a comment with the release/EOL links
   to check and its bump policy — read that first.
3. **Pick a version** using the rule below.
4. **Update** the `cfg_version("…")` default, and refresh the comment (EOL dates, "stay on LTS",
   last-checked).
5. **Confirm it still builds** — [`build-report`](/cli/build-report.md), then a real build (see
   [local development](/guides/local-development.md)).

## Patch vs major/minor

- **Patch bumps** (e.g. OpenSSL `3.5.6 → 3.5.7`) — almost always OK; stay within the current line
  and bump freely.
- **Major / minor bumps** (e.g. OpenSSL `3.6` or `4.0`) — **research them first.** Start from the
  official CPython build docs ([devguide: setup & building][cpython-build]) and see which versions
  the CPython team recommends. That is often not stated explicitly; when it isn't, do due-diligence
  research online before moving. When unsure, stay on the current / LTS line.
  - **Be extra wary of a fresh `.0`** (`3.6.0`, `4.0.0`, …) — wait for at least the `.1` before
    adopting a new line. Early `.0` releases carry the most bugs and are sometimes withdrawn
    (SQLite `3.52.0` was). Move to a `.0` only with a pressing reason.

[cpython-build]: https://devguide.python.org/getting-started/setup-building/index.html

There is **no local test matrix that validates component-version choices** — but "does it still
build" is a real check: building CPython runs its own test suite as part of the process (an
`--enable-optimizations` / PGO build exercises much of it), so a wrongly-built component — a broken
openssl, say — shows up as a build failure. The validation rests entirely on CPython's own tests;
portable-python doesn't re-validate CPython itself. Picking *which* version is safe is what the
research above is for.

## Record the policy in code, not here

Per-component specifics — which line is LTS, EOL dates, where to check, when it's safe to jump —
belong as a **comment in that module's `version` property**, right next to the value, so they can't
drift from these docs:

```python
@property
def version(self):
    # <which line is LTS + supported window / EOL dates>
    # <stay-on-LTS note, if a newer line isn't verified yet>
    # Check <upstream releases> and <e.g. endoflife.date/...>
    return self.cfg_version("X.Y.Z")
```

`Openssl.version` is the live model. When you bump a component whose `version` property lacks such a
comment, add one.

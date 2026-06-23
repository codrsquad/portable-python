---
type: Class
title: ModuleBuilder
description: Abstract base for everything that gets compiled — external C libraries and CPython itself — providing the common download/configure/make/install flow and environment injection.
tags: [class, abstract, build, module]
timestamp: 2026-06-23T00:00:00Z
---

# ModuleBuilder

The abstract base for everything the tool compiles (`__init__.py`). Both the [external C modules](/modules/index.md) and [`PythonBuilder`](/architecture/python-builder.md) (hence [`Cpython`](/architecture/cpython.md)) extend it, so every component is built the same way and lands in the same [build layout](/concepts/build-layout.md).

## Mental model

A subclass is mostly **declarative**: it sets a few `m_*` class attributes (name, [telltale](/concepts/telltale-detection.md) marker, Debian package, include subfolder) and provides a source `url` + `version`. The base class runs the rest of the flow — download → unpack → patch → configure → make → install — into the shared `build/deps/` prefix. Platform differences are isolated to `_do_linux_compile()` / `_do_macos_compile()`, dispatched on [`PPG.target`](/architecture/ppg.md).

Two mechanisms recur everywhere and are worth understanding:

- **Environment injection** (`xenv_*` methods) — each contributes one variable (CPATH, LDFLAGS, PATH, …) pointing the compiler at `build/deps/`. This is how a statically-built dependency gets found by the next build; see [static linking](/concepts/static-linking.md).
- **Per-module config overrides** — `cfg_*` helpers read `{module}-version`, `{module}-url`, `{module}-configure`, … from [configuration](/configuration/portable-python-yml.md), so any default can be overridden without code changes.

`linker_outcome()` decides, per module and platform, whether it will be linked `static` / `shared`, is `absent`, or would `fail` — the verdict surfaced by [`build-report`](/cli/build-report.md).

## Adding one

Subclass `ModuleBuilder`, set the `m_*` attributes, implement `url` / `version` and `_do_linux_compile()` — see the [guide](/guides/add-an-external-module.md).

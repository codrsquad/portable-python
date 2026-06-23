---
type: Class
title: PythonInspector
description: Validates the portability of a python installation by parsing the dynamic-library dependencies of every executable and .so, and reporting any non-portable references.
tags: [class, inspection, validation, portability]
timestamp: 2026-06-23T00:00:00Z
---

# PythonInspector

`PythonInspector` (`inspector.py`) answers the question the whole project exists for: *is this python [portable](/concepts/portability.md), and if not, why not?* It powers the [`inspect`](/cli/inspect.md) command and the portability gate at the end of [`BuildSetup.compile()`](/architecture/build-setup.md).

## How it works

It walks every executable and `.so` in an installation, lists each one's dynamic-library dependencies (parsing `ldd` on Linux / `otool` on macOS), and classifies every reference:

- **system / standard** library → fine;
- **relative / self** reference → fine (what a relocatable build should have);
- **absolute, non-system** reference → a portability problem.

For a portable build, any problem fails the inspection (the report exposes a single "first problem" verdict that callers check).

## Relativization

The fix lives in `LibAutoCorrect`: it rewrites absolute library references to relative form (`@loader_path` / `$ORIGIN`). It runs **during** the build's finalize step (so the result passes the portable check), and is also exposed standalone as [`lib-auto-correct`](/cli/lib-auto-correct.md) for iterating without a full rebuild.

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

The fix lives in `LibAutoCorrect`, which rewrites the absolute library paths (rpaths) baked into binaries so they resolve relative to the install — `patchelf` on Linux (an `$ORIGIN`-relative rpath), `install_name_tool` on macOS (`@rpath` / `@loader_path`). It runs **during** finalize (so the result passes the portable check) and is exposed standalone as [`lib-auto-correct`](/cli/lib-auto-correct.md).

The same step also supports **non-portable** builds: with `--prefix` or `--enable-shared`, it additionally keeps the real prefix's `lib/` in the rpath, so a build pinned to a fixed location still finds its libraries. (CPython is built with a deliberately long rpath — unlike `chrpath`, `patchelf` can set a fresh rpath of any length, leaving room to rewrite it.)

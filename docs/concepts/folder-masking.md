---
type: Concept
title: Folder Masking (macOS)
description: On macOS, /usr/local is temporarily masked with a RAM disk during the build so that CPython's configure cannot accidentally discover and dynamically link Homebrew libraries.
tags: [macos, folder-mask, concept, isolation]
timestamp: 2026-06-23T00:00:00Z
---

# Folder Masking (macOS)

On macOS, `/usr/local` is where Homebrew and other package managers install libraries and headers. If CPython's `configure` discovers those during a build, it may **dynamically link** against them — silently breaking [portability](/concepts/portability.md), because the resulting binary would depend on libraries that won't exist on another machine.

## The mask

To prevent this, the build temporarily **masks** `/usr/local` with an empty RAM disk for the duration of the compile. With `/usr/local` appearing empty, `configure` falls back to the statically-compiled libraries in `build/deps/` (see [static linking](/concepts/static-linking.md)) instead of system ones.

This is implemented by `FolderMask` and orchestrated by `BuildContext`:

- `BuildContext.__enter__` mounts the mask (and any other isolation hacks) before compilation begins.
- `BuildContext.__exit__` / `cleanup` unmounts it afterward, restoring `/usr/local`.

Because it is a RAM disk mounted over the path (not a deletion), the real `/usr/local` is untouched and reappears the moment the mask is removed.

## Scope

This mask applies to **macOS only**. On Linux, isolation is achieved through telltale-driven module selection and the injected `CPATH`/`LDFLAGS` pointing at `build/deps/` first.

# Citations

[1] [src/portable_python/__init__.py — FolderMask, BuildContext](https://github.com/codrsquad/portable-python/blob/main/src/portable_python/__init__.py)
[2] [ARCHITECTURE.md — Folder Masking pattern](https://github.com/codrsquad/portable-python/blob/main/ARCHITECTURE.md)

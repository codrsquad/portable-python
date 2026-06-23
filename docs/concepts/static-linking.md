---
type: Concept
title: Static Linking
description: Dependencies are compiled statically into a shared deps prefix and linked into CPython, so the binary carries no runtime dependency on system shared libraries.
tags: [static-linking, concept, build]
timestamp: 2026-06-23T00:00:00Z
---

# Static Linking

To make a binary [portable](/concepts/portability.md), its dependencies must travel with it rather than be loaded from the host at runtime. portable-python achieves this by compiling each external C library **statically**.

## How it works

1. Each [external module](/modules/index.md) is compiled with flags that disable shared output and enable static, position-independent code — typically `--enable-shared=no --enable-static=yes` (and `-fPIC` where needed).
2. All modules install into a single shared prefix, `build/deps/` (see [build layout](/concepts/build-layout.md)).
3. When CPython is compiled, environment variables injected by the [`ModuleBuilder`](/architecture/module-builder.md) point its `configure`/`make` at that prefix:
   - `CPATH` → `build/deps/include`
   - `LDFLAGS` → `build/deps/lib` (and `lib64`)
   - `PKG_CONFIG_PATH`, `PATH`, `LD_LIBRARY_PATH` as needed.
4. CPython links those static archives into `libpython` and its extension `.so` files.

The `xenv_*` methods on `ModuleBuilder` are the mechanism: each returns the value for one environment variable, and they are gathered just before `configure`/`make` runs.

## No source patches

Static linking is achieved **only** through `configure`/`make` flags — never by editing upstream source. This keeps the tool maintainable as upstream versions change. See the [guiding principles](/overview.md).

## Relativization

Static linking removes runtime library dependencies, but absolute *paths* can still leak into the install (shebang lines, `sysconfig` variables). The [`Cpython`](/architecture/cpython.md) finalize step rewrites these to be relative, and [`LibAutoCorrect`](/architecture/python-inspector.md) rewrites dynamic-library references in binaries to relative form (`@loader_path`/`$ORIGIN` style). Together these make the install relocatable.

# Citations

[1] [src/portable_python/__init__.py — ModuleBuilder.xenv_* methods](https://github.com/codrsquad/portable-python/blob/main/src/portable_python/__init__.py)
[2] [src/portable_python/cpython.py — finalize / relativize steps](https://github.com/codrsquad/portable-python/blob/main/src/portable_python/cpython.py)

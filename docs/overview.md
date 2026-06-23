---
type: Overview
title: Portable Python Overview
description: A CLI and library that compiles statically-linked, relocatable CPython binaries from source, and validates their portability.
tags: [overview, cpython, portability, build]
timestamp: 2026-06-23T00:00:00Z
---

# Overview

`portable-python` compiles CPython from source into a binary that is **statically linked** and **relocatable**: the resulting tarball can be unpacked into any folder and used immediately, with no installer and no dependency on system shared libraries. It targets **Linux and macOS** (Intel and Apple Silicon). Windows is not supported.

It is both:

- A **CLI** with one entry point, `portable-python` (see [CLI](/cli/index.md)).
- A **Python library** (`from portable_python import BuildSetup`) for driving builds or inspections programmatically.

## What a build produces

```
dist/cpython-3.13.2-macos-arm64.tar.gz
```

Unpack and run, no installation step:

```shell
tar -C ~/versions/ -xf dist/cpython-3.13.2-macos-arm64.tar.gz
~/versions/3.13.2/bin/python --version
```

## How a build flows

1. **Resolve** the requested [`PythonSpec`](/architecture/build-setup.md) (family + version) and target platform via the [`PPG`](/architecture/ppg.md) singleton.
2. **Select** which [external modules](/modules/index.md) to compile, based on config and [telltale detection](/concepts/telltale-detection.md).
3. **Compile external C libraries** first (openssl, zlib, xz, …) into a shared `build/deps/` prefix — see [build layout](/concepts/build-layout.md).
4. **Compile CPython** ([`Cpython`](/architecture/cpython.md)), pointing its `configure`/`make` at `build/deps/` via injected environment variables (CPATH, LDFLAGS, …).
5. **Finalize**: clean test files, byte-compile, [relativize paths](/concepts/static-linking.md) so the install is relocatable.
6. **Validate** portability with the [`PythonInspector`](/architecture/python-inspector.md), then compress into `dist/`.

The whole pipeline is coordinated by [`BuildSetup`](/architecture/build-setup.md).

## Guiding principles

- **One job, done well.** Compile a portable python, validate it really is portable, drop the result in `dist/`.
- **No source patches.** C compilation relies solely on `configure`/`make` flags (e.g. `--enable-shared=no`), never on modifying upstream source.
- **Validated builds.** A large part of the effort is the [`inspect`](/cli/inspect.md) capability that proves an installation is portable (and explains why if it isn't).
- **Only recent, non-EOL Pythons.** No historical support; older versions are dropped without notice as the tool evolves.
- **Pure Python, testable.** No shell scripts. 100% test coverage, a `--dryrun` mode for fast iteration, and the ability to run under a debugger.

# Examples

Dry-run a build to see exactly what would happen without doing it:

```shell
portable-python --dryrun build 3.13.2
```

Inspect any existing python for portability:

```shell
portable-python inspect /usr/bin/python3
```

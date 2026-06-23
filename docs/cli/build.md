---
type: CLI Command
title: build
description: Build a portable (or --prefix) python binary from source for the given version spec.
tags: [cli, build, command]
timestamp: 2026-06-23T00:00:00Z
---

# build

Build a portable python binary. Constructs a [`BuildSetup`](/architecture/build-setup.md) and calls `compile()`.

```
portable-python build [OPTIONS] PYTHON_SPEC
```

# Schema

| Argument / Option | Purpose |
|-------------------|---------|
| `PYTHON_SPEC` (required) | Full version to build, e.g. `3.13.2` or `cpython:3.13.2`. A bare `X.Y` is rejected — give `X.Y.Z`. `latest` resolves to the newest known version. |
| `--modules, -m CSV` | External modules to include, e.g. `-m openssl,zlib`. Default comes from config + auto-selection. |
| `--prefix, -p PATH` | Build for a fixed install location. **Disables portability** — the result must live at `PATH`. |

## Output

The finished tarball lands in `dist/`, named for the family, version, platform, and arch, e.g. `dist/cpython-3.13.2-macos-arm64.tar.gz`. See [build layout](/concepts/build-layout.md).

# Examples

```shell
# Portable build, modules auto-selected from config
portable-python build 3.13.2

# Restrict to specific modules
portable-python build 3.13.2 -m openssl,zlib,xz

# Non-portable build pinned to a prefix
portable-python build 3.13.2 --prefix /apps/python3.13

# See exactly what would happen, without compiling
portable-python --dryrun build 3.13.2
```

---
type: CLI Command
title: build
description: Build a portable (or --prefix) python binary from source for the given version spec.
tags: [cli, build, command]
timestamp: 2026-06-23T00:00:00Z
---

# build

Build a portable python binary from source — constructs a [`BuildSetup`](/architecture/build-setup.md) and runs it. The output tarball lands in `dist/` (e.g. `dist/cpython-3.13.2-macos-arm64.tar.gz`; see [build layout](/concepts/build-layout.md)).

```
portable-python build [OPTIONS] PYTHON_SPEC
```

Worth knowing (`--help` for the full flag list):

- The spec must be a **full** `X.Y.Z` (a bare `3.13` is rejected); `latest` resolves to the newest known version.
- `--prefix` builds for a fixed location and **disables portability** (see [ppp-marker](/concepts/ppp-marker.md)); without it you get a relocatable build.
- `--modules/-m` overrides which [external modules](/modules/index.md) are included (default: config + auto-selection).

# Examples

```shell
portable-python build 3.13.2                           # portable, modules auto-selected
portable-python build 3.13.2 -m openssl,zlib,xz        # restrict modules
portable-python build 3.13.2 --prefix /apps/python3.13 # non-portable, fixed location
portable-python --dryrun build 3.13.2                  # show the plan, compile nothing
```

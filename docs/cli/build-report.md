---
type: CLI Command
title: build-report
description: Show the status of buildable modules — which will be auto-compiled, which are present on the system, and which would fail — without building anything.
tags: [cli, build, report, command]
timestamp: 2026-06-23T00:00:00Z
---

# build-report

Show which [modules](/modules/index.md) would be compiled for a spec, and whether the selection can actually build on this host — **without** building. The fastest way to catch a "broken" module before committing to a full compile.

```
portable-python build-report [OPTIONS] [PYTHON_SPEC]
```

For each candidate module it shows the [telltale](/concepts/telltale-detection.md) status and the linker outcome — `static` (will be compiled), `shared` (system copy used), `absent`, or `failed` (can't build here, e.g. a `-`-sigil Debian dev package is present). `PYTHON_SPEC` defaults to the latest known version.

# Examples

```shell
portable-python build-report 3.13.2
portable-python build-report 3.13.2 -m openssl,sqlite
```

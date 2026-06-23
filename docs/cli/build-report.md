---
type: CLI Command
title: build-report
description: Show the status of buildable modules — which will be auto-compiled, which are present on the system, and which would fail — without building anything.
resource: https://github.com/codrsquad/portable-python/blob/main/src/portable_python/cli.py
tags: [cli, build, report, command]
timestamp: 2026-06-23T00:00:00Z
---

# build-report

Show which modules would be compiled for a given spec, and validate that the selection can actually build on this host — without running a build. It prints the [`ModuleCollection.report()`](/architecture/python-builder.md) table and then calls `validate_module_selection()`.

```
portable-python build-report [OPTIONS] [PYTHON_SPEC]
```

# Schema

| Argument / Option | Purpose |
|-------------------|---------|
| `PYTHON_SPEC` (optional) | Version to report on; defaults to the latest known version. |
| `--modules, -m CSV` | Specific modules to check. |

## What it tells you

For each candidate module the report shows its [telltale](/concepts/telltale-detection.md) status and its `linker_outcome`: whether it will be compiled `static`, linked `shared`, is `absent`, or is `failed` (a combination that cannot build on this host — e.g. a `-`-sigil Debian dev package being present). This is the fastest way to catch a "broken" module before committing to a full build.

# Examples

```shell
portable-python build-report 3.13.2
portable-python build-report 3.13.2 -m openssl,sqlite
```

# Citations

[1] [src/portable_python/cli.py — build_report](https://github.com/codrsquad/portable-python/blob/main/src/portable_python/cli.py)

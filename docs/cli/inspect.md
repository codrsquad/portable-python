---
type: CLI Command
title: inspect
description: Inspect a python installation for non-portable dynamic library usage, reporting any references that would break portability.
resource: https://github.com/codrsquad/portable-python/blob/main/src/portable_python/cli.py
tags: [cli, inspect, portability, command]
timestamp: 2026-06-23T00:00:00Z
---

# inspect

Inspect any python installation and report whether it is [portable](/concepts/portability.md). Backed by the [`PythonInspector`](/architecture/python-inspector.md); aborts non-zero if a portability problem is found (unless `--prefix` is given).

```
portable-python inspect [OPTIONS] PATH
```

# Schema

| Argument / Option | Purpose |
|-------------------|---------|
| `PATH` (required) | Path to a python installation or interpreter. The special value `invoker` inspects the python running the CLI. |
| `--modules, -m MODULES` | Which modules to inspect (`all` to check everything). |
| `--verbose, -v` | Show the full `.so` report. |
| `--prefix, -p` | The build used `--prefix` (not portable) — relaxes the portability check accordingly. |
| `--skip-so, -s` | Don't scan every `.so` file. |

## Exit behavior

After printing the report, if scanning `.so` files (and not skipped), it asks `full_so_report.get_problem(portable=not prefix)`. A non-empty problem aborts with a non-zero exit — making `inspect` usable as a CI gate.

# Examples

```shell
# Is the system python portable? (it usually is not)
portable-python inspect /usr/bin/python3

# Full detail
portable-python inspect -v ~/versions/3.13.2

# Inspect the interpreter running this CLI
portable-python inspect invoker
```

# Citations

[1] [src/portable_python/cli.py — inspect](https://github.com/codrsquad/portable-python/blob/main/src/portable_python/cli.py)
[2] [src/portable_python/inspector.py — PythonInspector](https://github.com/codrsquad/portable-python/blob/main/src/portable_python/inspector.py)

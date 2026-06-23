---
type: CLI Command
title: inspect
description: Inspect a python installation for non-portable dynamic library usage, reporting any references that would break portability.
tags: [cli, inspect, portability, command]
timestamp: 2026-06-23T00:00:00Z
---

# inspect

Inspect any python installation and report whether it is [portable](/concepts/portability.md) — powered by the [`PythonInspector`](/architecture/python-inspector.md).

```
portable-python inspect [OPTIONS] PATH
```

Worth knowing (`--help` for the full flag list):

- It **exits non-zero** when it finds a portability problem, so it works as a CI gate.
- `PATH` can be the special value `invoker` to inspect the python running the CLI itself.
- `--prefix` says the build was pinned to a prefix (not portable), relaxing the check; `--verbose/-v` shows the full `.so` report.

# Examples

```shell
portable-python inspect /usr/bin/python3     # system python — usually NOT portable
portable-python inspect -v ~/versions/3.13.2 # full detail
portable-python inspect invoker              # the python running this CLI
```

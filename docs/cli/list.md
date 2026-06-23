---
type: CLI Command
title: list
description: List the latest available versions for a python family (default cpython), optionally as JSON.
tags: [cli, list, versions, command]
timestamp: 2026-06-23T00:00:00Z
---

# list

List the latest available versions for a [version family](/architecture/ppg.md) (default `cpython`).

```
portable-python list [OPTIONS] [FAMILY]
```

Versions are fetched lazily from the network (python.org, or GitHub tags when `cpython-use-github` is set) and cached, so the first run may pause briefly. `--json` emits machine-readable output.

# Examples

```shell
portable-python list
portable-python list cpython --json
```

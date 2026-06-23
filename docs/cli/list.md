---
type: CLI Command
title: list
description: List the latest available versions for a python family (default cpython), optionally as JSON.
resource: https://github.com/codrsquad/portable-python/blob/main/src/portable_python/cli.py
tags: [cli, list, versions, command]
timestamp: 2026-06-23T00:00:00Z
---

# list

List the latest available versions for a [version family](/architecture/ppg.md). Versions are fetched lazily (from `python.org/ftp`, or GitHub tags when `cpython-use-github` is configured) and cached.

```
portable-python list [OPTIONS] [FAMILY]
```

# Schema

| Argument / Option | Purpose |
|-------------------|---------|
| `FAMILY` (optional) | Family to list; defaults to `cpython`. Unknown families abort with a message. |
| `--json` | Emit the available versions as JSON instead of a table. |

# Examples

```shell
portable-python list
portable-python list cpython --json
```

# Citations

[1] [src/portable_python/cli.py — list_cmd](https://github.com/codrsquad/portable-python/blob/main/src/portable_python/cli.py)
[2] [src/portable_python/versions.py — CPythonFamily.get_available_versions](https://github.com/codrsquad/portable-python/blob/main/src/portable_python/versions.py)

---
type: CLI Command
title: lib-auto-correct
description: Scan a python installation and rewrite executables/libraries to use relative paths — the same relativization the build applies internally, runnable standalone.
resource: https://github.com/codrsquad/portable-python/blob/main/src/portable_python/cli.py
tags: [cli, lib-auto-correct, relativize, command]
timestamp: 2026-06-23T00:00:00Z
---

# lib-auto-correct

Scan a python installation and auto-correct its executables and libraries to reference dependencies by **relative** path. This exercises the [`LibAutoCorrect`](/architecture/python-inspector.md) logic that the build runs internally — handy for iterating on relativization without waiting for a full build.

```
portable-python lib-auto-correct [OPTIONS] PATH
```

# Schema

| Argument / Option | Purpose |
|-------------------|---------|
| `PATH` (required) | The python installation to scan. |
| `--commit` | Actually perform the changes. Without it, the command runs in dry-run mode. |
| `--prefix, -p PATH` | The `--prefix` the program was built with. Defaults to the scanned python's own `sysconfig` prefix. |

By default this is **dry-run**: it shows what it would rewrite. Pass `--commit` to apply the changes. See [static linking](/concepts/static-linking.md) for why relativization is needed.

# Examples

```shell
# Preview corrections (dry-run)
portable-python lib-auto-correct ~/versions/3.13.2

# Apply them
portable-python lib-auto-correct --commit ~/versions/3.13.2
```

# Citations

[1] [src/portable_python/cli.py — lib_auto_correct](https://github.com/codrsquad/portable-python/blob/main/src/portable_python/cli.py)
[2] [src/portable_python/inspector.py — LibAutoCorrect](https://github.com/codrsquad/portable-python/blob/main/src/portable_python/inspector.py)

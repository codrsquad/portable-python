---
type: CLI Command
title: lib-auto-correct
description: Scan a python installation and rewrite executables/libraries to use relative paths — the same relativization the build applies internally, runnable standalone.
tags: [cli, lib-auto-correct, relativize, command]
timestamp: 2026-06-23T00:00:00Z
---

# lib-auto-correct

Rewrite a python installation's executables and libraries to reference their dependencies by **relative** path — the same [`LibAutoCorrect`](/architecture/python-inspector.md) step the build runs internally, exposed standalone so you can iterate on relativization without a full rebuild. See [static linking](/concepts/static-linking.md) for why it's needed.

```
portable-python lib-auto-correct [OPTIONS] PATH
```

It is **dry-run by default** — it shows what it would rewrite; pass `--commit` to actually apply the changes. `--prefix` overrides the build prefix (default: the scanned python's own `sysconfig` prefix).

# Examples

```shell
portable-python lib-auto-correct ~/versions/3.13.2          # preview (dry-run)
portable-python lib-auto-correct --commit ~/versions/3.13.2 # apply
```

---
type: CLI Command
title: recompress
description: Re-compress an existing binary tarball or folder into another format, mainly to compare resulting sizes.
tags: [cli, recompress, command]
timestamp: 2026-06-23T00:00:00Z
---

# recompress

Re-compress an existing build (folder or tarball) into a different compression format. Mildly useful for comparing the size trade-offs of different compressions.

```
portable-python recompress PATH EXT
```

# Schema

| Argument | Purpose |
|----------|---------|
| `PATH` (required) | An existing folder or tarball. Resolved against the configured base/build/dist/destdir folders if not absolute. |
| `EXT` (required) | Target compression extension. Constrained to the platform's `supported_compression` choices. |

After re-compressing, the command prints the size of both the source and the result so they can be compared.

# Examples

```shell
portable-python recompress dist/cpython-3.13.2-linux-x86_64.tar.gz tar.zst
```

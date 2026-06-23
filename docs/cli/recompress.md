---
type: CLI Command
title: recompress
description: Re-compress an existing binary tarball or folder into another format, mainly to compare resulting sizes.
tags: [cli, recompress, command]
timestamp: 2026-06-23T00:00:00Z
---

# recompress

Re-compress an existing build (folder or tarball) into a different format and print the before/after sizes — handy for comparing compression trade-offs. A utility, not part of a normal build.

```
portable-python recompress PATH EXT
```

`PATH` is an existing folder or tarball (resolved against the configured build/dist folders if relative); `EXT` is the target compression, limited to the platform's supported formats (`--help` lists them).

# Examples

```shell
portable-python recompress dist/cpython-3.13.2-linux-x86_64.tar.gz tar.zst
```

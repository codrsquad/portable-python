---
type: CLI Command
title: diagnostics
description: Show system diagnostics (invoker python, platform info) alongside the active configuration.
resource: https://github.com/codrsquad/portable-python/blob/main/src/portable_python/cli.py
tags: [cli, diagnostics, command]
timestamp: 2026-06-23T00:00:00Z
---

# diagnostics

Print system diagnostics next to the resolved [configuration](/architecture/config.md), as a two-column table. Useful when a build behaves unexpectedly and you need to confirm which config files and platform are in effect.

```
portable-python diagnostics
```

# Schema

Takes no arguments. The left column comes from `runez.SYS_INFO` (invoker python, platform, etc.); the right column is `PPG.config.represented()` — the merged config and the files it was loaded from.

# Citations

[1] [src/portable_python/cli.py — diagnostics](https://github.com/codrsquad/portable-python/blob/main/src/portable_python/cli.py)

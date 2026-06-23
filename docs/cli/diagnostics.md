---
type: CLI Command
title: diagnostics
description: Show system diagnostics (invoker python, platform info) alongside the active configuration.
tags: [cli, diagnostics, command]
timestamp: 2026-06-23T00:00:00Z
---

# diagnostics

Print system diagnostics next to the resolved [configuration](/architecture/config.md). Reach for it when a build behaves unexpectedly and you want to confirm which config files and target platform are actually in effect.

```
portable-python diagnostics
```

It shows the invoker python and platform info on one side, and the merged config — plus the files it was loaded from — on the other.

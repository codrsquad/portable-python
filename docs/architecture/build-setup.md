---
type: Class
title: BuildSetup
description: Orchestrates a build end to end — resolves the spec, builds external modules then CPython, validates, and compresses the result.
tags: [class, build, coordinator]
timestamp: 2026-06-23T00:00:00Z
---

# BuildSetup

The build orchestrator (`__init__.py`). The [`build`](/cli/build.md) command — and library users — construct one from a python spec and call `compile()`:

```python
from portable_python import BuildSetup

BuildSetup("cpython:3.13.2").compile()
```

## Mental model

A conductor: it compiles nothing itself, it sequences the pieces. `compile()` is the spine — it cleans the [build folders](/concepts/build-layout.md), enters a [`BuildContext`](/concepts/folder-masking.md) (macOS isolation), builds the [external modules](/modules/index.md) into `build/deps/`, then builds CPython through its [`PythonBuilder`](/architecture/python-builder.md) (a [`Cpython`](/architecture/cpython.md)), and finally compresses the install into `dist/`. **External libraries first, CPython last.**

It owns the [`Folders`](/architecture/config.md) (resolved paths) and the python builder; shared config, target platform, and version family come from [`PPG`](/architecture/ppg.md).

## Worth knowing

- **Start reading at `compile()`** — it calls everything else in order.
- A `--prefix` makes the build **non-portable**; without it the result is relocatable (see [ppp-marker](/concepts/ppp-marker.md) and [portability](/concepts/portability.md)).
- It requires a full `X.Y.Z` spec — a bare `3.13` is rejected; `"latest"` (or empty) resolves to the newest known version.

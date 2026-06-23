---
type: Playbook
title: Fix a Portability Issue
description: Diagnose a non-portable build with inspect, then fix it by selecting the right module or relativizing lib references.
tags: [playbook, portability, inspect, debugging]
timestamp: 2026-06-23T00:00:00Z
---

# Fix a Portability Issue

When a built python is flagged as non-[portable](/concepts/portability.md) — a dynamic dependency on a non-system library, or an absolute path baked in:

## Steps

1. **Diagnose** — run [`portable-python inspect <PATH>`](/cli/inspect.md) to see exactly which `.so` or executable carries the offending reference, via the [`PythonInspector`](/architecture/python-inspector.md).
2. **If a library is being dynamically linked** — make sure its [external module](/modules/index.md) is selected so it gets compiled statically, or tighten build isolation so `configure` can't discover the system copy. On macOS check the [folder mask](/concepts/folder-masking.md); see also [telltale detection](/concepts/telltale-detection.md).
3. **If an absolute path is baked in** — the [`LibAutoCorrect`](/architecture/python-inspector.md) logic rewrites lib references to relative form. Run [`lib-auto-correct`](/cli/lib-auto-correct.md) to reproduce/iterate on it standalone, and extend it if a new case isn't handled.
4. **Add a test case** in `tests/test_inspector.py`.

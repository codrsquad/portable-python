---
type: Class
title: PythonInspector
description: Validates the portability of a python installation by parsing the dynamic-library dependencies of every executable and .so, and reporting any non-portable references.
tags: [class, inspection, validation, portability]
timestamp: 2026-06-23T00:00:00Z
---

# PythonInspector

`PythonInspector` (in `inspector.py`) answers the question the whole project is built around: *is this python installation [portable](/concepts/portability.md), and if not, why not?* It powers the [`inspect`](/cli/inspect.md) command and the post-build validation in [`BuildSetup.compile()`](/architecture/build-setup.md).

```python
from portable_python.inspector import PythonInspector

inspector = PythonInspector("/usr/bin/python3")
print(inspector.represented())
problem = inspector.full_so_report.get_problem(portable=True)
if problem:
    print("not portable: %s" % problem)
```

# Schema

| Member | Kind | Purpose |
|--------|------|---------|
| `__init__(spec, modules)` | constructor | Resolve the python to inspect and the module set to report. |
| `full_so_report` | property (`FullSoReport`) | Aggregated scan of every `.so`/executable and its lib references. |
| `module_info` | property | Per-module info (versions, extra detail). |
| `represented(verbose)` | method | Render the human-readable report. |
| `get_problem(portable)` | method (on `FullSoReport`) | Return a description of the first portability problem, or empty if clean. |

## Supporting types

| Type | Role |
|------|------|
| `SoInfo` | One `.so`/executable; parses `ldd` (Linux) / `otool` (macOS) output into references. |
| `CLibInfo` | One referenced C library, classified by `LibType`. |
| `LibType` | Enum classifying a reference (system, relative/self, problematic, …). |
| `FullSoReport` | The complete scan and its `get_problem()` verdict. |
| `LibAutoCorrect` | Rewrites absolute lib references in binaries to **relative** form (`@loader_path` / `$ORIGIN`), making an install relocatable. Exposed via [`lib-auto-correct`](/cli/lib-auto-correct.md). |
| `Tracker` / `Trackable` | Categorize the found objects (libs, problems) by type and render the detailed reports (`tracking.py`); `SoInfo` and `CLibInfo` are `Trackable`. |

## How it detects problems

For each binary it lists dynamic dependencies, then classifies every reference:

- **System / standard** library → acceptable.
- **Relative / self** reference → acceptable (this is what `LibAutoCorrect` produces).
- **Absolute, non-system** reference → a portability problem; for a portable build this fails the inspection.

`LibAutoCorrect` is also used **during** the build's finalize step to convert references to relative form before the portable check runs.

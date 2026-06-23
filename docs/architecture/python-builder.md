---
type: Class
title: PythonBuilder
description: A ModuleBuilder specialization for python implementations — adds module selection, the python install layout, and helpers to run the freshly built interpreter.
tags: [class, abstract, python, build]
timestamp: 2026-06-23T00:00:00Z
---

# PythonBuilder

`PythonBuilder` extends [`ModuleBuilder`](/architecture/module-builder.md) with behavior specific to building a python interpreter. It is still abstract — the concrete implementation is [`Cpython`](/architecture/cpython.md). Defined in `__init__.py`.

# Schema

| Member | Kind | Purpose |
|--------|------|---------|
| `modules` | attribute (`ModuleCollection`) | The external modules selected/available for this build. |
| `selected_modules()` | method | Builds the `ModuleCollection` from candidates + the desired list. |
| `bin_python` | property | Path to the built interpreter (`.../bin/python`). |
| `version` | property | The python version being built. |
| `validate_setup()` | method | Pre-flight checks before compilation begins. |
| `run_python(*args)` | method | Invoke the freshly built interpreter (used during finalize/validation). |
| `xenv_LDFLAGS()` | method | Python-specific linker flags layered on the base `ModuleBuilder` behavior. |
| `_prepare()` | method | Hook run before the platform compile. |

## ModuleCollection

A `PythonBuilder` owns a `ModuleCollection`, which models the set of candidate external modules and resolves which are actually built:

- `candidates` — every possible module for this builder (from `candidate_modules()`).
- `selected` — only the modules chosen for *this* build (config + `--modules` + auto-selection). This is the list that actually gets compiled.
- `auto_selected` — modules force-selected because a build can't succeed without them (each module's `auto_select_reason()`).
- `report()` / `report_rows()` — the human-readable table shown by [`build-report`](/cli/build-report.md).

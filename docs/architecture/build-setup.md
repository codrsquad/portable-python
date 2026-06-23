---
type: Class
title: BuildSetup
description: Coordinates the overall compilation — resolves the python spec, prepares folders, builds external modules then CPython, validates, and compresses the result.
tags: [class, build, coordinator]
timestamp: 2026-06-23T00:00:00Z
---

# BuildSetup

`BuildSetup` drives a build from end to end. The CLI's [`build`](/cli/build.md) command (and library users) construct one and call `compile()`. Defined in `__init__.py`.

```python
from portable_python import BuildSetup

setup = BuildSetup("cpython:3.13.2")
setup.compile()
```

# Schema

| Member | Kind | Purpose |
|--------|------|---------|
| `__init__(python_spec, modules, prefix)` | constructor | Resolve the [`PythonSpec`](/cli/build.md), set up [`Folders`](/architecture/config.md), pick the extension, and instantiate the family's `python_builder`. |
| `python_spec` | attribute | The resolved family + version (full `X.Y.Z` required). |
| `folders` | attribute (`Folders`) | Resolved build/dist/sources/logs/destdir paths. |
| `prefix` | attribute | Optional `--prefix`; when set the build is **not** [portable](/concepts/portability.md). |
| `tarball_name` | attribute | Composed output name, e.g. `cpython-3.13.2-macos-arm64.tar.gz`. |
| `python_builder` | attribute (`PythonBuilder`) | The concrete builder, e.g. [`Cpython`](/architecture/cpython.md). |
| `validate_module_selection(fatal)` | method | Check every selected/candidate module's `linker_outcome`; abort on a `failed` outcome. |
| `compile()` | method | The full pipeline (see below). |

## The `compile()` pipeline

1. **Clean** the build folder (and logs); set up file logging to `logs/00-portable-python.log`.
2. `python_builder.validate_setup()`.
3. Enter a [`BuildContext`](/concepts/folder-masking.md) — applies macOS `/usr/local` masking and other isolation.
4. Log the platform, config files in use, and the build report.
5. `validate_module_selection()` (fatal unless dry-run / debug).
6. Clean `components/` and `deps/`.
7. `build_context.compile()` then `python_builder.compile()` — external modules first, then CPython.
8. If a `dist/` folder is configured, **compress** the install into `dist/{tarball_name}`.

## Spec validation

`BuildSetup` insists on a **full** version: a spec like `3.13` is rejected — you must give `3.13.2`. `"latest"` (or empty) resolves to `PPG.cpython.latest`. Invalid specs abort early with a red error.

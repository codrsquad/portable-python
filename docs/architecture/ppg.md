---
type: Class
title: PPG
description: Global singleton holding shared configuration, the target platform, and the registry of supported python version families.
resource: https://github.com/codrsquad/portable-python/blob/main/src/portable_python/versions.py
tags: [class, global-state, singleton, versions]
timestamp: 2026-06-23T00:00:00Z
---

# PPG

`PPG` is the global state holder for portable-python. Every module reaches shared state — configuration, the target platform, and version families — through `PPG`'s class attributes and classmethods. It is defined in `versions.py`.

# Schema

| Member | Kind | Purpose |
|--------|------|---------|
| `config` | attribute (`Config`) | The active merged [configuration](/architecture/config.md). |
| `target` | attribute (`PlatformId`) | Target OS/arch; drives platform dispatch and telltale expansion. |
| `families` | attribute (`dict`) | Registry mapping family name → `VersionFamily` (default: `{"cpython": ...}`). |
| `cpython` | attribute (`CPythonFamily`) | The built-in CPython family implementation. |
| `grab_config(paths, target)` | classmethod | (Re)load config from the given paths and set `target`. Called by the CLI's `main`. |
| `get_folders(base, family, version, abi_suffix)` | classmethod | Build a [`Folders`](/architecture/config.md) for a given family/version. |
| `family(name, fatal=True)` | classmethod | Look up a `VersionFamily` by name. |
| `find_python(spec)` | classmethod | Resolve a python on `PATH` via a cached `runez` `PythonDepot`. |
| `find_telltale(*telltales)` | classmethod | Expand `{include}` placeholders against `target.sys_include` and return the first existing path. See [telltale detection](/concepts/telltale-detection.md). |

## Version families

A `VersionFamily` (e.g. `CPythonFamily`) knows how to **list available versions** and **provide a builder**:

- `available_versions` / `latest` — lazily fetched and cached (CPython fetches from `python.org/ftp`, or GitHub tags when `cpython-use-github` is set). This lazy fetch is why [`list`](/cli/list.md) hits the network on first use.
- `get_builder()` — returns the concrete builder class ([`Cpython`](/architecture/cpython.md) for the cpython family).
- `min_version` — earliest non-EOL version known to compile well (currently `3.9`).

## Why a singleton

The build touches global, process-wide facts: which config file is active, what platform we are targeting, and which python versions exist. Centralizing them in `PPG` avoids threading that state through every constructor, and gives the CLI a single place ([`main`](/cli/index.md)) to initialize it.

# Citations

[1] [src/portable_python/versions.py](https://github.com/codrsquad/portable-python/blob/main/src/portable_python/versions.py)
[2] [CLAUDE.md — Key classes](https://github.com/codrsquad/portable-python/blob/main/CLAUDE.md)

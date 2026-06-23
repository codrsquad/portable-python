---
type: Class
title: Config & Folders
description: Config loads and merges YAML configuration with platform-specific overrides; Folders resolves the templated build/dist/sources paths.
resource: https://github.com/codrsquad/portable-python/blob/main/src/portable_python/config.py
tags: [class, configuration, folders, yaml]
timestamp: 2026-06-23T00:00:00Z
---

# Config & Folders

`Config` (in `config.py`) loads, merges, and queries the YAML [configuration](/configuration/portable-python-yml.md). `Folders` (in `versions.py`) turns templated path settings into concrete filesystem paths. Both are reached through [`PPG`](/architecture/ppg.md).

# Schema

## Config

| Member | Purpose |
|--------|---------|
| `__init__(paths, target)` | Layer the built-in `DEFAULT_CONFIG` under any user config files, for the given target platform. |
| `get_value(*key, by_platform=True)` | Fetch a config value, honoring platform-specific overrides (most specific wins). |
| `get_entry(*key, by_platform=True)` | Like `get_value` but returns the raw entry. |
| `resolved_path(*key)` | Fetch a value and resolve it to a path. |
| `config_files_report()` / `represented()` | Human-readable summary of which config files are in effect (used by [`diagnostics`](/cli/diagnostics.md)). |
| `cleanup_globs(...)` / `symlink_duplicates(...)` / `ensure_main_file_symlinks(...)` | Finalize-time file housekeeping in the install. |

## Folders

| Member | Purpose |
|--------|---------|
| `build_folder`, `components`, `deps`, `sources`, `logs`, `dist`, `destdir` | Resolved component paths — see [build layout](/concepts/build-layout.md). |
| `ppp-marker` | Template for the in-progress install folder name. |
| `formatted(text)` | Expand `{build}`, `{version}`, `{abi_suffix}`, … placeholders. |
| `resolved_destdir(relative_path)` | Compose a path under the marker'd destdir. |

## Precedence & overrides

Configuration merges multiple sources. The built-in `DEFAULT_CONFIG` provides sane defaults; user files (default `portable-python.yml`, plus any `include:`d files) layer on top. Within a file, **platform-specific** sections override generic ones:

```yaml
ext: gz            # generic default
windows:
  ext: zip         # used only when targeting windows
macos:
  env:
    MACOSX_DEPLOYMENT_TARGET: 13
```

`get_value(..., by_platform=True)` returns the most specific match for the current `PPG.target`.

# Citations

[1] [src/portable_python/config.py — Config, DEFAULT_CONFIG](https://github.com/codrsquad/portable-python/blob/main/src/portable_python/config.py)
[2] [src/portable_python/versions.py — Folders](https://github.com/codrsquad/portable-python/blob/main/src/portable_python/versions.py)
[3] [CONFIGURATION.md](https://github.com/codrsquad/portable-python/blob/main/CONFIGURATION.md)

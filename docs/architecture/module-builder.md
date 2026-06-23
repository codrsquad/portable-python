---
type: Class
title: ModuleBuilder
description: Abstract base for everything that gets compiled — external C libraries and CPython itself — providing the common download/configure/make/install flow and environment injection.
resource: https://github.com/codrsquad/portable-python/blob/main/src/portable_python/__init__.py
tags: [class, abstract, build, module]
timestamp: 2026-06-23T00:00:00Z
---

# ModuleBuilder

`ModuleBuilder` is the abstract base for anything compiled by the tool. Both [external C modules](/modules/index.md) and [`PythonBuilder`](/architecture/python-builder.md) (hence [`Cpython`](/architecture/cpython.md)) extend it, so every component shares the same [build layout](/concepts/build-layout.md) and flow.

# Schema

## Declarative class attributes

| Attribute | Purpose |
|-----------|---------|
| `m_name` | Module name (derived from the class name). |
| `m_telltale` | Marker file(s) indicating the lib is present on the system. See [telltale detection](/concepts/telltale-detection.md). |
| `m_debian` | Debian dev package, with `!` / `+` / `-` sigils encoding build constraints. |
| `m_include` | Optional subfolder to add to `CPATH` when active (e.g. `openssl`). |
| `m_build_cwd` | Optional subfolder (relative to unpacked source) to run configure/make from. |

## Source resolution (overridable)

| Member | Purpose |
|--------|---------|
| `url` | Download URL of the source tarball. |
| `version` | Version to build (default per module, overridable via config). |
| `headers` / `src_suffix` | HTTP headers and archive suffix when the URL lacks an extension. |
| `cfg_version`, `cfg_url`, `cfg_configure`, `cfg_patches`, `cfg_http_headers` | Read per-module overrides from [config](/configuration/portable-python-yml.md) (keys like `openssl-version`, `openssl-url`, …). |

## Environment injection (`xenv_*`)

Each `xenv_*` method supplies one environment variable for the compile, pointing tools at the shared `deps/` prefix — the mechanism behind [static linking](/concepts/static-linking.md):

`xenv_CPATH`, `xenv_LDFLAGS`, `xenv_PATH`, `xenv_LD_LIBRARY_PATH`, `xenv_PKG_CONFIG_PATH`. `_find_all_env_vars()` gathers every `xenv_*` on the instance just before running.

## Build flow

| Method | Role |
|--------|------|
| `compile()` | Download → unpack → patch → `_prepare()` → platform compile → `_finalize()`. |
| `run_configure(program, *args, prefix)` | Run `./configure` with the deps prefix. |
| `run_make(*args, cpu_count)` | Run `make` (parallelized by CPU count). |
| `_do_linux_compile()` / `_do_macos_compile()` | Platform-specific compile, dispatched by `PPG.target`. |
| `linker_outcome(is_selected)` | Decide `static` / `shared` / `absent` / `failed` for this module. |
| `captured_logs()` | Context manager routing this module's output to its own numbered log file. |

## Adding a module

To add a new external module you subclass `ModuleBuilder`, set the `m_*` attributes, implement `url`/`version`, and implement `_do_linux_compile()` (macOS reuses it unless overridden). See the [guide](/guides/add-an-external-module.md).

# Citations

[1] [src/portable_python/__init__.py — ModuleBuilder](https://github.com/codrsquad/portable-python/blob/main/src/portable_python/__init__.py)
[2] [src/portable_python/external/xcpython.py — concrete modules](https://github.com/codrsquad/portable-python/blob/main/src/portable_python/external/xcpython.py)

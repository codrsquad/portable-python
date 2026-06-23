---
type: Class
title: Cpython
description: The concrete PythonBuilder that compiles CPython — configure/make/install, optimization flags, and the finalize step that makes the install relocatable.
tags: [class, cpython, build, finalize]
timestamp: 2026-06-23T00:00:00Z
---

# Cpython

`Cpython` is the concrete [`PythonBuilder`](/architecture/python-builder.md) that actually compiles CPython. It is returned by `CPythonFamily.get_builder()` (see [`PPG`](/architecture/ppg.md)) and lives in `cpython.py`.

# Schema

| Member | Kind | Purpose |
|--------|------|---------|
| `candidate_modules()` | classmethod | The external modules CPython can statically link (the [external modules](/modules/index.md) set). |
| `url` | property | CPython source URL (`python.org/ftp/...Python-X.Y.Z.tar.xz`), overridable via config. |
| `c_configure_args()` | method | Assemble `./configure` args (from `cpython-configure` config + computed flags). |
| `has_configure_opt(name, *variants)` | method | Test whether a configure option is in effect. |
| `xenv_LDFLAGS_NODIST`, `xenv_LIBZSTD_*`, `xenv_LIBMPDEC_*` | methods | Environment for linking specific static deps (zstd, mpdec). |
| `_do_linux_compile()` | method | configure → make → make install (DESTDIR). |
| `_finalize()` | method | Clean, byte-compile, relativize — see below. |

## Configure arguments

CPython is configured with, by default, `--enable-optimizations`, `--with-lto`, and `--with-ensurepip=upgrade` (from `cpython-configure` in [config](/configuration/portable-python-yml.md)), plus computed flags pointing at the static deps. Following the [no-patches principle](/overview.md), **all** behavior comes from configure flags — never source edits.

## Finalize: making it relocatable

After `make install` the `_finalize()` step is what turns a normal install into a [portable](/concepts/portability.md) one. For a portable build the interpreter's prefix is still the placeholder [`/ppp-marker/{version}`](/concepts/ppp-marker.md), so finalize rewrites those baked-in absolute paths to be relative:

- **Clean passes** — remove tests/idle/2to3 before byte-compiling (`cpython-clean-1st-pass`, ~94 MB) and prune seldom-used pycaches after (`cpython-clean-2nd-pass`, ~1.8 MB).
- **Byte-compile** the standard library (`cpython-compile-all`).
- `_relativize_shebangs()` — rewrite `bin/` script shebangs to be relative.
- `_relativize_sysconfig()` (`RelSysConf`) — rewrite absolute paths in the `sysconfig` data so the install resolves relative to its own location.
- `_apply_pep668()` — mark the environment per PEP 668.
- `_validate_venv_creation()` / `_validate_venv_module()` — sanity-check that `venv` works in the finished build.

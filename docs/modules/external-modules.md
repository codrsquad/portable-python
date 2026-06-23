---
type: Reference
title: External Modules Reference
description: The C libraries compiled and statically linked into CPython, with default versions, telltale markers, and Linux build constraints.
resource: https://github.com/codrsquad/portable-python/blob/main/src/portable_python/external/xcpython.py
tags: [reference, modules, external, cpython]
timestamp: 2026-06-23T00:00:00Z
---

# External Modules Reference

These are the candidate external modules for CPython, in the order declared by `Cpython.candidate_modules()`. Each is a [`ModuleBuilder`](/architecture/module-builder.md) that compiles a C library statically into the shared `build/deps/` prefix before CPython is built. Default versions are overridable via [config](/configuration/portable-python-yml.md) (e.g. `openssl-version`).

# Schema

| Module | CPython feature | Default version | Telltale (`{include}/…`) | Linux dev pkg |
|--------|-----------------|-----------------|--------------------------|----------------|
| `LibFFI` | `ctypes` | 3.5.2 | `ffi.h`, `ffi/ffi.h` | `!libffi-dev` |
| `Zlib` | `zlib` | 1.3.2 | `zlib.h` | `!zlib1g-dev` |
| `Zstd` | compression (zstd) | 1.5.7 | `zstd.h` | `!libzstd-dev` |
| `Xz` | `lzma` | 5.8.3 | `lzma.h` | — |
| `Bzip2` | `bz2` | 1.0.8 | `bzlib.h` | — |
| `Readline` | `readline` | 8.3 | `readline/readline.h` | `-libreadline-dev` |
| `Openssl` | `ssl`, `hashlib` | 3.5.6 | `openssl/ssl.h` | — |
| `Sqlite` | `sqlite3` | 3.51.3 | `sqlite3.h` | `+libsqlite3-dev` |
| `Bdb` | `dbm.ndbm` | 6.2.32 | `dbm.h` | `libgdbm-compat-dev` |
| `Gdbm` | `dbm.gnu` | 1.26 | `gdbm.h` | `libgdbm-dev` |
| `Uuid` | `uuid` | 1.0.3 | `uuid/uuid.h` | `+uuid-dev` |
| `TkInter` | `tkinter` | 8.6.17 | `tk`, `tk.h` | `-tk-dev` |
| `Mpdec` | `decimal` | 4.0.1 | `mpdecimal.h` | `!libmpdec-dev` |

## Linux dev-package sigils

The leading character on the Debian package encodes a build constraint (see [telltale detection](/concepts/telltale-detection.md)):

| Sigil | Meaning |
|-------|---------|
| `!` | Required to compile **at all** (`LibFFI`, `Zlib`, `Zstd`, `Mpdec`). |
| `+` | Required when the module is **selected** for static compile (`Sqlite`, `Uuid`). |
| `-` | Dev package's presence **breaks** static compilation (`Readline`, `TkInter`). |
| (none) | Detection/reporting only. |

## Sub-modules and toolchain

Some modules bundle their own dependencies as sub-modules (their `candidate_modules()`):

- `Readline` → `Ncurses` (`ncursesw`).
- `TkInter` → `Tcl`, `Tk`, `Tix` (defined in `external/xtkinter.py`).
- A separate `Toolchain` builds `GettextTiny` to prevent `libintl` from being picked up out of `/usr/local` — complementing the macOS [folder mask](/concepts/folder-masking.md).

## Per-module config

Every module honors these config keys (replace `{module}` with the lowercased name, e.g. `openssl`): `{module}-version`, `{module}-url`, `{module}-src-suffix`, `{module}-configure`, `{module}-http-headers`, `{module}-patches`. See [configuration](/configuration/portable-python-yml.md).

# Citations

[1] [src/portable_python/external/xcpython.py](https://github.com/codrsquad/portable-python/blob/main/src/portable_python/external/xcpython.py)
[2] [src/portable_python/external/xtkinter.py](https://github.com/codrsquad/portable-python/blob/main/src/portable_python/external/xtkinter.py)
[3] [src/portable_python/cpython.py — Cpython.candidate_modules](https://github.com/codrsquad/portable-python/blob/main/src/portable_python/cpython.py)

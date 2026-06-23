---
type: Reference
title: External Modules Reference
description: The C libraries compiled and statically linked into CPython, with their telltale markers and Linux build constraints.
tags: [reference, modules, external, cpython]
timestamp: 2026-06-23T00:00:00Z
---

# External Modules Reference

These are the candidate external modules for CPython, in the order declared by `Cpython.candidate_modules()`. Each is a [`ModuleBuilder`](/architecture/module-builder.md) that compiles a C library statically into the shared `build/deps/` prefix before CPython is built.

Default versions are intentionally **not** listed here, to avoid drifting from the code: each module's default is the `cfg_version()` default in its source class (overridable via the `{module}-version` [config](/configuration/portable-python-yml.md) key). To see the versions that would actually be used for a build, run [`build-report`](/cli/build-report.md).

# Schema

| Module | CPython feature | Telltale (`{include}/…`) | Linux dev pkg |
|--------|-----------------|--------------------------|----------------|
| `LibFFI` | `ctypes` | `ffi.h`, `ffi/ffi.h` | `!libffi-dev` |
| `Zlib` | `zlib` | `zlib.h` | `!zlib1g-dev` |
| `Zstd` | compression (zstd) | `zstd.h` | `!libzstd-dev` |
| `Xz` | `lzma` | `lzma.h` | — |
| `Bzip2` | `bz2` | `bzlib.h` | — |
| `Readline` | `readline` | `readline/readline.h` | `-libreadline-dev` |
| `Openssl` | `ssl`, `hashlib` | `openssl/ssl.h` | — |
| `Sqlite` | `sqlite3` | `sqlite3.h` | `+libsqlite3-dev` |
| `Bdb` | `dbm.ndbm` | `dbm.h` | `libgdbm-compat-dev` |
| `Gdbm` | `dbm.gnu` | `gdbm.h` | `libgdbm-dev` |
| `Uuid` | `uuid` | `uuid/uuid.h` | `+uuid-dev` |
| `TkInter` | `tkinter` | `tk`, `tk.h` | `-tk-dev` |
| `Mpdec` | `decimal` | `mpdecimal.h` | `!libmpdec-dev` |

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

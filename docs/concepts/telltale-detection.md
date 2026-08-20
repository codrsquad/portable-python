---
type: Concept
title: Telltale Detection
description: Modules check for marker header files to determine whether a library is already present on the system, which drives whether it is compiled statically, linked dynamically, or skipped.
tags: [telltale, concept, module-selection]
timestamp: 2026-06-23T00:00:00Z
---

# Telltale Detection

Before compiling, the tool must decide, for each candidate [external module](/modules/index.md), whether the library is already available on the build host. It does this by looking for a **telltale** — a marker file (usually a development header) whose presence indicates the system has that library installed.

## The `m_telltale` attribute

Each [`ModuleBuilder`](/architecture/module-builder.md) subclass declares `m_telltale`, a path (or list of paths) using an `{include}` placeholder that is expanded against the target's system include directories:

```python
class Openssl(ModuleBuilder):
    m_telltale = "{include}/openssl/ssl.h"


class Sqlite(ModuleBuilder):
    m_telltale = ["{include}/sqlite3.h"]
```

`PPG.find_telltale()` expands the placeholder against each `target.sys_include` directory and returns the first existing path, or `None`.

## Linker outcome

The telltale result, combined with whether the module was *selected* and the platform, feeds `ModuleBuilder.linker_outcome()`, which classifies the module as one of:

| Outcome | Meaning |
|---------|---------|
| `static` | Will be compiled and statically linked. |
| `shared` | Present on system, will be dynamically linked (only acceptable for non-portable / system libs). |
| `absent` | Not present and not selected — skipped. |
| `failed` | A configuration that cannot succeed (see Debian markers below). |

## Debian markers (`m_debian`)

On Linux, `m_debian` names the Debian dev package and a leading sigil encodes a build constraint:

| Prefix | Meaning | Example |
|--------|---------|---------|
| `!` | Required to compile **at all** — build is broken without it. | `!zlib1g-dev`, `!libffi-dev` |
| `+` | Required when the module is **selected** for static compile. | `+libsqlite3-dev`, `+uuid-dev` |
| `-` | Presence of the dev package **breaks** static compilation. | `-libreadline-dev`, `-tk-dev` |
| (none) | Used for detection/reporting only. | `libgdbm-dev` |

This is why [`build-report`](/cli/build-report.md) can warn that a module is "broken" on the current host before a build is even attempted.

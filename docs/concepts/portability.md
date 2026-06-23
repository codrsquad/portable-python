---
type: Concept
title: Portability
description: A python installation is portable when it can be unpacked into any folder and run without depending on non-standard system shared libraries.
tags: [portability, concept, validation]
timestamp: 2026-06-23T00:00:00Z
---

# Portability

A python installation is **portable** when it can be copied or unpacked into an arbitrary folder and used as-is, without:

- An installer or post-install step.
- A dependency on shared libraries that may be absent (or a different version) on the target machine.
- Hard-coded absolute paths baked into binaries, scripts, or `sysconfig`.

Portability is the central guarantee of this project. Two design choices deliver it:

1. **[Static linking](/concepts/static-linking.md)** of dependencies, so the binary carries what it needs rather than loading it from the system at runtime.
2. **Path relativization**, so shebangs and `sysconfig` values resolve relative to the install folder instead of an absolute build-time prefix.

## Portable vs `--prefix` builds

The tool can produce two kinds of output:

| Build kind | Description | Relocatable? |
|------------|-------------|--------------|
| Portable (default) | Statically linked, paths relativized | Yes — run from anywhere |
| `--prefix PATH` | Built to live at a fixed location (e.g. `/apps/python3.13`) | No — must live at `PATH` |

See the [`build`](/cli/build.md) command for how to choose.

## Validation

Portability is not assumed — it is **verified**. The [`PythonInspector`](/architecture/python-inspector.md) walks every executable and `.so` file, parses their dynamic dependencies (`ldd` on Linux, `otool` on macOS), and classifies each reference as a system library, a relative reference, or a problem. The [`inspect`](/cli/inspect.md) command surfaces this report and fails if a non-portable reference is found.

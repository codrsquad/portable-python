---
type: Class
title: Cpython
description: The concrete PythonBuilder that compiles CPython — configure/make/install, optimization flags, and the finalize step that makes the install relocatable.
tags: [class, cpython, build, finalize]
timestamp: 2026-06-23T00:00:00Z
---

# Cpython

The concrete [`PythonBuilder`](/architecture/python-builder.md) that compiles CPython (`cpython.py`); `CPythonFamily.get_builder()` returns it (see [`PPG`](/architecture/ppg.md)). Most of its work is two things: configuring the build, and finalizing the install so it's relocatable.

## Configure

CPython is configured purely through flags — never source patches (the [no-patches principle](/overview.md)). Defaults come from `cpython-configure` in [config](/configuration/portable-python-yml.md) (optimizations, LTO, ensurepip), plus computed flags that point the build at the statically-compiled [deps](/concepts/static-linking.md).

## Finalize — making it relocatable

After `make install`, a portable build's interpreter still thinks it lives at the placeholder [`/ppp-marker/{version}`](/concepts/ppp-marker.md). Finalizing turns it into a [portable](/concepts/portability.md) install:

- **Trim** — remove tests / idle / 2to3 before byte-compiling, then prune seldom-used pycaches after (driven by the `cpython-clean-*` config).
- **Byte-compile** the standard library.
- **Relativize** — rewrite `bin/` shebangs and the absolute paths baked into `sysconfig` so everything resolves relative to the install's own location.
- **Verify** — sanity-check that `venv` works in the finished build.

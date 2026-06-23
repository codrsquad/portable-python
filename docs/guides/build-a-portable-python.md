---
type: Playbook
title: Build a Portable Python
description: Install portable-python, build a statically-linked python binary, and use it from any folder.
tags: [playbook, build, getting-started]
timestamp: 2026-06-23T00:00:00Z
---

# Build a Portable Python

End-to-end: from installing the tool to running the binary it produces.

## 1. Install the tool

`portable-python` is a regular python CLI:

```shell
pipx install portable-python      # or: pickley install portable-python
portable-python --help
```

## 2. (Optional) Preview the build

A dry run shows exactly what would happen — downloads, configure/make commands, and the selected [modules](/modules/index.md) — without compiling:

```shell
portable-python --dryrun build 3.13.2
```

Use [`build-report`](/cli/build-report.md) to confirm the module selection is buildable on this host:

```shell
portable-python build-report 3.13.2
```

## 3. Build

```shell
cd some-temp-folder
portable-python build 3.13.2
ls -l dist/cpython-3.13.2-*.tar.gz
```

This runs the full [`BuildSetup.compile()`](/architecture/build-setup.md) pipeline: external libraries first, then CPython, then finalize + validate, then compress into `dist/`.

## 4. Use it

The tarball is [portable](/concepts/portability.md) — unpack anywhere and run, no installer:

```shell
tar -C ~/versions/ -xf dist/cpython-3.13.2-macos-arm64.tar.gz
~/versions/3.13.2/bin/python --version
```

## 5. Verify portability (optional)

```shell
portable-python inspect ~/versions/3.13.2
```

A clean exit means no non-portable dynamic-library references — see [`inspect`](/cli/inspect.md).

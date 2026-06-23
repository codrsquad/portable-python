---
type: Class
title: PythonBuilder
description: A ModuleBuilder specialization for python implementations — adds module selection, the python install layout, and helpers to run the freshly built interpreter.
tags: [class, abstract, python, build]
timestamp: 2026-06-23T00:00:00Z
---

# PythonBuilder

The abstract [`ModuleBuilder`](/architecture/module-builder.md) specialization for building a python interpreter (`__init__.py`); the concrete implementation is [`Cpython`](/architecture/cpython.md).

## What it adds over ModuleBuilder

Beyond the base compile flow, a `PythonBuilder` owns the **module selection** (which [external modules](/modules/index.md) to build) and can **run the freshly-built interpreter** — used during finalize and validation.

## ModuleCollection

A `PythonBuilder` owns a `ModuleCollection` that resolves which external modules actually get built — a distinction worth keeping straight:

- **candidates** — every module this builder *could* compile.
- **selected** — the ones chosen for *this* build (config + `--modules` + auto-selection). This is what's actually compiled, not all candidates.
- **auto-selected** — modules force-included because the build can't succeed without them (each module's `auto_select_reason()`).

It's what [`build-report`](/cli/build-report.md) renders.

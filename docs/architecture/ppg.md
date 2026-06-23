---
type: Class
title: PPG
description: Global singleton holding shared configuration, the target platform, and the registry of supported python version families.
tags: [class, global-state, singleton, versions]
timestamp: 2026-06-23T00:00:00Z
---

# PPG

`PPG` ("**P**ortable **P**ython **G**lobals") is the global state holder (`versions.py`) — the one place the rest of the code reaches for three process-wide facts: the merged [configuration](/architecture/config.md), the target platform (OS/arch), and the registry of python version families. The CLI's `main` initializes it once; everything else reads from it.

Like [`ppp-marker`](/concepts/ppp-marker.md), the name is a deliberately uncommon, greppable token — searching for `PPG` surfaces only its own usages, with no collisions in upstream CPython or third-party source.

## Why a singleton

The build depends on global facts — which config is active, what platform we target, which python versions exist — so centralizing them avoids threading that state through every constructor and gives the CLI one initialization point. Shared helpers hang off it too: resolving a python on `PATH`, building [`Folders`](/architecture/config.md) for a version, and expanding [telltale](/concepts/telltale-detection.md) markers against the target's system includes.

## Version families

A `VersionFamily` (e.g. `CPythonFamily`) lists the available versions and hands back the right builder ([`Cpython`](/architecture/cpython.md) for cpython). Versions are fetched lazily and cached — from `python.org/ftp`, or GitHub tags when configured — which is why [`list`](/cli/list.md) hits the network on first use. A family also pins the minimum supported version (non-EOL only).

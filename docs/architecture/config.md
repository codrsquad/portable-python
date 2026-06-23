---
type: Class
title: Config & Folders
description: Config loads and merges YAML configuration with platform-specific overrides; Folders resolves the templated build/dist/sources paths.
tags: [class, configuration, folders, yaml]
timestamp: 2026-06-23T00:00:00Z
---

# Config & Folders

`Config` (`config.py`) loads, merges, and queries the YAML [configuration](/configuration/portable-python-yml.md). `Folders` (`versions.py`) turns its templated path settings into concrete filesystem paths. Both are reached through [`PPG`](/architecture/ppg.md).

## Merge & precedence

The mental model is layering. A built-in `DEFAULT_CONFIG` provides sane defaults; user files (default `portable-python.yml`, plus any `include:`d files) layer on top. Within a file, **platform-specific** sections override generic ones, and the most specific match for the [target platform](/architecture/ppg.md) wins:

```yaml
ext: gz            # generic default
windows:
  ext: zip         # used only when targeting windows
macos:
  env:
    MACOSX_DEPLOYMENT_TARGET: 13
```

A lookup returns that most-specific value (with the option to ignore platform overrides).

## Folders

`Folders` resolves the templated `folders:` settings (placeholders like `{build}`, `{version}`, `{abi_suffix}`) into the concrete `build/`, `deps/`, `dist/`, … paths every component uses — including the [ppp-marker](/concepts/ppp-marker.md) install prefix. See [build layout](/concepts/build-layout.md) for the resulting tree.

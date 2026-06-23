---
type: Playbook
title: Add a Config Option
description: Add a new configuration key by extending DEFAULT_CONFIG and reading it via PPG.config.get_value().
tags: [playbook, configuration, contributing]
timestamp: 2026-06-23T00:00:00Z
---

# Add a Config Option

## Steps

1. **Declare the default** in `DEFAULT_CONFIG` (in `src/portable_python/config.py`) so the key always has a value.
2. **Read it** where needed with [`PPG.config.get_value("your-key")`](/architecture/config.md) — pass `by_platform=False` if it should ignore platform-specific overrides.
3. **Add tests** in `tests/test_setup.py` (the suite runs in `--dryrun`).

## Notes

- Values support platform-specific overrides (`linux:` / `macos:` / `windows:` sections); the most specific match for [`PPG.target`](/architecture/ppg.md) wins. See [configuration](/configuration/portable-python-yml.md).
- For a per-module key, follow the `{module}-*` convention (`{module}-version`, `{module}-configure`, …) that the [`ModuleBuilder`](/architecture/module-builder.md) `cfg_*` helpers already read.

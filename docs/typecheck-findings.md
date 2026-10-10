---
type: Report
title: Type checking in v2.1.0
description: What introducing 6 type checkers found in v2.0.2, and what v2.1.0 changed in response (bugs, design, minor).
tags: [report, type-checking, ci, quality]
timestamp: 2026-10-09T00:00:00Z
---

# Type checking: v2.0.2 → v2.1.0

What v2.1.0 changed in response to type checker findings on v2.0.2.

| Checker | Version | v2.0.2 | v2.1.0 | Actionable | Bugs | Design | Minor |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ty | 0.0.85 | 51 | 0 | 51 | 0 | 5 | 6 |
| pyrefly | 1.3.2 | 96 | 0 | 96 | 1 | 6 | 7 |
| pyright | 1.1.414 | 93 | 0 | 93 | 1 | 6 | 8 |
| mypy | 2.4.0 | 32 | 0 | 32 | 0 | 3 | 4 |
| basedpyright | 1.40.2 | 2,979 | 2,576 | 646 | 1 | 6 | 8 |
| zuban | 0.10.0 | 38 | 0 | 38 | 2 | 4 | 5 |

- **v2.0.2**, **v2.1.0**: findings on that release's `src/` and `tests/`, both checked with v2.1.0's
  settings (`tox.ini`, `pyproject.toml`). "v2.0.2" is commit `c298694`: v2.0.2 plus the component
  bumps that preceded this work.
- **Actionable**: v2.0.2 findings resolved by a change in v2.1.0.
- **Bugs**, **Design**, **Minor**: how many of the changes listed under [Bug fixes](#bug-fixes),
  [Design](#design) and [Minor](#minor) the checker spotted.
- basedpyright counts include its warnings: 110 errors + 2,869 warnings on v2.0.2, 5 + 2,571 on
  v2.1.0. Its 5 remaining errors are import cycles (`__init__` ↔ `versions` ↔ `cpython` ↔
  `inspector`). basedpyright is available locally (`tox -e basedpyright`) but doesn't gate CI, the
  other 5 checkers do (see [CI/CD](/guides/ci-cd.md)).
- v2.1.0's zeros need runez 5.10.1, which fixed an annotation portable-python tripped on (see
  [Fixed in runez](#fixed-in-runez)).
- v2.0.2 had 3 `# type:` comments, v2.1.0 has none.

## Bug fixes

A checker pointed at code that misbehaved.

- With `cpython-use-github: true`, a failed GitHub API call (rate limiting, network error) crashed
  with a `TypeError`: `RestClient.get()` returns `None` on failure, and the response was iterated
  as-is [zuban, once `get_available_versions()` had a return annotation: mypy-style checkers skip
  the body of unannotated functions]
- When `bin/python` couldn't be found after `make install`, a configured `cpython-validate-script`
  or `cpython-additional-packages` ran `None` as the python executable before the "Can't find
  bin/python" check happened: `bin_python` is now always a `Path`, and aborts with that message on
  first use [pyrefly, pyright, basedpyright, zuban]

## Design

portable-python's invariants are now stated in its types, and enforced where they used to be
assumed.

- `BuildSetup` takes a `PythonSpec`, the new `required_python_spec()` turns CLI text (or
  `None`/`"latest"`) into one, with a clear error when it isn't a full `X.Y.Z`
  version [ty, pyrefly, pyright, basedpyright]
- `VersionFamily` is an ABC (`get_available_versions()` and `get_builder()` are abstract): `latest`
  is always a `Version`, aborting with "Could not determine latest cpython version" instead of the
  puzzling "Invalid python spec: None", and `available_versions` is always a dict [all six]
- `Folders`: `build`, `destdir`, `sources` and `ppp-marker` are required (clear error when not
  configured), only `dist` and `logs` are optional, and folders are `Path`s [pyrefly, pyright,
  basedpyright, zuban]
- `PPG.family()` always aborts for an unknown family (its `fatal=` parameter is gone) [all six]
- `m_telltale` is a plain `str` (several files are space-separated), instead of a mix of `str` and
  `ClassVar[list]` [all six]
- Library tracking: `Trackable` is an ABC declaring `relative_path` and `tracked_category`,
  `LibType` moved to `tracking.py` (the only enum `Tracker` was ever used with), and
  `Tracker.report()` no longer overrides `represented()` with a different return type [ty, pyrefly,
  pyright, basedpyright]

## Fixed in runez

portable-python tripped on this runez annotation, fixed in runez 5.10.1 rather than worked around.

- `to_path(None)` returns `None`: it always did at runtime, but runez 5.10.0's annotation only
  allowed `str | Path` [all six]

## Removed

A checker flagged code that turned out not to be needed.

- The `__main__` block of `cli.py` re-imported `main` from its own module [ty, pyrefly, zuban]

## Minor

The checker was right, the fix changes little in practice.

- Attributes say what they hold, including `None` (`ModuleBuilder.m_*`, `parent_module`,
  `ModuleCollection`, `_bin_python`, `BuildSetup.build_context`, ...) [all six]
- Base class methods declare their return type, so overrides agree (`url`, `auto_select_reason()`,
  `candidate_modules()`, `get_problem()`, `xenv_LDFLAGS()`) [all six]
- `config.py`: `ConfigSource.get_value()` walks the key in a loop, `SingleFileMatch` sets its
  attributes in `__init__`, and `is_match()` returns a `bool` [all six]
- `# type:` comments became annotations [pyrefly, pyright, basedpyright, zuban]
- Inspector: report lists hold strings, `relative_path()` returns a `str`, no `x and x.y`
  chains [pyrefly, mypy, zuban]
- Version listing checks `v.patch` truthiness instead of `v.patch > 0` [ty, pyrefly, pyright,
  basedpyright]
- Tests: no poking at `Config._sources`, the mock's patcher is created in `__init__` [ty, pyrefly,
  pyright, basedpyright]
- `runez.ActivateColors` instead of `runez.colors.ActivateColors` [pyright, basedpyright]
- `recompress` takes family and version from a spec only when the path names one [pyright,
  basedpyright]
- `run_make(cpu_count=...)` is annotated [ty]

## Not from a type checker

- Folder paths containing a space are refused by portable-python itself, with the reason spelled
  out ("escapes too complex with makefiles, shell scripts etc"), instead of relying on a niche
  runez helper
- New tests: missing `bin/python`, python.org listing no versions, folder path with a space

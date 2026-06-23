---
type: Playbook
title: Local Development
description: Set up a dev venv, run the tests, use dryrun mode, and build Linux binaries via Docker.
tags: [playbook, development, testing, docker]
timestamp: 2026-06-23T00:00:00Z
---

# Local Development

## Dev venv

```shell
uv sync
.venv/bin/portable-python list
.venv/bin/portable-python build-report 3.13.2
```

## Running the tests

The suite mocks `runez.run()` and builds in `--dryrun` mode, so it asserts the *planned* commands without actually compiling. Target is 100% coverage.

```shell
tox                 # all envs (py310-314, coverage, docs, style)
tox -e py313        # one python version
tox -e style        # lint check (ruff)
tox -e reformat     # auto-fix formatting

.venv/bin/pytest tests/                              # directly
.venv/bin/pytest tests/test_build.py::test_build_rc -vv   # a single test
```

CI runs `uvx --with tox-uv tox -e py`.

## Dryrun mode

`--dryrun` (`-n`) prints what would be done without doing it — invaluable for fast iteration and for understanding the build:

```shell
portable-python --dryrun build 3.13.2
```

## Debugging

`portable-python` can be run under a debugger (e.g. PyCharm: debug `.venv/bin/portable-python` with parameters like `build-report 3.13.2`). Set breakpoints in the [core classes](/architecture/index.md) or in any `tests/` file.

## Building a Linux binary via Docker

Real Linux builds (not dry runs) are easiest in a container:

```shell
docker build -t portable-python-jammy .
docker run -it -v./:/src/ portable-python-jammy /bin/bash
# inside the container:
portable-python build 3.13.2
```

## Key dependencies

| Package | Purpose |
|---------|---------|
| `click` | CLI framework. |
| `pyyaml` | [Configuration](/configuration/portable-python-yml.md) parsing. |
| `requests` / `urllib3` | HTTP downloads. |
| `runez` | Foundational utilities — file ops, system info, CLI decorators, logging, `Version`/`PythonSpec`. Check `runez` before reimplementing anything. |

# Citations

[1] [DEVELOP.md](https://github.com/codrsquad/portable-python/blob/main/DEVELOP.md)
[2] [CLAUDE.md — Common Commands, Testing](https://github.com/codrsquad/portable-python/blob/main/CLAUDE.md)

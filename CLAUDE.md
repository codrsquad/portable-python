# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

portable-python is a CLI tool and Python library for compiling portable CPython binaries from source. Binaries are statically linked so they can be extracted to any folder and used without installation. Supports Linux and macOS (not Windows).

## Common Commands

```bash
# Run all tests (tox manages envs for py310-314, coverage, docs, style)
tox

# Run tests for a single Python version
tox -e py313

# Run a single test
pytest tests/test_build.py::test_build_rc -vv

# Lint check / auto-fix
tox -e style
tox -e reformat

# Run tests directly (from venv)
pytest tests/

# CI uses: uvx --with tox-uv tox -e py
```

## Architecture

**Key classes:**

- `PPG` (versions.py) — Global singleton holding config, target platform, and version families. All modules access shared state through this.
- `BuildSetup` (__init__.py) — Coordinates overall compilation: downloads sources, builds external modules, then CPython.
- `ModuleBuilder` (__init__.py) — Abstract base for anything that gets compiled. Both external C modules and Python itself extend this.
- `PythonBuilder` (__init__.py) — Extends ModuleBuilder for Python implementations.
- `Cpython` (cpython.py) — Concrete PythonBuilder that handles CPython's configure/make/install, optimization, and finalization.
- `Config` (config.py) — Loads and merges YAML configuration (portable-python.yml) with platform-specific overrides.
- `PythonInspector` (inspector.py) — Validates portability of a built Python by checking shared library dependencies and paths.

**External modules** (external/xcpython.py): `Bdb`, `Bzip2`, `Gdbm`, `LibFFI`, `Mpdec`, `Openssl`, `Readline`, `Sqlite`, `Uuid`, `Xz`, `Zlib`, `Zstd` — each is a ModuleBuilder subclass that compiles a C library statically before CPython is built.

**Key patterns:**

- Platform-specific compile logic uses `_do_linux_compile()` / `_do_macos_compile()` method dispatch.
- Environment injection: `xenv_*` methods provide CPATH, LDFLAGS, PATH etc. for compilation.
- On macOS, `/usr/local` is masked with a RAM disk (`FolderMask`) to prevent accidental dynamic linking.
- External modules compile to a shared `build/deps/` prefix; CPython finds them via CPATH/LDFLAGS.
- Telltale detection: modules check for marker files (`m_telltale`) to determine if system already has the library.
- No patches to upstream CPython source — relies solely on configure flags.

**runez** is the foundational utility library (file ops, system info, CLI decorators, logging, Version/PythonSpec types). Check runez before reimplementing anything.

**Additional pointers:**

- `ModuleCollection.selected` contains only the modules chosen for a build — not all candidates.
- Build logs go to `build/logs/NN-modulename.log` (e.g. `01-openssl.log`, `02-cpython.log`).
- YAML config supports platform-specific overrides and path templates — see CONFIGURATION.md.
- See ARCHITECTURE.md for class hierarchy and design patterns, DEVELOP.md for common tasks and dependencies.

## Testing

- pytest with 100% code coverage target
- Tests mock `runez.run()` to avoid actual compilation — uses `--dryrun` mode
- `conftest.py` provides a `cli` fixture (from runez) and forbids HTTP calls (`GlobalHttpCalls.forbid()`)
- Sample YAML configs in `tests/sample-config*.yml` for testing configuration parsing

## Linting

Ruff handles all linting and formatting. Key settings in pyproject.toml:
- Line length: 140
- McCabe complexity: max 18
- Security checks (S rules) disabled in tests
- Numpy-style docstrings

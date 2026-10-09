# Changelog

## v2.1.0

- portable-python's code is now checked by 5 type checkers (ty, pyrefly, pyright, mypy and zuban) on every change
- Bumped SQLite to 3.53.4 and gettext-tiny to 0.3.3; re-checked every other component against upstream (all already current, or deliberately held back — see the `version` property comments).
- Bug fixes:
  - With `cpython-use-github: true`, a failed GitHub API call (e.g. rate limiting) crashed with a stack trace
  - A build where `bin/python` could not be found crashed (instead of reporting it) when `cpython-validate-script` or `cpython-additional-packages` was configured
  - Clearer error messages when the latest python version can't be determined, or a python family isn't supported
  - A `{module}-configure` setting with several options was passed to `./configure` as one single argument
  - Dry-run (`-n`) could modify files of an existing build (source patches, shebangs, permissions), a configured patch on a missing file is now reported
- Library use: `BuildSetup()` now takes a `PythonSpec`, get one via `required_python_spec("cpython:3.13.2")` (which validates it, `None` means latest)
- Tests cover more edge cases

## v2.0.2

- Corrected `readline` static linking

## v2.0.1

- Bumped the bundled components (OpenSSL, SQLite, Tcl/Tk, …) to current versions.
- Refreshed dependencies and modernized CI (now on uv / tox-uv, with updated GitHub Actions).
- Added an OKF documentation bundle under `docs/` (the old top-level docs folded into it).

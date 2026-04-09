# Configuration (portable-python.yml)

portable-python is configured via a YAML file (default: `portable-python.yml` in current directory, override with `--config`).


## Key Sections

### folders

- `build`, `dist`, `sources`, `logs`, `destdir`, `ppp-marker`
- All support path templates: `{build}`, `{version}`, `{abi_suffix}`

### cpython-modules (CSV)

Which external modules to auto-select.
Default is configured in `DEFAULT_CONFIG` (see `src/portable_python/config.py`).
Examples: openssl, zlib, xz, sqlite, bzip2, gdbm, libffi, readline, uuid

### cpython-configure (list)

Extra `./configure` args for CPython.
Default includes: `--enable-optimizations`, `--with-lto`, `--with-ensurepip=upgrade`

### cpython-clean-1st-pass (list)

Files to remove before `compileall` — removes test files, idle, 2to3 (~94 MB savings).

### cpython-clean-2nd-pass (list)

Files to remove after `compileall` — removes pycaches for seldom-used libs (~1.8 MB savings).


## Per-module config

Each external module can be customized with these keys (replace `{module}` with the module name, e.g. `openssl`):

| Key | Purpose |
|-----|---------|
| `{module}-version` | Version to use |
| `{module}-url` | URL to download from |
| `{module}-src-suffix` | File extension if not in URL |
| `{module}-configure` | Custom configure args |
| `{module}-http-headers` | HTTP headers for download |
| `{module}-patches` | File patches to apply |
| `{module}-debian` | Package name on Debian (for dependency detection) |


## Platform-specific overrides

Configuration supports platform-specific sections (e.g. `windows.ext`, `macos.env`, etc.).
The most specific setting wins.

`MACOSX_DEPLOYMENT_TARGET` defaults to 13 (Ventura).

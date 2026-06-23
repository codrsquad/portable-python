---
type: Configuration
title: portable-python.yml
description: The YAML configuration file controlling folders, module selection, configure flags, cleanup, and per-module overrides — with platform-specific sections.
tags: [configuration, yaml, config]
timestamp: 2026-06-23T00:00:00Z
---

# portable-python.yml

portable-python is configured via a YAML file — by default `portable-python.yml` in the current directory, overridable with `--config`. The built-in `DEFAULT_CONFIG` (in `config.py`) supplies defaults; user files layer on top and may `include:` other files. Values are read through [`Config.get_value()`](/architecture/config.md).

# Schema

## Top-level keys

| Key | Type | Purpose |
|-----|------|---------|
| `folders` | map | Build path templates (see below). |
| `ext` | string | Output archive extension (`gz` default; `zip` on windows). |
| `cpython-modules` | CSV/list | Which [external modules](/modules/index.md) to auto-select. |
| `cpython-configure` | list | Extra `./configure` args (default: `--enable-optimizations`, `--with-lto`, `--with-ensurepip=upgrade`). |
| `cpython-clean-1st-pass` | list | Files removed before byte-compiling (~94 MB: tests, idle, 2to3). |
| `cpython-clean-2nd-pass` | list | Pycaches pruned after byte-compiling (~1.8 MB). |
| `cpython-compile-all` | bool | Whether to byte-compile the stdlib. |
| `cpython-additional-packages` | list | Extra pip packages to install into the build. |
| `cpython-use-github` | bool | Fetch the available version list from GitHub tags instead of python.org. |
| `include` | path | Layer another config file (a leading `+` puts it in front). |

## `folders`

All support path templates: `{build}`, `{family}`, `{version}`, `{abi_suffix}`.

| Key | Default | Role |
|-----|---------|------|
| `build` | `build` | Root build folder. |
| `destdir` | `{build}` | `make install` DESTDIR. |
| `dist` | `dist` | Final tarball folder. |
| `logs` | `{build}/logs` | Per-component logs. |
| `sources` | `build/sources` | Downloaded tarball cache. |
| `ppp-marker` | `/ppp-marker/{version}{abi_suffix}` | The [ppp-marker](/concepts/ppp-marker.md) placeholder install prefix. |

See [build layout](/concepts/build-layout.md) for how these map onto disk.

## Per-module keys

Replace `{module}` with the lowercased module name (e.g. `openssl`):

| Key | Purpose |
|-----|---------|
| `{module}-version` | Version to build. |
| `{module}-url` | Source URL (`$version` is substituted; may carry a `#sha256=…` fragment, verified on download). |
| `{module}-src-suffix` | Archive extension when the URL lacks one. |
| `{module}-configure` | **Replace** the default configure args (`$deps_lib` substituted). |
| `{module}-http-headers` | Headers for the download (env vars expanded). |
| `{module}-patches` | Source patches to apply before compiling. |
| `{module}-debian` | Debian package name for dependency detection. |

## Platform-specific overrides

Sections named for a platform (`linux`, `macos`, `windows`) override generic keys; the most specific match for `PPG.target` wins. `MACOSX_DEPLOYMENT_TARGET` defaults to `13` (Ventura).

# Examples

```yaml
include: +pp-dev.yml

folders:
  build: "build/{family}-{version}{abi_suffix}"   # keep builds per-version

cpython-modules: libffi zlib xz bzip2 openssl uuid sqlite

# Override a dependency version and source
libffi-version: 3.3
openssl-url: https://my-openssl-mirror/openssl-$version.tar.gz
openssl-http-headers:
  - Authorization: Bearer ${GITHUB_TOKEN}

# Per-platform configure args
macos:
  openssl-configure: --with-terminfo-dirs=/usr/share/terminfo
```

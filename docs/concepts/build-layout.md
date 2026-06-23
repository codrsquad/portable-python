---
type: Concept
title: Build Folder Layout
description: Every component follows the same conventional layout under build/, with external libraries sharing a deps prefix and the finished binary landing in dist/.
tags: [build-layout, concept, folders]
timestamp: 2026-06-23T00:00:00Z
---

# Build Folder Layout

Every component — external modules and CPython alike — is built using the same conventional folder layout. This uniformity is what lets a single [`ModuleBuilder`](/architecture/module-builder.md) framework drive every compile. Folder paths are configurable; the defaults are shown below.

# Schema

```
build/
    sources/                            # Downloaded source tarballs (downloaded once, reused)
        openssl-3.5.6.tar.gz
        Python-3.13.2.tar.xz
    components/                         # Each module is unpacked + compiled here
        openssl/
        cpython/
    deps/                               # Shared --prefix for ALL external modules
        include/                        #   → injected into CPATH
        lib/  lib64/                    #   → injected into LDFLAGS
        bin/                            #   → injected into PATH
    logs/                               # Per-component build logs, ordered
        00-portable-python.log
        01-openssl.log
        02-cpython.log
    ppp-marker/{version}/               # The built python (its baked-in prefix is /ppp-marker/{version})
dist/
    cpython-3.13.2-macos-arm64.tar.gz   # Ready-to-go portable tarball
```

## Key folders

| Folder | Role |
|--------|------|
| `sources/` | Cache of downloaded tarballs. Survives if you point it outside `build/`. |
| `components/` | Scratch space where each component's source is unpacked and compiled. |
| `deps/` | The shared install prefix passed to every external module's `./configure --prefix=build/deps`. CPython finds these via injected env vars — see [static linking](/concepts/static-linking.md). |
| `logs/` | One log file per component, numbered so they sort in compile order. |
| `ppp-marker/{version}/` | The built python installation, under the [ppp-marker](/concepts/ppp-marker.md) prefix. |
| `dist/` | Final portable tarball(s). |

## Configurability

All of these paths are templated and overridable in [configuration](/configuration/portable-python-yml.md) under the `folders:` key, using placeholders like `{build}`, `{version}`, and `{abi_suffix}`. The [`Folders`](/architecture/config.md) helper resolves them. For example, the dev config keeps builds per-version with `build: "build/{family}-{version}{abi_suffix}"`.

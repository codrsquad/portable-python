---
type: Concept
title: The ppp-marker Prefix
description: "ppp-marker" (portable python path marker) is the install prefix handed to CPython's configure — the real --prefix for non-portable builds, or a searchable placeholder that gets relativized for portable builds.
tags: [ppp-marker, prefix, concept, portability, relativize]
timestamp: 2026-06-23T00:00:00Z
---

# The ppp-marker Prefix

`ppp-marker` stands for **portable python path marker**. It is the install prefix the build hands to CPython's `configure`, and its role depends on the build kind:

- **Non-portable (`--prefix`) builds** — `ppp-marker` is simply the `--prefix` you asked for; the python is built to live there for real.
- **Portable builds** — there is no real install location, so `ppp-marker` is a *dummy* placeholder folder that fills in for `--prefix`. CPython is configured with `--prefix=/ppp-marker/{version}`, so the freshly built interpreter initially believes it lives at `/ppp-marker/{version}`. The [finalize step](/architecture/cpython.md) then rewrites those baked-in absolute paths to be relative (see [static linking](/concepts/static-linking.md) and [portability](/concepts/portability.md)), making the install relocatable.

## Why "ppp"

The `ppp` token is chosen to be **easy to search and impossible to collide with**: grepping the codebase for `ppp` turns up only these usages, and `ppp-marker` appears nowhere in upstream CPython source. That uniqueness is what lets the finalize step find and rewrite every occurrence of the placeholder prefix unambiguously. ([`PPG`](/architecture/ppg.md) — "Portable Python Globals" — is named on the same principle.)

## Where it shows up

- Configured via the `ppp-marker` key (default `/ppp-marker/{version}{abi_suffix}`) — see [configuration](/configuration/portable-python-yml.md) and [`Folders`](/architecture/config.md).
- On disk the install lands under it, at `build/ppp-marker/{version}/` — see [build layout](/concepts/build-layout.md).
- Visible in `--dryrun` output as `./configure --prefix=/ppp-marker/{version}`.

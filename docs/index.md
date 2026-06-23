---
okf_version: "0.1"
---

# Portable Python — Knowledge Bundle

A knowledge bundle (in [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) format) describing `portable-python`: a CLI and Python library for compiling statically-linked, relocatable CPython binaries from source.

Start with the [Overview](/overview.md), then drill into the area you need.

## Sections

* [Overview](/overview.md) - What portable-python does, its guiding principles, and how a build flows end to end.
* [Concepts](/concepts/index.md) - Domain ideas: portability, static linking, telltale detection, folder masking, build layout.
* [Architecture](/architecture/index.md) - The core classes and how they collaborate during a build.
* [CLI](/cli/index.md) - The `portable-python` subcommands and their options.
* [External Modules](/modules/index.md) - The C libraries compiled and statically linked into CPython.
* [Configuration](/configuration/index.md) - The `portable-python.yml` file, its sections and overrides.
* [Guides](/guides/index.md) - Playbooks for common tasks: building, extending, local development.

## Conventions

* Concept IDs are file paths minus `.md` (e.g. `architecture/ppg`).
* Cross-links are bundle-relative, beginning with `/` (the bundle root is this `docs/` folder).
* `resource:` frontmatter points to the canonical source file on GitHub when a concept maps to code.
* Change history lives in [log.md](/log.md).

## Relationship to the root-level docs

This bundle is additive. The repository's hand-written `README.rst`, `ARCHITECTURE.md`, `CONFIGURATION.md`, and `DEVELOP.md` remain authoritative for now; this bundle reorganizes and expands that material into discrete, linkable concepts. See [Overview](/overview.md#citations) for pointers back to those files.

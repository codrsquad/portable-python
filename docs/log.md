# Knowledge Bundle Update Log

## 2026-06-23

* **Update**: Pulled two verified facts in from the project wiki — the relativization tools (`patchelf` / `install_name_tool`) and `--prefix` / `--enable-shared` support ([PythonInspector](/architecture/python-inspector.md)), and the `#sha256=` download-checksum URL fragment ([configuration](/configuration/portable-python-yml.md)). Skipped the wiki's `sources:` download-url design — it's an unimplemented draft.
* **Update**: Trimmed the CLI pages — dropped the per-command option tables (which mirror `--help`) for purpose + non-obvious gotchas + examples, pointing at `--help` for the full flag list.
* **Update**: Reshaped the six architecture `type: Class` pages — dropped the `# Schema` member tables (which mirrored code and risked drift) for a condensed mental-model + "worth knowing" framing; the code stays authoritative for the API.
* **Update**: Removed the `resource:` frontmatter field from all concept files — unrendered, unreferenced by any tooling, and brittle (GitHub URLs). Source is pointed to inline in the prose instead. The bundle now contains no `github.com` repo links.
* **Update**: Removed the `# Citations` sections from all concept files — they duplicated the `resource:` frontmatter and inline source mentions, and added brittle GitHub-URL boilerplate that nothing referenced. Source pointers now live only in `resource:` and inline prose.
* **Update**: Inverted the `docs/` ↔ `CLAUDE.md` relationship — `CLAUDE.md` is now a thin pointer into the bundle. Folded the test-harness and code-style notes into [local development](/guides/local-development.md), and removed all back-references to `CLAUDE.md` from `docs/`.
* **Update**: Promoted `docs/` to the authoritative documentation; folded in and removed the root `ARCHITECTURE.md`, `CONFIGURATION.md`, and `DEVELOP.md`.
* **Creation**: Added guides for [CI/CD](/guides/ci-cd.md), [adding a config option](/guides/add-a-config-option.md), [fixing a portability issue](/guides/fix-a-portability-issue.md), and [bumping python support](/guides/bump-python-support.md).
* **Update**: Dropped the default-version column from the [external modules reference](/modules/external-modules.md) to avoid drift; it now points at `cfg_version()` in source and [`build-report`](/cli/build-report.md).
* **Creation**: Added the [ppp-marker prefix](/concepts/ppp-marker.md) concept.
* **Update**: Centralized the `ppp-marker` explanation there; build layout, PPG, Cpython, and configuration now link to it instead of repeating it.
* **Creation**: Established the portable-python knowledge bundle in OKF format.
* **Creation**: Added the [Overview](/overview.md).
* **Creation**: Added the [Concepts](/concepts/index.md) section (portability, static linking, telltale detection, folder masking, build layout).
* **Creation**: Added the [Architecture](/architecture/index.md) section covering the core classes (`PPG`, `BuildSetup`, `ModuleBuilder`, `PythonBuilder`, `Cpython`, `Config`, `PythonInspector`).
* **Creation**: Added the [CLI](/cli/index.md) reference for all subcommands.
* **Creation**: Added the [External Modules](/modules/index.md) reference.
* **Creation**: Added the [Configuration](/configuration/index.md) section.
* **Creation**: Added the [Guides](/guides/index.md) section (building, adding a module, local development).

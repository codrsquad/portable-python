# CLAUDE.md

Guidance for Claude Code working in this repository.

`portable-python` is a CLI and Python library that compiles portable (statically-linked, relocatable) CPython binaries from source — see [`docs/overview.md`](docs/overview.md) for the full picture.

## Documentation lives in `docs/`

The authoritative, self-contained documentation is the OKF knowledge bundle under **`docs/`** — start at [`docs/index.md`](docs/index.md). **Don't duplicate it in this file — link to it.** When you change behavior, update the matching `docs/` entry and add a line to [`docs/log.md`](docs/log.md).

| Looking for… | Go to |
|--------------|-------|
| What it does, guiding principles, end-to-end build flow | [`docs/overview.md`](docs/overview.md) |
| Core classes & how they collaborate | [`docs/architecture/`](docs/architecture/index.md) |
| Concepts: portability, static linking, telltale detection, folder masking, ppp-marker, build layout | [`docs/concepts/`](docs/concepts/index.md) |
| CLI commands & options | [`docs/cli/`](docs/cli/index.md) |
| External modules (the statically-linked C libraries) | [`docs/modules/`](docs/modules/index.md) |
| Configuration (`portable-python.yml`) | [`docs/configuration/`](docs/configuration/index.md) |
| Dev setup, tests, code style, debugging, Docker, CI/CD, and common tasks | [`docs/guides/`](docs/guides/index.md) |

## Working in this repo

- Check **runez** before reimplementing file / system / CLI / logging / version helpers — see [`docs/guides/local-development.md`](docs/guides/local-development.md).
- The docs use the OKF format; keep the bundle conformant (`scripts/check_okf.py docs`) when you edit it.
- As changes land, keep a top section in [`docs/changelog.md`](docs/changelog.md) for the upcoming release — `## Unreleased`, or the next version directly once it's known. Maintain it as PRs come in; it's double-checked at release. Don't fuss over marking released-vs-unreleased (small audience, `git tag` says what's out).

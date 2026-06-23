# CLI

`portable-python` is a single-entry-point CLI built with `click` (via `runez.click`). All commands are defined in `cli.py`.

```
portable-python [GLOBAL OPTIONS] COMMAND [ARGS]
```

## Global options

| Option | Purpose |
|--------|---------|
| `--config, -c PATH` | Config file to use (default: `portable-python.yml`). |
| `--quiet, -q` | Turn off DEBUG logging. |
| `--dryrun, -n` | Show what would be done without doing it. |
| `--target, -t` | Override the detected platform (internal/testing). |
| `--version` / `--color` | Standard `runez` options. |

The `main` group initializes logging and calls [`PPG.grab_config()`](/architecture/ppg.md) before any subcommand runs.

## Commands

* [build](/cli/build.md) - Build a portable python binary.
* [build-report](/cli/build-report.md) - Show which modules will be compiled and whether they can build.
* [inspect](/cli/inspect.md) - Check whether a python installation is portable.
* [list](/cli/list.md) - List available versions for a family.
* [diagnostics](/cli/diagnostics.md) - Show system diagnostics and active config.
* [recompress](/cli/recompress.md) - Re-compress an existing tarball/folder (compare sizes).
* [lib-auto-correct](/cli/lib-auto-correct.md) - Rewrite a build's lib references to relative paths.

# CLI

`portable-python` is a single-entry-point CLI (built with `click` via `runez.click`); every command lives in `cli.py`.

```
portable-python [GLOBAL OPTIONS] COMMAND [ARGS]
```

Two global options are worth knowing: `--config/-c` (which [config](/configuration/portable-python-yml.md) file to use) and `--dryrun/-n` (print what *would* happen without doing it — the fastest way to understand a build). `portable-python --help` lists the rest. The top-level group loads config (via [`PPG`](/architecture/ppg.md)) before any subcommand runs.

## Commands

* [build](/cli/build.md) - Build a portable python binary.
* [build-report](/cli/build-report.md) - Show which modules will be compiled and whether they can build.
* [inspect](/cli/inspect.md) - Check whether a python installation is portable.
* [list](/cli/list.md) - List available versions for a family.
* [diagnostics](/cli/diagnostics.md) - Show system diagnostics and active config.
* [recompress](/cli/recompress.md) - Re-compress an existing tarball/folder (compare sizes).
* [lib-auto-correct](/cli/lib-auto-correct.md) - Rewrite a build's lib references to relative paths.

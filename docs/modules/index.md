# External Modules

The C libraries that get compiled statically and linked into CPython, so that the corresponding standard-library modules work in a [portable](/concepts/portability.md) build.

* [External modules reference](/modules/external-modules.md) - The full table: default versions, telltales, and Linux build constraints.

Each module is a [`ModuleBuilder`](/architecture/module-builder.md) subclass. The set of candidates CPython can link is declared in `Cpython.candidate_modules()`; which ones are actually built depends on config, the `--modules` flag, [telltale detection](/concepts/telltale-detection.md), and auto-selection.

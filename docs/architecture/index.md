# Architecture

The core classes and how they collaborate during a build.
## Global state & configuration

* [PPG](/architecture/ppg.md) - Global singleton holding config, target platform, and version families.
* [Config](/architecture/config.md) - Loads and merges YAML configuration; the `Folders` helper resolves build paths.

## Build coordination

* [BuildSetup](/architecture/build-setup.md) - Drives the overall compilation: resolve spec, select modules, build, validate, compress.
* [ModuleBuilder](/architecture/module-builder.md) - Abstract base for anything that gets compiled (external C libs and Python itself).
* [PythonBuilder](/architecture/python-builder.md) - `ModuleBuilder` specialization for python implementations.
* [Cpython](/architecture/cpython.md) - Concrete builder: CPython's configure/make/install, optimization, and finalization.

## Validation

* [PythonInspector](/architecture/python-inspector.md) - Validates the portability of a built (or any) python by checking shared-library dependencies and paths.

## Collaboration at a glance

```
PPG (config, target, families)
  └─ BuildSetup(python_spec)
       ├─ Folders            (resolved build/dist/... paths)
       ├─ BuildContext       (macOS folder masking, isolation)
       └─ python_builder : Cpython (a PythonBuilder, a ModuleBuilder)
            └─ modules : ModuleCollection
                 └─ candidates/selected : ModuleBuilder (Openssl, Zlib, ...)
```

## Architecture

### Core Classes Hierarchy

```
ModuleBuilder (abstract base)
├── PythonBuilder (abstract, extends ModuleBuilder)
│   └── Cpython (concrete implementation in cpython.py)
└── External modules (in external/xcpython.py, xtkinter.py)
    ├── Bdb, Bzip2, Gdbm, LibFFI, Mpdec, Openssl, Readline
    ├── Sqlite, Uuid, Xz, Zlib, Zstd, TkInter

BuildSetup (coordinates overall compilation)
├── BuildContext (handles isolation hacks on macOS)
├── Folders (manages build directory structure)
└── ModuleCollection (manages module selection and dependencies)

PPG (Global state singleton)
├── config: Config (YAML configuration)
├── target: PlatformId (target OS/arch)
├── cpython: CPythonFamily (available versions)
└── families: dict (extensible family support)

Config
├── Folders (build/dist/sources/logs directories)
├── target platform detection
├── YAML config merging (platform-specific overrides)

PythonInspector
├── Inspect Python installation for portability
├── LibAutoCorrect (rewrite paths to be relative)
└── Report system and shared lib detection

Tracker/Trackable
├── Categorizes found issues/objects by type
└── Provides detailed reports
```

### Key Design Patterns

1. **Hierarchical Module Building**: External modules are compiled first, then Python itself, using the same build framework.

2. **Environment Variable Injection**: `xenv_*` methods dynamically provide environment variables (CPATH, LDFLAGS, PATH, etc.) for compilation.

3. **Platform Abstraction**: `PPG.target` (PlatformId) encapsulates platform logic. Compile methods named `_do_<platform>_compile()` dispatch to platform-specific implementations.

4. **Configuration Precedence**: YAML config supports platform-specific overrides (windows.ext, macos.env, etc.). Most specific setting wins.

5. **Folder Masking (macOS)**: On macOS, `/usr/local` is temporarily masked with a RAM disk to prevent accidental dynamic linking.

6. **Build Isolation**: All external modules compiled to a shared `build/deps/` folder, Python finds them via CPATH/LDFLAGS.

7. **Lazy Version Fetching**: `VersionFamily` caches available versions, fetching from python.org on first access.

8. **Telltale Detection**: Modules check for marker files (`m_telltale`) to determine if they're already available on the system (as shared libs).

9. **Log Aggregation**: Each module logs to a separate file (`01-openssl.log`, `02-cpython.log`, etc.) under `build/logs/`.


## CI/CD

### GitHub Actions

**tests.yml** (main branch & PRs):
- Matrix test on py3.10, 3.11, 3.12, 3.13, 3.14
- Runs: `uvx --with tox-uv tox -e py`
- Coverage upload to coveralls.io (parallel, then finish)
- Linter job: docs + style checks on 3.14

**release.yml** (version tags v*):
- Triggers on `v[0-9]*` tags
- Runs all tests + docs + style
- Builds distribution with `uv build`
- Publishes to PyPI via trusted publishing (OIDC)
